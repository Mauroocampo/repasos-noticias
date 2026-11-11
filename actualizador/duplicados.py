"""Eliminación de duplicados: misma URL o titular casi igual en varios sitios."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from rapidfuzz import fuzz, process

SIMILITUD_MINIMA = 90       # 0–100: qué tan parecidos deben ser dos titulares
DIAS_MAXIMOS = 3            # dos notas parecidas con más días de diferencia no se unen
LARGO_MINIMO_DIFUSO = 25    # titulares muy cortos solo se unen si son idénticos

_PARAMETROS_BASURA = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|source$|cmpid|ocid|guccounter)", re.I)


def url_canonica(url: str) -> str:
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = urlencode([(k, v) for k, v in parse_qsl(p.query) if not _PARAMETROS_BASURA.match(k)])
    ruta = p.path.rstrip("/") or "/"
    return urlunsplit(("https", host, ruta, query, ""))


def clave_titular(titular: str) -> str:
    t = unicodedata.normalize("NFKD", titular or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _fecha(n: dict) -> datetime:
    return datetime.fromisoformat(n["fecha"])


def _preferencia(n: dict):
    # Primero las que vienen por RSS (traen bajada), luego la publicación más antigua.
    return (0 if n.get("via") == "rss" else 1, n["fecha"])


def _unir(base: dict, otra: dict) -> None:
    if otra["fuente_id"] != base["fuente_id"]:
        ya = {t["fuente_id"] for t in base["tambien_en"]}
        if otra["fuente_id"] not in ya:
            base["tambien_en"].append({
                "fuente_id": otra["fuente_id"],
                "fuente": otra.get("fuente", otra["fuente_id"]),
                "enlace": otra["enlace"],
            })
    for t in otra.get("tematicas", []):
        if t not in base["tematicas"]:
            base["tematicas"].append(t)
    # Si la principal no tiene bajada se usa la de la copia, salvo que la principal sea
    # "solo titular": ahí la bajada de otro medio quedaría atribuida al medio equivocado
    if not base.get("bajada") and otra.get("bajada") and not base.get("solo_titular"):
        base["bajada"] = otra["bajada"]


def eliminar(notas: list[dict]) -> list[dict]:
    """Devuelve una sola versión por nota; las demás quedan en `tambien_en`."""
    ordenadas = sorted(notas, key=_preferencia)
    finales: list[dict] = []
    por_url: dict[str, dict] = {}
    por_titular: dict[str, dict] = {}
    claves_difusas: list[str] = []
    notas_difusas: list[dict] = []

    for n in ordenadas:
        n = {**n, "tematicas": list(n.get("tematicas", [])), "tambien_en": list(n.get("tambien_en", []))}
        url = url_canonica(n["enlace"])
        clave = clave_titular(n["titular"])

        base = por_url.get(url) or por_titular.get(clave)
        if base is None and len(clave) >= LARGO_MINIMO_DIFUSO and claves_difusas:
            hallado = process.extractOne(clave, claves_difusas, scorer=fuzz.ratio, score_cutoff=SIMILITUD_MINIMA)
            if hallado:
                candidata = notas_difusas[hallado[2]]
                if abs((_fecha(candidata) - _fecha(n)).days) <= DIAS_MAXIMOS:
                    base = candidata

        if base is not None:
            _unir(base, n)
            por_url.setdefault(url, base)
            continue

        finales.append(n)
        por_url[url] = n
        por_titular[clave] = n
        if len(clave) >= LARGO_MINIMO_DIFUSO:
            claves_difusas.append(clave)
            notas_difusas.append(n)

    return finales
