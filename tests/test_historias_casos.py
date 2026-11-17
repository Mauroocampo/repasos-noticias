"""Casos reales de agrupación de historias (17 de noviembre de 2026)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actualizador import config, proceso
from actualizador.historias import Agrupador

CFG = config.cargar()


def nota(i, fuente, titular, hora, bajada="", grupo="especializada"):
    return {"id": f"n{i}", "fuente_id": fuente, "fuente": fuente, "titular": titular, "bajada": bajada,
            "enlace": f"https://{fuente}.example/{i}", "fecha": f"2026-11-17T{hora:02d}:00:00+00:00",
            "via": "rss", "grupo": grupo, "tipo": "prensa", "tematicas": ["ciber-it"], "tambien_en": [], "oculta": None}


# Relleno variado: da frecuencias realistas (nombres raros vs comunes)
TEMAS = ["anuncia nueva planta", "reporta caída en ventas", "lanza servicio en la nube", "firma acuerdo con gobierno",
         "abre oficina regional", "presenta plan de inversión", "cambia de director financiero", "amplía su red de tiendas"]
RELLENO = [nota(1000 + k, f"relleno{k % 9}", f"Compañía{k} {TEMAS[k % len(TEMAS)]} en la región {k % 13}", 1 + k % 20)
           for k in range(180)]
# Nvidia es frecuente en la semana: muchas notas sobre la salida de su CEO
NVIDIA_CEO = [nota(2000 + k, ["cnbc", "wsj", "forbes", "techcrunch"][k % 4],
                   f"Nvidia board weighs Jensen Huang return after resignation, report {k}", 2 + k % 10,
                   bajada="Investors pressed the board about governance after Huang resigned as chief executive.")
              for k in range(16)]


def grupos(notas):
    salida = Agrupador(CFG.palabras_clave.get("historias")).agrupar(notas + RELLENO, proceso.prioridad)
    return salida


def juntos(salida, *fragmentos):
    def grupo_de(frag):
        for n in salida:
            if frag in n["titular"] or any(frag in (t.get("titular") or "") for t in n.get("tambien_en", [])):
                return n["id"]
    ids = [grupo_de(f) for f in fragmentos]
    return None not in ids and len(set(ids)) == 1


def test_optimizely():
    casos = [
        nota(1, "the-hacker-news", "Hijacked Optimizely Scripts Served Card Skimmer and iOS Exploit Kits to CNN, BBC", 7,
             "Attackers compromised Optimizely scripts to inject malicious JavaScript into major websites."),
        nota(2, "securityweek", "Optimizely Vulnerability Exploited to Serve Malware on Major Websites", 9,
             "A compromised Optimizely component served malware to visitors of 178 websites."),
        nota(3, "cyberpress", "Hackers Infect 178 Major Websites With Malware Through Optimizely Supply Chain Attack", 10,
             "The Optimizely supply chain attack injected malicious JavaScript and a card skimmer."),
        nota(4, "macrumors", "Optimizely Hack Pushed iOS Exploit Kit to iPhone Users Visiting News Sites", 12,
             "Visitors on iPhone were served an exploit kit through hijacked Optimizely scripts."),
    ]
    assert juntos(grupos(casos), "Hijacked Optimizely", "Optimizely Vulnerability", "Through Optimizely", "Optimizely Hack")


def test_screenconnect():
    casos = [
        nota(5, "cybersecurity-news", "Hackers Exploit Critical ScreenConnect Flaw to Silently Run Malware on MSP Servers", 12,
             "Attackers are exploiting a critical ScreenConnect flaw against managed service providers."),
        nota(6, "the-hacker-news", "ConnectWise Warns ScreenConnect Attacks Continue as SCKit Targets Unpatched Servers", 6,
             "ConnectWise said attackers keep exploiting unpatched ScreenConnect servers at managed service providers."),
    ]
    assert juntos(grupos(casos), "Critical ScreenConnect Flaw", "ConnectWise Warns ScreenConnect")


def test_apple_macos_permisos_y_agentes():
    casos = [
        nota(7, "the-hacker-news", "Apple Tightens macOS App Permissions to Limit Data Access Amid AI Agent Security Concerns", 11,
             "Apple introduced granular permissions so AI agents cannot control apps or access user data without consent."),
        nota(8, "cyberpress", "Apple Tightens macOS 27.3 Security to Stop AI Agents From Accessing Sensitive Data", 9,
             "Apple is tightening macOS with granular permissions that stop AI agents from controlling apps and data."),
    ]
    assert juntos(grupos(casos), "Apple Tightens macOS App", "Apple Tightens macOS 27.3")


def test_resultados_de_nvidia_aparte_de_la_salida_de_su_ceo():
    casos = [
        nota(9, "cnbc", "Nvidia's Colette Kress confronts key questions in first earnings report since Huang exit", 13,
             "The interim chief faces questions as Nvidia reports quarterly earnings."),
        nota(10, "wsj", "Nvidia Earnings, Anthropic IPO Ahead in New Test for AI Economy", 14,
             "Nvidia reports quarterly earnings this week."),
        nota(11, "yahoo-finance", "How much could Nvidia stock move tomorrow after earnings?", 15,
             "Options traders price a big move after Nvidia earnings."),
        nota(12, "unite-ai", "Nvidia Earnings Preview: Data Center Revenue in Focus", 16,
             "Analysts expect data center revenue to drive Nvidia quarterly earnings."),
    ]
    salida = grupos(casos + NVIDIA_CEO)
    assert juntos(salida, "Colette Kress confronts", "Nvidia Earnings, Anthropic", "after earnings?", "Nvidia Earnings Preview")
    # Y no se mezclan con las notas sobre la salida del CEO
    assert not juntos(salida, "Nvidia Earnings Preview", "weighs Jensen Huang return after resignation, report 0")


def test_no_mezcla_rondas_de_inversion_distintas():
    casos = [
        nota(13, "unite-ai", "Bay Raises $37M Series A to Scale Enterprise AI Agent Security", 10,
             "The startup raised funding to scale its platform and expand its team."),
        nota(14, "unite-ai", "XpertDox Raises $20M Series A to Expand Autonomous Medical Coding", 11,
             "The startup raised funding to scale its platform and expand its team."),
    ]
    assert not juntos(grupos(casos), "Bay Raises", "XpertDox Raises")
