"""«Portadas de hoy»: qué notas están en la portada de cada medio en esta actualización.

En fuentes.yaml, una fuente con `portada: {url, patron, excluir}` se lee en cada
actualización. Las notas que ya están guardadas quedan marcadas «En portada hoy»;
las que no, se incorporan leyendo su titular y su fecha en la propia nota, aunque
se hayan publicado hace varios días.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from . import paginas
from .duplicados import url_canonica

log = logging.getLogger("actualizador")

# Notas de portada más viejas que esto no se incorporan (p. ej. un especial fijo de hace meses)
DIAS_MAXIMOS = 30
MAX_NUEVAS = 60


def enlaces_de_portada(fuente: dict) -> list[str]:
    p = fuente["portada"]
    urls = paginas.enlaces(p["url"], p["patron"])
    excluir = [x.lower() for x in p.get("excluir", [])]
    return [u for u in urls if not any(x in u.lower() for x in excluir)]


def leer(fuentes: list[dict], ahora: datetime, conocidas: set[str]) -> tuple[dict, list[dict], dict]:
    """Lee las portadas. Devuelve ({fuente_id: [urls canónicas]}, notas nuevas, {fuente_id: error})."""
    con_portada = [f for f in fuentes if f.get("portada")]
    portadas, nuevas, errores = {}, [], {}

    def una(f):
        try:
            urls = enlaces_de_portada(f)
        except Exception as e:  # noqa: BLE001 — si una portada falla, el resto sigue
            return f, None, [], f"{type(e).__name__}: {str(e)[:150]}"
        notas, err = paginas.notas_de_enlaces(urls, f, ahora, DIAS_MAXIMOS, "portada", conocidas, MAX_NUEVAS)
        return f, urls, notas, "; ".join(err[:3]) if err else None

    with ThreadPoolExecutor(max(1, len(con_portada))) as pool:
        for f, urls, notas, error in pool.map(una, con_portada):
            if urls is not None:
                portadas[f["id"]] = [url_canonica(u) for u in urls]
                nuevas.extend(notas)
                log.info("▣ portada de %s: %d notas (%d nuevas)", f["id"], len(urls), len(notas))
            if error:
                errores[f["id"]] = error
                log.warning("◐ portada de %s: %s", f["id"], error[:200])
    return portadas, nuevas, errores
