import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actualizador import config, duplicados, lector, marcas
from actualizador.filtro import Filtro

CLAVES = {
    "colombia": {"contexto": ["colombia", "colombian*"], "incluir": ["desempleo", "economi*"], "excluir": ["futbol"]},
    "tecnologia": {"incluir": ["ia", "inteligencia artificial", "chip*"]},
    "internacional": {"incluir": ["s&p 500", "wall street"]},
}


def nota(fid, titular, enlace, fecha="2026-11-05T10:00:00+00:00", via="rss", bajada=""):
    return {"id": lector.id_de(enlace), "fuente_id": fid, "fuente": fid, "titular": titular,
            "bajada": bajada, "enlace": enlace, "fecha": fecha, "via": via, "tematicas": ["tecnologia"]}


# ── filtro ───────────────────────────────────────────────────────────────────
def test_filtro_sin_tildes_y_prefijo():
    f = Filtro(CLAVES)
    assert f.coincide("colombia", "La ECONOMÍA crece", "CO")
    assert f.coincide("colombia", "Economista advierte", "CO")  # economi*


def test_filtro_palabra_completa():
    f = Filtro(CLAVES)
    assert not f.coincide("tecnologia", "Crisis en Asia")       # "ia" no dentro de "Asia"
    assert f.coincide("tecnologia", "La IA llega a la banca")
    assert f.coincide("internacional", "El S&P 500 cae 2 %")


def test_filtro_excluir_y_contexto():
    f = Filtro(CLAVES)
    assert not f.coincide("colombia", "Desempleo y fútbol", "CO")
    assert not f.coincide("colombia", "El desempleo en España baja", None)   # medio extranjero sin mención
    assert f.coincide("colombia", "El desempleo en Colombia baja", None)


def test_asignar_fija_mas_filtro():
    f = Filtro(CLAVES)
    fuente = {"id": "x", "tematicas": ["colombia"], "tematicas_por_filtro": ["tecnologia"], "pais": "CO"}
    temas, como = f.asignar({"titular": "Bancos usan IA", "bajada": ""}, fuente)
    assert temas == ["colombia", "tecnologia"] and como == "contenido"
    assert f.asignar({"titular": "Sube el recaudo", "bajada": ""}, fuente) == (["colombia"], "fuente")
    general = {"id": "y", "tematicas_por_filtro": ["tecnologia"]}
    assert f.asignar({"titular": "Receta de arepas", "bajada": ""}, general)[0] == []


# ── duplicados ───────────────────────────────────────────────────────────────
def test_url_canonica():
    a = duplicados.url_canonica("http://www.ejemplo.com/nota/?utm_source=x&id=3#arriba")
    b = duplicados.url_canonica("https://ejemplo.com/nota?id=3")
    assert a == b


def test_duplicados_techday():
    t = "Acme launches new AI-powered security platform for enterprises"
    n1 = nota("it-brief", t, "https://itbrief.com.au/story/acme", "2026-11-05T08:00:00+00:00")
    n2 = nota("securitybrief", t + ".", "https://securitybrief.com.au/story/acme", "2026-11-05T09:00:00+00:00")
    n3 = nota("channellife", "Something completely different happened today here", "https://channellife.com.au/story/x")
    r = duplicados.eliminar([n2, n1, n3])
    assert len(r) == 2
    principal = next(n for n in r if n["fuente_id"] == "it-brief")    # se queda la más antigua
    assert [o["fuente_id"] for o in principal["tambien_en"]] == ["securitybrief"]


def test_duplicados_prefiere_rss_sobre_google_news():
    t = "Gobierno anuncia nueva reforma tributaria para el próximo año"
    gn = nota("a", t, "https://news.google.com/rss/articles/abc", "2026-11-05T07:00:00+00:00", via="google_news")
    rss = nota("b", t, "https://medio.co/reforma", "2026-11-05T09:00:00+00:00", bajada="Detalles")
    r = duplicados.eliminar([gn, rss])
    assert len(r) == 1 and r[0]["fuente_id"] == "b"


# ── marcas ───────────────────────────────────────────────────────────────────
def test_marcas():
    f = {"marcas": ["analistas"]}
    assert marcas.marcar({"titular": "Study sponsored by Acme", "bajada": ""}, f) == ["analistas", "patrocinado"]
    assert marcas.marcar({"titular": "Normal", "bajada": ""}, {}) == []


# ── lector ───────────────────────────────────────────────────────────────────
RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Nota nueva &amp; buena</title><link>https://m.co/1</link>
<description>&lt;p&gt;Bajada con &lt;b&gt;HTML&lt;/b&gt;&lt;/p&gt;</description>
<pubDate>Thu, 05 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Nota vieja</title><link>https://m.co/2</link><pubDate>Thu, 01 Jan 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_interpretar_rss():
    ahora = datetime(2026, 11, 6, tzinfo=timezone.utc)
    notas = lector.interpretar(RSS, {"id": "m", "metodo": "rss"}, ahora, 7)
    assert len(notas) == 1
    assert notas[0]["titular"] == "Nota nueva & buena"
    assert notas[0]["bajada"] == "Bajada con HTML"


def test_titular_google_news():
    gn = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Gran anuncio - El Universal</title><link>https://news.google.com/rss/articles/1</link>
<pubDate>Thu, 05 Nov 2026 10:00:00 GMT</pubDate><source url="https://eluniversal.com.co">El Universal</source></item>
</channel></rss>"""
    ahora = datetime(2026, 11, 6, tzinfo=timezone.utc)
    notas = lector.interpretar(gn, {"id": "u", "metodo": "google_news"}, ahora, 7)
    assert notas[0]["titular"] == "Gran anuncio" and notas[0]["bajada"] == ""


def test_respaldo_google_news_si_falla_rss(monkeypatch):
    gn = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Aviso ICS - CISA</title><link>https://news.google.com/rss/articles/9</link>
<pubDate>Thu, 05 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>"""

    def falso(url, intentos=2):
        if "news.google.com" in url:
            return gn
        raise ConnectionError("403")

    monkeypatch.setattr(lector, "descargar", falso)
    fuente = {"id": "cisa", "metodo": "rss", "feeds": ["https://cisa.gov/x.xml"],
              "respaldo_google_news": {"consulta": "site:cisa.gov", "idioma": "en"}}
    notas, est = lector.leer_fuente(fuente, datetime(2026, 11, 6, tzinfo=timezone.utc), 7)
    assert est["ok"] and est["respaldo"] and len(notas) == 1 and notas[0]["via"] == "google_news"


def test_fuente_caida_no_lanza(monkeypatch):
    monkeypatch.setattr(lector, "descargar", lambda url, intentos=2: (_ for _ in ()).throw(ConnectionError("caída")))
    notas, est = lector.leer_fuente({"id": "x", "metodo": "rss", "feeds": ["https://x"]},
                                    datetime(2026, 11, 6, tzinfo=timezone.utc), 7)
    assert notas == [] and not est["ok"] and est["errores"]


# ── configuración real del repositorio ──────────────────────────────────────
def test_configuracion_del_repositorio_es_valida():
    cfg = config.cargar()
    assert len(cfg.fuentes_activas()) > 50
    assert cfg.ventana_dias == 7
