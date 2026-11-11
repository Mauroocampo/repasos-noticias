"""Lectura de fuentes: RSS/Atom o Google News filtrado por sitio."""
from __future__ import annotations

import calendar
import hashlib
import html
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import requests

from .duplicados import url_canonica

# Algunos sitios (Cloudflare) cortan la conexión si el agente dice "compatible" o trae un enlace.
AGENTE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) repasos-noticias/1.0"
TIEMPO_LIMITE = 25
MAX_BAJADA = 280

_IDIOMAS_GN = {
    "es": ("es-419", "CO", "CO:es-419"),
    "en": ("en-US", "US", "US:en"),
}
_ETIQUETAS = re.compile(r"<[^>]+>")
_ESPACIOS = re.compile(r"\s+")


def limpiar(texto: str | None) -> str:
    if not texto:
        return ""
    t = html.unescape(html.unescape(texto))
    t = _ETIQUETAS.sub(" ", t)
    return _ESPACIOS.sub(" ", t).strip()


def recortar(texto: str, limite: int = MAX_BAJADA) -> str:
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0]
    return corte.rstrip(",.;:") + "…"


def url_google_news(gn: dict, dias: int) -> str:
    hl, gl, ceid = _IDIOMAS_GN.get(gn.get("idioma", "es"), _IDIOMAS_GN["es"])
    q = quote_plus(f"{gn['consulta']} when:{dias}d")
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


def muestra_bajada(fuente: dict) -> bool:
    """False si la fuente pide mostrar solo titular, fuente y enlace (`mostrar_bajada: false`)."""
    return fuente.get("mostrar_bajada", True) is not False


def urls_de(fuente: dict, dias: int) -> list[str]:
    if fuente.get("metodo") == "google_news":
        return [url_google_news(fuente["google_news"], dias)]
    return list(fuente.get("feeds", []))


def descargar(url: str, intentos: int = 2) -> bytes:
    ultimo: Exception | None = None
    for n in range(intentos):
        try:
            r = requests.get(
                url,
                headers={
                    "User-Agent": AGENTE,
                    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
                },
                timeout=TIEMPO_LIMITE,
            )
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            ultimo = e
            if n + 1 < intentos:
                time.sleep(2)
    raise ultimo  # type: ignore[misc]


def _fecha(entrada) -> datetime | None:
    for campo in ("published_parsed", "updated_parsed", "created_parsed"):
        valor = entrada.get(campo)
        if valor:
            try:
                return datetime.fromtimestamp(calendar.timegm(valor), tz=timezone.utc)
            except (OverflowError, ValueError, TypeError):
                continue
    return None


def _titular_google_news(titulo: str, entrada) -> str:
    """Google News agrega ' - Nombre del medio' al final del titular."""
    medio = (entrada.get("source") or {}).get("title")
    if medio and titulo.endswith(f" - {medio}"):
        return titulo[: -len(medio) - 3].strip()
    if " - " in titulo:
        return titulo.rsplit(" - ", 1)[0].strip()
    return titulo


def id_de(enlace: str) -> str:
    return hashlib.sha1(url_canonica(enlace).encode("utf-8")).hexdigest()[:14]


def interpretar(contenido: bytes, fuente: dict, ahora: datetime, dias: int) -> list[dict]:
    """Convierte un feed en notas crudas, dentro de la ventana de días."""
    feed = feedparser.parse(contenido)
    if not feed.entries and not feed.bozo and feed.get("feed", {}).get("title") is not None:
        return []  # feed válido sin notas (p. ej. una búsqueda de Google News sin resultados esta semana)
    if not feed.entries:
        motivo = getattr(feed, "bozo_exception", None)
        raise ValueError(f"el feed no trae notas{f' ({motivo})' if motivo else ''}")

    via = fuente.get("metodo", "rss")
    limite = ahora - timedelta(days=dias)
    exigido = (fuente.get("solo_titulares_con") or "").lower()
    resumen = fuente.get("dividir_resumen") or {}
    notas = []
    for e in feed.entries:
        enlace = (e.get("link") or "").strip()
        titular = limpiar(e.get("title"))
        if not enlace or not titular:
            continue
        if resumen and resumen.get("titulo_contiene", "").lower() in titular.lower():
            notas.extend(_avisos_del_resumen(e, enlace, titular, fuente, resumen, ahora, limite))
            continue
        if via == "google_news":
            titular = _titular_google_news(titular, e)
        if exigido and exigido not in titular.lower():
            continue
        if via == "google_news" or not muestra_bajada(fuente):
            # Google News solo repite el titular; y hay medios que prohíben reproducir su texto
            bajada = ""
        else:
            bajada = limpiar(e.get("summary") or e.get("description"))
            if bajada.lower().startswith(titular.lower()[:40]) and len(bajada) <= len(titular) + 20:
                bajada = ""
            bajada = recortar(bajada)
        fecha = _fecha(e)
        if fecha and fecha > ahora + timedelta(hours=2):
            fecha = ahora  # fechas en el futuro: zona horaria mal declarada
        if fecha and fecha < limite:
            continue
        notas.append({
            "id": id_de(enlace),
            "fuente_id": fuente["id"],
            "titular": titular,
            "bajada": bajada,
            "enlace": enlace,
            "fecha": fecha.isoformat() if fecha else None,
            "via": via,
        })
    return notas


