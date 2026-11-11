"""Marcas automáticas junto a cada noticia, según el método del documento."""
from __future__ import annotations

import re

from .filtro import normalizar

PATROCINIO = re.compile(
    r"sponsored by|sponsored content|paid post|commissioned by|in partnership with|"
    r"patrocinad[oa]s? por|contenido patrocinado|publirreportaje|en alianza con|encargado por|"
    r"underwritten by|funded by|financiad[oa]s? por|made possible by|sponsored research|sponsored study|"
    r"commissioned (?:research|study|survey)|estudio patrocinado|investigaci[oó]n patrocinada"
)


def marcar(nota: dict, fuente: dict) -> list[str]:
    marcas = list(fuente.get("marcas", []))
    texto = normalizar(f"{nota.get('titular', '')} {nota.get('bajada', '')}")
    if PATROCINIO.search(texto) and "patrocinado" not in marcas:
        marcas.append("patrocinado")
    return marcas
