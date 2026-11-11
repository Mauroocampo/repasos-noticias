/* Repasos de noticias — modo claro/oscuro, filtros y paginación. Sin dependencias. */
(function () {
  'use strict';

  // ── Modo claro / oscuro ──────────────────────────────────────────────────
  var raiz = document.documentElement;
  var boton = document.getElementById('boton-tema');
  function temaActual() {
    var t = raiz.getAttribute('data-theme');
    if (t) return t;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  if (boton) {
    boton.addEventListener('click', function () {
      var nuevo = temaActual() === 'dark' ? 'light' : 'dark';
      raiz.setAttribute('data-theme', nuevo);
      try { localStorage.setItem('tema-color', nuevo); } catch (e) {}
    });
  }

  // ── Botón "Actualizar" ───────────────────────────────────────────────────
  // El sitio es estático: el botón abre GitHub para lanzar la actualización (solo la
  // cuenta dueña puede). Mientras tanto, esta página revisa estado.json y avisa al terminar.
  var cuerpo = document.body;
  var botonAct = document.getElementById('boton-actualizar');
  var aviso = document.getElementById('aviso-actualizacion');
  var avisoTexto = document.getElementById('aviso-texto');
  var avisoRecargar = document.getElementById('aviso-recargar');
  var avisoCerrar = document.getElementById('aviso-cerrar');
  var actual = cuerpo.getAttribute('data-actualizado') || '';
  var CLAVE = 'actualizacion-pedida';
  var INTERVALO = 30000, MAXIMO = 20 * 60000;
  var temporizador = null;

  function mostrarAviso(texto, conRecargar) {
    avisoTexto.textContent = texto;
    avisoRecargar.hidden = !conRecargar;
    aviso.hidden = false;
  }
  function detener() {
    clearInterval(temporizador); temporizador = null;
    if (botonAct) botonAct.classList.remove('girando');
    try { sessionStorage.removeItem(CLAVE); } catch (e) {}
  }
  function revisar(inicio) {
    if (Date.now() - inicio > MAXIMO) {
      detener();
      mostrarAviso('Todavía no hay datos nuevos. Revisa en GitHub (pestaña Actions) si la actualización terminó o falló.', false);
      return;
    }
    fetch(cuerpo.getAttribute('data-raiz') + 'estado.json?t=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (d && d.actualizado && d.actualizado !== actual) {
          detener();
          mostrarAviso('Listo: ya hay noticias nuevas publicadas.', true);
        }
      })
      .catch(function () {});
  }
  var worker = botonAct ? botonAct.getAttribute('data-worker') : '';
  var MSJ_GITHUB = 'Se abrió GitHub en otra pestaña: presiona «Run workflow». Tarda unos 4 minutos; esta página te avisará cuando termine.';
  var MSJ_LANZADA = 'Buscando noticias nuevas… Tarda unos 4 minutos; esta página te avisará cuando termine.';

  function esperar(inicio, texto) {
    try { sessionStorage.setItem(CLAVE, JSON.stringify({ inicio: inicio, actualizado: actual })); } catch (e) {}
    if (botonAct) botonAct.classList.add('girando');
    mostrarAviso(texto || MSJ_LANZADA, false);
    if (!temporizador) temporizador = setInterval(function () { revisar(inicio); }, INTERVALO);
  }

  // Con Worker: el clic lanza la actualización directamente. Si el Worker falla, se abre GitHub.
  function lanzarConWorker() {
    if (temporizador) { mostrarAviso(MSJ_LANZADA, false); return; }
    botonAct.classList.add('girando');
    mostrarAviso('Pidiendo la actualización…', false);
    fetch(worker + '/actualizar', { method: 'POST' })
      .then(function (r) { return r.json().then(function (d) { return { codigo: r.status, d: d }; }); })
      .then(function (x) {
        if (x.codigo === 202) esperar(Date.now());
        else if (x.codigo === 409) esperar(Date.now(), 'Ya había una actualización en curso; esta página te avisará cuando termine.');
        else if (x.codigo === 429) { detener(); mostrarAviso('Las noticias se actualizaron hace muy poco. Intenta de nuevo en ' + x.d.faltan_minutos + ' min.', false); }
        else throw new Error(x.d && x.d.mensaje);
      })
      .catch(function () {
        detener();
        mostrarAviso('No se pudo lanzar la actualización automática. Puedes hacerlo desde GitHub: ', false);
        var a = document.createElement('a');
        a.href = botonAct.href; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'abrir GitHub';
        avisoTexto.appendChild(a);
      });
  }

  if (botonAct && aviso) {
    botonAct.addEventListener('click', function (ev) {
      if (worker) { ev.preventDefault(); lanzarConWorker(); }
      else esperar(Date.now(), MSJ_GITHUB);
    });
    avisoRecargar.addEventListener('click', function () { location.reload(); });
    avisoCerrar.addEventListener('click', function () { aviso.hidden = true; detener(); });
    // Si cambió de pestaña del sitio mientras esperaba, se sigue esperando
    try {
      var pedida = JSON.parse(sessionStorage.getItem(CLAVE) || 'null');
      if (pedida && Date.now() - pedida.inicio < MAXIMO) {
        if (pedida.actualizado !== actual) { detener(); }
        else { esperar(pedida.inicio, worker ? MSJ_LANZADA : MSJ_GITHUB); }
      }
    } catch (e) {}
  }

  // ── Filtros ──────────────────────────────────────────────────────────────
  var form = document.getElementById('filtros');
  if (!form) return;

  var POR_PAGINA = 60;
  var visibles = POR_PAGINA;
  var notas = Array.prototype.slice.call(document.querySelectorAll('#flujo .nota'));
  var dias = Array.prototype.slice.call(document.querySelectorAll('#flujo .dia'));
  var conteo = document.getElementById('conteo');
  var verMas = document.getElementById('ver-mas');
  var sinResultados = document.getElementById('sin-resultados');
  var limpiar = document.getElementById('limpiar');
  var compartir = document.getElementById('compartir');
  var campos = ['periodo', 'tema', 'fuente', 'tipo', 'q', 'fijas', 'descartadas'];
  var sinResultadosTexto = sinResultados.textContent;

  // "Hoy" es el día actual en la hora de Colombia (no la del navegador)
  function hoy() {
    try {
      return new Intl.DateTimeFormat('en-CA', { timeZone: form.getAttribute('data-zona') || 'America/Bogota',
        year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
    } catch (e) {
      var d = new Date(Date.now() - 5 * 3600000);
      return d.toISOString().slice(0, 10);
    }
  }

  function normalizar(s) {
    return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  notas.forEach(function (n) { n._texto = normalizar(n.getAttribute('data-texto')); });

  function valores() {
    var v = {};
    campos.forEach(function (c) {
      var el = form.elements[c];
      if (!el) return;
      v[c] = el.type === 'checkbox' ? (el.checked ? '1' : '') : el.value.trim();
    });
    return v;
  }

  function desdeURL() {
    var p = new URLSearchParams(location.search);
    campos.forEach(function (c) {
      var el = form.elements[c];
      if (!el || !p.has(c)) return;
      if (el.type === 'checkbox') el.checked = p.get(c) === '1';
      else el.value = p.get(c);
      // Si el valor no existe en la lista (fuente sin notas en esta sección), se deja vacío
      if (el.tagName === 'SELECT' && el.value !== p.get(c)) el.value = '';
    });
  }

  function aURL(v) {
    var p = new URLSearchParams();
    Object.keys(v).forEach(function (k) { if (v[k]) p.set(k, v[k]); });
    var qs = p.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : ''));
  }

  function aplicar(reiniciar) {
    if (reiniciar) visibles = POR_PAGINA;
    var v = valores();
    var q = normalizar(v.q);
    var dia = v.periodo === 'hoy' ? hoy() : '';
    var soloPortada = v.periodo === 'portada';
    var coinciden = 0, mostradas = 0;
    notas.forEach(function (n) {
      // «Portadas de hoy»: solo lo que está en portada (aunque sea de días antes);
      // en las demás vistas no salen las notas de portada más viejas que la ventana
      var ok = (soloPortada ? n.hasAttribute('data-portada') : !n.hasAttribute('data-solo-portada')) &&
               (!dia || n.getAttribute('data-dia') === dia) &&
               (!v.tema || (' ' + n.getAttribute('data-temas') + ' ').indexOf(' ' + v.tema + ' ') >= 0) &&
               (!v.fuente || n.getAttribute('data-fuente') === v.fuente) &&
               (!v.tipo || n.getAttribute('data-tipo') === v.tipo) &&
               (!v.fijas || n.getAttribute('data-grupo') === 'fija') &&
               (v.descartadas || !n.hasAttribute('data-oculta')) &&
               (!q || n._texto.indexOf(q) >= 0);
      if (ok) coinciden++;
      var mostrar = ok && mostradas < visibles;
      if (mostrar) mostradas++;
      n.hidden = !mostrar;
    });
    dias.forEach(function (d) { d.hidden = !d.querySelector('.nota:not([hidden])'); });
    conteo.textContent = coinciden;
    verMas.hidden = coinciden <= mostradas;
    sinResultados.hidden = coinciden > 0 || notas.length === 0;
    sinResultados.textContent = dia && !Object.keys(v).some(function (k) { return k !== 'periodo' && v[k]; })
      ? 'Todavía no hay noticias de hoy. La actualización diaria es a las 6:00 a. m.'
      : sinResultadosTexto;
    limpiar.hidden = !Object.keys(v).some(function (k) { return v[k]; });
    aURL(v);
  }

  form.addEventListener('change', function () { aplicar(true); });
  var espera;
  form.addEventListener('input', function (e) {
    if (e.target.name !== 'q') return;
    clearTimeout(espera);
    espera = setTimeout(function () { aplicar(true); }, 200);
  });
  verMas.addEventListener('click', function () { visibles += POR_PAGINA; aplicar(false); });
  limpiar.addEventListener('click', function () { form.reset(); aplicar(true); });
  compartir.addEventListener('click', function () {
    var texto = compartir.textContent;
    function listo(msg) { compartir.textContent = msg; setTimeout(function () { compartir.textContent = texto; }, 2000); }
    if (navigator.share && /Android|iPhone|iPad/i.test(navigator.userAgent)) {
      navigator.share({ title: document.title, url: location.href }).catch(function () {});
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(location.href).then(function () { listo('Enlace copiado'); }, function () { listo('No se pudo copiar'); });
    } else {
      window.prompt('Copia este enlace:', location.href);
    }
  });

  desdeURL();
  aplicar(true);
})();
