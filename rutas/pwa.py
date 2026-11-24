"""Piezas de la PWA: service worker, manifiesto, página sin conexión y el QR (vía Flask para guardarlo en caché)."""
from flask import Blueprint, Response, current_app, render_template, send_from_directory

import api

bp = Blueprint("pwa", __name__)


@bp.get("/sw.js")
def service_worker():
    # Se sirve desde la raíz para que su alcance cubra toda la aplicación.
    response = send_from_directory(current_app.static_folder, "js/sw.js", mimetype="text/javascript")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@bp.get("/manifest.webmanifest")
def manifiesto():
    response = send_from_directory(current_app.static_folder, "manifest.webmanifest")
    response.mimetype = "application/manifest+json"
    return response


@bp.get("/offline")
def sin_conexion():
    # Se guarda en caché al instalar la PWA: se renderiza sin datos del usuario.
    return render_template("offline.html", usuario=None, es_admin=False)


@bp.get("/qr/<codigo>.png")
def qr(codigo):
    response = Response(api.qr_png(codigo), mimetype="image/png")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response