def _avisos_del_resumen(e, enlace: str, titular: str, fuente: dict, resumen: dict,
                        ahora: datetime, limite: datetime) -> list[dict]:
    """Una nota por cada aviso numerado de un resumen (p. ej. "Daily OT Security News")."""
    from .resumenes import dividir  # import local: evita un ciclo de imports

    fecha = _fecha(e) or ahora
    if fecha > ahora + timedelta(hours=2):
        fecha = ahora
    if fecha < limite:
        return []
    contenido = ((e.get("content") or [{}])[0].get("value") or e.get("summary") or "")
    salida = []
    for a in dividir(contenido, enlace, resumen.get("dominios_primarios", [])):
        salida.append({
            # El id sale de la edición y el número: dos avisos pueden citar el mismo enlace primario
            "id": id_de(f"{enlace.split('#')[0]}#aviso-{a['numero']}"),
            "fuente_id": fuente["id"],
            "titular": a["titular"],
            "bajada": recortar(a["bajada"]) if muestra_bajada(fuente) else "",
            "enlace": a["enlace"],
            "fecha": fecha.isoformat(),
            "via": "resumen",
            "resumen": {"edicion": titular, "enlace": enlace, "numero": a["numero"]},
        })
    return salida


def leer_fuente(fuente: dict, ahora: datetime, dias: int,
                conocidas: set[str] | None = None) -> tuple[list[dict], dict]:
    """Lee una fuente (feeds, páginas de sección o página de avisos). Nunca lanza.

    `conocidas`: URLs canónicas ya guardadas, para no volver a leer notas de las páginas.
    """
    notas: list[dict] = []
    errores: list[str] = []
    if fuente.get("metodo") == "avisos_html":
        from . import paginas
        urls = [fuente["pagina_avisos"]]
        try:
            notas.extend(paginas.leer_avisos(fuente, ahora, dias))
        except Exception as e:  # noqa: BLE001
            errores.append(f"{urls[0]}: {type(e).__name__}: {str(e)[:200]}")
    else:
        urls = urls_de(fuente, dias)
    for url in (urls if fuente.get("metodo") != "avisos_html" else []):
        try:
            notas.extend(interpretar(descargar(url), fuente, ahora, dias))
        except Exception as e:  # noqa: BLE001 — una fuente rota no detiene a las demás
            errores.append(f"{url}: {type(e).__name__}: {str(e)[:200]}")
    if fuente.get("paginas"):
        # Secciones cuyo RSS es corto o no existe: se leen sus páginas (errores aparte)
        from . import paginas
        conocidas = set(conocidas or set()) | {url_canonica(n["enlace"]) for n in notas}
        de_paginas, errores_paginas = paginas.leer_listados(fuente, ahora, dias, conocidas)
        notas.extend(de_paginas)
        extra = [f"página: {x}" for x in errores_paginas]
    else:
        extra = []
    respaldo = fuente.get("respaldo_google_news")
    usado_respaldo = False
    if len(errores) == len(urls) and respaldo and fuente.get("metodo") == "rss":
        # El RSS falló por completo (p. ej., bloquea servidores de GitHub): se intenta Google News
        alterna = {**fuente, "metodo": "google_news"}
        url = url_google_news(respaldo, dias)
        try:
            notas.extend(interpretar(descargar(url), alterna, ahora, dias))
            usado_respaldo = True
        except Exception as e:  # noqa: BLE001
            errores.append(f"respaldo Google News: {type(e).__name__}: {str(e)[:200]}")
    vistos, unicas = set(), []
    for n in notas:
        if n["id"] not in vistos:
            vistos.add(n["id"])
            unicas.append(n)
    # Si responden los feeds (o la página de avisos), la fuente respondió; los errores de
    # notas sueltas de las páginas de sección solo la marcan como "en parte"
    ok = len(errores) < len(urls) or usado_respaldo
    errores = errores + extra
    estado = {
        "ok": ok,
        "parcial": bool(errores) and ok,
        "respaldo": usado_respaldo,
        "notas": len(unicas),
        "errores": errores,
        "metodo": fuente.get("metodo"),
        "revisado": ahora.isoformat(),
    }
    return unicas, estado
