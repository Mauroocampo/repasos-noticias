"""Ajustes del double check del 17 de noviembre: falsos positivos y grupos mezclados."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actualizador import config, lector, proceso
from actualizador.relevancia import Relevancia

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_historias_casos import RELLENO, grupos, juntos, nota  # noqa: E402

CFG = config.cargar()
R = Relevancia(CFG.palabras_clave["relevancia"])


@pytest.mark.parametrize("titular", [
    '"Traigan a Jensen de vuelta": la campaña de los millonarios tecnológicos a favor del regreso de Huang',
    "Renunció Jaime Uribe, gerente del Fondo Milagro, tras polémica por millonarios salarios",
    "Un colombiano, vicepresidente de Nike, le metió un gol a Adidas por el balón de fútbol del Mundial",
    "Final de la Copa Sudamericana dejaría millonaria cifra en Barranquilla: hoteles y comercio se preparan",
    "Aeropuerto de Barranquilla estrenó una nueva sala internacional",
    "Anthropic estrenó nueva herramienta para reuniones antes de salir a bolsa",
    "Quién es Strauss Zelnick, el CEO detrás de GTA VI que dejó la presidencia de 20th Century Fox por los videojuegos",
    "Xsolla Acquires GamePix to Build a Complete Platform for Web and AI-Created Video Games",
    "Apple Now Sells DIY Repair Parts for iPhone Duo",
])
def test_ya_no_se_ocultan(titular):
    assert R.categoria({"titular": titular, "bajada": ""}) is None


@pytest.mark.parametrize("titular, cat", [
    ("Millonarios FC venció a Junior de Barranquilla en el clásico", "deportes"),
    ("The 8 Best Movies to Stream Right Now (November 2026)", "entretenimiento"),
])
def test_siguen_ocultas(titular, cat):
    assert R.categoria({"titular": titular, "bajada": ""}) == cat


def test_no_se_mezclan_historias_de_malware_distintas():
    casos = [
        nota(30, "cybersecurity-news", "ClickFix Attacks Evolve to Hide Malware in PNG Images and Hijack Windows Domains", 8,
             "Attackers hide malware inside PNG images in a new wave of ClickFix intrusions."),
        nota(31, "cybersecurity-news", "Hackers Exploit AhsayCBS Vulnerabilities to Hide Malware in PNG Images", 10,
             "Intrusions against AhsayCBS backup servers hide malware inside PNG images."),
    ]
    # Mismo verbo ("Hide") y misma sigla ("PNG"), pero campañas distintas
    assert not juntos(grupos(casos), "ClickFix Attacks Evolve", "Hackers Exploit AhsayCBS")


def test_no_se_mezclan_fallas_de_dia_cero_distintas():
    casos = [
        nota(32, "cyberpress", "CISA Confirms Active Exploitation of Outlook User Interaction 0-Day Vulnerability", 9,
             "CISA added the Outlook flaw to its catalog of exploited vulnerabilities."),
        nota(33, "cybersecurity-news", "Google Chrome 0-Day Vulnerability in the Wild to Execute Malicious Code Remotely", 11,
             "Google patched an exploited Chrome flaw that lets attackers run code."),
    ]
    assert not juntos(grupos(casos), "Outlook User Interaction 0-Day", "Google Chrome 0-Day")


def test_edicion_del_resumen_no_choca_con_el_resumen_de_ia():
    from test_fin_de_semana_y_google_news import FEED, AHORA  # noqa: E402
    notas = proceso.enriquecer(lector.interpretar(FEED, CFG.fuentes_por_id["viakoo"], AHORA, 7), CFG, AHORA)
    assert all(n["edicion"]["titulo"].startswith("Daily OT Security News") and n["resumen"] is None for n in notas)
