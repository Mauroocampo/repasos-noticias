"""Enlaces de Google News → URL original del medio.

Los enlaces news.google.com/rss/articles/… ya no llevan la URL del medio: Google la
entrega con JavaScript y un servicio interno que no es público, y no se usa. En su
lugar, para las fuentes que publican un mapa del sitio (`mapa_del_sitio` en
fuentes.yaml), se busca el titular de la nota en ese mapa:

  - si el mapa trae titulares (mapas de noticias), el titular debe coincidir casi igual;
  - si solo trae direcciones, las palabras de la dirección deben estar en el titular
    (al menos 4 palabras, 90 % de la dirección y 60 % del titular).

Lo resuelto (y lo que no) se guarda en datos/registro/google-news.json para no
volver a buscarlo. Las notas que no se resuelven llevan la marca «Enlace vía Google News».
"""
from __future__ import annotations

import gzip
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from rapidfuzz import fuzz

from . import lector
from .duplicados import clave_titular, url_canonica

log = logging.getLogger("actualizador")

HIJOS_MAXIMOS = 4          # de un índice de mapas, solo los más recientes
ENTRADAS_MAXIMAS = 60000   # tope de direcciones leídas por fuente
SIMILITUD_TITULAR = 92     # 0-100, para mapas con titulares
DIAS_REINTENTO = 3         # una nota no resuelta se vuelve a buscar durante estos días
TIEMPO_MAPA = 90           # segundos: algunos mapas son grandes y lentos (Business Wire)


def es_google_news(enlace: str) -> bool:
    return "news.google.com/" in (enlace or "")


def _xml(url: str):
    contenido = lector.descargar(url, tiempo=TIEMPO_MAPA)
    if contenido[:2] == bytes([31, 139]):  # .gz
        contenido = gzip.decompress(contenido)
    return ET.fromstring(contenido)


def entradas_del_mapa(url: str, profundidad: int = 0) -> list[tuple[str, str]]:
    """[(dirección, titular o "")] de un mapa del sitio, siguiendo índices."""
    raiz = _xml(url)
    if raiz.tag.endswith("sitemapindex") and profundidad < 2:
        hijos = []
        for sm in raiz:
            loc = next((c.text for c in sm if c.tag.endswith("loc")), None)
            lm = next((c.text for c in sm if c.tag.endswith("lastmod")), "") or ""
            if loc:
                hijos.append((lm, loc.strip()))
        salida = []
        for _, loc in sorted(hijos, reverse=True)[:HIJOS_MAXIMOS]:
            try:
                salida += entradas_del_mapa(loc, profundidad + 1)
            except Exception as e:  # noqa: BLE001 — un hijo roto no detiene a los demás
                log.warning("mapa del sitio %s: %s", loc[-60:], e)
        return salida
    salida = []
    for u in raiz:
        loc = titulo = None
        for c in u.iter():
            etiqueta = c.tag.split("}")[-1]
            if etiqueta == "loc" and loc is None:
                loc = (c.text or "").strip()
            elif etiqueta == "title" and titulo is None:
                titulo = (c.text or "").strip()
        if loc:
            salida.append((loc, titulo or ""))
        if len(salida) >= ENTRADAS_MAXIMAS:
            break
    return salida


def _texto_de_direccion(url: str) -> str:
    s = url.rstrip("/").split("/")[-1]
    s = re.sub(r"\.(html?|aspx?|php)$", "", s)
    s = re.sub(r"[-_]+", " ", s)
    s = re.sub(r"\b[0-9a-f]{8,}\b|\b\d{5,}\b", " ", s)
    return clave_titular(s)


class Indice:
    """Entradas de un mapa del sitio, listas para buscar titulares."""

    def __init__(self, entradas: list[tuple[str, str]]):
        self.con_titular = {}
        self.por_direccion = []
        for url, titulo in entradas:
            if titulo:
                self.con_titular.setdefault(clave_titular(titulo), url)
            else:
                palabras = set(_texto_de_direccion(url).split())
                if len(palabras) >= 4:
                    self.por_direccion.append((palabras, url))
        self._claves = list(self.con_titular)

    def buscar(self, titular: str) -> str | None:
        clave = clave_titular(titular)
        if not clave:
            return None
        if clave in self.con_titular:
            return self.con_titular[clave]
        mejor, puntaje = None, 0.0
        for c in self._claves:
            p = fuzz.ratio(clave, c)
            if p > puntaje:
                mejor, puntaje = c, p
        if mejor and puntaje >= SIMILITUD_TITULAR:
            return self.con_titular[mejor]
        del_titular = set(clave.split())
        candidatas = []
        for palabras, url in self.por_direccion:
            comunes = len(palabras & del_titular)
            if comunes / len(palabras) >= 0.9 and comunes / len(del_titular) >= 0.6:
                candidatas.append((comunes, url))
        return max(candidatas)[1] if candidatas else None


def resolver(notas: list[dict], fuentes: dict, cache: dict, ahora: datetime) -> tuple[list[dict], dict]:
    """Cambia los enlaces de Google News por la URL del medio cuando se encuentra.

    Devuelve (notas, conteo por fuente {fuente_id: {"resueltas", "sin_resolver"}}).
    `cache` se actualiza en el lugar: {url_google_canónica: {"url": … o None, "revisado": fecha}}.
    """
    pendientes: dict[str, list[int]] = {}
    salida = list(notas)
    for i, n in enumerate(salida):
        if not es_google_news(n.get("enlace")):
            continue
        clave = url_canonica(n["enlace"])
        guardado = cache.get(clave)
        if guardado and guardado.get("url"):
            salida[i] = {**n, "enlace": guardado["url"], "enlace_google_news": n["enlace"]}
            continue
        f = fuentes.get(n["fuente_id"]) or {}
        if not f.get("mapa_del_sitio"):
            continue
        if guardado and guardado.get("revisado"):
            primera = datetime.fromisoformat(guardado.get("primer_intento") or guardado["revisado"])
            if ahora - primera > timedelta(days=DIAS_REINTENTO):
                continue  # ya se buscó varios días sin éxito
        pendientes.setdefault(n["fuente_id"], []).append(i)

    conteo: dict[str, dict] = {}
    for fid, indices in pendientes.items():
        entradas = []
        for url in fuentes[fid]["mapa_del_sitio"]:
            try:
                entradas += entradas_del_mapa(url)
            except Exception as e:  # noqa: BLE001
                log.warning("mapa del sitio de %s: %s", fid, str(e)[:150])
        indice = Indice(entradas)
        c = conteo.setdefault(fid, {"resueltas": 0, "sin_resolver": 0})
        for i in indices:
            n = salida[i]
            clave = url_canonica(n["enlace"])
            final = indice.buscar(n["titular"]) if entradas else None
            previo = cache.get(clave) or {}
            cache[clave] = {"url": final, "revisado": ahora.isoformat(),
                            "primer_intento": previo.get("primer_intento") or ahora.isoformat()}
            if final:
                salida[i] = {**n, "enlace": final, "enlace_google_news": n["enlace"]}
                c["resueltas"] += 1
            else:
                c["sin_resolver"] += 1
        log.info("↪ Google News de %s: %d enlaces resueltos, %d sin resolver", fid, c["resueltas"], c["sin_resolver"])
    return salida, conteo


def podar(cache: dict, ahora: datetime, dias: int = 30) -> dict:
    """Quita del registro lo revisado hace más de `dias` días."""
    limite = ahora - timedelta(days=dias)
    return {k: v for k, v in cache.items() if datetime.fromisoformat(v["revisado"]) >= limite}
