"""Lectura de páginas HTML, para lo que no tiene RSS (o lo tiene muy corto).

  - Listados de sección (p. ej. Portafolio Energía, columnas de La República):
    se toman los enlaces que cumplen un patrón y, de cada nota nueva, su titular,
    bajada y fecha desde las etiquetas <meta> de la propia nota.
  - Portadas: los enlaces de la portada del día, en orden.
  - Avisos de fabricantes sin RSS: CERT@VDE, Schneider Electric, Johnson Controls.

No se intenta saltar ningún bloqueo: si un sitio no responde, se registra el error.
"""
from __future__ import annotations

import html as H
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin

from . import lector
from .duplicados import url_canonica

HILOS = 4            # consultas simultáneas a un mismo medio
MAX_NUEVAS = 30      # notas nuevas por listado y por actualización


def texto_html(contenido: bytes) -> str:
    return contenido.decode("utf-8", errors="replace")


def _meta(t: str, *claves: str) -> str:
    for c in claves:
        m = re.search(rf'<meta[^>]+(?:property|name|itemprop)="{re.escape(c)}"[^>]+content="([^"]*)"', t, re.I) or \
            re.search(rf'<meta[^>]+content="([^"]*)"[^>]+(?:property|name|itemprop)="{re.escape(c)}"', t, re.I)
        if m:
            return H.unescape(m.group(1)).strip()
    return ""


def _a_fecha(valor: str) -> datetime | None:
    if not valor:
        return None
    valor = valor.strip()
    try:
        d = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        # Formatos de las páginas de avisos: "Nov. 10, 2026, 11:00 AM", "November 3, 2026"
        limpio = re.sub(r"\b(Sept)\b", "Sep", valor.replace(".", "")).strip()
        d = None
        for formato in ("%b %d, %Y, %I:%M %p", "%B %d, %Y, %I:%M %p", "%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
            try:
                d = datetime.strptime(limpio, formato)
                break
            except ValueError:
                continue
        if d is None:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def metadatos(url: str) -> dict | None:
    """Titular, bajada y fecha de una nota, desde sus etiquetas <meta>."""
    t = texto_html(lector.descargar(url))
    titular = _meta(t, "og:title", "twitter:title")
    if not titular:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S | re.I)
        titular = lector.limpiar(m.group(1)) if m else ""
    fecha = _a_fecha(_meta(t, "article:published_time", "datePublished"))
    if not fecha:
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', t)
        fecha = _a_fecha(m.group(1)) if m else None
    if not titular:
        return None
    return {"titular": lector.limpiar(titular), "bajada": lector.limpiar(_meta(t, "og:description", "description")),
            "fecha": fecha}


def enlaces(url: str, patron: str) -> list[str]:
    """Enlaces de una página que cumplen el patrón, en orden y sin repetir."""
    t = texto_html(lector.descargar(url))
    vistos, salida = set(), []
    for h in re.findall(r'href="([^"#?]+)"', t):
        absoluto = urljoin(url, H.unescape(h))
        if re.search(patron, absoluto) and url_canonica(absoluto) not in vistos:
            vistos.add(url_canonica(absoluto))
            salida.append(absoluto)
    return salida


def notas_de_enlaces(urls: list[str], fuente: dict, ahora: datetime, dias: int, via: str,
                     conocidas: set[str] | None = None, maximo: int = MAX_NUEVAS) -> tuple[list[dict], list[str]]:
    """Convierte enlaces nuevos en notas crudas leyendo cada nota. Devuelve (notas, errores)."""
    conocidas = conocidas or set()
    nuevas = [u for u in urls if url_canonica(u) not in conocidas][:maximo]
    limite = ahora - timedelta(days=dias)
    notas, errores = [], []

    def una(u):
        try:
            return u, metadatos(u), None
        except Exception as e:  # noqa: BLE001
            return u, None, f"{u}: {type(e).__name__}: {str(e)[:120]}"

    with ThreadPoolExecutor(HILOS) as pool:
        for u, m, error in pool.map(una, nuevas):
            if error:
                errores.append(error)
                continue
            if not m or not m["fecha"] or m["fecha"] < limite:
                continue
            fecha = min(m["fecha"], ahora)
            notas.append({
                "id": lector.id_de(u), "fuente_id": fuente["id"], "titular": m["titular"],
                "bajada": lector.recortar(m["bajada"]) if lector.muestra_bajada(fuente) else "",
                "enlace": u, "fecha": fecha.isoformat(), "via": via,
            })
    return notas, errores


