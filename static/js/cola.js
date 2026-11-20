/*
 * Cola de solicitudes sin conexión (IndexedDB).
 *
 * La usan la página (app.js) y el service worker (sw.js, con importScripts), así que no toca el DOM.
 * Cada solicitud guardada es un registro que el usuario hizo sin señal: crear o editar un lote,
 * o registrar una venta. Se reenvía en orden a la API JSON de Flask (/api/...) cuando vuelve la
 * conexión, ya sea desde la página (evento "online", cada 30 s, al abrirla) o desde el service
 * worker con Background Sync, aunque la página esté cerrada.
 *
 * Estados: "pendiente" (se reintentará) · "error" (el servidor rechazó los datos: el usuario decide).
 * Cada registro guarda el id del usuario que lo creó y solo se envía con la sesión de ese usuario.
 *
 * Al enviar, cada registro lleva su id (X-Evento-Id) y el momento en que se guardó (X-Evento-Creado):
 * el servidor no aplica dos veces el mismo registro y mide cuánto tardó en llegar.
 */
(function (global) {
  "use strict";

  const NOMBRE_BD = "agrotracker-cola";
  const ALMACEN = "solicitudes";
  const ETIQUETA_SYNC = "agrotracker-cola";
  const canal = "BroadcastChannel" in global ? new BroadcastChannel("agrotracker-cola") : null;

  let bdPromesa = null;
  function abrir() {
    if (!bdPromesa) {
      bdPromesa = new Promise((resolver, rechazar) => {
        const solicitud = indexedDB.open(NOMBRE_BD, 1);
        solicitud.onupgradeneeded = () => {
          solicitud.result.createObjectStore(ALMACEN, { keyPath: "id" });
        };
        solicitud.onsuccess = () => {
          const bd = solicitud.result;
          bd.onversionchange = () => { bd.close(); bdPromesa = null; };
          resolver(bd);
        };
        solicitud.onerror = () => { bdPromesa = null; rechazar(solicitud.error); };
      });
    }
    return bdPromesa;
  }

  function promesa(solicitud) {
    return new Promise((resolver, rechazar) => {
      solicitud.onsuccess = () => resolver(solicitud.result);
      solicitud.onerror = () => rechazar(solicitud.error);
    });
  }

  async function almacen(modo) {
    const bd = await abrir();
    return bd.transaction(ALMACEN, modo).objectStore(ALMACEN);
  }

  async function listar(usuarioId) {
    const items = await promesa((await almacen("readonly")).getAll());
    return items
      .filter((item) => usuarioId == null || item.usuarioId === usuarioId)
      .sort((a, b) => a.creado - b.creado);
  }

  async function guardar(item) {
    await promesa((await almacen("readwrite")).put(item));
  }

  async function borrar(id) {
    await promesa((await almacen("readwrite")).delete(id));
    avisar({ tipo: "cambio" });
  }

  function nuevoId() {
    if (global.crypto && global.crypto.randomUUID) return global.crypto.randomUUID();
    return Date.now().toString(36) + Math.random().toString(36).slice(2);
  }

  /**
   * Guarda una solicitud para enviarla después. Si ya se intentó enviar en línea, se reutilizan su
   * id y su hora: si ese primer envío sí llegó, el servidor reconoce el reintento y no lo duplica.
   */
  async function encolar({ url, metodo, cuerpo, usuarioId, tipo, filtro, titulo, resumen, id, creado }) {
    const item = {
      id: id || nuevoId(), url, metodo, cuerpo, usuarioId, tipo, filtro: filtro || null,
      titulo, resumen, creado: creado || Date.now(), estado: "pendiente", error: null, intentos: 0,
    };
    await guardar(item);
    await pedirSincronizacionEnSegundoPlano();
    avisar({ tipo: "cambio" });
    return item;
  }

  async function reintentar(id) {
    const item = (await listar()).find((i) => i.id === id);
    if (!item) return;
    item.estado = "pendiente";
    item.error = null;
    await guardar(item);
    avisar({ tipo: "cambio" });
  }

  async function pedirSincronizacionEnSegundoPlano() {
    // Background Sync (Chrome/Edge/Android): el navegador despierta al service worker cuando vuelve
    // la red, aunque la pestaña esté cerrada. En otros navegadores la página sincroniza sola.
    try {
      const registro = global.registration || (global.navigator.serviceWorker && (await global.navigator.serviceWorker.ready));
      if (registro && registro.sync) await registro.sync.register(ETIQUETA_SYNC);
    } catch (_) { /* sin soporte: queda la sincronización desde la página */ }
  }

  function avisar(mensaje) {
    if (canal) canal.postMessage(mensaje); // otras pestañas y el service worker
    if (global.dispatchEvent && typeof CustomEvent === "function" && global.document) {
      global.dispatchEvent(new CustomEvent("cola", { detail: mensaje })); // esta misma página
    }
  }

  function escuchar(funcion) {
    if (canal) canal.addEventListener("message", (e) => funcion(e.data));
    if (global.addEventListener && global.document) global.addEventListener("cola", (e) => funcion(e.detail));
  }

  async function leerJson(respuesta) {
    try { return await respuesta.clone().json(); } catch (_) { return {}; }
  }

  let enCurso = null;
  /**
   * Reenvía lo pendiente en orden. Se detiene ante el primer problema transitorio para no desordenar.
   * Las pestañas abiertas y el service worker pueden intentar sincronizar a la vez: un candado
   * compartido (Web Locks) asegura que solo uno envíe, para no registrar dos veces la misma venta.
   */
  function sincronizar() {
    if (!enCurso) {
      const locks = global.navigator && global.navigator.locks;
      const tarea = locks ? locks.request(NOMBRE_BD, () => sincronizarAhora()) : sincronizarAhora();
      enCurso = tarea.finally(() => { enCurso = null; });
    }
    return enCurso;
  }

  async function sincronizarAhora() {
    const resultado = { enviados: [], rechazados: [], sinRed: false, sinSesion: false, quedan: 0 };
    const pendientes = (await listar()).filter((i) => i.estado === "pendiente");
    if (!pendientes.length) return resultado;
    avisar({ tipo: "enviando" });

    let sesion;
    try {
      const r = await fetch("/api/sesion", { credentials: "same-origin", cache: "no-store" });
      if (r.status === 401) resultado.sinSesion = true;
      else if (!r.ok) resultado.sinRed = true;
      else sesion = await r.json();
    } catch (_) {
      resultado.sinRed = true;
    }

    if (sesion) {
      for (const item of pendientes) {
        if (item.usuarioId !== sesion.usuario_id) continue; // es de otra persona que usó este equipo
        const vigente = await promesa((await almacen("readonly")).get(item.id));
        if (!vigente || vigente.estado !== "pendiente") continue; // descartado o enviado mientras tanto
        let r;
        try {
          r = await fetch(item.url, {
            method: item.metodo,
            credentials: "same-origin",
            headers: {
              "Content-Type": "application/json", "X-CSRF": sesion.csrf, "X-Cola": "1",
              "X-Evento-Id": item.id, "X-Evento-Creado": String(item.creado),
            },
            body: JSON.stringify(item.cuerpo),
          });
        } catch (_) {
          resultado.sinRed = true;
          break;
        }
        const datos = await leerJson(r);
        if (r.ok) {
          await promesa((await almacen("readwrite")).delete(item.id));
          resultado.enviados.push({ item, datos });
          continue;
        }
        if (r.status === 401) { resultado.sinSesion = true; break; }
        if (r.status >= 500 || r.status === 408 || r.status === 429 || (r.status === 403 && datos.csrf)) {
          item.intentos += 1;
          await guardar(item);
          resultado.sinRed = true; // servidor no disponible: se reintenta más tarde
          break;
        }
        item.estado = "error";
        item.error = datos.detail || `El servidor rechazó el registro (${r.status}).`;
        await guardar(item);
        resultado.rechazados.push(item);
      }
    }

    resultado.quedan = (await listar()).filter((i) => i.estado === "pendiente").length;
    avisar({ tipo: "sincronizado", resultado: { ...resultado, enviados: resultado.enviados.map((e) => ({ titulo: e.item.titulo, tipo: e.item.tipo, datos: e.datos })) } });
    return resultado;
  }

  global.Cola = { encolar, listar, borrar, reintentar, sincronizar, escuchar, nuevoId, ETIQUETA_SYNC };
})(self);
