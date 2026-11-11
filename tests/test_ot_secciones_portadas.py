"""Resumen de OT aviso por aviso, fuentes primarias, secciones nuevas, portadas y JSON públicos."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actualizador import config, duplicados, lector, paginas, proceso, resumenes

CFG = config.cargar()
AHORA = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)

# Edición de ejemplo con el formato real de Viakoo (encabezados <h2> numerados)
EDICION = """
<p>Daily OT Security News: November 10, 2026</p>
<h2>1. Axis discloses critical Camera Station vulnerability; fix details need clarification</h2>
<p>Source and event dates: Axis published on November 9, 2026.</p>
<p>News briefing</p>
<p>Axis disclosed CVE-2026-13312, an input-validation flaw that could lead to system compromise in Camera Station.</p>
<p><a href="https://www.axis.com/dam/public/cve-2026-13312.pdf">Axis advisory</a> <a href="https://cveawg.mitre.org/api/cve/CVE-2026-13312">CVE</a></p>
<h2>2. Helmholz discloses flaws in myREX24V2 industrial remote-access software</h2>
<p>Source date: November 10, 2026. Event dates: none.</p>
<p>Helmholz disclosed 12 vulnerabilities, CVE-2026-60035 through CVE-2026-60046, in myREX24V2.</p>
<p><a href="https://certvde.com/en/advisories/VDE-2026-141/">CERT@VDE</a></p>
<h2>3. Prosys updates OPC UA tools after eMudhra certificate compromise</h2>
<p>Prosys released new versions of its OPC UA tools after the eMudhra intermediate CA compromise.</p>
<p><a href="https://prosysopc.com/blog/security-advisory-emudhra/">Prosys</a></p>
<h2>4. Industry survey finds OT budgets grow</h2>
<p>A survey from a consultancy found that OT security budgets are growing across sectors this year.</p>
<p><a href="https://www.example.com/survey">Survey</a></p>
"""
URL_EDICION = "https://www.viakoo.com/blog/daily-ot-security-news-november-10-2026/"
FEED = f"""<?xml version="1.0"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>Viakoo</title>
<item><title>Daily OT Security News: November 10, 2026</title><link>{URL_EDICION}</link>
<pubDate>Tue, 10 Nov 2026 12:00:00 GMT</pubDate><content:encoded><![CDATA[{EDICION}]]></content:encoded></item>
</channel></rss>""".encode()


# ── 1. OT: avisos uno por uno ───────────────────────────────────────────────
def test_resumen_se_divide_en_avisos_con_enlace_primario():
    viakoo = CFG.fuentes_por_id["viakoo"]
    notas = lector.interpretar(FEED, viakoo, AHORA, 7)
    titulares = [n["titular"] for n in notas]
    assert len(notas) == 4
    assert titulares[0].startswith("Axis discloses critical Camera Station")
    assert titulares[1].startswith("Helmholz discloses flaws in myREX24V2")
    assert titulares[2].startswith("Prosys updates OPC UA tools")
    assert notas[0]["enlace"].startswith("https://www.axis.com/")          # aviso primario del fabricante
    assert notas[1]["enlace"] == "https://certvde.com/en/advisories/VDE-2026-141/"
    assert notas[3]["enlace"] == URL_EDICION + "#aviso-4"                  # sin aviso primario: la edición
    assert "CVE-2026-60035" in notas[1]["bajada"]
    assert not notas[2]["bajada"].lower().startswith("source")             # los rótulos no son bajada
    assert len({n["id"] for n in notas}) == 4                              # cada aviso es una nota


def test_avisos_de_viakoo_marcados_y_en_ciber_ot():
    notas = proceso.enriquecer(lector.interpretar(FEED, CFG.fuentes_por_id["viakoo"], AHORA, 7), CFG, AHORA)
    assert all(n["marcas"] == ["proveedor-viakoo"] and "ciber-ot" in n["tematicas"] for n in notas)
    assert CFG.marcas["proveedor-viakoo"]["texto"] == "Proveedor (Viakoo)"


def test_aviso_de_viakoo_se_une_al_aviso_primario():
    viakoo = proceso.enriquecer(lector.interpretar(FEED, CFG.fuentes_por_id["viakoo"], AHORA, 7), CFG, AHORA)
    primario = proceso.enriquecer([{
        "id": "vde141", "fuente_id": "certvde", "titular": "Helmholz: Multiple Vulnerabilities in myREX24V2",
        "bajada": "", "enlace": "https://certvde.com/en/advisories/vde-2026-141/",  # otra mayúscula: mismo aviso
        "fecha": "2026-11-10T09:00:00+00:00", "via": "pagina"}], CFG, AHORA)
    salida = duplicados.eliminar(viakoo + primario)
    helmholz = next(n for n in salida if "myREX24V2" in n["titular"])
    assert helmholz["fuente_id"] == "certvde"                              # la primaria es la principal
    assert [t["fuente_id"] for t in helmholz["tambien_en"]] == ["viakoo"]


def test_fuentes_primarias_de_ot_configuradas():
    ids = {f["id"] for f in CFG.fuentes_activas()}
    assert {"cisa-ics", "siemens-productcert", "certvde", "rockwell-psirt", "schneider-psirt",
            "abb-psirt", "jci-psirt"} <= ids
    assert CFG.fuentes_por_id["security-boulevard-ot"]["grupo"] == "excluida"


def test_extractores_de_paginas_de_avisos():
    vde = """<div class="card-body"><div class="small"><div>VDE-2026-141</div><div>Nov. 10, 2026, 11:00 AM</div></div>
    <div class="card-title"><h3><a href="/en/advisories/VDE-2026-141/" title="Helmholz: Multiple Vulnerabilities in myREX24V2">x</a></h3></div>
    <div class="card-text pb-3"> Multiple vulnerabilities in myREX24V2. </div> </div> </div>"""
    a = list(paginas._certvde(vde, "https://certvde.com/en/advisories/"))
    assert a[0]["enlace"] == "https://certvde.com/en/advisories/VDE-2026-141/" and a[0]["fecha"].day == 10
    se = """<table><tr><td>2026/11/10</td><td>Use After Free vulnerability on EcoStruxure Power Build Rapsody</td>
    <td>CVE-2026-119055</td><td>Desc</td><td>Prod</td>
    <td><a href="https://download.schneider-electric.com/files?p_Doc_Ref=SEVD-2026-314-01&amp;x=1">PDF</a></td></tr></table>"""
    a = list(paginas._schneider(se, "https://www.se.com/"))
    assert a[0]["enlace"] == "https://www.se.com/ww/en/download/document/SEVD-2026-314-01/"
    jci = """<table><tr><td>EasyIO Neo <a href="https://tyco.widen.net/s/x/jci-psa-2026-15">JCI-PSA-2026-15</a></td>
    <td>EasyIO Neo</td><td>Vulnerability impacting EasyIO Neo</td><td>CVE-2026-106020</td><td>See link</td>
    <td>November 3, 2026</td><td>November 3, 2026</td></tr></table>"""
    a = list(paginas._jci(jci, "https://www.johnsoncontrols.com/"))
    assert a[0]["titular"].startswith("JCI-PSA-2026-15") and a[0]["fecha"].month == 11


# ── 2. Secciones nuevas y tipo Opinión ──────────────────────────────────────
def test_secciones_nuevas_configuradas():
    pf, lr = CFG.fuentes_por_id["portafolio"], CFG.fuentes_por_id["la-republica"]
    for sec in ("energia", "tecnologia", "opinion", "opinion/editorial"):
        assert f"https://www.portafolio.co/rss/{sec}.xml" in pf["feeds"]
    assert "https://www.larepublica.co/rss/editorial" in lr["feeds"]
    assert any("analisis" in p["url"] for p in lr["paginas"])


def test_columnas_y_editoriales_son_opinion():
    pf, lr = CFG.fuentes_por_id["portafolio"], CFG.fuentes_por_id["la-republica"]
    assert proceso.tipo_de({"enlace": "https://www.portafolio.co/opinion/editorial/el-gas-que-necesitamos-505990"}, pf) == "opinion"
    assert proceso.tipo_de({"enlace": "https://www.larepublica.co/analisis/felipe-jaramillo-velez-4190102/cheque-cruzado-4522024"}, lr) == "opinion"
    assert proceso.tipo_de({"enlace": "https://www.portafolio.co/energia/enlaza-energiza-dos-circuitos-506050"}, pf) == "prensa"
    assert CFG.tipos["opinion"] == "Opinión"


def test_patrones_de_paginas_y_portada():
    import re
    pf, lr = CFG.fuentes_por_id["portafolio"], CFG.fuentes_por_id["la-republica"]
    assert re.search(pf["paginas"][0]["patron"], "https://www.portafolio.co/energia/pago-de-air-e-destraba-300-000-millones-506001")
    assert re.search(lr["paginas"][0]["patron"], "https://www.larepublica.co/analisis/felipe-jaramillo-velez-4190102/cheque-cruzado-4522024")
    assert not re.search(lr["paginas"][0]["patron"], "https://www.larepublica.co/analisis/felipe-jaramillo-velez-4190102")
    assert re.search(pf["portada"]["patron"], "https://www.portafolio.co/economia/gobierno/salario-minimo-506115")


# ── 3. Portadas de hoy ──────────────────────────────────────────────────────
def test_portada_marca_y_conserva_notas_viejas():
    vieja = {"id": "v", "fuente_id": "la-republica", "titular": "Editorial: la economía colombiana necesita gas",
             "bajada": "", "enlace": "https://www.larepublica.co/opinion/editorial/el-gas-4500000",
             "fecha": "2026-10-30T10:00:00+00:00", "via": "portada"}
    en_portada = {duplicados.url_canonica(vieja["enlace"])}
    guardadas = proceso.combinar([], [vieja], AHORA, 7, {}, en_portada)
    assert guardadas  # se conserva aunque tenga más de 7 días, porque está en portada
    n = proceso.enriquecer(guardadas, CFG, AHORA, en_portada)[0]
    assert n["en_portada"] and n["fuera_de_ventana"] and n["tipo"] == "opinion"
    assert proceso.combinar([], [vieja], AHORA, 7, {}, set()) == []  # sin portada, se descarta


# ── 4. Datos legibles ───────────────────────────────────────────────────────
def test_json_publicos_si_existe_el_sitio():
    ruta = Path(__file__).resolve().parent.parent / "sitio" / "datos"
    if not (ruta / "hoy.json").exists():
        return  # se genera con el build; la prueba completa corre después de generar el sitio
    for nombre in ("hoy.json", "semana.json"):
        d = json.loads((ruta / nombre).read_text(encoding="utf-8"))
        assert d["zona_horaria"] == "America/Bogota" and d["total"] == len(d["notas"])
        n = d["notas"][0]
        for campo in ("titular", "enlace", "fuente", "tipo_fuente", "tematicas", "fecha_colombia", "fija",
                      "en_portada_hoy", "oculta", "tambien_en"):
            assert campo in n
        assert n["fecha_colombia"].endswith("-05:00")
