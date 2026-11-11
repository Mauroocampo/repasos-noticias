"""Lectura y escritura de datos/ (versionados en el repositorio)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import RAIZ

DATOS = RAIZ / "datos"
NOTICIAS = DATOS / "noticias.json"
ARCHIVO = DATOS / "archivo"
REGISTRO = DATOS / "registro"
ESTADO = REGISTRO / "estado-fuentes.json"
ERRORES = REGISTRO / "errores.log"


def _leer(ruta: Path, defecto):
    if not ruta.exists():
        return defecto
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defecto


def _escribir(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cargar_noticias() -> list[dict]:
    return _leer(NOTICIAS, {}).get("notas", [])


def guardar_noticias(notas: list[dict], actualizado: datetime) -> None:
    _escribir(NOTICIAS, {"actualizado": actualizado.isoformat(), "notas": notas})


def cargar_estado() -> dict:
    return _leer(ESTADO, {})


def guardar_estado(estado: dict) -> None:
    _escribir(ESTADO, estado)


def registrar_errores(estado_fuentes: dict, ahora: datetime) -> None:
    lineas = []
    for fid, est in sorted(estado_fuentes.items()):
        for err in est.get("errores", []):
            lineas.append(f"{ahora.isoformat()}\t{fid}\t{err}")
    if not lineas:
        return
    REGISTRO.mkdir(parents=True, exist_ok=True)
    previas = ERRORES.read_text(encoding="utf-8").splitlines() if ERRORES.exists() else []
    # Se guardan solo las últimas 2.000 líneas para que el archivo no crezca sin límite
    todas = (previas + lineas)[-2000:]
    ERRORES.write_text("\n".join(todas) + "\n", encoding="utf-8")


def archivar(notas: list[dict], zona: str, sin_bajada: set | None = None) -> None:
    """Guarda cada nota cruda en datos/archivo/AAAA-MM-DD.json según su fecha local.

    `sin_bajada`: fuentes cuya bajada no se guarda (prohíben reproducir su contenido).
    """
    sin_bajada = sin_bajada or set()
    tz = ZoneInfo(zona)
    por_dia: dict[str, list[dict]] = {}
    for n in notas:
        dia = datetime.fromisoformat(n["fecha"]).astimezone(tz).date().isoformat()
        por_dia.setdefault(dia, []).append(n)
    for dia, nuevas in por_dia.items():
        ruta = ARCHIVO / f"{dia}.json"
        previas = {n["id"]: n for n in _leer(ruta, [])}
        for n in nuevas:
            previas.setdefault(n["id"], n)
        for i, n in previas.items():
            if n.get("bajada") and n.get("fuente_id") in sin_bajada:
                previas[i] = {**n, "bajada": ""}
        _escribir(ruta, sorted(previas.values(), key=lambda n: n["fecha"], reverse=True))
