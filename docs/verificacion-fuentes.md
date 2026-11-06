# Verificación de fuentes

Fecha: 6 de noviembre de 2026. Cada fuente se probó de forma automática: se descargó el feed, se comprobó que fuera RSS o Atom válido y se contaron las notas de los últimos 7 días. Si el RSS no funcionaba o estaba detenido, se probó Google News filtrado por el sitio (`site:dominio`).

**Resumen:** 66 fuentes activas: 53 por RSS, 12 por Google News y 1 sin acceso. Además hay 15 en Datos de referencia y 35 excluidas.

"Notas en 7 días" cuenta lo que trajo el feed en la prueba. Muchos feeds solo muestran las 10 o 20 más recientes, así que el número real puede ser mayor. El sitio guarda lo nuevo cada día, y con eso la ventana de 7 días se va llenando.

## Fijas

| Fuente | Temática | Método | Notas en 7 días | Observación |
|---|---|---|---|---|
| Portafolio | Colombia (+ manufactura, sostenibilidad por filtro) | RSS (economía + negocios) | 10 + 10 | |
| La República | Colombia (+ internacional, manufactura, sostenibilidad) | RSS (economía, empresas, finanzas, globoeconomía) | 60 por sección | El RSS general da 404; se usan las secciones |
| Agronegocios | Colombia (+ sostenibilidad) | RSS | 20 | |
| Asuntos Legales | Colombia | RSS | 20 | |
| BBC Mundo | Internacional (+ Colombia, tecnología, sostenibilidad) | RSS | 30 | |
| Wired | Tecnología (+ ciber IT) | RSS | 50 | Muro de pago |
| IT Brief | Tecnología | RSS | 10 | Red TechDay |
| SecurityBrief | Ciberseguridad IT (+ OT) | RSS | 10 | Red TechDay |
| ChannelLife | Tecnología | RSS | 10 | Red TechDay |
| DataCentreNews | Tecnología (+ sostenibilidad) | RSS | 10 | Red TechDay |
| CFOtech | Tecnología | RSS | 10 | Red TechDay |
| eCommerceNews | Tecnología | RSS | 10 | Red TechDay |
| TelcoNews | Tecnología | RSS | 10 | Red TechDay |
| FutureFive | Tecnología | RSS | 10 | Red TechDay |
| LNS Research | Manufactura (+ sostenibilidad, ciber OT) | RSS | 0 | ⚠ El feed funciona, pero la última entrada es del 30 sep. Publica poco |

## Especializadas

| Fuente | Temática | Método | Notas en 7 días | Observación |
|---|---|---|---|---|
| The Hacker News | Ciber IT (+ OT) | RSS | 50 | |
| SecurityWeek | Ciber IT (+ OT) | RSS | 10 | |
| Help Net Security | Ciber IT | RSS | 10 | |
| CyberPress | Ciber IT | RSS | 10 | |
| Cybersecurity News | Ciber IT | RSS | 10 | |
| TheHackerWire | Ciber IT | RSS | 10 | |
| Petri | Ciber IT (+ tecnología) | RSS | 10 | |
| Redmond Magazine | Ciber IT (+ tecnología) | RSS | 3 | |
| Malwarebytes | Ciber IT | RSS | 15 | Proveedor |
| Microsoft Threat Intelligence | Ciber IT | RSS | 6 | La empresa |
| CISA, avisos ICS | Ciber OT | RSS | 1 | ⚠ Solo 1 aviso en 7 días (3 nov); hay que vigilarlo |
| Siemens ProductCERT | Ciber OT | RSS | 6 | El feed trae casi 2.500 avisos históricos; se toman solo los recientes |
| Industrial Cyber | Ciber OT | RSS | 9 | |
| Automation.com (ISA) | Ciber OT (+ manufactura) | **Google News** | 1 | El RSS responde 403 (bloquea la lectura automática) |
| Security Boulevard, Daily OT Security News | Ciber OT | **Google News** | ~5 (uno diario) | El RSS responde 403. La búsqueda exacta "Daily OT Security News" trae solo el resumen. Proveedor (Viakoo) |
| Viakoo | Ciber OT | RSS | 6 | Proveedor |
| TechCrunch | Tecnología (+ ciber IT) | RSS | 20 | |
| The Register | Tecnología (+ ciber IT, OT) | RSS | 50 | |
| MacRumors | Tecnología | RSS | 20 | |
| Unite.AI | Tecnología | RSS | 25 | |
| Infobae Tecno | Tecnología | RSS | 100 | |
| Blog de Google | Tecnología | RSS | 20 | La empresa |
| Linux Foundation | Tecnología | RSS | 0 | ⚠ Funciona; última entrada 26 oct. Publica poco |
| The Manufacturer | Manufactura | **Google News** | 16 | El RSS responde 403 |
| MarkLines | Manufactura | **Google News** | 5 | Sin RSS público |
| Climate Home News | Sostenibilidad | RSS | 16 | |
| Mongabay Latam | Sostenibilidad | RSS | 30 | Edición en español |
| SustainabilityOnline | Sostenibilidad | RSS | 9 | |
| UICN | Sostenibilidad | **Google News** | 2 | El RSS está abandonado desde 2022 |
| Beyond Fossil Fuels | Sostenibilidad | RSS | 1 | Activista |
| Geneva Environment Network | Sostenibilidad | **Sin acceso** | — | ✖ El servidor corta la conexión y Google News no tiene notas. Queda inactiva |

