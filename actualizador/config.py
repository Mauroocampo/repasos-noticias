"""Carga y valida fuentes.yaml, palabras-clave.yaml e ia.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import re

import yaml

RAIZ = Path(__file__).resolve().parent.parent
GRUPOS = {"fija", "especializada", "general", "referencia", "excluida"}
GRUPOS_FLUJO = {"fija", "especializada", "general"}
METODOS = {"rss", "google_news", "avisos_html", "sin_acceso"}
METODOS_LECTURA = ("rss", "google_news", "avisos_html")
EXTRACTORES = {"certvde", "schneider", "jci"}


class ErrorConfig(ValueError):
    pass


@dataclass
class Config:
    ventana_dias: int
    zona_horaria: str
    tematicas: list[dict]
    grupos: dict
    tipos: dict
    marcas: dict
    fuentes: list[dict]
    palabras_clave: dict
    ia: dict = field(default_factory=dict)
    url_actualizar: str = ""

    @property
    def nombres_tematicas(self) -> dict:
        return {t["id"]: t["nombre"] for t in self.tematicas}

    @property
    def fuentes_por_id(self) -> dict:
        return {f["id"]: f for f in self.fuentes}

    def fuentes_activas(self) -> list[dict]:
        """Fuentes que alimentan el flujo de noticias y tienen método de lectura."""
        return [
            f for f in self.fuentes
            if f["grupo"] in GRUPOS_FLUJO and f.get("metodo") in METODOS_LECTURA
        ]

    def fuentes_del_flujo(self) -> list[dict]:
        return [f for f in self.fuentes if f["grupo"] in GRUPOS_FLUJO]


def _leer_yaml(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    with ruta.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def cargar(raiz: Path = RAIZ) -> Config:
    datos = _leer_yaml(raiz / "fuentes.yaml")
    claves = _leer_yaml(raiz / "palabras-clave.yaml")
    ia = _leer_yaml(raiz / "ia.yaml")
    cfg = Config(
        ventana_dias=int(datos.get("ventana_dias", 7)),
        zona_horaria=datos.get("zona_horaria", "America/Bogota"),
        tematicas=datos.get("tematicas", []),
        grupos=datos.get("grupos", {}),
        tipos=datos.get("tipos", {}),
        marcas=datos.get("marcas", {}),
        fuentes=datos.get("fuentes", []),
        palabras_clave=claves,
        ia=ia,
        url_actualizar=(datos.get("url_actualizar") or "").strip().rstrip("/"),
    )
    validar(cfg)
    return cfg


def validar(cfg: Config) -> None:
    """Revisa la configuración y reúne TODOS los problemas en un solo mensaje."""
    problemas: list[str] = []
    temas = {t["id"] for t in cfg.tematicas}
    vistos: set[str] = set()

    for i, f in enumerate(cfg.fuentes, start=1):
        nombre = f.get("nombre") or f.get("id") or f"fuente n.º {i}"
        fid = f.get("id")
        if not fid:
            problemas.append(f"{nombre}: falta `id`.")
            continue
        if fid in vistos:
            problemas.append(f"{nombre}: el id `{fid}` está repetido.")
        vistos.add(fid)
        if not f.get("nombre"):
            problemas.append(f"{fid}: falta `nombre`.")
        grupo = f.get("grupo")
        if grupo not in GRUPOS:
            problemas.append(f"{fid}: grupo `{grupo}` no válido (usa {', '.join(sorted(GRUPOS))}).")
            continue
        if grupo == "excluida":
            continue
        if f.get("tipo") not in cfg.tipos:
            problemas.append(f"{fid}: tipo `{f.get('tipo')}` no está en la lista `tipos`.")
        for t in list(f.get("tematicas", [])) + list(f.get("tematicas_por_filtro", [])):
            if t not in temas:
                problemas.append(f"{fid}: temática `{t}` no existe.")
        for m in f.get("marcas", []):
            if m not in cfg.marcas:
                problemas.append(f"{fid}: marca `{m}` no está en la lista `marcas`.")
        if grupo == "referencia":
            if not f.get("sitio"):
                problemas.append(f"{fid}: las fuentes de referencia necesitan `sitio`.")
            continue
        metodo = f.get("metodo")
        if metodo not in METODOS:
            problemas.append(f"{fid}: método `{metodo}` no válido (usa rss, google_news o sin_acceso).")
        elif metodo == "rss" and not f.get("feeds"):
            problemas.append(f"{fid}: método rss sin `feeds`.")
        elif metodo == "google_news" and not (f.get("google_news") or {}).get("consulta"):
            problemas.append(f"{fid}: método google_news sin `google_news.consulta`.")
        elif metodo == "avisos_html" and (not f.get("pagina_avisos") or f.get("extractor") not in EXTRACTORES):
            problemas.append(f"{fid}: avisos_html necesita `pagina_avisos` y `extractor` ({', '.join(sorted(EXTRACTORES))}).")
        for pag in f.get("paginas", []) + ([f["portada"]] if f.get("portada") else []):
            try:
                re.compile(pag["patron"])
            except (KeyError, re.error) as e:
                problemas.append(f"{fid}: patrón de página no válido ({e}).")
        if f.get("tipo_por_ruta"):
            for ruta, tipo in f["tipo_por_ruta"].items():
                if tipo not in cfg.tipos:
                    problemas.append(f"{fid}: tipo_por_ruta usa el tipo `{tipo}`, que no está en `tipos`.")
        for m in [x for x in f.get("marcas", []) if x not in cfg.marcas]:
            problemas.append(f"{fid}: marca `{m}` no existe.")
        if f.get("tematica_por_defecto") and f["tematica_por_defecto"] not in temas:
            problemas.append(f"{fid}: tematica_por_defecto `{f['tematica_por_defecto']}` no existe.")
        if "mostrar_bajada" in f and not isinstance(f["mostrar_bajada"], bool):
            problemas.append(f"{fid}: mostrar_bajada debe ser true o false.")
        if f.get("ventana_dias") is not None and (not isinstance(f["ventana_dias"], int) or f["ventana_dias"] < 1):
            problemas.append(f"{fid}: ventana_dias debe ser un número entero de días.")
        if not f.get("tematicas") and not f.get("tematicas_por_filtro"):
            problemas.append(f"{fid}: no tiene ninguna temática.")
        if grupo == "general" and f.get("tematicas"):
            problemas.append(f"{fid}: un medio general solo debe usar `tematicas_por_filtro`.")

    for t in temas:
        if any(t in f.get("tematicas_por_filtro", []) for f in cfg.fuentes) and t not in cfg.palabras_clave:
            problemas.append(f"palabras-clave.yaml: falta la temática `{t}`.")

    ajustes = cfg.palabras_clave.get("ajustes") or {}
    for t in list(ajustes.get("tematicas_abiertas") or []) + [ajustes.get("tematica_exterior") or "internacional"]:
        if t not in temas:
            problemas.append(f"palabras-clave.yaml: en `ajustes`, la temática `{t}` no existe.")
        elif t not in cfg.palabras_clave:
            problemas.append(f"palabras-clave.yaml: falta la temática `{t}`.")

    if cfg.url_actualizar and not cfg.url_actualizar.startswith("https://"):
        problemas.append("url_actualizar: debe empezar por https:// (o dejarse vacía).")

    if problemas:
        raise ErrorConfig("Hay problemas en la configuración:\n  - " + "\n  - ".join(problemas))
