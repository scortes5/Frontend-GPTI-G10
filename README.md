# Frontend AgroTracker · GPTI G10

Interfaz (Streamlit) del sistema de trazabilidad y gestión de cosecha para la Cooperativa Newen al Sur.

## Estructura

```
app.py                   # punto de entrada: menú según sesión y rol
sesion.py                # sesión del usuario (token y datos), una por pestaña
api.py                   # llamadas al backend
vistas/login.py          # iniciar sesión
vistas/inicio.py         # dashboard con indicadores
vistas/lotes.py          # registrar y editar lotes (eliminar: solo admin)
vistas/ventas.py         # ventas por lote
vistas/trazabilidad.py   # ficha del lote (destino del QR), reporte por correo y recomendación IA
vistas/usuarios.py       # gestión de usuarios (solo admin)
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
```

## Correr

Con el backend corriendo:

```bash
streamlit run app.py
```

Abre http://localhost:8501

## Configuración

La única variable es `BACKEND_URL` (URL de la API). La arquitectura de despliegue está
en el README del backend.

## Manual de usuario (piloto)

AgroTracker sirve para registrar cada cosecha como un **lote**, anotar a quién se vende y
mostrar su origen con un **código QR**.

### Entrar

1. Abre la página que te entregó la cooperativa.
2. Escribe tu **correo** y **contraseña** y presiona **Entrar**.
3. Para salir, usa **Cerrar sesión** en el menú de la izquierda.

¿No tienes cuenta o olvidaste tu contraseña? Pídela a la directiva de la cooperativa.

### Si eres productor

- **Registrar una cosecha:** menú **Lotes** → completa cultivo, kilos y fecha → **Guardar**.
  Aparece el código QR del lote: guárdalo o imprímelo para la caja o el envío.
- **Corregir un lote:** en **Lotes**, baja a **Editar**, elige el lote, cambia los datos y
  presiona **Guardar cambios**.
- **Registrar una venta:** menú **Ventas** → elige el lote → comprador, kilos, precio por kilo
  y fecha → **Registrar**. No se puede vender más de lo que queda disponible.
- **Ver el historial de un lote:** menú **Trazabilidad** → escribe el código del lote.
  Ahí puedes **enviar el reporte por correo** (por ejemplo, a un auditor) y pedir una
  **recomendación** para conservar y vender lo que queda.
- En **Inicio** ves un resumen de tus kilos e ingresos.

Solo ves tus propios lotes.

### Si eres administrador (directiva)

Puedes hacer todo lo anterior con los lotes de **todos** los socios, y además:

- **Crear cuentas:** menú **Usuarios** → nombre, correo, contraseña inicial y rol → **Crear**.
  Entrega el correo y la contraseña al socio.
- **Quitar el acceso o cambiar el rol:** en **Usuarios**, elige a la persona, desmarca
  **Puede iniciar sesión** o cambia el rol y presiona **Guardar cambios**.
- **Eliminar un lote:** en **Lotes**, marca la confirmación y presiona **Eliminar lote**
  (también borra sus ventas).
- En **Inicio** ves el resumen de toda la cooperativa.

### Para compradores y auditores (sin cuenta)

Escanea el código QR del lote con la cámara del teléfono. Se abre la ficha con el origen del
lote: productor, cultivo, fecha de cosecha y kilos. Las ventas y precios no se muestran.
