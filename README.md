# Frontend AgroTracker · GPTI G10

Interfaz (Streamlit) del sistema de trazabilidad y gestión de cosecha para la Cooperativa Newen al Sur.

## Estructura

```
app.py                  # inicio / dashboard con indicadores
pages/1_Lotes.py        # registrar, editar y eliminar lotes
pages/2_Ventas.py       # ventas por lote
pages/3_Trazabilidad.py # ficha pública del lote (destino del QR), reporte por correo y recomendación IA
api.py          # llamadas al backend
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