## Medios generales (filtro de palabras clave)

| Fuente | Temáticas posibles | Método | Notas en 7 días (antes del filtro) | Observación |
|---|---|---|---|---|
| El Heraldo | Colombia, manufactura, sostenibilidad | RSS | 100 | |
| Infobae Colombia | Colombia, sostenibilidad | RSS | 100 | |
| El Universal (Cartagena) | Colombia | **Google News** | 100 | El RSS estaba detenido desde el 31 oct |
| ABC Economía | Colombia (si menciona Colombia), internacional | RSS | 25 | |
| CNBC | Internacional, tecnología | RSS | 30 | |
| Forbes | Internacional, tecnología | RSS | 25 | Muro de pago parcial |
| Yahoo Finance | Internacional | **Google News** | 32 | Sin RSS que funcione |
| Wall Street Journal | Internacional, tecnología | RSS (mundo, mercados, negocios) | 56 + | Muro de pago. El feed antiguo de Dow Jones está muerto desde ene 2025; se usa el nuevo |
| Investing.com | Internacional | RSS | 10 | Republica a Reuters |
| Business Wire | Tecnología, ciber IT y OT, manufactura, sostenibilidad | **Google News** | 39 | Comunicados. Su RSS no trae fechas |
| Fuels & Lubes | Sostenibilidad, manufactura | RSS | 16 | Comunicados |
| OMS | Sostenibilidad | **Google News** | 4 | El RSS estaba detenido desde el 10 oct |
| Noticias ONU | Sostenibilidad, internacional | RSS | 14 | |
| ONU Colombia | Sostenibilidad, Colombia | **Google News** | 2 | El RSS estaba detenido desde el 19 oct |
| UNICEF | Sostenibilidad | **Google News** | 5 | El RSS corta la conexión |
| House of Commons Library | Sostenibilidad | RSS | 10 | |
| Bloomberg Professional | Sostenibilidad, internacional | RSS | 10 | |
| Amnistía Internacional | Sostenibilidad | RSS | 11 | Activista |
| BBVA | Sostenibilidad | **Google News** | 28 | Banco. El RSS llega vacío |
| Tech Funding News | Manufactura, tecnología | RSS | 10 | La pasé a "general": publica rondas de todos los sectores |

## Datos de referencia (sin flujo, solo enlaces)

Dane · Congreso Visible · NYU Stern · PwC · Kantar · Kearney · Bank of America Institute · Bain & Company · SEC (EDGAR) · Microsoft, relación con inversionistas · NSC Research Center · Comisión Europea · Rappi · Megatiendas · Novaventa

## Excluidas (confirmadas)

Deia, Azat TV, Modern Ghana, Geo TV, Washington Times, Sustenia, AI Weekly, boletines de Substack, FinanceFeeds, El Economista, Irish Times, ABC News Australia, Cambio, IFM Noticias, El Frente, DiariOriente, La Silla Vacía, HNGN, GamingBolt, Qué.es, The Tribune, Clearwater Security, WIU Cybersecurity Center, Tech Insider, Bloomberg Línea, Insighted, Tiempo Real, Mercado, Investinglive, Harpers, Vegconomist, Green Queen, Infobae (resumen SOFI), Acento, El Clarín de Chile.

## Sobre Google News

- Los enlaces pasan por una redirección de Google antes de llegar a la nota original.
- Google News no trae la bajada, solo el titular. En esas fuentes el filtro de palabras clave trabaja únicamente con el titular.
- Si alguna de estas fuentes vuelve a tener un RSS que funcione, basta con cambiar `metodo` y `feeds` en `fuentes.yaml`.
