# Frontend AgroTracker · GPTI G10

Interfaz (Streamlit) del sistema de trazabilidad y gestión de cosecha para la Cooperativa Newen al Sur.

## Estructura

```
app.py                  # inicio / dashboard con indicadores
pages/1_Lotes.py        # registrar, editar y eliminar lotes
pages/2_Ventas.py       # ventas por lote
pages/3_Trazabilidad.py # ficha pública del lote (destino del QR) + recomendación IA
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

## Despliegue (Streamlit Community Cloud)

1. En [share.streamlit.io](https://share.streamlit.io) crear una app desde este repo con `app.py`.
2. En **Settings > Secrets** agregar:

   ```toml
   BACKEND_URL = "https://<api-en-render>.onrender.com"
   ```

   Streamlit expone los secrets de primer nivel como variables de entorno, que lee `api.py`.
3. Copiar la URL de la app en `FRONTEND_URL` del backend para que funcionen CORS y el QR.
