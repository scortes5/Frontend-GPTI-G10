/*
 * Service worker de AgroTracker (se sirve en /sw.js para cubrir toda la app).
 *
 * - Estáticos (CSS, JS, iconos): se guardan al instalar y se actualizan en segundo plano.
 * - Páginas: red primero; si no hay señal, la última copia guardada; si no existe, /offline.
 *   Las copias se borran al cerrar sesión (app.js) para no dejar datos en equipos compartidos.
 * - QR de los lotes: caché primero (no cambian).
 * - POST/PATCH y /api/*: siempre a la red. Lo que falla sin señal lo guarda la cola (cola.js),
 *   y este worker la reenvía con Background Sync cuando vuelve la conexión.
 */
importScripts("/static/js/cola.js");

const VERSION = "v1";
const ESTATICOS = `agrotracker-estaticos-${VERSION}`;
const PAGINAS = `agrotracker-paginas-${VERSION}`;
const QR = `agrotracker-qr-${VERSION}`;
const VIGENTES = [ESTATICOS, PAGINAS, QR];

const PRECARGA = [
  "/offline",
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/js/cola.js",
  "/static/img/icono.svg",
  "/static/img/icono-192.png",
  "/static/img/icono-512.png",
  "/manifest.webmanifest",
];
const SIN_GUARDAR = ["/login", "/recuperar", "/logout", "/offline"];

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(ESTATICOS).then((cache) => cache.addAll(PRECARGA)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((nombres) => Promise.all(nombres.filter((n) => n.startsWith("agrotracker-") && !VIGENTES.includes(n)).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const { request } = evento;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname === "/sw.js") return;

  if (request.mode === "navigate") {
    evento.respondWith(pagina(request, url));
  } else if (url.pathname.startsWith("/qr/")) {
    evento.respondWith(primeroCache(request, QR));
  } else if (url.pathname.startsWith("/static/") || url.pathname === "/manifest.webmanifest") {
    evento.respondWith(cacheYActualizar(request, evento));
  }
});

async function pagina(request, url) {
  try {
    const respuesta = await fetch(request);
    const guardable = respuesta.ok && !respuesta.redirected && respuesta.type === "basic"
      && !respuesta.headers.get("X-Con-Avisos") && !SIN_GUARDAR.includes(url.pathname);
    if (guardable) {
      const cache = await caches.open(PAGINAS);
      await cache.put(request.url, respuesta.clone());
    }
    return respuesta;
  } catch (_) {
    const cache = await caches.open(PAGINAS);
    const guardada = await cache.match(request.url);
    if (guardada) return guardada;
    return (await caches.match("/offline")) || new Response("Sin conexión", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}

async function primeroCache(request, nombre) {
  const cache = await caches.open(nombre);
  const guardada = await cache.match(request);
  if (guardada) return guardada;
  try {
    const respuesta = await fetch(request);
    if (respuesta.ok) await cache.put(request, respuesta.clone());
    return respuesta;
  } catch (_) {
    return new Response("", { status: 504 });
  }
}

async function cacheYActualizar(request, evento) {
  const cache = await caches.open(ESTATICOS);
  const guardada = await cache.match(request, { ignoreSearch: true });
  const red = fetch(request)
    .then((respuesta) => { if (respuesta.ok) cache.put(request, respuesta.clone()); return respuesta; })
    .catch(() => null);
  if (guardada) {
    evento.waitUntil(red);
    return guardada;
  }
  return (await red) || new Response("", { status: 504 });
}

// Background Sync: el navegador nos despierta cuando vuelve la red.
self.addEventListener("sync", (evento) => {
  if (evento.tag !== Cola.ETIQUETA_SYNC) return;
  evento.waitUntil(
    Cola.sincronizar().then((resultado) => {
      // Si aún no hay red o servidor, fallar hace que el navegador reintente más tarde.
      if (resultado.sinRed) throw new Error("Sin conexión: se reintentará");
    })
  );
});

self.addEventListener("message", (evento) => {
  if (evento.data && evento.data.tipo === "sincronizar") evento.waitUntil(Cola.sincronizar());
});
