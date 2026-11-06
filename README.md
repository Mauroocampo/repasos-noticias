# Repasos de noticias

Sitio estático de noticias que se arma con las fuentes del documento de repasos y se publica con GitHub Pages. Reúne las notas de los últimos 7 días, organizadas por temática:

Colombia (negocios, economía y energía) · Internacional y mercados · Tecnología e IT · Ciberseguridad IT · Ciberseguridad OT · Manufactura · Sostenibilidad

**Sitio:** https://mauroocampo.github.io/repasos-noticias/

## Cómo funciona

- **Actualización diaria.** Todos los días a las 6:00 a. m. (hora de Colombia), GitHub Actions lee las fuentes, guarda los datos en `datos/` y publica el sitio.
- **Cómo se lee cada fuente.** Se usa su RSS. Si no tiene uno que funcione, se usa Google News filtrado por su sitio.
- **Los grupos de fuentes:**
  - Fijas y especializadas: todo lo que publican entra en su temática.
  - Medios generales: solo entran las notas que pasan el filtro de palabras clave.
  - Datos y estudios: no van al flujo; están en la página *Datos de referencia*.
- **Duplicados.** Si la misma nota sale en varios sitios (por ejemplo, en la red TechDay), se muestra una sola versión, con «También en».
- **Marcas.** Junto a cada nota aparece su marca: muro de pago, proveedor, comunicado de empresa, activista, posible patrocinio, etc.
- **Fuentes que fallan.** Si una fuente no responde, el sitio se actualiza igual con las demás. El error queda en `datos/registro/` y en la página *Fuentes y método*.

## Archivos que puedes editar sin tocar código

| Archivo | Para qué |
|---|---|
| [`fuentes.yaml`](fuentes.yaml) | Todas las fuentes: grupo, tipo, temáticas, método, feeds, marcas y notas. Para agregar una fuente, copia un bloque; para sacarla, pon `grupo: excluida`. |
| [`palabras-clave.yaml`](palabras-clave.yaml) | Filtro por temática para los medios generales. Las instrucciones están al inicio del archivo. |
| [`ia.yaml`](ia.yaml) | Fase 2 (desactivada): resúmenes, comentario editorial y clasificación con IA. |

Después de editar, guarda el cambio en GitHub. El sitio se vuelve a publicar solo en uno o dos minutos.

## Actualizar a mano

**Desde GitHub:** pestaña *Actions* → *Actualizar y publicar* → *Run workflow*.

**En tu computador**, la primera vez:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Y luego, cada vez:

```bash
python actualizar.py              # lee las fuentes y genera sitio/
python actualizar.py --sin-red    # solo regenera el sitio con los datos guardados
python actualizar.py --verificar  # prueba cada fuente y muestra una tabla
python -m pytest -q               # pruebas
```

Para ver el sitio en tu computador: `python -m http.server 8765 --directory sitio` y abre http://localhost:8765.

## Estructura

```
fuentes.yaml            fuentes, grupos, temáticas, marcas (único archivo de fuentes)
palabras-clave.yaml     filtro por temática
ia.yaml                 fase 2 (desactivada)
actualizar.py           comando principal
actualizador/           lector, filtro, duplicados, marcas, generador
  ia/                   fase 2: resumen, clasificador, búsqueda abierta (solo estructura)
plantillas/             HTML (Jinja2)
estaticos/              CSS y JavaScript
datos/
  noticias.json         notas de la ventana actual
  archivo/AAAA-MM-DD.json   histórico por día de publicación
  registro/             estado de cada fuente y errores
herramientas/           verificador de fuentes
docs/                   verificación inicial de fuentes
tests/                  pruebas
.github/workflows/      actualización diaria y publicación
```

## Claves y datos personales

Este repositorio es público. **Nunca** pongas claves, tokens ni datos personales en los archivos.

Si más adelante hace falta una clave (por ejemplo, para la fase 2 con IA), va en *Settings → Secrets and variables → Actions* con el nombre indicado en `ia.yaml`.

## Fase 2 (estructura lista, sin construir)

- Resúmenes en español y comentario editorial con IA, siguiendo las reglas de marcado.
- Clasificación por temática con IA para los medios generales.
- Búsqueda abierta más allá de las fuentes del documento.
- Dominio propio: basta con agregar un archivo `CNAME` y configurarlo en *Settings → Pages*.
