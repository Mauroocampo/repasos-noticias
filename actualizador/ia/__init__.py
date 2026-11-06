"""FASE 2 — IA (todavía desactivada).

Punto único de entrada: `procesar(notas, cfg_ia)`. Con `habilitado: false` en
ia.yaml devuelve las notas sin tocarlas y no hace ninguna llamada externa.

Cuando se active:
  - resumen.py       → llena `resumen` (español) y `comentario` de cada nota.
  - clasificador.py  → reemplaza el filtro de palabras clave para medios generales.
  - busqueda.py      → agrega notas de fuera del documento (marcadas como tales).
La clave se lee de la variable de entorno indicada en `secreto_clave`, que en
GitHub Actions viene de los secretos del repositorio.
"""
from __future__ import annotations


def procesar(notas: list[dict], cfg_ia: dict | None) -> list[dict]:
    cfg_ia = cfg_ia or {}
    if not cfg_ia.get("habilitado"):
        return notas
    raise NotImplementedError(
        "La fase 2 (IA) todavía no está construida. Pon `habilitado: false` en ia.yaml."
    )
