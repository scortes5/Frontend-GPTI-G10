/*
 * Comportamiento de la interfaz. Todo es mejora progresiva: sin JavaScript los formularios
 * se envían igual al servidor; con JavaScript se agregan la cola sin conexión y la PWA.
 */
(function () {
  "use strict";

  const $ = (selector, raiz = document) => raiz.querySelector(selector);
  const $$ = (selector, raiz = document) => Array.from(raiz.querySelectorAll(selector));
  const usuarioId = document.body.dataset.usuarioId ? Number(document.body.dataset.usuarioId) : null;
  const numero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 1 });
  const pesos = new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 });

  // ---------- Service worker (PWA) ----------

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch((e) => console.warn("Service worker no registrado", e));
    });
  }

  // ---------- Avisos flotantes ----------

  function toast(mensaje, { tipo = "info", accion = null, duracion = 6000 } = {}) {
    const contenedor = $("[data-toasts]");
    if (!contenedor) return;
    const el = document.createElement("div");
    el.className = `toast toast--${tipo}`;
    el.setAttribute("role", tipo === "error" ? "alert" : "status");
    const texto = document.createElement("span");
    texto.textContent = mensaje;
    el.append(texto);
    if (accion) {
      const boton = document.createElement("button");
      boton.type = "button";
      boton.className = "boton boton--chico boton--suave";
      boton.textContent = accion.texto;
      boton.addEventListener("click", accion.hacer);
      el.append(boton);
    }
    contenedor.append(el);
    setTimeout(() => el.remove(), duracion);
  }

  // ---------- Estado de la red ----------

  function actualizarRed() {
    const banda = $("[data-banda-red]");
    if (banda) banda.hidden = navigator.onLine;
  }
  window.addEventListener("online", () => { actualizarRed(); sincronizar(); });
  window.addEventListener("offline", actualizarRed);
  actualizarRed();

  // ---------- Formularios que se pueden guardar sin conexión ----------

  function csrf() {
    const meta = $('meta[name="csrf"]');
    return meta ? meta.content : "";
  }

  function datosDe(form) {
    const datos = {};
    new FormData(form).forEach((valor, clave) => { if (clave !== "csrf") datos[clave] = valor; });
    return datos;
  }

  function rellenar(plantilla, datos) {
    return (plantilla || "").replace(/\{(\w+)\}/g, (_, campo) => {
      const valor = datos[campo];
      if (valor == null || valor === "") return "—";
      if (campo === "fecha_cosecha" || campo === "fecha") return valor.split("-").reverse().join("-");
      if (campo === "kilos") return numero.format(Number(valor));
      if (campo === "precio_por_kilo") return new Intl.NumberFormat("es-CL").format(Number(valor));
      return valor;
    });
  }

  function ocupado(form, si) {
    const boton = $('button[type="submit"]', form);
    if (boton) { boton.disabled = si; boton.setAttribute("aria-busy", si ? "true" : "false"); }
  }

  async function guardarEnCola(form, datos, motivo) {
    if (usuarioId == null || !window.Cola) return false;
    await Cola.encolar({
      url: form.dataset.cola,
      metodo: form.dataset.colaMetodo || "POST",
      cuerpo: datos,
      usuarioId,
      tipo: form.dataset.colaTipo,
      filtro: form.dataset.colaFiltro,
      titulo: form.dataset.colaTitulo,
      resumen: rellenar(form.dataset.colaResumen, datos),
    });
    if (form.dataset.colaMetodo !== "PATCH") form.reset();
    toast(motivo, { tipo: "aviso", duracion: 8000 });
    return true;
  }

  $$("form[data-cola]").forEach((form) => {
    form.addEventListener("submit", async (evento) => {
      if (!window.Cola || !("indexedDB" in window)) return; // envío normal al servidor
      evento.preventDefault();
      const datos = datosDe(form);
      ocupado(form, true);
      try {
        if (!navigator.onLine) {
          await guardarEnCola(form, datos, "Guardado en este equipo. Se enviará solo cuando vuelva la señal.");
          return;
        }
        let respuesta;
        try {
          respuesta = await fetch(form.dataset.cola, {
            method: form.dataset.colaMetodo || "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRF": csrf() },
            body: JSON.stringify(datos),
          });
        } catch (_) {
          await guardarEnCola(form, datos, "No hubo conexión. Quedó guardado y se enviará solo cuando vuelva la señal.");
          return;
        }
        const cuerpo = await respuesta.json().catch(() => ({}));
        if (respuesta.ok) {
          window.location.assign(cuerpo.redirect || window.location.href);
          return;
        }
        if (respuesta.status === 401) {
          await guardarEnCola(form, datos, "Tu sesión expiró. Quedó guardado: se enviará cuando vuelvas a iniciar sesión.");
          setTimeout(() => window.location.assign("/login?siguiente=" + encodeURIComponent(location.pathname + location.search)), 2500);
          return;
        }
        if (respuesta.status >= 500 || (respuesta.status === 403 && cuerpo.csrf)) {
          await guardarEnCola(form, datos, "El servidor no respondió. Quedó guardado y se reintentará en un momento.");
          sincronizar();
          return;
        }
        toast(cuerpo.detail || "No se pudo guardar. Revisa los datos.", { tipo: "error", duracion: 9000 });
      } finally {
        ocupado(form, false);
      }
    });
  });

  // ---------- Pendientes en pantalla ----------

  function hace(ms) {
    const minutos = Math.round((Date.now() - ms) / 60000);
    if (minutos < 1) return "recién";
    if (minutos < 60) return `hace ${minutos} min`;
    const horas = Math.round(minutos / 60);
    if (horas < 24) return `hace ${horas} h`;
    return new Date(ms).toLocaleDateString("es-CL");
  }

  function elemento(etiqueta, clase, texto) {
    const el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    if (texto != null) el.textContent = texto;
    return el;
  }

  async function pintarCola(enviando = false) {
    if (usuarioId == null || !window.Cola) return;
    let items;
    try { items = await Cola.listar(usuarioId); } catch (_) { return; }

    // Chip de la barra superior
    const chip = $("[data-cola-abrir]");
    if (chip) {
      const errores = items.filter((i) => i.estado === "error").length;
      chip.hidden = items.length === 0;
      chip.dataset.estado = errores ? "error" : enviando ? "enviando" : "pendiente";
      $("[data-cola-cuenta]", chip).textContent = items.length;
      $("[data-cola-texto]", chip).textContent = errores
        ? (items.length === 1 ? "con problema" : "pendientes · revisar")
        : (items.length === 1 ? "pendiente" : "pendientes");
    }

    // Listas dentro de la página (lotes / ventas del lote)
    $$("[data-cola-lista]").forEach((caja) => {
      const propios = items.filter((i) => i.tipo === caja.dataset.colaLista && (!caja.dataset.colaFiltro || i.filtro === caja.dataset.colaFiltro));
      caja.hidden = propios.length === 0;
      const lista = $("ul", caja);
      lista.replaceChildren(...propios.map((i) => {
        const li = elemento("li");
        li.dataset.estado = i.estado;
        li.append(elemento("span", null, i.resumen), elemento("small", null, i.estado === "error" ? "No se pudo enviar · revisar" : `Guardado ${hace(i.creado)}`));
        return li;
      }));
    });

    // Panel con el detalle
    const contenedor = $("[data-cola-items]");
    if (contenedor) {
      contenedor.replaceChildren(...items.map((i) => {
        const li = elemento("li", "item-cola");
        li.dataset.estado = i.estado;
        const cabeza = elemento("div", "item-cola__cabeza");
        const estado = elemento("span", "pastilla" + (i.estado === "error" ? " pastilla--error" : ""), i.estado === "error" ? "Rechazado" : "Pendiente");
        cabeza.append(elemento("strong", null, i.titulo), estado);
        li.append(cabeza, elemento("span", null, i.resumen), elemento("small", null, `Guardado ${hace(i.creado)}`));
        if (i.error) li.append(elemento("span", "item-cola__error", i.error));
        const acciones = elemento("div", "item-cola__acciones");
        if (i.estado === "error") {
          const reintentar = elemento("button", "boton boton--chico boton--suave", "Reintentar");
          reintentar.type = "button";
          reintentar.addEventListener("click", async () => { await Cola.reintentar(i.id); sincronizar(); });
          acciones.append(reintentar);
        }
        const descartar = elemento("button", "boton boton--chico boton--fantasma", "Descartar");
        descartar.type = "button";
        descartar.addEventListener("click", async () => {
          if (confirm(`¿Descartar «${i.titulo}»? No se enviará.`)) await Cola.borrar(i.id);
        });
        acciones.append(descartar);
        li.append(acciones);
        return li;
      }));
      if (!items.length) contenedor.replaceChildren(elemento("li", "vacio", "No hay nada pendiente."));
    }
  }

  const panel = $("[data-cola-panel]");
  if (panel) {
    $("[data-cola-abrir]").addEventListener("click", () => { pintarCola(); panel.showModal(); });
    $("[data-cola-cerrar]").addEventListener("click", () => panel.close());
    panel.addEventListener("click", (e) => { if (e.target === panel) panel.close(); });
    $("[data-cola-sincronizar]").addEventListener("click", async () => {
      if (!navigator.onLine) { toast("Sigues sin conexión. Se enviará solo cuando vuelva la señal.", { tipo: "aviso" }); return; }
      await sincronizar();
    });
  }

  // ---------- Sincronización ----------

  async function sincronizar() {
    if (usuarioId == null || !window.Cola || !navigator.onLine) return;
    try { await Cola.sincronizar(); } catch (e) { console.warn("No se pudo sincronizar", e); }
  }

  if (window.Cola && usuarioId != null) {
    Cola.escuchar((mensaje) => {
      if (mensaje.tipo === "enviando") { pintarCola(true); return; }
      pintarCola();
      if (mensaje.tipo !== "sincronizado") return;
      const { enviados, rechazados, sinSesion } = mensaje.resultado;
      if (enviados.length) {
        const texto = enviados.length === 1
          ? `Se envió: ${enviados[0].titulo}${enviados[0].datos && enviados[0].datos.lote && enviados[0].tipo === "lote" ? ` (código ${enviados[0].datos.lote.codigo})` : ""}.`
          : `Se enviaron ${enviados.length} registros que estaban pendientes.`;
        toast(texto, { tipo: "ok", accion: { texto: "Actualizar", hacer: () => location.reload() }, duracion: 10000 });
      }
      if (rechazados.length) {
        toast(`${rechazados.length === 1 ? "Un registro" : rechazados.length + " registros"} no se pudo enviar. Revísalo en Pendientes.`, {
          tipo: "error", accion: { texto: "Revisar", hacer: () => { pintarCola(); panel && panel.showModal(); } }, duracion: 12000,
        });
      }
      if (sinSesion) toast("Inicia sesión para enviar lo pendiente.", { tipo: "aviso" });
    });

    pintarCola();
    sincronizar();
    setInterval(async () => {
      const items = await Cola.listar(usuarioId).catch(() => []);
      if (items.some((i) => i.estado === "pendiente")) sincronizar();
    }, 30000);
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") sincronizar(); });
  }

  // ---------- Cerrar sesión: borrar las páginas guardadas en este equipo ----------

  $$("form[data-cerrar-sesion]").forEach((form) => {
    form.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      if (window.Cola && usuarioId != null) {
        const pendientes = await Cola.listar(usuarioId).catch(() => []);
        if (pendientes.length && !confirm(
          `Tienes ${pendientes.length} registro(s) sin enviar. Quedarán guardados en este equipo y se enviarán cuando vuelvas a iniciar sesión. ¿Cerrar sesión igual?`
        )) return;
      }
      if ("caches" in window) {
        const nombres = await caches.keys();
        await Promise.all(nombres.filter((n) => n.startsWith("agrotracker-paginas")).map((n) => caches.delete(n)));
      }
      form.submit();
    });
  });

  // ---------- Clima: ubicación del campo y gráfico ----------

  $$("[data-pos-x]").forEach((el) => { el.style.left = el.dataset.posX + "%"; });

  $$("[data-usar-ubicacion]").forEach((boton) => {
    const form = boton.form;
    const estado = $("[data-ubicacion-estado]", form);
    if (!("geolocation" in navigator)) { boton.hidden = true; return; }
    boton.addEventListener("click", () => {
      boton.setAttribute("aria-busy", "true");
      estado.textContent = "Buscando tu ubicación…";
      navigator.geolocation.getCurrentPosition(
        (posicion) => {
          boton.removeAttribute("aria-busy");
          form.elements.latitud.value = posicion.coords.latitude.toFixed(6);
          form.elements.longitud.value = posicion.coords.longitude.toFixed(6);
          estado.textContent = `Ubicación encontrada (precisión de unos ${Math.round(posicion.coords.accuracy)} m). Revisa y guarda.`;
        },
        () => {
          boton.removeAttribute("aria-busy");
          estado.textContent = "No pudimos obtener tu ubicación. Revisa el permiso del navegador o escribe las coordenadas.";
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
      );
    });
  });

  // ---------- Entrada: mostrar el formulario al elegir "Iniciar sesión" ----------

  // Si la persona tocó "Iniciar sesión" antes de que cargara este script, el enlace ya saltó al
  // formulario (#iniciar-sesion): se deja visible en vez de esconderlo bajo sus dedos.
  $$("[data-oculto-con-js]").forEach((el) => { if (location.hash !== "#" + el.id) el.hidden = true; });
  $$("[data-mostrar]").forEach((enlace) => {
    enlace.addEventListener("click", (evento) => {
      const destino = document.getElementById(enlace.dataset.mostrar);
      if (!destino) return;
      evento.preventDefault();
      destino.hidden = false;
      enlace.setAttribute("aria-expanded", "true");
      destino.scrollIntoView({ behavior: "smooth", block: "start" });
      const primero = $("input:not([type=hidden])", destino);
      if (primero) setTimeout(() => primero.focus(), 250);
    });
  });

  // ---------- Escáner de QR (cámara + BarcodeDetector del navegador) ----------

  function codigoDesdeQr(texto) {
    // Los QR de AgroTracker llevan la URL de la ficha (…/Trazabilidad?codigo=XXXX). Solo se toma el
    // código: nunca se navega a la URL leída, así un QR ajeno no puede llevar a otro sitio.
    try {
      const url = new URL(texto);
      const codigo = url.searchParams.get("codigo");
      if (codigo) return codigo;
    } catch (_) { /* no es una URL */ }
    const limpio = texto.trim();
    return /^[A-Za-z0-9-]{4,40}$/.test(limpio) ? limpio : null;
  }

  $$("[data-escaner]").forEach((caja) => {
    const estado = $("[data-escaner-estado]", caja);
    const visor = $("[data-escaner-visor]", caja);
    const video = $("[data-escaner-video]", caja);
    const iniciar = $("[data-escaner-iniciar]", caja);
    const alternativa = $("[data-escaner-alternativa]", caja);
    const soportado = "BarcodeDetector" in window && navigator.mediaDevices && navigator.mediaDevices.getUserMedia;
    let flujo = null;

    function detener() {
      if (flujo) flujo.getTracks().forEach((pista) => pista.stop());
      flujo = null;
    }
    window.addEventListener("pagehide", detener);

    if (!soportado) {
      iniciar.hidden = true;
      alternativa.hidden = false;
      return;
    }

    iniciar.addEventListener("click", async () => {
      let detector;
      try {
        const formatos = await BarcodeDetector.getSupportedFormats();
        if (!formatos.includes("qr_code")) throw new Error("sin qr_code");
        detector = new BarcodeDetector({ formats: ["qr_code"] });
        flujo = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      } catch (e) {
        detener();
        iniciar.hidden = true;
        alternativa.hidden = false;
        estado.textContent = e && e.name === "NotAllowedError"
          ? "No diste permiso para usar la cámara. Puedes activarlo en los ajustes del navegador o escribir el código."
          : "No pudimos abrir la cámara.";
        return;
      }
      video.srcObject = flujo;
      await video.play();
      visor.hidden = false;
      iniciar.hidden = true;
      estado.textContent = "Buscando un código QR…";

      // Se lee desde un canvas con el cuadro actual: más confiable que leer el <video> directamente.
      const lienzo = document.createElement("canvas");
      const pincel = lienzo.getContext("2d", { willReadFrequently: true });
      const buscar = async () => {
        if (!flujo) return;
        try {
          if (!video.videoWidth) throw new Error("sin cuadro");
          lienzo.width = video.videoWidth;
          lienzo.height = video.videoHeight;
          pincel.drawImage(video, 0, 0);
          const encontrados = await detector.detect(lienzo);
          for (const encontrado of encontrados) {
            const codigo = codigoDesdeQr(encontrado.rawValue || "");
            if (codigo) {
              estado.textContent = "¡Código leído! Abriendo la ficha…";
              detener();
              if (navigator.vibrate) navigator.vibrate(80);
              window.location.assign(`${caja.dataset.destino}?codigo=${encodeURIComponent(codigo)}`);
              return;
            }
            estado.textContent = "Ese QR no es de AgroTracker. Prueba con el de la caja o etiqueta.";
          }
        } catch (_) { /* cuadro sin imagen todavía */ }
        setTimeout(buscar, 250);
      };
      buscar();
    });
  });

  // ---------- Detalles de la interfaz ----------

  $$("form[data-requiere-red]").forEach((form) => {
    form.addEventListener("submit", (evento) => {
      if (!navigator.onLine) {
        evento.preventDefault();
        toast("Esto necesita conexión a internet. Inténtalo cuando vuelva la señal.", { tipo: "aviso" });
        return;
      }
      ocupado(form, true);
      if (form.dataset.cargando) $('button[type="submit"]', form).lastChild.textContent = " " + form.dataset.cargando;
    });
  });

  $$("form[data-confirmar]").forEach((form) => {
    form.addEventListener("submit", (e) => { if (!confirm(form.dataset.confirmar)) e.preventDefault(); });
  });

  $$("[data-imprimir]").forEach((b) => b.addEventListener("click", () => window.print()));
  $$("[data-recargar]").forEach((b) => b.addEventListener("click", () => location.reload()));
  $$("form[data-autoenvio] select").forEach((s) => s.addEventListener("change", () => s.form.submit()));

  $$("form[data-calculo-total]").forEach((form) => {
    const caja = $("[data-total]", form);
    const valor = $("[data-total-valor]", form);
    const calcular = () => {
      const kilos = parseFloat(form.elements.kilos.value);
      const precio = parseFloat(form.elements.precio_por_kilo.value);
      const hay = kilos > 0 && precio > 0;
      caja.hidden = !hay;
      if (hay) valor.textContent = pesos.format(kilos * precio);
    };
    form.addEventListener("input", calcular);
    form.addEventListener("reset", () => setTimeout(calcular));
  });

  $$("[data-filtro-tabla]").forEach((entrada) => {
    const tabla = document.getElementById(entrada.dataset.filtroTabla);
    const vacio = $(`[data-filtro-vacio="${entrada.dataset.filtroTabla}"]`);
    entrada.addEventListener("input", () => {
      const q = entrada.value.trim().toLowerCase();
      let visibles = 0;
      $$("tbody tr", tabla).forEach((fila) => {
        const ver = !q || fila.textContent.toLowerCase().includes(q);
        fila.hidden = !ver;
        if (ver) visibles += 1;
      });
      if (vacio) vacio.hidden = visibles > 0;
    });
  });
})();
