"""Clasificación por contenido (palabras-clave.yaml).

La temática de una nota sale de su titular y su bajada:
  - `incluir`: basta una de estas palabras.
  - `ambiguas` + `acompanantes`: una palabra ambigua solo cuenta si además
    aparece alguna acompañante (p. ej., "PLC" junto a "vulnerabilidad").
  - `excluir`: si aparece alguna, la nota no entra en la temática.
  - Colombia: `contexto` (señales de que la nota trata de Colombia) y
    `exterior` (señales de que trata de otro país).
"""
from __future__ import annotations

import re
import unicodedata

# Claves de palabras-clave.yaml que no son temáticas
RESERVADAS = {"ajustes", "no_noticias", "relevancia", "historias"}


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar sin importar la escritura."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.lower()


def _patron(termino: str) -> str:
    t = normalizar(str(termino)).strip().strip('"').strip()
    prefijo = t.endswith("*")
    t = t.rstrip("*").strip()
    partes = [re.escape(p) for p in t.split()]
    cuerpo = r"\s+".join(partes)
    inicio = r"(?<![\w])"
    fin = r"\w*" if prefijo else r"(?![\w])"
    return inicio + cuerpo + fin


def compilar(terminos: list | None) -> re.Pattern | None:
    terminos = [t for t in (terminos or []) if str(t).strip()]
    if not terminos:
        return None
    return re.compile("|".join(_patron(t) for t in terminos))


def _hay(patron: re.Pattern | None, texto: str) -> bool:
    return bool(patron and patron.search(texto))


class Filtro:
    def __init__(self, palabras_clave: dict):
        palabras_clave = palabras_clave or {}
        ajustes = palabras_clave.get("ajustes") or {}
        # Temáticas que cualquier fuente puede recibir si el contenido lo dice
        self.abiertas = list(ajustes.get("tematicas_abiertas") or [])
        # A dónde van las notas de medios colombianos que tratan de otro país
        self.tema_exterior = ajustes.get("tematica_exterior") or "internacional"
        self.reglas = {}
        for tema, regla in palabras_clave.items():
            if tema in RESERVADAS:
                continue
            regla = regla or {}
            self.reglas[tema] = {
                clave: compilar(regla.get(clave))
                for clave in ("incluir", "ambiguas", "acompanantes", "excluir", "contexto", "exterior")
            }

    # ── piezas ──────────────────────────────────────────────────────────────
    def _por_contenido(self, tema: str, t: str) -> bool:
        """¿El texto (ya normalizado) habla de esta temática?"""
        regla = self.reglas.get(tema)
        if not regla:
            return False
        directo = _hay(regla["incluir"], t)
        con_compania = _hay(regla["ambiguas"], t) and _hay(regla["acompanantes"], t)
        if not (directo or con_compania):
            return False
        return not _hay(regla["excluir"], t)

    def _geografia(self, t: str, enlace: str = "", fuente: dict | None = None) -> tuple[bool, bool]:
        """Devuelve (menciona Colombia, tiene señales de otro país)."""
        regla = self.reglas.get("colombia") or {}
        de_colombia = _hay(regla.get("contexto"), t)
        secciones = (fuente or {}).get("secciones_exterior")
        if secciones and enlace and "news.google.com" not in enlace:
            # El medio separa lo internacional en una sección propia: manda la sección.
            # ("Dólar sube por dato de empleo en EE. UU." en /finanzas/ sigue siendo de Colombia.)
            exterior = any(s.lower() in enlace.lower() for s in secciones)
        else:
            exterior = _hay(regla.get("exterior"), t)
        return de_colombia, exterior

    def coincide(self, tema: str, texto: str, pais: str | None = None) -> bool:
        """¿La nota entra en la temática? Para Colombia también mira de qué país trata."""
        t = normalizar(texto)
        if not self._por_contenido(tema, t):
            return False
        if tema == "colombia":
            de_colombia, exterior = self._geografia(t)
            if pais == "CO":
                return de_colombia or not exterior
            return de_colombia
        return True

    # ── clasificación completa ──────────────────────────────────────────────
    def asignar(self, nota: dict, fuente: dict) -> tuple[list[str], str]:
        """Devuelve (temáticas, cómo se clasificó: "contenido" o "fuente")."""
        t = normalizar(f"{nota.get('titular', '')} {nota.get('bajada', '')}")
        pais = fuente.get("pais")
        base = list(fuente.get("tematicas", []))
        candidatas = [x for x in list(fuente.get("tematicas_por_filtro", [])) + self.abiertas if x not in base]
        de_colombia, exterior = self._geografia(t, nota.get("enlace", ""), fuente)
        solo_exterior = exterior and not de_colombia

        temas: list[str] = []
        por_contenido = False

        def agregar(tema: str) -> None:
            if tema not in temas:
                temas.append(tema)

        # 1. Temáticas propias de la fuente. Colombia no se hereda: depende del contenido.
        for tema in base:
            if tema == "colombia" and pais == "CO" and solo_exterior:
                agregar(self.tema_exterior)
                por_contenido = True
            else:
                agregar(tema)

        # 2. Temáticas que dependen del contenido
        for tema in candidatas:
            if not self._por_contenido(tema, t):
                continue
            if tema == "colombia":
                # Medio colombiano: basta que no sea una nota del exterior.
                # Medio extranjero: tiene que mencionar a Colombia.
                if solo_exterior if pais == "CO" else not de_colombia:
                    continue
                agregar("colombia")
            elif tema == self.tema_exterior and pais == "CO" and not exterior:
                continue  # medio colombiano hablando de Colombia: no es internacional
            else:
                agregar(tema)
            por_contenido = True

        return temas, ("contenido" if por_contenido or not base else "fuente")
