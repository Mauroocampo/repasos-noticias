"""Filtro de relevancia: oculta (sin borrar) lo que no corresponde a las temáticas.

Las reglas están en `relevancia` de palabras-clave.yaml. Cada categoría tiene:
  texto        cómo se muestra la etiqueta ("Oculta: ofertas")
  incluir      palabras que la detectan (en el titular y la bajada)
  al_inicio    el titular empieza así (p. ej. "review:")
  al_final     el titular termina así (p. ej. "review")
  excepto      si aparece alguna, la nota NO se oculta (p. ej. negocios del deporte)
  solo_titular true para buscar `incluir` solo en el titular
"""
from __future__ import annotations

import re

from .filtro import _patron, compilar, normalizar

_PUNTUACION_FINAL = re.compile(r"[\s\.\!\?\:\;\,\-–—\"'”’)\]]+$")


def _extremo(terminos: list | None, al_final: bool) -> re.Pattern | None:
    terminos = [t for t in (terminos or []) if str(t).strip()]
    if not terminos:
        return None
    cuerpo = "|".join(f"(?:{_patron(t)})" for t in terminos)
    return re.compile(rf"(?:{cuerpo})$" if al_final else rf"^(?:{cuerpo})")


class Relevancia:
    def __init__(self, reglas: dict | None):
        self.categorias = []
        for cid, r in (reglas or {}).items():
            r = r or {}
            self.categorias.append({
                "id": cid,
                "texto": r.get("texto") or cid,
                "incluir": compilar(r.get("incluir")),
                "al_inicio": _extremo(r.get("al_inicio"), al_final=False),
                "al_final": _extremo(r.get("al_final"), al_final=True),
                "excepto": compilar(r.get("excepto")),
                "solo_titular": bool(r.get("solo_titular")),
            })

    @property
    def textos(self) -> dict:
        return {c["id"]: c["texto"] for c in self.categorias}

    def categoria(self, nota: dict) -> str | None:
        """Devuelve la categoría por la que se oculta la nota, o None si es relevante."""
        titular = normalizar(nota.get("titular", "")).strip()
        recortado = _PUNTUACION_FINAL.sub("", titular)
        completo = f"{titular} {normalizar(nota.get('bajada', ''))}"
        for c in self.categorias:
            donde = titular if c["solo_titular"] else completo
            hallada = (
                (c["incluir"] and c["incluir"].search(donde))
                or (c["al_inicio"] and c["al_inicio"].search(titular))
                or (c["al_final"] and c["al_final"].search(recortado))
            )
            if hallada and not (c["excepto"] and c["excepto"].search(completo)):
                return c["id"]
        return None
