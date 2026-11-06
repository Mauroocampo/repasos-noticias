/**
 * Worker de Cloudflare para el botón "Actualizar" de repasos-noticias.
 *
 * Recibe el clic del sitio y lanza la GitHub Action "Actualizar y publicar".
 * La clave de GitHub NO está en este archivo ni en el repositorio: se guarda
 * como secreto del Worker en Cloudflare, con el nombre GITHUB_TOKEN.
 *
 * Protecciones para que nadie abuse del botón:
 *   - Solo acepta pedidos que vienen del sitio publicado (ORIGEN).
 *   - Si ya hay una actualización en curso, no lanza otra.
 *   - Entre una actualización y la siguiente deben pasar al menos ESPERA_MINUTOS.
 *
 * Rutas:
 *   POST /actualizar  → lanza la actualización (o explica por qué no)
 *   GET  /estado      → dice si hay una actualización en curso y cuándo fue la última
 */

const REPO = 'Mauroocampo/repasos-noticias';
const FLUJO = 'actualizar.yml';
const RAMA = 'main';
const ORIGEN = 'https://mauroocampo.github.io';
const ESPERA_MINUTOS = 10;

const API = `https://api.github.com/repos/${REPO}/actions/workflows/${FLUJO}`;

function cabecerasCors(origen) {
  return {
    'Access-Control-Allow-Origin': origen === ORIGEN ? ORIGEN : 'null',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

function responder(cuerpo, estado, origen) {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...cabecerasCors(origen) },
  });
}

function github(env, ruta, opciones = {}) {
  return fetch(API + ruta, {
    ...opciones,
    headers: {
      'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'repasos-noticias-worker',
      ...(opciones.body ? { 'Content-Type': 'application/json' } : {}),
    },
  });
}

async function ultimasEjecuciones(env) {
  const r = await github(env, '/runs?per_page=5');
  if (!r.ok) throw new Error(`GitHub respondió ${r.status} al consultar las ejecuciones`);
  const datos = await r.json();
  return datos.workflow_runs || [];
}

async function estado(env) {
  const runs = await ultimasEjecuciones(env);
  const enCurso = runs.find((x) => x.status !== 'completed');
  const ultima = runs[0];
  return {
    en_curso: Boolean(enCurso),
    ultima_inicio: ultima ? ultima.created_at : null,
    ultima_resultado: ultima ? (ultima.conclusion || ultima.status) : null,
  };
}

async function actualizar(env) {
  const e = await estado(env);
  if (e.en_curso) {
    return [{ resultado: 'en_curso', mensaje: 'Ya hay una actualización en curso.' }, 409];
  }
  if (e.ultima_inicio) {
    const minutos = (Date.now() - Date.parse(e.ultima_inicio)) / 60000;
    if (minutos < ESPERA_MINUTOS) {
      const faltan = Math.ceil(ESPERA_MINUTOS - minutos);
      return [{ resultado: 'reciente', faltan_minutos: faltan,
        mensaje: `La última actualización fue hace menos de ${ESPERA_MINUTOS} minutos. Intenta en ${faltan} min.` }, 429];
    }
  }
  const r = await github(env, '/dispatches', { method: 'POST', body: JSON.stringify({ ref: RAMA }) });
  if (r.status !== 204) {
    throw new Error(`GitHub respondió ${r.status} al lanzar la actualización`);
  }
  return [{ resultado: 'lanzada', mensaje: 'Actualización lanzada. Tarda unos 4 minutos.' }, 202];
}

export default {
  async fetch(request, env) {
    const origen = request.headers.get('Origin') || '';
    const ruta = new URL(request.url).pathname;

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cabecerasCors(origen) });
    }
    if (!env.GITHUB_TOKEN) {
      return responder({ resultado: 'error', mensaje: 'Falta el secreto GITHUB_TOKEN en el Worker.' }, 500, origen);
    }

    try {
      if (ruta === '/estado' && request.method === 'GET') {
        return responder(await estado(env), 200, origen);
      }
      if (ruta === '/actualizar' && request.method === 'POST') {
        if (origen !== ORIGEN) {
          return responder({ resultado: 'prohibido', mensaje: 'Solo se puede actualizar desde el sitio.' }, 403, origen);
        }
        const [cuerpo, codigo] = await actualizar(env);
        return responder(cuerpo, codigo, origen);
      }
      return responder({ resultado: 'no_encontrado', mensaje: 'Usa POST /actualizar o GET /estado.' }, 404, origen);
    } catch (err) {
      return responder({ resultado: 'error', mensaje: String(err.message || err) }, 502, origen);
    }
  },
};
