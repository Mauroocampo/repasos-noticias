"""Descarta entradas que no son noticias: páginas de sección, paginación y portadas.

Los patrones están en `no_noticias` de palabras-clave.yaml.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from .filtro import normalizar


def _patron_titular(texto: str) -> str:
    """Convierte "page # of #" en una expresión regular (# = un número)."""
    partes = [re.escape(p) for p in normalizar(str(texto)).strip().split("#")]
    return r"\d+".join(partes).replace(r"\ ", r"\s+")


class Descartes:
    def __init__(self, reglas: dict | None):
        reglas = reglas or {}
        titulares = [t for t in reglas.get("titulares") or [] if str(t).strip()]
        self.titulares = re.compile("|".join(_patron_titular(t) for t in titulares)) if titulares else None
        self.rutas = [str(r).lower() for r in reglas.get("rutas") or []]
        self.portadas = bool(reglas.get("portadas", True))

    def motivo(self, nota: dict, fuente: dict) -> str | None:
        """Devuelve por qué la entrada no es una noticia, o None si sí lo es."""
        titular = normalizar(nota.get("titular", "")).strip()
        if self.titulares and self.titulares.search(titular):
            return "titular de paginación o sección"

        enlace = nota.get("enlace", "")
        partes = urlsplit(enlace)
        # Los enlaces de Google News son opacos: ahí solo se puede revisar el titular
        es_google = partes.netloc.endswith("news.google.com")
        if not es_google:
            ruta = partes.path.lower()
            if not ruta.endswith("/"):
                ruta += "/"
            if any(r in ruta for r in self.rutas):
                return "ruta de sección"
            if re.search(r"/page/\d+/", ruta):
                return "ruta de paginación"
            if self.portadas and ruta == "/" and not partes.query:
                return "portada"

        if self.portadas:
            nombre = normalizar(fuente.get("nombre", "")).strip()
            # "Yahoo Finance - Stock Market Live, Quotes…": la portada del medio
            if nombre and (titular == nombre or re.match(re.escape(nombre) + r"\s*[-|–—]\s", titular)):
                return "portada"
        return None
