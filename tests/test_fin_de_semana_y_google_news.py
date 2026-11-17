"""Resumen de OT de fin de semana y enlaces de Google News."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actualizador import config, enlaces_gn, lector, marcas, proceso

CFG = config.cargar()
AHORA = datetime(2026, 11, 17, 13, 0, tzinfo=timezone.utc)

# Edición de domingo con el formato real de Viakoo
DOMINGO = """
<p>Daily OT Security News: November 16, 2026</p>
<h2>1. A hotel pool alarm went to email, and the email never arrived</h2>
<h3>Source and event dates</h3><p>Source date: November 14, 2026. Event date: November 12, 2026.</p>
<h3>News briefing</h3>
<p>Fifteen guests at the hotel suffered respiratory irritation after using the pool, according to WDR.</p>
<p>The chlorine dosing alarm was sent by email through Microsoft 365, which was down on November 12, so nobody saw it.</p>
<h2>2. A drone maker’s update channel is the suspected path into QBase</h2>
<p>Quantum Systems, a German defense company that builds reconnaissance drones, confirmed a cybersecurity incident affecting its QBase software.</p>
<h2>3. Ransomware set an October record, and manufacturing ranked third</h2>
<p>Check Point Research recorded 1,063 ransomware attacks in October, a record and a 35% increase over the same month last year.</p>
<h2>4. Offshore energy told to engineer connectivity resilience, not bolt it on</h2>
<p>Marlink published an analysis arguing that network resilience is a critical requirement for offshore energy operations.</p>
"""
URL = "https://www.viakoo.com/blog/daily-ot-security-news-november-16-2026/"
FEED = f"""<?xml version="1.0"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>Viakoo</title>
<item><title>Daily OT Security News: November 16, 2026</title><link>{URL}</link>
<pubDate>Sun, 16 Nov 2026 12:00:00 GMT</pubDate><content:encoded><![CDATA[{DOMINGO}]]></content:encoded></item>
</channel></rss>""".encode()


# ── 1. Fin de semana ────────────────────────────────────────────────────────
def test_edicion_de_domingo_se_divide_en_avisos_de_ot():
    notas = proceso.enriquecer(lector.interpretar(FEED, CFG.fuentes_por_id["viakoo"], AHORA, 7), CFG, AHORA)
    assert len(notas) == 4
    assert all("ciber-ot" in n["tematicas"] and n["marcas"] == ["proveedor-viakoo"] for n in notas)
    assert len({n["id"] for n in notas}) == 4


def test_la_busqueda_encuentra_los_avisos_por_lo_que_dicen():
    notas = lector.interpretar(FEED, CFG.fuentes_por_id["viakoo"], AHORA, 7)
    texto = {n["titular"][:20]: f"{n['titular']} {n['bajada']} {n['terminos']}".lower() for n in notas}
    assert "microsoft 365" in texto["A hotel pool alarm w"] and "chlorine" in texto["A hotel pool alarm w"]
    assert "quantum systems" in texto["A drone maker’s upda"]
    assert "check point" in texto["Ransomware set an Oc"] and "1,063" in texto["Ransomware set an Oc"]
    assert "marlink" in texto["Offshore energy told"]


def test_edicion_sin_dividir_no_se_muestra():
    vieja = {"id": "x", "fuente_id": "viakoo", "titular": "Daily OT Security News: November 10, 2026",
             "bajada": "", "enlace": "https://www.viakoo.com/blog/daily-ot-security-news-november-10-2026/",
             "fecha": "2026-11-16T10:00:00+00:00", "via": "rss"}
    assert proceso.enriquecer([vieja], CFG, AHORA) == []


# ── 2. Google News ──────────────────────────────────────────────────────────
GN = "https://news.google.com/rss/articles/CBMiqAFBVV95cUxQRzJh"


def test_indice_con_titulares():
    i = enlaces_gn.Indice([
        ("https://www.businesswire.com/news/home/20261116893089/en/elf-Brands", "e.l.f. Brands Expands Impact Through Glow For Glory"),
        ("https://www.businesswire.com/news/home/2/en/otra", "Omdia: Middle East Smartphone Shipments Fall 29%"),
    ])
    assert i.buscar("e.l.f. Brands Expands Impact Through Glow For Glory").endswith("elf-Brands")
    assert i.buscar("Una nota que no está en el mapa del sitio") is None


def test_indice_por_direccion_es_estricto():
    i = enlaces_gn.Indice([
        ("https://www.bbva.com/es/salud-financiera/inflacion-estas-son-las-causas-y-herramientas-para-controlarla/", ""),
        ("https://www.bbva.com/es/economia-y-finanzas/finanzas/", ""),
    ])
    assert "inflacion-estas-son" in i.buscar("Inflación: estas son las causas y herramientas para controlarla")
    # Una dirección corta y genérica no basta para emparejar
    assert i.buscar("Entender mejor tus finanzas para avanzar a tu ritmo") is None


def test_resolver_cambia_el_enlace_y_usa_el_registro(monkeypatch):
    monkeypatch.setattr(enlaces_gn, "entradas_del_mapa", lambda url: [
        ("https://www.businesswire.com/news/home/1/en/Acme", "Acme Launches New Industrial Platform for Plants")])
    notas = [{"id": "a", "fuente_id": "business-wire", "titular": "Acme Launches New Industrial Platform for Plants",
              "enlace": GN, "fecha": "2026-11-17T10:00:00+00:00"},
             {"id": "b", "fuente_id": "business-wire", "titular": "Otra nota sin rastro en el mapa",
              "enlace": GN + "XYZ", "fecha": "2026-11-17T10:00:00+00:00"}]
    cache = {}
    salida, conteo = enlaces_gn.resolver(notas, CFG.fuentes_por_id, cache, AHORA)
    assert salida[0]["enlace"] == "https://www.businesswire.com/news/home/1/en/Acme"
    assert salida[0]["enlace_google_news"] == GN and salida[0]["id"] == "a"
    assert salida[1]["enlace"].startswith("https://news.google.com/")
    assert conteo["business-wire"] == {"resueltas": 1, "sin_resolver": 1}
    # La segunda vez se usa el registro, sin volver a leer el mapa
    monkeypatch.setattr(enlaces_gn, "entradas_del_mapa", lambda url: (_ for _ in ()).throw(AssertionError("no debía leer el mapa")))
    otra_vez, _ = enlaces_gn.resolver(notas[:1], CFG.fuentes_por_id, cache, AHORA)
    assert otra_vez[0]["enlace"].endswith("/Acme")


def test_sin_resolver_lleva_marca():
    f = CFG.fuentes_por_id["yahoo-finance"]
    assert "via-google-news" in marcas.marcar({"titular": "x", "bajada": "", "enlace": GN}, f)
    assert "via-google-news" not in marcas.marcar({"titular": "x", "bajada": "", "enlace": "https://finance.yahoo.com/news/x"}, f)
    assert CFG.marcas["via-google-news"]["texto"] == "Enlace vía Google News"