def leer_listados(fuente: dict, ahora: datetime, dias: int, conocidas: set[str]) -> tuple[list[dict], list[str]]:
    """Lee las páginas de sección de `paginas` en fuentes.yaml."""
    notas, errores = [], []
    for p in fuente.get("paginas", []):
        try:
            urls = enlaces(p["url"], p["patron"])
        except Exception as e:  # noqa: BLE001
            errores.append(f"{p['url']}: {type(e).__name__}: {str(e)[:150]}")
            continue
        n, err = notas_de_enlaces(urls, fuente, ahora, dias, "pagina", conocidas, p.get("max", MAX_NUEVAS))
        notas.extend(n)
        errores.extend(err)
        conocidas |= {url_canonica(x["enlace"]) for x in n}
    return notas, errores


# ── Avisos de fabricantes sin RSS ───────────────────────────────────────────
class _Tabla(HTMLParser):
    """Filas de tablas HTML: [(celdas de texto, enlaces)]."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.filas, self._fila, self._celda, self._links = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._fila, self._links = [], []
        elif tag in ("td", "th") and self._fila is not None:
            self._celda = []
        elif tag == "a" and self._fila is not None:
            href = dict(attrs).get("href")
            if href:
                self._links.append(href)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._celda is not None:
            self._fila.append(" ".join("".join(self._celda).split()))
            self._celda = None
        elif tag == "tr" and self._fila is not None:
            self.filas.append((self._fila, self._links))
            self._fila = None

    def handle_data(self, data):
        if self._celda is not None:
            self._celda.append(data)


def _filas(t: str):
    p = _Tabla()
    p.feed(t)
    return p.filas


def _certvde(t: str, url: str):
    # Tarjetas: <div>VDE-2026-128</div><div>Nov. 10, 2026, 11:00 AM</div> … <a href="/en/advisories/VDE-2026-128/" title="…">
    patron = re.compile(r"<div>\s*(VDE-\d{4}-\d+)\s*</div>\s*<div>\s*([^<]+?)\s*</div>.*?<a href=\"([^\"]+)\"[^>]*title=\"([^\"]+)\"(.*?)</div>\s*</div>", re.S)
    for vde, fecha, enlace, titulo, resto in patron.findall(t):
        m = re.search(r'card-text[^>]*>(.*?)</div>', resto, re.S)
        yield {"titular": H.unescape(titulo), "fecha": _a_fecha(fecha.replace("Sept.", "Sep.")),
               "enlace": urljoin(url, enlace), "bajada": lector.limpiar(m.group(1)) if m else "", "clave": vde}


def _schneider(t: str, url: str):
    for celdas, links in _filas(t):
        doc = next((re.search(r"SEVD-\d{4}-\d+-\d+", l).group(0) for l in links if re.search(r"SEVD-\d{4}-\d+-\d+", l)), None)
        if not doc or len(celdas) < 2:
            continue
        # Enlace al documento oficial (el mismo que citan los resúmenes)
        yield {"titular": celdas[1], "fecha": _a_fecha(celdas[0].replace("/", "-")),
               "enlace": f"https://www.se.com/ww/en/download/document/{doc}/",
               "bajada": celdas[3] if len(celdas) > 3 else "", "clave": doc}


def _jci(t: str, url: str):
    for celdas, links in _filas(t):
        if len(celdas) < 6:
            continue
        m = re.search(r"JCI-PSA-\d{4}-\d+", celdas[0])
        if not m:
            continue
        producto = celdas[1] or celdas[0].replace(m.group(0), "").strip()
        yield {"titular": f"{m.group(0)}: {celdas[2] or 'Vulnerability impacting ' + producto}",
               "fecha": _a_fecha(celdas[5]), "enlace": urljoin(url, links[0]) if links else url,
               "bajada": f"Producto: {producto}. {celdas[3]}".strip(), "clave": m.group(0)}


EXTRACTORES = {"certvde": _certvde, "schneider": _schneider, "jci": _jci}


def leer_avisos(fuente: dict, ahora: datetime, dias: int) -> list[dict]:
    """Avisos de una página de fabricante (`metodo: avisos_html`, `extractor: …`)."""
    extractor = EXTRACTORES[fuente["extractor"]]
    url = fuente["pagina_avisos"]
    t = texto_html(lector.descargar(url))
    limite = ahora - timedelta(days=dias)
    notas = []
    for a in extractor(t, url):
        if not a["fecha"] or a["fecha"] < limite:
            continue
        notas.append({
            "id": lector.id_de(a["enlace"]), "fuente_id": fuente["id"], "titular": lector.limpiar(a["titular"]),
            "bajada": lector.recortar(lector.limpiar(a["bajada"])), "enlace": a["enlace"],
            "fecha": min(a["fecha"], ahora).isoformat(), "via": "pagina",
        })
    if not notas and not any(True for _ in extractor(t, url)):
        raise ValueError("la página no trae avisos reconocibles (¿cambió su formato?)")
    return notas
