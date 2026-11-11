"""Orquesta una actualización: leer → combinar → clasificar → marcar → deduplicar."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from . import almacen, duplicados, ia, lector, marcas
from .config import Config
from .descartes import Descartes
from .filtro import Filtro
from .historias import Agrupador
from .relevancia import Relevancia

log = logging.getLogger("actualizador")


def recolectar(cfg: Config, ahora: datetime) -> tuple[list[dict], dict]:
    fuentes = cfg.fuentes_activas()
    notas: list[dict] = []
    estado: dict = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futuros = {f["id"]: pool.submit(lector.leer_fuente, f, ahora, ventana_de(f, cfg)) for f in fuentes}
        for fid, fut in futuros.items():
            nuevas, est = fut.result()
            estado[fid] = est
            notas.extend(nuevas)
            if not est["ok"]:
                log.warning("✖ %s: sin respuesta (%s)", fid, "; ".join(est["errores"])[:300])
            elif est["parcial"]:
                log.warning("◐ %s: %d notas, con errores parciales", fid, est["notas"])
            else:
                log.info("✓ %s: %d notas", fid, est["notas"])
    for f in cfg.fuentes_del_flujo():
        if f.get("metodo") == "sin_acceso":
            estado[f["id"]] = {"ok": False, "parcial": False, "notas": 0, "metodo": "sin_acceso",
                               "errores": [], "revisado": ahora.isoformat()}
    return notas, estado


def ventana_de(fuente: dict | None, cfg: Config) -> int:
    """Días que se guardan de una fuente: los del sitio, o más si la fuente publica poco
    (`ventana_dias` en fuentes.yaml). Esas notas viejas solo salen en «Fuentes fijas: lo último»."""
    return max(cfg.ventana_dias, int((fuente or {}).get("ventana_dias") or 0))


def combinar(previas: list[dict], nuevas: list[dict], ahora: datetime, dias: int,
             ventanas: dict | None = None) -> list[dict]:
    """Une lo ya guardado con lo nuevo (por id) y recorta a la ventana de días."""
    por_id = {n["id"]: n for n in previas}
    for n in nuevas:
        if n["id"] in por_id:
            vieja = por_id[n["id"]]
            # Se conserva cuándo se vio por primera vez; se actualizan textos
            n = {**n, "primera_vista": vieja.get("primera_vista") or ahora.isoformat()}
            if not n.get("fecha"):
                n["fecha"] = vieja.get("fecha")
        else:
            n = {**n, "primera_vista": ahora.isoformat()}
        if not n.get("fecha"):
            n["fecha"] = n["primera_vista"]
        por_id[n["id"]] = n
    ventanas = ventanas or {}

    def dentro(n: dict) -> bool:
        limite = ahora - timedelta(days=ventanas.get(n["fuente_id"], dias))
        return datetime.fromisoformat(n["fecha"]) >= limite

    return sorted(
        (n for n in por_id.values() if dentro(n)),
        key=lambda n: n["fecha"],
        reverse=True,
    )


def enriquecer(crudas: list[dict], cfg: Config, ahora: datetime | None = None) -> list[dict]:
    """Aplica la configuración actual: fuente, tipo, temáticas y marcas."""
    ahora = ahora or datetime.now(timezone.utc)
    limite_sitio = ahora - timedelta(days=cfg.ventana_dias)
    filtro = Filtro(cfg.palabras_clave)
    descartes = Descartes(cfg.palabras_clave.get("no_noticias"))
    relevancia = Relevancia(cfg.palabras_clave.get("relevancia"))
    fuentes = cfg.fuentes_por_id
    salida = []
    descartadas = 0
    for n in crudas:
        f = fuentes.get(n["fuente_id"])
        if not f or f["grupo"] not in ("fija", "especializada", "general"):
            continue  # la fuente se quitó o se excluyó
        exigido = (f.get("solo_titulares_con") or "").lower()
        if exigido and exigido not in n["titular"].lower():
            continue
        if not lector.muestra_bajada(f) and n.get("bajada"):
            n = {**n, "bajada": ""}  # el medio prohíbe reproducir su texto: solo titular y enlace
        if descartes.motivo(n, f):
            descartadas += 1  # página de sección, paginación o portada: no es una noticia
            continue
        temas, como = filtro.asignar(n, f)
        if not temas:
            continue
        salida.append({
            **n,
            "fuente": f["nombre"],
            "red": f.get("red"),
            "tipo": f.get("tipo"),
            "grupo": f["grupo"],
            "tematicas": temas,
            "marcas": marcas.marcar(n, f),
            "clasificado_por": como,
            "solo_titular": not lector.muestra_bajada(f),
            # Notas de fuentes que publican poco, más viejas que la ventana del sitio:
            # no van al flujo, solo a «Fuentes fijas: lo último»
            "fuera_de_ventana": datetime.fromisoformat(n["fecha"]) < limite_sitio,
            # Categoría de relevancia por la que se oculta (None: se muestra)
            "oculta": relevancia.categoria(n),
            "tambien_en": [],
            # Campos reservados para la fase 2 (IA)
            "resumen": None,
            "comentario": None,
        })
    if descartadas:
        log.info("Se descartaron %d entradas que no son noticias (secciones, paginación, portadas)", descartadas)
    return salida


TIPOS_PRIMARIOS = {"oficial", "la-empresa"}


def prioridad(n: dict):
    """Orden para elegir la nota principal de una historia (menor = primero)."""
    if n.get("grupo") == "fija":
        nivel = 0
    elif n.get("tipo") in TIPOS_PRIMARIOS:
        nivel = 1
    elif n.get("grupo") == "especializada":
        nivel = 2
    else:
        nivel = 3
    return (nivel, 0 if n.get("bajada") else 1, n["fecha"])


def agrupar(notas: list[dict], cfg: Config) -> list[dict]:
    """Une copias (misma nota en varios sitios) y luego notas de la misma historia.

    Las notas ocultas por relevancia se agrupan aparte, para que nunca sean la
    principal de una historia visible.
    """
    agrupador = Agrupador(cfg.palabras_clave.get("historias"))
    viejas = [n for n in notas if n.get("fuera_de_ventana")]
    notas = [n for n in notas if not n.get("fuera_de_ventana")]
    visibles = duplicados.eliminar([n for n in notas if not n.get("oculta")])
    ocultas = duplicados.eliminar([n for n in notas if n.get("oculta")])
    return agrupador.agrupar(visibles, prioridad) + ocultas + viejas


def actualizar(cfg: Config, con_red: bool = True) -> dict:
    ahora = datetime.now(timezone.utc).replace(microsecond=0)
    previas = almacen.cargar_noticias()
    estado_previo = almacen.cargar_estado()

    ventanas = {f["id"]: ventana_de(f, cfg) for f in cfg.fuentes}
    if con_red:
        nuevas, estado_fuentes = recolectar(cfg, ahora)
        crudas = combinar(previas, nuevas, ahora, cfg.ventana_dias, ventanas)
        crudas = sin_bajadas_restringidas(crudas, cfg)
        almacen.guardar_noticias(crudas, ahora)
        sin_bajada = {f["id"] for f in cfg.fuentes if not lector.muestra_bajada(f)}
        almacen.archivar(nuevas_con_fecha(crudas, nuevas), cfg.zona_horaria, sin_bajada)
        almacen.registrar_errores(estado_fuentes, ahora)
        estado = {"actualizado": ahora.isoformat(), "fuentes": estado_fuentes}
        almacen.guardar_estado(estado)
    else:
        crudas = combinar(previas, [], ahora, cfg.ventana_dias, ventanas)
        estado = estado_previo or {"actualizado": None, "fuentes": {}}

    notas = agrupar(enriquecer(crudas, cfg, ahora), cfg)
    notas.sort(key=lambda n: n["fecha"], reverse=True)
    notas = ia.procesar(notas, cfg.ia)
    return {"ahora": ahora, "notas": notas, "estado": estado}


def sin_bajadas_restringidas(notas: list[dict], cfg: Config) -> list[dict]:
    """Quita la bajada de las fuentes con `mostrar_bajada: false` antes de guardar en datos/."""
    fuentes = cfg.fuentes_por_id
    return [{**n, "bajada": ""} if n.get("bajada") and not lector.muestra_bajada(fuentes.get(n["fuente_id"], {})) else n
            for n in notas]


def nuevas_con_fecha(crudas: list[dict], nuevas: list[dict]) -> list[dict]:
    ids = {n["id"] for n in nuevas}
    return [n for n in crudas if n["id"] in ids]
