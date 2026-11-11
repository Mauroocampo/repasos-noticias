"""Genera el sitio estático en sitio/ a partir de las notas y la configuración."""
from __future__ import annotations

import json
import os
import shutil
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import RAIZ, Config

SALIDA = RAIZ / "sitio"
PLANTILLAS = RAIZ / "plantillas"
ESTATICOS = RAIZ / "estaticos"
# En GitHub Actions viene en GITHUB_REPOSITORY; en local se usa el repositorio publicado
REPOSITORIO = os.environ.get("GITHUB_REPOSITORY") or "Mauroocampo/repasos-noticias"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
METODOS = {"rss": "RSS", "google_news": "Google News", "sin_acceso": "Sin acceso"}


def hora(d: datetime) -> str:
    h = d.hour % 12 or 12
    return f"{h}:{d.minute:02d} {'a. m.' if d.hour < 12 else 'p. m.'}"


def dia_largo(d: datetime) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


def fecha_hora(d: datetime) -> str:
    return f"{d.day} {MESES_CORTOS[d.month - 1]} {d.year}, {hora(d)}"


class Generador:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.tz = ZoneInfo(cfg.zona_horaria)
        self.textos_ocultas = {k: (v or {}).get("texto", k) for k, v in (cfg.palabras_clave.get("relevancia") or {}).items()}
        self.nombres = {f["id"]: f["nombre"] for f in cfg.fuentes}
        self.env = Environment(
            loader=FileSystemLoader(PLANTILLAS),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # ── preparación de datos ────────────────────────────────────────────────
    def _vista(self, n: dict) -> dict:
        local = datetime.fromisoformat(n["fecha"]).astimezone(self.tz)
        temas = self.cfg.nombres_tematicas
        hoy = getattr(self, "hoy_local", None)
        anterior = bool(n.get("en_portada") and hoy and local.date() < hoy)
        return {
            **n,
            "local": local,
            "hora": hora(local),
            # Nota de portada publicada antes del día de la actualización
            "publicada_el": f"{local.day} {MESES_CORTOS[local.month - 1]}" if anterior else "",
            # Si la nota no está en portada pero otra de su grupo sí: de qué medio es esa portada
            "portada_otras": [self.nombres.get(f, f) for f in n.get("en_portada_de", [])]
                             if n.get("en_portada") and n["fuente_id"] not in n.get("en_portada_de", []) else [],
            # Más vieja que la ventana del sitio pero en portada hoy: solo en «Portadas de hoy»
            "solo_portada": bool(n.get("fuera_de_ventana") and n.get("en_portada")),
            "tipo_txt": self.cfg.tipos.get(n.get("tipo"), n.get("tipo") or ""),
            "temas_txt": [(t, temas.get(t, t)) for t in n["tematicas"]],
            "tambien_por_titular": self._por_titular(n),
            "oculta_txt": self.textos_ocultas.get(n.get("oculta"), n.get("oculta") or ""),
            "marcas_txt": [
                (m, self.cfg.marcas[m]["texto"], self.cfg.marcas[m].get("explicacion", ""))
                for m in n.get("marcas", []) if m in self.cfg.marcas
            ],
        }

    def _por_titular(self, n: dict) -> list[dict]:
        """"También en" de una historia: una línea por titular, con todas las fuentes que lo publicaron."""
        lineas: OrderedDict[str, dict] = OrderedDict()
        nombres = {f["id"]: f["nombre"] for f in self.cfg.fuentes}
        for o in n.get("tambien_en", []):
            titular = o.get("titular") or n["titular"]
            linea = lineas.setdefault(titular, {"titular": titular, "enlace": o["enlace"], "fuentes": []})
            linea["fuentes"].append((nombres.get(o["fuente_id"], o["fuente_id"]), o["enlace"]))
        return list(lineas.values())

    def _por_dia(self, notas: list[dict]) -> list[tuple[str, list[dict]]]:
        grupos: OrderedDict[str, list[dict]] = OrderedDict()
        for n in notas:
            grupos.setdefault(dia_largo(n["local"]), []).append(n)
        return list(grupos.items())

    def _opciones(self, notas: list[dict]):
        fuentes = sorted({(n["fuente_id"], n["fuente"]) for n in notas}, key=lambda x: x[1].lower())
        tipos = sorted({n["tipo"] for n in notas if n.get("tipo")}, key=lambda t: self.cfg.tipos.get(t, t))
        return fuentes, [(t, self.cfg.tipos.get(t, t)) for t in tipos]

    def _destacadas(self, notas: list[dict], por_familia: int = 1) -> list[dict]:
        """Las más recientes de cada fuente fija (TechDay y La República cuentan como una)."""
        conteo: dict[str, int] = {}
        salida = []
        for n in notas:
            if n["grupo"] != "fija" or n.get("oculta"):
                continue
            familia = n.get("red") or n["fuente_id"]
            if conteo.get(familia, 0) < por_familia:
                conteo[familia] = conteo.get(familia, 0) + 1
                salida.append(n)
        return salida

    # ── escritura ───────────────────────────────────────────────────────────
    def _pagina(self, plantilla: str, destino: Path, raiz: str, **ctx) -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        html = self.env.get_template(plantilla).render(raiz=raiz, cfg=self.cfg, **self.comun, **ctx)
        destino.write_text(html, encoding="utf-8")

    def generar(self, notas: list[dict], estado: dict, ahora: datetime) -> Path:
        if SALIDA.exists():
            shutil.rmtree(SALIDA)
        SALIDA.mkdir(parents=True)
        shutil.copytree(ESTATICOS, SALIDA / "estaticos")
        (SALIDA / ".nojekyll").write_text("", encoding="utf-8")

        actualizado = estado.get("actualizado") if estado else None
        self.hoy_local = (datetime.fromisoformat(actualizado) if actualizado else ahora).astimezone(self.tz).date()
        todas = [self._vista(n) for n in notas]
        # Notas más viejas que la ventana: las de fuentes que publican poco solo van a destacadas;
        # las que siguen en portada van al flujo, ocultas salvo en «Portadas de hoy»
        vistas = [n for n in todas if not n.get("fuera_de_ventana") or n["solo_portada"]]
        est_fuentes = {k: v for k, v in (estado or {}).get("fuentes", {}).items() if "ok" in v}
        con_error = [fid for fid, e in est_fuentes.items() if not e.get("ok") and e.get("metodo") != "sin_acceso"]
        self.comun = {
            "version": int(ahora.timestamp()),
            "actualizado": actualizado,
            "url_ejecutar": f"https://github.com/{REPOSITORIO}/actions/workflows/actualizar.yml",
            "tematicas": self.cfg.tematicas,
            "actualizado_txt": fecha_hora(datetime.fromisoformat(actualizado).astimezone(self.tz)) if actualizado else "sin datos",
            "total_fuentes": len(est_fuentes),
            "fuentes_con_error": con_error,
            "nombres_fuentes": {f["id"]: f["nombre"] for f in self.cfg.fuentes},
        }

        fuentes_op, tipos_op = self._opciones(vistas)
        self._pagina(
            "flujo.html", SALIDA / "index.html", "",
            pagina="portada", titulo="Lo más reciente", tema_fijo=None,
            destacadas=self._destacadas([n for n in todas if not n["solo_portada"]]), dias=self._por_dia(vistas),
            fuentes_op=fuentes_op, tipos_op=tipos_op, **self._conteos(vistas),
        )
        for t in self.cfg.tematicas:
            del_tema = [n for n in vistas if t["id"] in n["tematicas"]]
            del_tema_todas = [n for n in todas if t["id"] in n["tematicas"] and not n["solo_portada"]]
            fo, to = self._opciones(del_tema)
            self._pagina(
                "flujo.html", SALIDA / "tematica" / t["id"] / "index.html", "../../",
                pagina=t["id"], titulo=t["nombre"], tema_fijo=t["id"],
                destacadas=self._destacadas(del_tema_todas, por_familia=1), dias=self._por_dia(del_tema),
                fuentes_op=fo, tipos_op=to, **self._conteos(del_tema),
            )

        self._pagina("fuentes.html", SALIDA / "fuentes" / "index.html", "../",
                     pagina="fuentes", titulo="Fuentes y método", **self._ctx_fuentes(todas, est_fuentes))
        self._pagina("datos.html", SALIDA / "datos" / "index.html", "../",
                     pagina="datos", titulo="Datos de referencia", **self._ctx_datos())

        publicas = [{k: v for k, v in n.items() if k not in ("red",)} for n in notas]
        (SALIDA / "noticias.json").write_text(
            json.dumps({"actualizado": actualizado, "notas": publicas}, ensure_ascii=False), encoding="utf-8")
        # Archivo pequeño que la página consulta para saber si ya hay una actualización nueva
        (SALIDA / "estado.json").write_text(
            json.dumps({"actualizado": actualizado, "notas": len(notas)}), encoding="utf-8")
        self._exportar(todas, actualizado)
        return SALIDA

    @staticmethod
    def _conteos(vistas: list[dict]) -> dict:
        """Conteos de la barra de filtros: visibles por defecto, ocultas y en portada."""
        return {
            "total": sum(1 for n in vistas if not n.get("oculta") and not n["solo_portada"]),
            "ocultas": sum(1 for n in vistas if n.get("oculta") and not n["solo_portada"]),
            "en_portada": sum(1 for n in vistas if n.get("en_portada") and not n.get("oculta")),
        }

    # ── Datos legibles para otras herramientas ─────────────────────────────
    def _exportar(self, todas: list[dict], actualizado: str | None) -> None:
        """/datos/hoy.json (publicado hoy o en portada hoy) y /datos/semana.json (ventana completa)."""
        temas = self.cfg.nombres_tematicas
        nombres = {f["id"]: f["nombre"] for f in self.cfg.fuentes}

        def registro(n: dict) -> dict:
            return {
                "titular": n["titular"],
                "enlace": n["enlace"],
                "fuente": n["fuente"],
                "fuente_id": n["fuente_id"],
                "tipo_fuente": n["tipo_txt"],
                "tipo_fuente_id": n.get("tipo"),
                "tematicas": [{"id": t, "nombre": temas.get(t, t)} for t in n["tematicas"]],
                "fecha_colombia": n["local"].isoformat(),
                "fecha": n["local"].date().isoformat(),
                "hora": n["hora"],
                "fija": n.get("grupo") == "fija",
                "en_portada_hoy": bool(n.get("en_portada")),
                "en_portada_de": [nombres.get(f, f) for f in n.get("en_portada_de", [])],
                "oculta": ({"regla": n["oculta"], "texto": n["oculta_txt"]} if n.get("oculta") else None),
                "marcas": [texto for _, texto, _ in n["marcas_txt"]],
                "bajada": n.get("bajada") or "",
                "tambien_en": [{"fuente": nombres.get(t["fuente_id"], t["fuente_id"]), "fuente_id": t["fuente_id"],
                                "titular": t.get("titular") or n["titular"], "enlace": t["enlace"]}
                               for t in n.get("tambien_en", [])],
            }

        semana = [n for n in todas if not n.get("fuera_de_ventana") or n["solo_portada"]]
        hoy = [n for n in semana if n["local"].date() == self.hoy_local or n.get("en_portada")]
        carpeta = SALIDA / "datos"
        carpeta.mkdir(parents=True, exist_ok=True)
        for nombre, lista, descripcion in (
            ("hoy.json", hoy, f"Notas publicadas el {self.hoy_local.isoformat()} (hora de Colombia) o en la portada de hoy"),
            ("semana.json", semana, f"Notas de los últimos {self.cfg.ventana_dias} días y las que siguen en portada"),
        ):
            (carpeta / nombre).write_text(json.dumps({
                "actualizado": actualizado, "zona_horaria": self.cfg.zona_horaria, "descripcion": descripcion,
                "total": len(lista), "notas": [registro(n) for n in lista],
            }, ensure_ascii=False, indent=1), encoding="utf-8")

    def _ctx_fuentes(self, vistas: list[dict], est_fuentes: dict) -> dict:
        por_fuente: dict[str, int] = {}
        for n in vistas:
            por_fuente[n["fuente_id"]] = por_fuente.get(n["fuente_id"], 0) + 1
            for t in n.get("tambien_en", []):
                por_fuente[t["fuente_id"]] = por_fuente.get(t["fuente_id"], 0) + 1
        temas = self.cfg.nombres_tematicas
        grupos = []
        for g in ("fija", "especializada", "general"):
            filas = []
            for f in self.cfg.fuentes:
                if f["grupo"] != g:
                    continue
                e = est_fuentes.get(f["id"], {})
                if f.get("metodo") == "sin_acceso":
                    estado_txt, clase = "Sin acceso", "error"
                elif not e:
                    estado_txt, clase = "Sin revisar", "neutro"
                elif not e.get("ok"):
                    estado_txt, clase = "No respondió", "error"
                elif e.get("respaldo"):
                    estado_txt, clase = "Respondió por Google News (respaldo)", "aviso"
                elif e.get("parcial"):
                    estado_txt, clase = "Respondió en parte", "aviso"
                else:
                    estado_txt, clase = "Respondió", "ok"
                filas.append({
                    "f": f,
                    "temas": [temas[t] for t in f.get("tematicas", [])],
                    "temas_filtro": [temas[t] for t in f.get("tematicas_por_filtro", [])],
                    "tipo": self.cfg.tipos.get(f.get("tipo"), ""),
                    "metodo": METODOS.get(f.get("metodo"), f.get("metodo")),
                    "estado": estado_txt, "clase": clase,
                    "errores": e.get("errores", []),
                    "en_sitio": por_fuente.get(f["id"], 0),
                    "marcas": [self.cfg.marcas[m]["texto"] for m in f.get("marcas", []) if m in self.cfg.marcas],
                    "solo_titular": f.get("mostrar_bajada") is False,
                })
            grupos.append((g, self.cfg.grupos.get(g, g), filas))
        excluidas = [f for f in self.cfg.fuentes if f["grupo"] == "excluida"]
        return {"grupos_fuentes": grupos, "excluidas": excluidas, "marcas": self.cfg.marcas}

    def _ctx_datos(self) -> dict:
        temas = self.cfg.nombres_tematicas
        por_tema: OrderedDict[str, list] = OrderedDict((t["id"], []) for t in self.cfg.tematicas)
        for f in self.cfg.fuentes:
            if f["grupo"] == "referencia":
                tema = (f.get("tematicas") or ["sostenibilidad"])[0]
                por_tema.setdefault(tema, []).append({**f, "tipo_txt": self.cfg.tipos.get(f.get("tipo"), "")})
        return {"referencias": [(temas.get(t, t), fs) for t, fs in por_tema.items() if fs]}
