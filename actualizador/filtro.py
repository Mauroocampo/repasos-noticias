"""Filtro de palabras clave por temática (palabras-clave.yaml)."""
from __future__ import annotations

import re
import unicodedata


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


class Filtro:
    def __init__(self, palabras_clave: dict):
        self.reglas = {}
        for tema, regla in (palabras_clave or {}).items():
            regla = regla or {}
            self.reglas[tema] = {
                "incluir": compilar(regla.get("incluir")),
                "excluir": compilar(regla.get("excluir")),
                "contexto": compilar(regla.get("contexto")),
            }

    def coincide(self, tema: str, texto: str, pais: str | None = None) -> bool:
        regla = self.reglas.get(tema)
        if not regla or not regla["incluir"]:
            return False
        t = normalizar(texto)
        if not regla["incluir"].search(t):
            return False
        if regla["excluir"] and regla["excluir"].search(t):
            return False
        # Para medios que no son colombianos, la temática Colombia exige mencionar Colombia
        if regla["contexto"] and pais != "CO" and not regla["contexto"].search(t):
            return False
        return True

    def asignar(self, nota: dict, fuente: dict) -> tuple[list[str], str]:
        """Devuelve (temáticas, cómo se clasificó)."""
        temas = list(fuente.get("tematicas", []))
        texto = f"{nota.get('titular', '')} {nota.get('bajada', '')}"
        por_filtro = [
            t for t in fuente.get("tematicas_por_filtro", [])
            if t not in temas and self.coincide(t, texto, fuente.get("pais"))
        ]
        if fuente.get("tematicas"):
            como = "fuente"
        else:
            como = "palabras_clave"
        return temas + por_filtro, como
