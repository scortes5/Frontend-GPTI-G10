"""Iniciar y cerrar sesión, y recuperar la contraseña con un código por correo."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

import api
import sesion
from rutas.permisos import destino_seguro

bp = Blueprint("auth", __name__)

_EMAIL_RECUPERACION = "recuperacion_email"


@bp.route("/login", methods=["GET", "POST"])
def login():
    siguiente = destino_seguro(request.values.get("siguiente"), url_for("panel.inicio"))
    if sesion.activa():
        return redirect(siguiente)

    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        clave = request.form.get("clave", "")
        if not email or not clave:
            flash("Escribe tu correo y tu contraseña.", "error")
        else:
            try:
                respuesta = api.login(email, clave)
            except api.BackendError as e:
                flash(str(e), "error")
            else:
                sesion.iniciar(respuesta["access_token"], respuesta["usuario"])
                return redirect(siguiente)
    return render_template("login.html", email=email, siguiente=siguiente), 200 if request.method == "GET" else 400


@bp.post("/logout")
def logout():
    if sesion.activa():
        try:
            api.logout()  # revoca el token en el backend
        except api.BackendError:
            pass  # si ya expiró o no hay conexión, igual se cierra la sesión local
    sesion.cerrar()
    flash("Cerraste sesión.", "ok")
    return redirect(url_for("auth.login"))


@bp.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    email = session.get(_EMAIL_RECUPERACION)
    if request.method == "GET":
        return render_template("recuperar.html", email=email)

    paso = request.form.get("paso")
    if paso == "otro":
        session.pop(_EMAIL_RECUPERACION, None)
        return redirect(url_for("auth.recuperar"))

    if paso == "pedir":
        email = request.form.get("email", "").strip()
        if not email:
            flash("Escribe tu correo.", "error")
            return redirect(url_for("auth.recuperar"))
        try:
            api.solicitar_codigo(email)
        except api.BackendError as e:
            flash(str(e), "error")
            return redirect(url_for("auth.recuperar"))
        session[_EMAIL_RECUPERACION] = email
        return redirect(url_for("auth.recuperar"))

    # paso == "cambiar"
    if not email:
        return redirect(url_for("auth.recuperar"))
    codigo = request.form.get("codigo", "").strip()
    clave = request.form.get("clave", "")
    confirmacion = request.form.get("confirmacion", "")
    if not (codigo.isdigit() and len(codigo) == 6):
        flash("El código tiene 6 dígitos.", "error")
    elif len(clave) < 8 or clave != confirmacion:
        flash("Las contraseñas deben coincidir y tener al menos 8 caracteres.", "error")
    else:
        try:
            api.restablecer_clave(email, codigo, clave)
        except api.BackendError as e:
            flash(str(e), "error")
        else:
            session.pop(_EMAIL_RECUPERACION, None)
            flash("Tu contraseña cambió. Ya puedes iniciar sesión.", "ok")
            return redirect(url_for("auth.login"))
    return redirect(url_for("auth.recuperar"))
