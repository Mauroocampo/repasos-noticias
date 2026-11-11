# Repasos de noticias

Sitio estático de noticias que se arma con las fuentes del documento de repasos y se publica con GitHub Pages. Reúne las notas de los últimos 7 días, organizadas por temática:

Colombia (negocios, economía y energía) · Internacional y mercados · Tecnología e IT · Ciberseguridad IT · Ciberseguridad OT · Manufactura · Sostenibilidad

**Sitio:** https://mauroocampo.github.io/repasos-noticias/

## Cómo funciona

- **Actualización diaria.** Todos los días a las 6:00 a. m. (hora de Colombia), GitHub Actions lee las fuentes, guarda los datos en `datos/` y publica el sitio.
- **Cómo se lee cada fuente.** Se usa su RSS. Si no tiene uno que funcione, se usa Google News filtrado por su sitio.
- **Los grupos de fuentes:**
  - Fijas y especializadas: conservan su temática propia y suman las que indique el contenido.
  - Medios generales: solo entran las notas que pasan las palabras clave.
  - Datos y estudios: no van al flujo; están en la página *Datos de referencia*.
- **Clasificación por contenido.** La temática sale del titular y la bajada, con las reglas de `palabras-clave.yaml`:
  - Colombia solo si la nota trata de Colombia; las notas internacionales de medios colombianos van a Internacional y mercados.
  - Ciberseguridad OT entra desde cualquier fuente si la nota trata de sistemas de control o físicos.
  - Se descartan las entradas que no son noticias (páginas de sección, paginación y portadas).
  - Se ocultan, sin borrarlas, las notas que no corresponden a las temáticas (sección `relevancia`): se ven con «Mostrar descartadas».
- **Historias.** Notas distintas sobre la misma historia en 48 horas se agrupan en «También en», con una nota principal (sección `historias` de `palabras-clave.yaml`).
- **Duplicados.** Si la misma nota sale en varios sitios (por ejemplo, en la red TechDay), se muestra una sola versión, con «También en».
- **Marcas.** Junto a cada nota aparece su marca: muro de pago, proveedor, comunicado de empresa, activista, posible patrocinio, etc.
- **Fuentes que fallan.** Si una fuente no responde, el sitio se actualiza igual con las demás. El error queda en `datos/registro/` y en la página *Fuentes y método*.

## Archivos que puedes editar sin tocar código

| Archivo | Para qué |
|---|---|
| [`fuentes.yaml`](fuentes.yaml) | Todas las fuentes: grupo, tipo, temáticas, método, feeds, marcas y notas. Para agregar una fuente, copia un bloque; para sacarla, pon `grupo: excluida`. |
| [`palabras-clave.yaml`](palabras-clave.yaml) | Reglas para clasificar por contenido: palabras por temática, señales de Colombia y del exterior, reglas de Ciberseguridad OT y patrones de entradas que no son noticias. Las instrucciones están al inicio del archivo. |
| [`ia.yaml`](ia.yaml) | Fase 2 (desactivada): resúmenes, comentario editorial y clasificación con IA. |

Después de editar, guarda el cambio en GitHub. El sitio se vuelve a publicar solo en uno o dos minutos.

## Actualizar a mano

**Desde el sitio:** botón *Actualizar* de la barra superior. Si `url_actualizar` en `fuentes.yaml` tiene la dirección del Worker de Cloudflare, el botón lanza la actualización directamente; si está vacía, abre GitHub.

**Desde GitHub:** pestaña *Actions* → *Actualizar y publicar* → *Run workflow*.

### Botón Actualizar con Cloudflare

El código está en `cloudflare/worker.js`. Solo acepta pedidos del sitio publicado, no lanza una actualización si ya hay otra en curso y exige 10 minutos entre una y otra.

1. **Clave de GitHub:** en GitHub, *Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token*. Solo el repositorio `repasos-noticias`, permiso *Actions: Read and write*. Cópiala; no la pegues en ningún archivo.
2. **Worker:** en Cloudflare, *Workers & Pages → Create → Start with Hello World*, nombre `repasos-actualizar`, *Deploy*. Luego *Edit code*, reemplaza todo por el contenido de `cloudflare/worker.js` y *Deploy*.
3. **Secreto:** en el Worker, *Settings → Variables and Secrets → Add*, tipo *Secret*, nombre `GITHUB_TOKEN`, valor: la clave del paso 1.
4. **Conectar el sitio:** pon la dirección del Worker (algo como `https://repasos-actualizar.<tu-cuenta>.workers.dev`) en `url_actualizar` de `fuentes.yaml`.

La clave de GitHub vence (máximo un año). Cuando venza, el botón vuelve a abrir GitHub; genera una nueva y reemplaza el secreto en Cloudflare.

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
palabras-clave.yaml     reglas de clasificación por contenido
ia.yaml                 fase 2 (desactivada)
actualizar.py           comando principal
actualizador/           lector, filtro, descartes, duplicados, marcas, generador
  ia/                   fase 2: resumen, clasificador, búsqueda abierta (solo estructura)
plantillas/             HTML (Jinja2)
estaticos/              CSS y JavaScript
datos/
  noticias.json         notas de la ventana actual
  archivo/AAAA-MM-DD.json   histórico por día de publicación
  registro/             estado de cada fuente y errores
cloudflare/worker.js    Worker que lanza la actualización desde el botón (sin claves)
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
