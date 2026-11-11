"""Agrupa notas distintas sobre la misma historia (sin servicios externos).

Dos notas son la misma historia si se publicaron con poca diferencia de tiempo
(`ventana_horas`) y:
  - comparten al menos `min_entidades` entidades distintivas (nombres propios,
    empresas, siglas, cifras) y al menos una palabra clave del hecho, o
  - comparten `min_entidades_solas` entidades distintivas, o
  - la historia ya tiene 3 o más notas y la nota comparte `min_entidades` entidades
    de su núcleo (p. ej. Nvidia y Huang), aunque no comparta palabras clave, o
  - la historia ya tiene 3 o más notas y la nota comparte una entidad y
    `min_claves_con_una_entidad` palabras clave de su núcleo, o
  - comparten una entidad distintiva y sus titulares son muy parecidos.

Las entidades demasiado generales (EE. UU., Trump, China…) no cuentan; están en
`historias.genericas` de palabras-clave.yaml, igual que los demás ajustes. Además:
  - una palabra que aparece en más de `max_frecuencia` de las notas se considera general;
  - una palabra solo es entidad si casi nunca aparece en minúscula en las demás notas
    (así "Critical" o "Files" en un titular en inglés no cuentan como nombre propio);
  - se ignoran las palabras que se repiten en muchas notas de una misma fuente
    (p. ej. "CVE" en TheHackerWire o "Gen-AI Analysis" en MarkLines);
  - una historia necesita notas de al menos dos fuentes distintas.

Cada grupo muestra una nota principal (fija > primaria > especializada > con
bajada > más antigua) y el resto en "También en".
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timedelta

from rapidfuzz import fuzz

from .filtro import normalizar

# Palabras funcionales en español e inglés: nunca son entidades ni palabras clave
VACIAS = set("""
a al ante bajo cabe con contra de del desde durante en entre hacia hasta mediante para por segun sin
so sobre tras versus via el la lo los las un una unos unas y e ni o u pero sino que quien quienes cual
cuales cuyo como cuando donde mientras porque pues si no ya aun mas menos muy tan tanto todo toda todos
todas otro otra otros otras mismo misma este esta estos estas ese esa esos esas aquel su sus mi mis tu
tus nuestro nuestra se le les me te nos es son fue fueron ser sera seran ha han hay haber habia tiene
tienen tener hace hacen puede pueden podria deberia esta estan estaba sido cada sus ante segun tras
the a an and or but nor of to in on at by for from with without into onto over under about after before
between through during against as is are was were be been being has have had do does did will would
can could should may might must shall it its this that these those their there here his her he she they
them we our you your i my me us who whom whose which what when where why how not no yes so than then too
very just also only more most less least all any some each every other another such up down out off new
says said say amid via vs per year years day days week weeks month months today tonight now still
""".split())

_PALABRA = re.compile(r"[A-Za-zÀ-ÿ0-9][\wÀ-ÿ$%&\.\-']*")
_POSESIVO = re.compile(r"['’]s$")


def _tokens(texto: str) -> list[tuple[str, str]]:
    """Devuelve (palabra normalizada, forma) para cada palabra del texto.

    forma: "fuerte" (sigla o con cifras), "mayuscula" (empieza con mayúscula y no
    es la primera palabra) o "minuscula".
    """
    salida = []
    for i, m in enumerate(_PALABRA.finditer(texto or "")):
        crudo = _POSESIVO.sub("", m.group(0)).strip(".-'’")
        if not crudo:
            continue
        norm = normalizar(crudo)
        norm = norm.replace(".", "").replace(",", "") if not any(c.isdigit() for c in norm) else norm.rstrip(".,")
        if len(norm) < 2 or norm in VACIAS:
            continue
        tiene_cifra = any(c.isdigit() for c in norm)
        sigla = 2 <= len(crudo) <= 6 and crudo.isupper()
        if tiene_cifra or sigla:
            forma = "fuerte"
        elif crudo[0].isupper():
            forma = "mayuscula" if i > 0 else "inicio"
        else:
            forma = "minuscula"
        salida.append((norm, forma))
    return salida


def _raiz(palabra: str) -> str:
    """Raíz muy simple para que 'despidos' y 'despido', 'spies' y 'spy' coincidan."""
    if len(palabra) > 5 and palabra.endswith("es"):
        return palabra[:-2]
    if len(palabra) > 4 and palabra.endswith("s"):
        return palabra[:-1]
    return palabra


class Agrupador:
    def __init__(self, ajustes: dict | None):
        a = ajustes or {}
        self.activo = a.get("activo", True)
        self.ventana = timedelta(hours=float(a.get("ventana_horas", 48)))
        self.min_entidades = int(a.get("min_entidades", 2))
        self.min_entidades_solas = int(a.get("min_entidades_solas", 3))
        self.similitud_titular = float(a.get("similitud_titular", 70))
        self.max_frecuencia = float(a.get("max_frecuencia", 0.05))
        self.min_claves_una = int(a.get("min_claves_con_una_entidad", 2))
        self.max_grupo = int(a.get("max_grupo", 60))
        self.min_fuentes = int(a.get("min_fuentes", 2))
        # Una palabra que sale en minúscula en más de esta proporción de sus apariciones no es entidad
        self.max_minuscula = float(a.get("max_minuscula", 0.25))
        # Palabras que se repiten en más de esta proporción de las notas de una fuente: rutina de esa fuente
        self.max_por_fuente = float(a.get("max_por_fuente", 0.2))
        self.genericas = {_raiz(normalizar(str(g))) for g in a.get("genericas") or []}
        # Equivalencias entre idiomas: todas las palabras de un grupo cuentan como la primera
        self.equivalencias: dict[str, str] = {}
        for grupo in a.get("equivalencias") or []:
            palabras = [_raiz(normalizar(str(p))) for p in grupo]
            for p in palabras:
                self.equivalencias[p] = palabras[0]

    # ── rasgos de cada nota ─────────────────────────────────────────────────
    def _palabras(self, n: dict) -> list[tuple[str, str, bool]]:
        """(raíz, forma, ¿viene del titular?) de cada palabra útil del titular y la bajada."""
        salida = []
        for texto, del_titular in ((n.get("titular", ""), True), ((n.get("bajada") or "")[:220], False)):
            for palabra, forma in _tokens(texto):
                r = _raiz(palabra)
                r = self.equivalencias.get(r, r)
                if r in self.genericas or len(r) < 2:
                    continue
                salida.append((r, forma, del_titular))
        return salida

    def _rasgos(self, palabras, minuscula: Counter, total: Counter) -> tuple[set, set]:
        # Las entidades salen solo del titular; la bajada aporta palabras clave del hecho.
        entidades, claves = set(), set()
        for r, forma, del_titular in palabras:
            es_entidad = forma == "fuerte" or (
                forma in ("mayuscula", "inicio") and minuscula[r] <= self.max_minuscula * total[r])
            if es_entidad and del_titular:
                entidades.add(r)
            elif not es_entidad:
                claves.add(r)
        return entidades, claves - entidades

    # ── agrupación ──────────────────────────────────────────────────────────
    def agrupar(self, notas: list[dict], prioridad) -> list[dict]:
        if not self.activo or len(notas) < 2:
            return notas
        palabras = [self._palabras(n) for n in notas]
        # ¿Cuántas veces aparece cada palabra en minúscula? Las que casi nunca: nombres propios
        minuscula, total = Counter(), Counter()
        for ps in palabras:
            for r, forma, _ in ps:
                total[r] += 1
                if forma == "minuscula":
                    minuscula[r] += 1
        rasgos = []
        for n, ps in zip(notas, palabras):
            e, c = self._rasgos(ps, minuscula, total)
            rasgos.append((e, c, normalizar(n.get("titular", ""))))
        # Palabras demasiado frecuentes en la ventana actual: no distinguen una historia
        frecuencia = Counter(p for e, c, _ in rasgos for p in e | c)
        limite = max(10, math.ceil(self.max_frecuencia * len(notas)))  # con pocas notas no hay "comunes"
        comunes = {p for p, k in frecuencia.items() if k > limite}
        # Rutina de cada fuente: palabras que repite en muchas de sus notas
        por_fuente: dict[str, Counter] = {}
        notas_fuente = Counter(n["fuente_id"] for n in notas)
        for n, (e, c, _) in zip(notas, rasgos):
            por_fuente.setdefault(n["fuente_id"], Counter()).update(e | c)
        rutina = {
            fid: {p for p, k in cnt.items() if k >= 3 and k > self.max_por_fuente * notas_fuente[fid]}
            for fid, cnt in por_fuente.items()
        }
        fechas = [datetime.fromisoformat(n["fecha"]) for n in notas]

        orden = sorted(range(len(notas)), key=lambda i: fechas[i])
        grupos: list[dict] = []   # {miembros, entidades: Counter, claves: Counter, ultima}
        for i in orden:
            quitar = comunes | rutina.get(notas[i]["fuente_id"], set())
            ent_i = rasgos[i][0] - quitar
            cla_i = rasgos[i][1] - quitar
            mejor, mejor_puntaje = None, 0.0
            for g in grupos:
                if fechas[i] - g["ultima"] > self.ventana or len(g["miembros"]) >= self.max_grupo:
                    continue
                puntaje = self._puntaje(i, ent_i, cla_i, g, rasgos, fechas)
                if puntaje > mejor_puntaje:
                    mejor, mejor_puntaje = g, puntaje
            if mejor is None:
                grupos.append({"miembros": [i], "entidades": Counter(ent_i), "claves": Counter(cla_i), "ultima": fechas[i]})
            else:
                mejor["miembros"].append(i)
                mejor["entidades"].update(ent_i)
                mejor["claves"].update(cla_i)
                mejor["ultima"] = max(mejor["ultima"], fechas[i])

        grupos = self._fusionar(grupos, fechas)

        salida = []
        for g in grupos:
            miembros = [notas[i] for i in g["miembros"]]
            if len(miembros) == 1 or len({m["fuente_id"] for m in miembros}) < self.min_fuentes:
                salida.extend(miembros)  # una sola nota, o una serie de la misma fuente
                continue
            principal, *resto = sorted(miembros, key=prioridad)
            principal = {**principal, "tematicas": list(principal["tematicas"]),
                         "tambien_en": list(principal.get("tambien_en", []))}
            for otra in resto:
                principal["tambien_en"].append({
                    "fuente_id": otra["fuente_id"], "fuente": otra.get("fuente", otra["fuente_id"]),
                    "enlace": otra["enlace"], "titular": otra["titular"], "historia": True,
                })
                # Las copias exactas que ya traía la otra nota también van al grupo
                for t in otra.get("tambien_en", []):
                    principal["tambien_en"].append({**t, "titular": t.get("titular") or otra["titular"]})
                for t in otra["tematicas"]:
                    if t not in principal["tematicas"]:
                        principal["tematicas"].append(t)
            principal["historia_notas"] = len(miembros)
            salida.append(principal)
        return salida

    @staticmethod
    def _nucleo(g: dict) -> set:
        tam = len(g["miembros"])
        minimo = 1 if tam <= 2 else max(2, math.ceil(tam / 2))
        return {p for p, k in g["entidades"].items() if k >= minimo}

    def _fusionar(self, grupos: list[dict], fechas) -> list[dict]:
        """Segunda pasada: une grupos de la misma historia que quedaron separados
        (comparten al menos `min_entidades` entidades del núcleo y están en la ventana)."""
        cambiado = True
        while cambiado:
            cambiado = False
            grupos.sort(key=lambda g: -len(g["miembros"]))
            for a in range(len(grupos)):
                ga = grupos[a]
                if len(ga["miembros"]) < 2:
                    continue
                na = self._nucleo(ga)
                ini_a = min(fechas[i] for i in ga["miembros"])
                for b in range(a + 1, len(grupos)):
                    gb = grupos[b]
                    if len(gb["miembros"]) < 2 or len(ga["miembros"]) + len(gb["miembros"]) > self.max_grupo:
                        continue
                    ini_b = min(fechas[i] for i in gb["miembros"])
                    if ini_b - ga["ultima"] > self.ventana or ini_a - gb["ultima"] > self.ventana:
                        continue
                    if len(na & self._nucleo(gb)) >= self.min_entidades:
                        ga["miembros"].extend(gb["miembros"])
                        ga["entidades"].update(gb["entidades"])
                        ga["claves"].update(gb["claves"])
                        ga["ultima"] = max(ga["ultima"], gb["ultima"])
                        del grupos[b]
                        cambiado = True
                        break
                if cambiado:
                    break
        return grupos

    def _puntaje(self, i, ent_i, cla_i, g, rasgos, fechas) -> float:
        """0 si la nota no es de la historia; si lo es, cuánto se parece."""
        # Núcleo del grupo: lo que comparte al menos la mitad de sus notas (o todo, si es pequeño).
        # Así el grupo no se va desviando de tema a medida que crece.
        tam = len(g["miembros"])
        minimo = 1 if tam <= 2 else max(2, math.ceil(tam / 2))
        nucleo_ent = self._nucleo(g)
        nucleo_cla = {p for p, k in g["claves"].items() if k >= minimo}
        comp_ent = ent_i & nucleo_ent
        comp_cla = cla_i & nucleo_cla
        if len(comp_ent) >= self.min_entidades_solas:
            return 10 + len(comp_ent) + len(comp_cla)
        if len(comp_ent) >= self.min_entidades and comp_cla:
            return 5 + len(comp_ent) + len(comp_cla)
        # Solo para historias ya formadas (3 o más notas): recoge las notas rezagadas
        if tam >= 3 and len(comp_ent) >= self.min_entidades:
            return 4 + len(comp_ent) + len(comp_cla)
        if tam >= 3 and len(comp_ent) >= 1 and len(comp_cla) >= self.min_claves_una:
            return 4 + len(comp_ent) + len(comp_cla)
        if len(comp_ent) >= 1:
            # Titular muy parecido a alguna nota cercana del grupo
            titular = rasgos[i][2]
            for j in g["miembros"][-12:]:
                if abs(fechas[i] - fechas[j]) <= self.ventana and \
                        fuzz.token_sort_ratio(titular, rasgos[j][2]) >= self.similitud_titular:
                    return 3 + len(comp_ent)
        return 0.0
