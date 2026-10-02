# Frontend AgroTracker · GPTI G10

Interfaz (Streamlit) del sistema de trazabilidad y gestión de cosecha para la Cooperativa Newen al Sur.

## Estructura

```
app.py          # inicio / dashboard
pages/          # una página por módulo (Streamlit las agrega al menú)
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
