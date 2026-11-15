"""Punto de entrada del frontend AgroTracker (Flask).

Las páginas se renderizan en el servidor; el navegador solo recibe HTML y una cookie de sesión
firmada. El JavaScript agrega la cola sin conexión y el service worker (PWA).
"""
import logging
import os
import secrets
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for
from markupsafe import Markup, escape

import api
import sesion
from rutas import auth, clima, cola, panel, pwa, trazabilidad

load_dotenv()

ROLES = {"admin": "Administrador", "productor": "Productor"}
METODOS_CON_EFECTO = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    clave = os.getenv("FLASK_SECRET_KEY")
    if not clave:
        clave = secrets.token_urlsafe(32)
        logging.getLogger(__name__).warning(
            "FLASK_SECRET_KEY no está definida: se usa una clave temporal y las sesiones se pierden al reiniciar."
        )
    app.config.update(
        SECRET_KEY=clave,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SEGURA", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    if config:
        app.config.update(config)

    for blueprint in (auth.bp, panel.bp, clima.bp, trazabilidad.bp, cola.bp, pwa.bp):
        app.register_blueprint(blueprint)

    app.jinja_env.globals["csrf_token"] = sesion.csrf_token  # global: lo usan las macros importadas
    registrar_filtros(app)
    registrar_seguridad(app)
    registrar_errores(app)

    @app.context_processor
    def contexto():
        return {
            "usuario": sesion.usuario(),
            "es_admin": sesion.es_admin(),
            "ROLES": ROLES,
            "hoy": date.today().isoformat(),
        }

    return app


def registrar_seguridad(app: Flask) -> None:
    @app.before_request
    def verificar_csrf():
        if request.method not in METODOS_CON_EFECTO or app.config.get("TESTING_SIN_CSRF"):
            return None
        valor = request.headers.get("X-CSRF") or request.form.get("csrf")
        if sesion.csrf_valido(valor):
            return None
        if es_peticion_json():
            return jsonify(detail="La página caducó. Recárgala e intenta de nuevo.", csrf=True), 403
        flash("La página caducó. Intenta de nuevo.", "error")
        return redirect(request.referrer or url_for("panel.inicio"))

    @app.after_request
    def cabeceras(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'; "
            "frame-src https://www.openstreetmap.org",  # mapa del campo
        )
        if response.mimetype == "text/html":
            # Las páginas con datos del usuario no quedan en la caché HTTP; el service worker
            # guarda su propia copia para verlas sin conexión y la borra al cerrar sesión.
            response.headers["Cache-Control"] = "no-store"
            if g.get("con_avisos"):
                response.headers["X-Con-Avisos"] = "1"
        return response


def registrar_errores(app: Flask) -> None:
    @app.errorhandler(api.SesionExpirada)
    def sesion_expirada(e):
        if es_peticion_json():
            return jsonify(detail=str(e)), 401
        flash(str(e), "error")
        return redirect(url_for("auth.login", siguiente=request.full_path))

    @app.errorhandler(api.BackendError)
    def error_backend(e):
        if es_peticion_json():
            return jsonify(detail=str(e)), e.status
        return render_template("error.html", mensaje=str(e)), e.status

    @app.errorhandler(404)
    def no_encontrado(_):
        if es_peticion_json():
            return jsonify(detail="No encontrado."), 404
        return render_template("error.html", mensaje="Esta página no existe."), 404


def es_peticion_json() -> bool:
    return request.path.startswith("/api/")


def registrar_filtros(app: Flask) -> None:
    @app.template_filter("kg")
    def kg(valor) -> str:
        return f"{numero(valor, 1)} kg"

    @app.template_filter("num")
    def num(valor, decimales: int = 1) -> str:
        return numero(valor, decimales)

    @app.template_filter("clp")
    def clp(valor) -> str:
        return f"${numero(valor, 0)}"

    @app.template_filter("fecha")
    def fecha(valor) -> str:
        try:
            return date.fromisoformat(str(valor)[:10]).strftime("%d-%m-%Y")
        except ValueError:
            return str(valor)

    @app.template_filter("hora")
    def hora(valor) -> str:
        try:
            return datetime.fromisoformat(str(valor)).strftime("%d-%m %H:%M")
        except ValueError:
            return str(valor)

    app.template_filter("texto_ia")(texto_ia)


def numero(valor, decimales: int) -> str:
    """Formato chileno: 12.345,5 (sin decimales si son cero)."""
    valor = float(valor or 0)
    texto = f"{valor:,.{decimales}f}"
    if decimales and texto.endswith("0" * decimales):
        texto = texto[: -(decimales + 1)]
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def texto_ia(texto: str) -> Markup:
    """Markdown mínimo y seguro para la recomendación: párrafos, listas y **negritas**. Todo se escapa."""
    import re

    def en_linea(linea: str) -> str:
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(escape(linea)))

    html, en_lista = [], False
    for linea in (texto or "").splitlines():
        linea = linea.strip()
        item = re.match(r"^([-*]|\d+\.)\s+(.*)", linea)
        if item:
            if not en_lista:
                html.append("<ul>")
                en_lista = True
            html.append(f"<li>{en_linea(item.group(2))}</li>")
            continue
        if en_lista:
            html.append("</ul>")
            en_lista = False
        if not linea:
            continue
        titulo = re.match(r"^#{1,6}\s+(.*)", linea)
        if titulo:
            html.append(f"<h4>{en_linea(titulo.group(1))}</h4>")
        else:
            html.append(f"<p>{en_linea(linea)}</p>")
    if en_lista:
        html.append("</ul>")
    return Markup("".join(html))


app = create_app()

if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8501")), debug=os.getenv("FLASK_DEBUG") == "1")
