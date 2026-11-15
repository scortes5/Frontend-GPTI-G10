# Frontend AgroTracker · GPTI G10

Interfaz web (Flask) del sistema de trazabilidad y gestión de cosecha para la Cooperativa Newen al Sur.
Es una **PWA**: se instala en el teléfono y sigue funcionando sin señal en el campo.

## Arquitectura

- **Flask renderiza en el servidor** (plantillas Jinja). El token del backend vive en una cookie de
  sesión firmada y `HttpOnly`: el navegador nunca lo ve. Todos los formularios llevan token CSRF.
- **Mejora progresiva:** sin JavaScript todo funciona con formularios normales. Con JavaScript se
  agregan la cola sin conexión y el service worker.
- **Cola sin conexión** (`static/js/cola.js`, IndexedDB): registrar lote, editar lote y registrar
  venta se pueden hacer sin señal. Quedan guardados en el equipo y se reenvían en orden a la API
  JSON de Flask (`/api/...`) cuando vuelve la conexión: al recuperar la red, cada 30 s, al abrir la
  app o, en Chrome/Android, con **Background Sync** aunque la app esté cerrada. Un candado compartido
  (Web Locks) evita envíos duplicados entre pestañas y el service worker.
  - Error de red o servidor caído (5xx) → se reintenta.
  - Sesión expirada (401) → se envía después de volver a iniciar sesión (solo con el mismo usuario).
  - Datos rechazados (409, 422; p. ej. vender más kilos de los disponibles) → queda marcado y el
    usuario lo reintenta o descarta desde **Pendientes**.
- **Service worker** (`static/js/sw.js`, servido en `/sw.js`): guarda CSS/JS/iconos, las páginas
  visitadas (red primero, copia guardada sin señal, `/offline` si no hay copia) y los QR. Al cerrar
  sesión se borran las páginas guardadas (equipos compartidos).

## Estructura

```
app.py                 # crea la app Flask: seguridad (CSRF, CSP, cookies), filtros y errores
api.py                 # llamadas al backend (desde el servidor)
sesion.py              # sesión en cookie firmada y token CSRF
formularios.py         # validación compartida por formularios y API de la cola
rutas/auth.py          # iniciar/cerrar sesión, recuperar contraseña
rutas/panel.py         # inicio, lotes, ventas, usuarios (admin)
rutas/clima.py         # dashboard de clima: mapa del campo, estación Agromet, alertas, gráfico, IA
rutas/trazabilidad.py  # ficha del lote (destino del QR), reporte por correo, recomendación IA
rutas/cola.py          # API JSON que usa la cola sin conexión
rutas/pwa.py           # /sw.js, manifiesto, /offline y QR
templates/             # páginas (Jinja)
static/css/app.css     # estilos (móvil primero, modo oscuro)
static/js/app.js       # interfaz: formularios con cola, pendientes, avisos
static/js/cola.js      # cola en IndexedDB (la usan la página y el service worker)
static/js/sw.js        # service worker
static/manifest.webmanifest, static/img/   # PWA instalable
tests/                 # pytest con backend simulado
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # completa FLASK_SECRET_KEY
```

## Correr

Con el backend corriendo:

```bash
python app.py
```

Abre http://localhost:8501 (el mismo puerto que usaba Streamlit, así el `FRONTEND_URL` del backend,
los QR ya impresos y CORS siguen sirviendo).

En producción: `gunicorn -w 2 -b 0.0.0.0:8501 app:app`, detrás de HTTPS y con `COOKIE_SEGURA=1`.
El service worker solo funciona en `localhost` o con HTTPS.

## Tests

```bash
pytest
```

## Configuración

| Variable | Uso |
|---|---|
| `BACKEND_URL` | URL de la API. Flask la llama desde el servidor. |
| `FLASK_SECRET_KEY` | Firma la cookie de sesión. Sin ella se usa una temporal y las sesiones se pierden al reiniciar. |
| `PORT` | Puerto (8501 por defecto). |
| `COOKIE_SEGURA` | `1` con HTTPS. |

El mapa del campo se muestra con OpenStreetMap (iframe permitido en la CSP con `frame-src`).

La arquitectura de despliegue está en el README del backend.

## Manual de usuario (piloto)

