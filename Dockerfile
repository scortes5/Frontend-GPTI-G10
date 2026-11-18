# Frontend de AgroTracker (Flask + PWA) servido con gunicorn.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8501

WORKDIR /srv
RUN useradd --create-home --uid 10001 agrotracker

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py api.py sesion.py formularios.py ./
COPY rutas ./rutas
COPY templates ./templates
COPY static ./static
USER agrotracker

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/offline', timeout=4)"

# --preload crea la app una vez antes de abrir los workers: todos comparten la misma configuración.
CMD ["sh", "-c", "exec gunicorn --preload --workers 2 --threads 4 --bind 0.0.0.0:${PORT} --access-logfile - app:app"]
