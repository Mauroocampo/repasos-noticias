"""LNS Research, hora de Colombia, aviso automático y bajada por fuente."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actualizador import config, lector, marcas, proceso
from actualizador.generador import Generador

CFG = config.cargar()
AHORA = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


def cruda(fid, titular, fecha, bajada="", enlace=None):
    return {"id": f"{fid}-{fecha}", "fuente_id": fid, "titular": titular, "bajada": bajada,
            "enlace": enlace or f"https://{fid}.example/{fecha}", "fecha": fecha, "via": "rss"}


# ── 5. LNS Research ─────────────────────────────────────────────────────────
def test_lns_es_fija_de_analistas_industriales():
    lns = CFG.fuentes_por_id["lns-research"]
    assert lns["grupo"] == "fija" and lns["tipo"] == "analistas-industriales"
    assert CFG.tipos["analistas-industriales"] == "Firma de analistas industriales"
    assert proceso.ventana_de(lns, CFG) > CFG.ventana_dias


def test_lns_tematica_por_contenido():
    notas = proceso.enriquecer([
        cruda("lns-research", "Survey: manufacturers cut carbon emissions with smart factory programs", "2026-11-10T12:00:00+00:00"),
        cruda("lns-research", "What is Asset Intelligence: Category Definition", "2026-11-10T13:00:00+00:00"),
    ], CFG, AHORA)
    assert notas[0]["tematicas"] == ["manufactura", "sostenibilidad"]
    assert notas[1]["tematicas"] == ["manufactura"]  # sin pistas en el contenido: su temática por defecto


def test_lns_marca_estudio_patrocinado():
    nota = {"titular": "Industrial AI study", "bajada": "This research was sponsored by Acme Software."}
    assert marcas.marcar(nota, CFG.fuentes_por_id["lns-research"]) == ["analistas", "patrocinado"]
    nota = {"titular": "Commissioned research: the state of MES", "bajada": ""}
    assert "patrocinado" in marcas.marcar(nota, CFG.fuentes_por_id["lns-research"])


def test_lns_vieja_no_va_al_flujo_pero_si_a_destacadas():
    vieja = cruda("lns-research", "Survey Snippets #7: The Perception vs Reality Gap in Industrial AI",
                  "2026-09-30T14:00:00+00:00")
    nueva = cruda("portafolio", "Ecopetrol anuncia nuevas inversiones en Colombia", "2026-11-10T14:00:00+00:00")
    # combinar respeta la ventana de cada fuente
    guardadas = proceso.combinar([], [vieja, nueva], AHORA, CFG.ventana_dias,
                                 {f["id"]: proceso.ventana_de(f, CFG) for f in CFG.fuentes})
    assert {n["fuente_id"] for n in guardadas} == {"lns-research", "portafolio"}
    notas = proceso.enriquecer(guardadas, CFG, AHORA)
    lns = next(n for n in notas if n["fuente_id"] == "lns-research")
    assert lns["fuera_de_ventana"] is True
    # Y una nota de 30 días de otra fuente sí se descarta
    otra = cruda("bbc-mundo", "Nota vieja de BBC", "2026-10-01T14:00:00+00:00")
    assert proceso.combinar([], [otra], AHORA, CFG.ventana_dias, {"bbc-mundo": 7}) == []


# ── 6. Hora de Colombia ─────────────────────────────────────────────────────
def test_horas_en_hora_de_colombia():
    g = Generador(CFG)
    g.textos_ocultas = {}
    v = g._vista({**cruda("bbc-mundo", "x", "2026-11-11T04:30:00+00:00"), "tematicas": ["internacional"],
                  "tipo": "prensa", "marcas": []})
    # 4:30 UTC = 11:30 p. m. del día anterior en Bogotá
    assert v["hora"] == "11:30 p. m." and v["local"].day == 10


# ── 8. Derechos de los medios ───────────────────────────────────────────────
RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Titular de prueba sobre la economia</title><link>https://m.co/1</link>
<description>Bajada con mucho texto del medio que no se puede reproducir.</description>
<pubDate>Wed, 11 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>"""


def test_portafolio_y_pies_que_prohiben_solo_titular():
    for fid in ("portafolio", "el-heraldo", "wired"):
        assert lector.muestra_bajada(CFG.fuentes_por_id[fid]) is False, fid
    assert lector.muestra_bajada(CFG.fuentes_por_id["la-republica"]) is True


def test_sin_bajada_no_se_lee_ni_se_guarda():
    notas = lector.interpretar(RSS, CFG.fuentes_por_id["portafolio"], AHORA, 7)
    assert notas[0]["bajada"] == ""
    notas = lector.interpretar(RSS, CFG.fuentes_por_id["la-republica"], AHORA, 7)
    assert notas[0]["bajada"].startswith("Bajada con mucho texto")
    # Lo guardado antes también se limpia
    guardada = cruda("portafolio", "Titular", "2026-11-10T10:00:00+00:00", bajada="Texto del medio")
    assert proceso.sin_bajadas_restringidas([guardada], CFG)[0]["bajada"] == ""
    assert proceso.enriquecer([{**guardada, "titular": "Ecopetrol invierte en Colombia"}], CFG, AHORA)[0]["bajada"] == ""


def test_google_news_no_trae_bajada():
    gn = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Gran anuncio de la empresa sobre su nueva planta - El Universal</title>
<link>https://news.google.com/rss/articles/1</link><description>&lt;a href="x"&gt;Gran anuncio de la empresa&lt;/a&gt; El Universal y otro texto largo que no es bajada</description>
<pubDate>Wed, 11 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
    notas = lector.interpretar(gn, {"id": "u", "metodo": "google_news"}, AHORA, 7)
    assert notas[0]["bajada"] == ""