AgroTracker sirve para registrar cada cosecha como un **lote**, anotar a quién se vende y
mostrar su origen con un **código QR**.

### Entrar

1. Abre la página que te entregó la cooperativa.
2. Escribe tu **correo** y **contraseña** y presiona **Entrar**.
3. Para salir, usa **Cerrar sesión** (menú de la izquierda en computador, botón arriba a la derecha en el teléfono). Hazlo siempre en computadores
   compartidos.

¿No tienes cuenta? Pídela a la directiva de la cooperativa.

### Olvidé mi contraseña

1. En la pantalla de entrada presiona **¿Olvidaste tu contraseña?**
2. Escribe tu correo y presiona **Enviar código**. Te llegará un correo con un código de 6
   dígitos (revisa también spam).
3. Escribe el código y tu nueva contraseña dos veces, y presiona **Cambiar contraseña**.

El código dura 15 minutos y sirve una sola vez. Al cambiar la contraseña se cierra tu sesión en
todos los dispositivos. Si fallas 5 veces seguidas al entrar, espera 15 minutos o recupera tu
contraseña.

### Instalar en el teléfono

Abre la página en Chrome (Android) o Safari (iPhone) y elige **Agregar a la pantalla de inicio**.
Queda como una aplicación más.

### Sin señal

Si se corta la conexión aparece un aviso arriba. Igual puedes **registrar lotes, editarlos y
anotar ventas**: quedan guardados en el teléfono y se envían solos cuando vuelve la señal. Arriba
verás cuántos hay **pendientes**; tócalo para verlos, enviarlos o descartarlos. Si alguno no se
pudo guardar (por ejemplo, vendiste más kilos de los que quedaban), aparece en rojo para que lo
revises. Las páginas que ya abriste se pueden mirar sin señal.

### Si eres productor

- **Registrar una cosecha:** menú **Lotes** → completa cultivo, kilos y fecha → **Guardar**.
  Aparece el código QR del lote: guárdalo o imprímelo para la caja o el envío.
- **Corregir un lote:** en **Lotes**, presiona **Ver y editar** en el lote, cambia los datos y
  presiona **Guardar cambios**. Ahí también puedes **imprimir la etiqueta** con el QR.
- **Registrar una venta:** menú **Ventas** → elige el lote → comprador, kilos, precio por kilo
  y fecha → **Registrar**. No se puede vender más de lo que queda disponible.
- **Ver el historial de un lote:** menú **Trazabilidad** → escribe el código del lote.
  Ahí puedes **enviar el reporte por correo** (por ejemplo, a un auditor) y pedir una
  **recomendación** para conservar y vender lo que queda.
- **Clima de tu campo:** menú **Clima**. La primera vez escribe el nombre de tu campo y presiona
  **Usar mi ubicación actual** (hazlo parado en el campo) o escribe las coordenadas, y
  **Guardar ubicación**. Verás el mapa, el clima de la estación más cercana de la Red
  Agroclimática Nacional, avisos de helada, lluvia, calor, viento u hongos, y el gráfico de las
  últimas 48 horas. Presiona **¿Qué debo tomar en consideración?** para una recomendación con IA.
- En **Inicio** ves un resumen de tus kilos e ingresos, y el clima de tu campo.

Solo ves tus propios lotes.

### Si eres administrador (directiva)

Puedes hacer todo lo anterior con los lotes de **todos** los socios, y además:

- **Crear cuentas:** menú **Usuarios** → nombre, correo, contraseña inicial y rol → **Crear**.
  Entrega el correo y la contraseña al socio.
- **Quitar el acceso o cambiar el rol:** en **Usuarios**, junto a la persona, desmarca
  **Puede entrar** o cambia el rol y presiona **Guardar**.
- **Eliminar un lote:** en **Lotes** → **Ver y editar**, marca la confirmación y presiona **Eliminar lote**
  (también borra sus ventas).
- En **Inicio** ves el resumen de toda la cooperativa.
- En **Clima** puedes elegir el campo de cualquier socio en **Ver campo de**.

### Para compradores y auditores (sin cuenta)

Escanea el código QR del lote con la cámara del teléfono. Se abre la ficha con el origen del
lote: productor, cultivo, fecha de cosecha y kilos. Las ventas y precios no se muestran.
