"""Clasificación por contenido y descarte de entradas que no son noticias.

Usan la configuración real del repositorio (fuentes.yaml y palabras-clave.yaml),
así que también avisan si un cambio en las reglas daña un caso ya resuelto.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actualizador import config, proceso
from actualizador.descartes import Descartes
from actualizador.filtro import Filtro

CFG = config.cargar()
FILTRO = Filtro(CFG.palabras_clave)
DESCARTES = Descartes(CFG.palabras_clave.get("no_noticias"))


def clasificar(fuente_id: str, titular: str, bajada: str = "", enlace: str = "") -> list[str]:
    fuente = CFG.fuentes_por_id[fuente_id]
    temas, _ = FILTRO.asignar({"titular": titular, "bajada": bajada, "enlace": enlace}, fuente)
    return temas


# ── Colombia solo si la nota trata de Colombia ──────────────────────────────
@pytest.mark.parametrize("titular, esperado", [
    ("PepsiCo recortará 1.000 puestos de trabajo en su reestructuración en Norteamérica", ["internacional"]),
    ("SpaceX planea construir centro de datos y una planta de gas de US$24 mil millones en Texas",
     ["internacional", "tecnologia"]),
    ("Meloni apoya tope al precio de gasolina para frenar gastos antes de elecciones en Italia", ["internacional"]),
    ("El gobierno francés aumenta el salario mínimo a US$1.680 en respuesta a las protestas", ["internacional"]),
    ("Ecuador supera sexta revisión del FMI y espera desembolso de US$390 millones", ["internacional"]),
    ("MinTrabajo abrió diálogo con universidades antes de negociar el mínimo de 2027", ["colombia"]),
])
def test_la_republica_por_contenido(titular, esperado):
    assert clasificar("la-republica", titular) == esperado


def test_la_seccion_internacional_del_medio_decide():
    # Sin palabras de otro país en el titular, pero publicada en la sección internacional
    exterior = clasificar("la-republica", "Revolut prevé multiplicar por cinco sus clientes",
                          enlace="https://www.larepublica.co/globoeconomia/revolut-preve-123")
    assert "colombia" not in exterior and "internacional" in exterior
    # El dólar en Colombia se mueve por un dato de EE. UU.: sigue siendo una nota de Colombia
    local = clasificar("la-republica", "Dólar cerró al alza en $3.269, en medio de la expectativa por la inflación de EE.UU.",
                       enlace="https://www.larepublica.co/finanzas/dolar-cerro-al-alza-456")
    assert local == ["colombia"]
    # En la sección internacional, pero trata de Colombia
    mixta = clasificar("la-republica", "Colombia se consolida entre los mayores exportadores de banano",
                       enlace="https://www.larepublica.co/globoeconomia/colombia-banano-789")
    assert "colombia" in mixta


def test_medio_general_colombiano():
    mundo = "https://www.elheraldo.co/mundo/nota-1"
    # Nota del exterior sin tema económico: no entra
    assert clasificar("el-heraldo", "Choque de dos trenes en Egipto deja al menos cuatro muertos",
                      bajada="El accidente ocurrió en una zona agrícola.", enlace=mundo) == []
    # Nota del exterior con tema económico: Internacional, no Colombia
    assert clasificar("el-heraldo", "El Banco Central de Paraguay comienza los pagos a los ahorristas", enlace=mundo) == ["internacional"]
    # Nota local con tema económico: Colombia
    assert clasificar("el-heraldo", "Empresarios de Barranquilla piden bajar las tarifas de energía",
                      enlace="https://www.elheraldo.co/economia/nota-2") == ["colombia"]


def test_medio_extranjero_necesita_mencionar_colombia():
    assert "colombia" in clasificar("bbc-mundo", "La economía de Colombia crece más de lo esperado")
    assert "colombia" not in clasificar("bbc-mundo", "La economía de España crece más de lo esperado")


# ── Ciberseguridad OT por contenido, en cualquier fuente ────────────────────
@pytest.mark.parametrize("fuente_id, titular", [
    ("techcrunch", "France blames Iran for mass-hacks targeting freezers in grocery stores and blood banks"),
    ("cyberpress", "CISA and FBI Warn Hackers Are Targeting Industrial Refrigeration Systems Worldwide"),
    ("help-net-security", "Hackers abuse refrigeration controllers to send spam and route proxy traffic"),
    ("cybersecurity-news",
     "CISA Warns Two Critical 9.0 Flaws in PowerSYSTEM Center Allow Unauthorized Access and SQL Injection"),
    ("unite-ai", "Nozomi Networks Takes AI Security Cloud to FedRAMP Moderate"),
    ("securityweek", "Siemens patches critical vulnerability in SIMATIC controllers"),
    ("the-hacker-news", "Researchers find Modbus gateways exposed to the internet"),
    ("wsj", "Hackers Crank the Heat on Europe’s Supermarket Freezers to Above 120 Degrees"),
])
def test_ciber_ot_por_contenido(fuente_id, titular):
    assert "ciber-ot" in clasificar(fuente_id, titular)


@pytest.mark.parametrize("fuente_id, titular", [
    ("business-wire", "Dole plc Reports Third Quarter 2026 Financial Results"),
    ("business-wire", "Arm Holdings plc Reports Results for the Second Quarter of the Fiscal Year Ending 2027"),
    ("business-wire", "Siemens Reports Record Orders in Fiscal 2026"),
    ("business-wire", "Honeywell Completes Acquisition of Refrigeration Business"),
    ("techcrunch", "Samsung unveils smart freezers with built-in screens"),
])
def test_no_es_ciber_ot(fuente_id, titular):
    assert "ciber-ot" not in clasificar(fuente_id, titular)


def test_la_fuente_especializada_conserva_su_tematica():
    assert clasificar("cyberpress", "CISA and FBI Warn Hackers Are Targeting Industrial Refrigeration Systems Worldwide") \
        == ["ciber-it", "ciber-ot"]
    assert clasificar("mongabay", "New frog species found in the cloud forest") == ["sostenibilidad"]


# ── Entradas que no son noticias ────────────────────────────────────────────
GN = "https://news.google.com/rss/articles/CBMiabc"


@pytest.mark.parametrize("fuente_id, titular, enlace", [
    ("the-manufacturer", "Apprenticeships - Page 72 of 74 - The Manufacturer", GN),
    ("the-manufacturer", "Jobs - Page 256 of 261", GN),
    ("the-manufacturer", "The Manufacturer, Author at The Manufacturer - Page 1380 of 1382", GN),
    ("yahoo-finance", "Yahoo Finance - Stock Market Live, Quotes, Business & Finance News", GN),
    ("techcrunch", "Startups", "https://techcrunch.com/category/startups/"),
    ("techcrunch", "Latest AI news", "https://techcrunch.com/tag/artificial-intelligence/"),
    ("wired", "Security", "https://www.wired.com/category/security/page/3/"),
    ("wired", "Wired", "https://www.wired.com/"),
])
def test_descarta_lo_que_no_es_noticia(fuente_id, titular, enlace):
    nota = {"titular": titular, "enlace": enlace}
    assert DESCARTES.motivo(nota, CFG.fuentes_por_id[fuente_id]) is not None


@pytest.mark.parametrize("fuente_id, titular, enlace", [
    ("techcrunch", "France blames Iran for mass-hacks targeting freezers",
     "https://techcrunch.com/2026/11/09/france-blames-iran-for-mass-hacks/"),
    ("bbva", "BBVA, mejor banca privada de Colombia, México y Perú", GN),
    ("sustainabilityonline", "SustainabilityOnline: The Sustainability Brief – 9 November 2026",
     "https://sustainabilityonline.net/news/the-sustainability-brief-9-november-2026/"),
    ("the-manufacturer", "UK factories turn the page on a difficult year", GN),
])
def test_no_descarta_noticias_reales(fuente_id, titular, enlace):
    nota = {"titular": titular, "enlace": enlace}
    assert DESCARTES.motivo(nota, CFG.fuentes_por_id[fuente_id]) is None


def test_enriquecer_descarta_y_clasifica():
    crudas = [
        {"id": "1", "fuente_id": "the-manufacturer", "titular": "Skills - Page 333 of 370 - The Manufacturer",
         "bajada": "", "enlace": GN, "fecha": "2026-11-09T10:00:00+00:00", "via": "google_news"},
        {"id": "2", "fuente_id": "la-republica", "titular": "Meloni apoya tope al precio de gasolina en Italia",
         "bajada": "", "enlace": "https://www.larepublica.co/globoeconomia/meloni-1", "fecha": "2026-11-09T10:00:00+00:00", "via": "rss"},
    ]
    notas = proceso.enriquecer(crudas, CFG)
    assert [n["id"] for n in notas] == ["2"]
    assert notas[0]["tematicas"] == ["internacional"] and notas[0]["clasificado_por"] == "contenido"
    # Lo que ya funcionaba sigue igual: fuente fija, tipo y red
    assert notas[0]["grupo"] == "fija" and notas[0]["tipo"] == "prensa" and notas[0]["red"] == "la-republica"
