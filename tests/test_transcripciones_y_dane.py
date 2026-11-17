"""Transcripciones de resultados y Dane como fuente primaria."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actualizador import config, dane, proceso
from actualizador.relevancia import Relevancia

CFG = config.cargar()
AHORA = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)


def cruda(fid, titular, enlace, fecha="2026-11-17T12:00:00+00:00", bajada=""):
    return {"id": enlace[-20:], "fuente_id": fid, "titular": titular, "bajada": bajada, "enlace": enlace,
            "fecha": fecha, "via": "rss"}


# ── 6. Transcripciones ──────────────────────────────────────────────────────
def test_transcripcion_extranjera_oculta_y_con_tipo():
    n = proceso.enriquecer([cruda("investing-com", "Earnings call transcript: JD.com posts Q3 2026 revenue beat as shares slip",
                                  "https://www.investing.com/news/transcripts/jd-1")], CFG, AHORA)[0]
    assert n["tipo"] == "transcripcion" and n["oculta"] == "transcripciones"
    assert CFG.tipos["transcripcion"] == "Transcripción de resultados"


def test_transcripcion_de_empresa_de_la_lista_se_muestra():
    n = proceso.enriquecer([cruda("investing-com", "Earnings call transcript: Siemens beats Q4 estimates on automation demand",
                                  "https://www.investing.com/news/transcripts/siemens-1")], CFG, AHORA)[0]
    assert n["tipo"] == "transcripcion" and n["oculta"] is None


def test_otras_notas_de_investing_no_cambian():
    r = Relevancia(CFG.palabras_clave["relevancia"])
    assert r.categoria({"titular": "Wall Street falls as investors await Nvidia earnings", "bajada": ""}) is None


# ── 7. Dane ─────────────────────────────────────────────────────────────────
def test_dane_es_fija_oficial_en_colombia():
    f = CFG.fuentes_por_id["dane"]
    assert f["grupo"] == "fija" and f["tipo"] == "oficial" and "colombia" in f["tematicas"]
    assert {op["sigla"] for op in f["operaciones"]} >= {"PIB", "IPC", "GEIH", "EMMET"}


def test_calendario_del_dane(monkeypatch):
    rss = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Calendario</title>
<item><title>17 Nov 2026 10:00 : Producto Interno Bruto (PIB)</title><link>https://www.dane.gov.co/cal/pib</link></item>
<item><title>17 Nov 2026 14:00 : Financiaci\xc3\xb3n de Vivienda (FIVI)</title><link>https://www.dane.gov.co/cal/fivi</link></item>
</channel></rss>"""
    monkeypatch.setattr(dane.lector, "descargar", lambda url, **k: rss)
    notas = dane.calendario(CFG.fuentes_por_id["dane"], AHORA, 7)
    assert [n["titular"] for n in notas] == ["Calendario del Dane: Producto Interno Bruto (PIB), 17 de noviembre a las 10:00 a. m."]
    assert notas[0]["fecha"].startswith("2026-11-17T15:00")  # 10:00 a. m. en Colombia = 15:00 UTC


def test_periodo_de_los_boletines():
    assert dane._periodo("bol-PIB-IIItrim2026.pdf") == "III trimestre 2026"
    assert dane._periodo("bol-EMMET-sep2026.pdf") == "septiembre 2026"


def test_boletin_del_dane_es_la_principal_de_la_historia_del_pib():
    notas = proceso.enriquecer([
        cruda("dane", "Boletín técnico: Producto Interno Bruto (PIB), III trimestre 2026",
              "https://www.dane.gov.co/files/operaciones/PIB/bol-PIB-IIItrim2026.pdf", "2026-11-17T15:00:00+00:00",
              "Publicación oficial del Dane (PDF del boletín técnico)."),
        cruda("portafolio", "Economía colombiana creció 0,5% en el tercer trimestre del 2026",
              "https://www.portafolio.co/economia/pib-tercer-trimestre-506200", "2026-11-17T15:30:00+00:00"),
        cruda("la-republica", "La economía creció 0,5% en el tercer trimestre jalonada por minas y canteras",
              "https://www.larepublica.co/economia/pib-tercer-trimestre-4530100", "2026-11-17T16:00:00+00:00"),
    ], CFG, AHORA)
    salida = proceso.agrupar(notas, CFG)
    principal = next(n for n in salida if n.get("historia_notas"))
    assert principal["fuente_id"] == "dane" and principal["historia_notas"] == 3
