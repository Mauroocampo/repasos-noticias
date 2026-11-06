"""Carga y valida fuentes.yaml, palabras-clave.yaml e ia.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
GRUPOS = {"fija", "especializada", "general", "referencia", "excluida"}
GRUPOS_FLUJO = {"fija", "especializada", "general"}
METODOS = {"rss", "google_news", "sin_acceso"}


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
            if f["grupo"] in GRUPOS_FLUJO and f.get("metodo") in ("rss", "google_news")
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
        if not f.get("tematicas") and not f.get("tematicas_por_filtro"):
            problemas.append(f"{fid}: no tiene ninguna temática.")
        if grupo == "general" and f.get("tematicas"):
            problemas.append(f"{fid}: un medio general solo debe usar `tematicas_por_filtro`.")

    for t in temas:
        if any(t in f.get("tematicas_por_filtro", []) for f in cfg.fuentes) and t not in cfg.palabras_clave:
            problemas.append(f"palabras-clave.yaml: falta la temática `{t}`.")

    if cfg.url_actualizar and not cfg.url_actualizar.startswith("https://"):
        problemas.append("url_actualizar: debe empezar por https:// (o dejarse vacía).")

    if problemas:
        raise ErrorConfig("Hay problemas en la configuración:\n  - " + "\n  - ".join(problemas))
