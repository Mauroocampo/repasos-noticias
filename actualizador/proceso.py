"""Orquesta una actualización: leer → combinar → clasificar → marcar → deduplicar."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from . import almacen, duplicados, ia, lector, marcas
from .config import Config
from .filtro import Filtro

log = logging.getLogger("actualizador")


def recolectar(cfg: Config, ahora: datetime) -> tuple[list[dict], dict]:
    fuentes = cfg.fuentes_activas()
    notas: list[dict] = []
    estado: dict = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futuros = {f["id"]: pool.submit(lector.leer_fuente, f, ahora, cfg.ventana_dias) for f in fuentes}
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


def combinar(previas: list[dict], nuevas: list[dict], ahora: datetime, dias: int) -> list[dict]:
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
    limite = ahora - timedelta(days=dias)
    return sorted(
        (n for n in por_id.values() if datetime.fromisoformat(n["fecha"]) >= limite),
        key=lambda n: n["fecha"],
        reverse=True,
    )


def enriquecer(crudas: list[dict], cfg: Config) -> list[dict]:
    """Aplica la configuración actual: fuente, tipo, temáticas y marcas."""
    filtro = Filtro(cfg.palabras_clave)
    fuentes = cfg.fuentes_por_id
    salida = []
    for n in crudas:
        f = fuentes.get(n["fuente_id"])
        if not f or f["grupo"] not in ("fija", "especializada", "general"):
            continue  # la fuente se quitó o se excluyó
        exigido = (f.get("solo_titulares_con") or "").lower()
        if exigido and exigido not in n["titular"].lower():
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
            "tambien_en": [],
            # Campos reservados para la fase 2 (IA)
            "resumen": None,
            "comentario": None,
        })
    return salida


def actualizar(cfg: Config, con_red: bool = True) -> dict:
    ahora = datetime.now(timezone.utc).replace(microsecond=0)
    previas = almacen.cargar_noticias()
    estado_previo = almacen.cargar_estado()

    if con_red:
        nuevas, estado_fuentes = recolectar(cfg, ahora)
        crudas = combinar(previas, nuevas, ahora, cfg.ventana_dias)
        almacen.guardar_noticias(crudas, ahora)
        almacen.archivar(nuevas_con_fecha(crudas, nuevas), cfg.zona_horaria)
        almacen.registrar_errores(estado_fuentes, ahora)
        estado = {"actualizado": ahora.isoformat(), "fuentes": estado_fuentes}
        almacen.guardar_estado(estado)
    else:
        crudas = combinar(previas, [], ahora, cfg.ventana_dias)
        estado = estado_previo or {"actualizado": None, "fuentes": {}}

    notas = duplicados.eliminar(enriquecer(crudas, cfg))
    notas.sort(key=lambda n: n["fecha"], reverse=True)
    notas = ia.procesar(notas, cfg.ia)
    return {"ahora": ahora, "notas": notas, "estado": estado}


def nuevas_con_fecha(crudas: list[dict], nuevas: list[dict]) -> list[dict]:
    ids = {n["id"] for n in nuevas}
    return [n for n in crudas if n["id"] in ids]
