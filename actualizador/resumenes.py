"""Divide un resumen con avisos numerados (p. ej. "Daily OT Security News" de Viakoo)
en notas individuales: una por aviso, con su titular, una bajada corta y, si el
resumen lo cita, el enlace al aviso primario del fabricante o de la agencia.

Se configura en fuentes.yaml, en la fuente del resumen:
  dividir_resumen:
    titulo_contiene: "Daily OT Security News"   # qué entradas del feed son resúmenes
    dominios_primarios: [cisa.gov, cert-portal.siemens.com, certvde.com, ...]
"""
from __future__ import annotations

import html
import re
from urllib.parse import urlsplit

_ENCABEZADO = re.compile(r"<(h[2-4])[^>]*>\s*(?:<strong>)?\s*(\d{1,2})\.\s*(.*?)</\1>", re.S | re.I)
_ENLACE = re.compile(r'href="([^"]+)"', re.I)
_PARRAFO = re.compile(r"<p[^>]*>(.*?)</p>", re.S | re.I)
_ETIQUETAS = re.compile(r"<[^>]+>")
# Párrafos que son rótulos del resumen, no la noticia
_ROTULOS = re.compile(r"^(source (and event )?dates?|source date|event dates?|news briefing|ot implications|"
                      r"recommended actions|why it matters)\b", re.I)


def _texto(fragmento: str) -> str:
    t = html.unescape(_ETIQUETAS.sub(" ", fragmento))
    return re.sub(r"\s+", " ", t).strip()


def _es_primario(url: str, dominios: list[str]) -> bool:
    host = urlsplit(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in dominios)


def dividir(contenido: str, edicion_url: str, dominios_primarios: list[str]) -> list[dict]:
    """Devuelve [{numero, titular, bajada, enlace, enlace_primario}] de un resumen en HTML."""
    encabezados = list(_ENCABEZADO.finditer(contenido or ""))
    avisos = []
    for i, m in enumerate(encabezados):
        fin = encabezados[i + 1].start() if i + 1 < len(encabezados) else len(contenido)
        cuerpo = contenido[m.end():fin]
        titular = _texto(m.group(3))
        if not titular:
            continue
        enlaces = [html.unescape(u) for u in _ENLACE.findall(cuerpo)]
        primario = next((u for u in enlaces if _es_primario(u, dominios_primarios)), None)
        # Bajada: el primer párrafo con contenido, después de los rótulos y las fechas
        bajada = ""
        for p in _PARRAFO.findall(cuerpo):
            t = _texto(p)
            if len(t) < 40 or _ROTULOS.match(t):
                continue
            bajada = t
            break
        numero = int(m.group(2))
        avisos.append({
            "numero": numero,
            "titular": titular,
            "bajada": bajada,
            "enlace": primario or f"{edicion_url.rstrip('#')}#aviso-{numero}",
            "enlace_primario": bool(primario),
            "edicion": edicion_url,
        })
    return avisos
