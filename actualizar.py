"""Actualiza las noticias y genera el sitio.

Uso:
    python actualizar.py               lee todas las fuentes y genera sitio/
    python actualizar.py --sin-red     solo regenera el sitio con los datos guardados
    python actualizar.py --verificar   prueba cada fuente y muestra una tabla (no cambia datos)
"""
from __future__ import annotations

import argparse
import logging
import sys

from actualizador import config, proceso
from actualizador.generador import Generador


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Actualiza el sitio repasos-noticias.")
    ap.add_argument("--sin-red", action="store_true", help="no leer fuentes; regenerar el sitio con los datos guardados")
    ap.add_argument("--verificar", action="store_true", help="probar cada fuente y mostrar la tabla de verificación")
    ap.add_argument("-v", "--detalle", action="store_true", help="mostrar más mensajes")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.detalle else logging.INFO, format="%(message)s")
    log = logging.getLogger("actualizador")

    try:
        cfg = config.cargar()
    except config.ErrorConfig as e:
        log.error(str(e))
        return 2

    if args.verificar:
        from herramientas.verificar_fuentes import verificar
        return verificar(cfg)

    if args.sin_red:
        log.info("Regenerando el sitio con los datos guardados…")
    else:
        log.info("Leyendo %d fuentes…", len(cfg.fuentes_activas()))
    r = proceso.actualizar(cfg, con_red=not args.sin_red)
    salida = Generador(cfg).generar(r["notas"], r["estado"], r["ahora"])

    fuentes = r["estado"].get("fuentes", {})
    fallidas = [f for f, e in fuentes.items() if not e.get("ok") and e.get("metodo") != "sin_acceso"]
    log.info("")
    log.info("Listo: %d noticias en el sitio (%s).", len(r["notas"]), salida)
    if fallidas:
        log.warning("No respondieron %d fuentes: %s. El detalle queda en datos/registro/.",
                    len(fallidas), ", ".join(fallidas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
