"""Prueba cada fuente activa y muestra una tabla: fuente, grupo, temática, método y resultado.

Se usa con `python actualizar.py --verificar`. No modifica datos/.
Escribe el resultado en datos/registro/verificacion.md.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from actualizador import lector
from actualizador.almacen import REGISTRO
from actualizador.config import Config


def verificar(cfg: Config) -> int:
    ahora = datetime.now(timezone.utc)
    temas = cfg.nombres_tematicas
    fuentes = cfg.fuentes_del_flujo()

    def probar(f):
        if f.get("metodo") == "sin_acceso":
            return f, "sin acceso", 0
        notas, est = lector.leer_fuente(f, ahora, cfg.ventana_dias)
        if not est["ok"]:
            return f, "FALLA: " + "; ".join(est["errores"])[:120], 0
        return f, "parcial" if est["parcial"] else "ok", len(notas)

    with ThreadPoolExecutor(max_workers=12) as pool:
        resultados = list(pool.map(probar, fuentes))

    filas = ["| Fuente | Grupo | Temática | Método | Resultado | Notas en la ventana |", "|---|---|---|---|---|---|"]
    for f, res, n in resultados:
        t = ", ".join(temas[x] for x in f.get("tematicas", []) + f.get("tematicas_por_filtro", []))
        filas.append(f"| {f['nombre']} | {f['grupo']} | {t} | {f.get('metodo')} | {res} | {n} |")
    tabla = "\n".join(filas)
    print(tabla)

    REGISTRO.mkdir(parents=True, exist_ok=True)
    (REGISTRO / "verificacion.md").write_text(
        f"# Verificación automática\n\n{ahora.isoformat()}\n\n{tabla}\n", encoding="utf-8")
    fallas = sum(1 for _, r, _ in resultados if r.startswith("FALLA"))
    print(f"\n{len(resultados)} fuentes revisadas, {fallas} con falla.")
    return 0
