"""Filtro de relevancia y agrupación de historias, con la configuración real del repositorio."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actualizador import config, proceso
from actualizador.historias import Agrupador
from actualizador.relevancia import Relevancia

CFG = config.cargar()
RELEVANCIA = Relevancia(CFG.palabras_clave.get("relevancia"))


def categoria(titular: str, bajada: str = "") -> str | None:
    return RELEVANCIA.categoria({"titular": titular, "bajada": bajada})


# ── Relevancia ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("titular, esperada", [
    ("The 9 Best TV Shows to Stream This Month (November 2026)", "entretenimiento"),
    ("King Arthur Baking Sourdough Sidekick Review: Rising to the Occasion", "resenas"),
    ("Apple Watch Ultra 4 Gets $99 Amazon Discounts, Starting at $699.99", "ofertas"),
    ("Así puede hacer un pesebre casero y original con materiales económicos para decorar en Navidad", "manualidades"),
    ("Conozca todos los resultados de las Loterías de Boyacá y Cauca que se jugaron el sábado", "loterias"),
    ("NVDA Investors Have Opportunity to Join NVIDIA Corporation Fraud Investigation with SBS Law", "bufetes"),
    ("Rosen Law Firm Encourages NVIDIA Corporation Investors to Inquire About Securities Class Action Investigation",
     "bufetes"),
    ("Cristiano Ronaldo anuncia su retiro de la selección de Portugal tras el Mundial de Fútbol", "deportes"),
    ("Google Pixel 11, 11 Pro, and 11 Pro XL Sale: Save Up to $350", "ofertas"),
])
def test_oculta_lo_que_no_corresponde(titular, esperada):
    assert categoria(titular) == esperada


@pytest.mark.parametrize("titular", [
    "Apple reports record earnings as iPhone sales grow",
    "Liga BetPlay vende sus derechos de transmisión por $500.000 millones",
    "El Banco Mundial prevé que la economía mundial crecerá 2,8%",
    "Ecuador supera sexta revisión del FMI y espera desembolso de US$390 millones",
    "IMF completes review of Argentina's program",
    "Harvey AI To Assist CBD Lawyers With Research, Drafting And Review",
    "Lo que debe tener en cuenta para aplicar al descuento de 85% en sanción de la Dian",
    "Tobacco company got smoked by leaving secret recipes on a file share",
    "Apple faces class action over Siri privacy",
    "El partido de gobierno pierde la mayoría en el Senado",
    "Fed cuts rates as inflation cools: what to watch next for stocks",
])
def test_no_oculta_noticias_relevantes(titular):
    assert categoria(titular) is None


def test_ocultas_se_marcan_y_no_se_borran():
    crudas = [{"id": "x", "fuente_id": "wired", "titular": "The 9 Best TV Shows to Stream This Month",
               "bajada": "", "enlace": "https://www.wired.com/story/best-tv-shows/", "fecha": "2026-11-09T10:00:00+00:00",
               "via": "rss"}]
    notas = proceso.enriquecer(crudas, CFG)
    assert len(notas) == 1 and notas[0]["oculta"] == "entretenimiento"


# ── Historias ───────────────────────────────────────────────────────────────
def nota(i, fuente, titular, fecha, grupo="general", tipo="prensa", bajada=""):
    return {"id": str(i), "fuente_id": fuente, "fuente": fuente, "titular": titular, "bajada": bajada,
            "enlace": f"https://{fuente}.example/{i}", "fecha": fecha, "via": "rss", "grupo": grupo,
            "tipo": tipo, "tematicas": ["tecnologia"], "tambien_en": [], "oculta": None}


RELLENO = [  # notas variadas: el agrupador mide frecuencias sobre el conjunto
    nota(100 + k, f"relleno{k % 7}", t, f"2026-11-0{5 + k % 4}T0{k % 9}:00:00+00:00")
    for k, t in enumerate([
        "Microsoft lanza nuevas herramientas para desarrolladores en la nube",
        "Ecopetrol reporta aumento de producción en el tercer trimestre",
        "Samsung presenta su nuevo teléfono plegable en Seúl",
        "Banco de la República mantiene estable la tasa de interés",
        "OpenAI anuncia un nuevo modelo de lenguaje para empresas",
        "Amazon abre un centro logístico en Bogotá",
        "Siemens firma acuerdo con Ecopetrol para digitalizar refinerías",
        "Trump anuncia nuevos aranceles al acero europeo",
        "Trump se reúne con líderes del G7 en Canadá",
        "El dólar cae frente al peso colombiano",
        "Intel recorta su previsión de ingresos para 2027",
        "Tesla abre una fábrica nueva en México",
    ])
]

NVIDIA = [
    nota(1, "bbc-mundo", "Nvidia abre una investigación sobre la relación de Jensen Huang con una presunta espía china",
         "2026-11-08T10:00:00+00:00", grupo="fija"),
    nota(2, "cnbc", "Jensen Huang's affair with alleged Chinese spy complicates Nvidia's China problem",
         "2026-11-08T14:00:00+00:00"),
    nota(3, "techcrunch", "Nvidia will investigate CEO Jensen Huang's relationship with possible Chinese spy",
         "2026-11-08T16:00:00+00:00", grupo="especializada"),
    nota(4, "la-republica", "¿Aguantará Jensen Huang como CEO de Nvidia tras el escándalo del espionaje?",
         "2026-11-09T09:00:00+00:00", grupo="fija"),
    nota(5, "wsj", "Jensen Huang's Spy Scandal Lays Bare Nvidia's Governance Vacuum", "2026-11-09T20:00:00+00:00"),
]


def agrupar(notas):
    return Agrupador(CFG.palabras_clave.get("historias")).agrupar(notas, proceso.prioridad)


def test_agrupa_la_misma_historia_en_varios_idiomas():
    salida = agrupar(NVIDIA + RELLENO)
    principal = next(n for n in salida if n.get("historia_notas"))
    assert principal["historia_notas"] == 5
    # Principal: fuente fija, la más antigua de las fijas
    assert principal["fuente_id"] == "bbc-mundo"
    assert {t["fuente_id"] for t in principal["tambien_en"]} == {"cnbc", "techcrunch", "la-republica", "wsj"}
    assert all(t["titular"] for t in principal["tambien_en"])


def test_no_une_notas_de_otra_historia_con_la_misma_empresa():
    resultados = nota(9, "cnbc", "Nvidia reports record quarterly revenue from data center chips",
                      "2026-11-08T12:00:00+00:00")
    salida = agrupar(NVIDIA + RELLENO + [resultados])
    assert any(n["id"] == "9" and not n.get("historia_notas") for n in salida)


def test_no_une_por_entidades_generales():
    trump = [nota(20, "wsj", "Trump anuncia nuevos aranceles a China", "2026-11-08T10:00:00+00:00"),
             nota(21, "cnbc", "Trump se reúne con el presidente de Brasil", "2026-11-08T11:00:00+00:00")]
    salida = agrupar(trump + RELLENO)
    assert not any(n.get("historia_notas") for n in salida)


def test_fuera_de_la_ventana_no_se_une():
    lejos = nota(30, "wsj", "Jensen Huang's Chinese spy affair: Nvidia board finishes investigation",
                 "2026-11-14T10:00:00+00:00")
    salida = agrupar(NVIDIA[:2] + RELLENO + [lejos])
    assert any(n["id"] == "30" and not n.get("historia_notas") for n in salida)


def test_serie_de_una_sola_fuente_no_es_historia():
    serie = [nota(40 + k, "thehackerwire", f"CVE-2026-{1000 + k}: Critical Auth Bypass in Product{k}",
                  f"2026-11-08T1{k}:00:00+00:00") for k in range(4)]
    salida = agrupar(serie + RELLENO)
    assert not any(n.get("historia_notas") for n in salida)


def test_prioridad_fija_luego_primaria():
    otras = [nota(50, "wsj", "x", "2026-11-08T10:00:00+00:00"),
             nota(51, "cisa", "x", "2026-11-08T12:00:00+00:00", grupo="especializada", tipo="oficial"),
             nota(52, "portafolio", "x", "2026-11-08T13:00:00+00:00", grupo="fija")]
    assert [n["id"] for n in sorted(otras, key=proceso.prioridad)] == ["52", "51", "50"]
