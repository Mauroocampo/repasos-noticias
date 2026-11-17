"""Dane como fuente primaria: calendario de publicaciones y boletines oficiales.

En fuentes.yaml (`metodo: dane`):
  calendario_rss: RSS del calendario de difusión (las publicaciones del día)
  operaciones: [{nombre, calendario, sigla, pagina}]
      nombre      cómo se muestra ("Producto Interno Bruto (PIB)")
      calendario  texto con el que aparece en el calendario
      sigla       carpeta de sus archivos (/files/operaciones/PIB/…)
      pagina      página técnica donde están el boletín y el comunicado (PDF)

  - Calendario: una nota por cada publicación del día de esas operaciones.
  - Boletines y comunicados: cuando aparece un PDF nuevo (boletín técnico `bol-…` o
    comunicado de prensa `cp-…`), una nota con enlace al PDF. Su fecha es la de
    publicación del archivo (Last-Modified).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import feedparser
import requests

from . import lector
from .filtro import normalizar

BOGOTA = ZoneInfo("America/Bogota")
MESES = {"ene": "enero", "feb": "febrero", "mar": "marzo", "abr": "abril", "may": "mayo", "jun": "junio",
         "jul": "julio", "ago": "agosto", "sep": "septiembre", "oct": "octubre", "nov": "noviembre", "dic": "diciembre"}
MESES_EN = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
            "oct": 10, "nov": 11, "dec": 12}
TIPOS_PDF = {"bol": "Boletín técnico", "cp": "Comunicado de prensa"}


def _hora(d: datetime) -> str:
    h = d.hour % 12 or 12
    return f"{h}:{d.minute:02d} {'a. m.' if d.hour < 12 else 'p. m.'}"


def _operacion_del_calendario(titulo: str, operaciones: list[dict]) -> dict | None:
    t = normalizar(titulo)
    for op in operaciones:
        if normalizar(op["calendario"]) in t or f"({op['sigla'].lower()})" in t:
            return op
    return None


def _fecha_del_calendario(titulo: str) -> datetime | None:
    """"17 Nov 2026 10:00 : Producto Interno Bruto (PIB)" → fecha en hora de Colombia."""
    m = re.match(r"\s*(\d{1,2}) (\w{3})\w* (\d{4}) (\d{1,2}):(\d{2})", titulo)
    if not m or m.group(2).lower() not in MESES_EN:
        return None
    dia, mes, anio, h, mi = int(m.group(1)), MESES_EN[m.group(2).lower()], int(m.group(3)), int(m.group(4)), int(m.group(5))
    return datetime(anio, mes, dia, h, mi, tzinfo=BOGOTA)


def calendario(fuente: dict, ahora: datetime, dias: int) -> list[dict]:
    feed = feedparser.parse(lector.descargar(fuente["calendario_rss"]))
    limite = ahora - timedelta(days=dias)
    notas = []
    for e in feed.entries:
        titulo = lector.limpiar(e.get("title"))
        op = _operacion_del_calendario(titulo, fuente["operaciones"])
        fecha = _fecha_del_calendario(titulo)
        if not op or not fecha or fecha < limite:
            continue
        enlace = (e.get("link") or fuente["sitio"]).strip()
        notas.append({
            "id": lector.id_de(enlace), "fuente_id": fuente["id"],
            "titular": f"Calendario del Dane: {op['nombre']}, {fecha.day} de {list(MESES.values())[fecha.month - 1]} a las {_hora(fecha)}",
            "bajada": "Publicación programada en el calendario de difusión del Dane.",
            "enlace": enlace, "fecha": min(fecha, ahora + timedelta(days=2)).astimezone(timezone.utc).isoformat(),
            "via": "calendario",
        })
    return notas


def _periodo(nombre_archivo: str) -> str:
    """"bol-PIB-IIItrim2026.pdf" → "III trimestre 2026"; "bol-ISE-sep2026.pdf" → "septiembre 2026"."""
    m = re.search(r"-([IVX]+)trim(\d{4})", nombre_archivo, re.I)
    if m:
        return f"{m.group(1).upper()} trimestre {m.group(2)}"
    m = re.search(r"-([a-z]{3})(\d{4})", nombre_archivo, re.I)
    if m and m.group(1).lower() in MESES:
        return f"{MESES[m.group(1).lower()]} {m.group(2)}"
    return ""


def boletines(fuente: dict, ahora: datetime, dias: int) -> tuple[list[dict], list[str]]:
    limite = ahora - timedelta(days=dias)
    notas, errores = [], []
    for op in fuente["operaciones"]:
        try:
            t = lector.descargar(op["pagina"]).decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            errores.append(f"{op['sigla']}: {type(e).__name__}: {str(e)[:120]}")
            continue
        patron = rf'href="([^"]*/files/operaciones/{re.escape(op["sigla"])}/[^"]*?/?((bol|cp)-[^"/]+\.pdf))"'
        vistos = set()
        for ruta, archivo, tipo in re.findall(patron, t, re.I):
            url = urljoin(op["pagina"], ruta)
            if url in vistos:
                continue
            vistos.add(url)
            try:
                r = requests.head(url, headers={"User-Agent": lector.AGENTE}, timeout=lector.TIEMPO_LIMITE,
                                  allow_redirects=True)
                if r.status_code >= 400:
                    continue
                fecha = datetime.strptime(r.headers["Last-Modified"], "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
            except Exception:  # noqa: BLE001 — sin fecha no se puede saber si es nuevo
                continue
            if fecha < limite:
                continue
            periodo = _periodo(archivo)
            notas.append({
                "id": lector.id_de(url), "fuente_id": fuente["id"],
                "titular": f"{TIPOS_PDF[tipo.lower()]}: {op['nombre']}" + (f", {periodo}" if periodo else ""),
                "bajada": f"Publicación oficial del Dane ({'PDF del boletín técnico' if tipo.lower() == 'bol' else 'PDF del comunicado de prensa'}).",
                "enlace": url, "fecha": min(fecha, ahora).isoformat(), "via": "pagina",
            })
    return notas, errores


def leer(fuente: dict, ahora: datetime, dias: int) -> tuple[list[dict], list[str], int]:
    """(notas, errores, cuántas lecturas se intentaron) del calendario y los boletines."""
    notas, errores = [], []
    try:
        notas += calendario(fuente, ahora, dias)
    except Exception as e:  # noqa: BLE001
        errores.append(f"calendario: {type(e).__name__}: {str(e)[:150]}")
    de_boletines, err = boletines(fuente, ahora, dias)
    notas += de_boletines
    errores += err
    return notas, errores, 1 + len(fuente["operaciones"])
