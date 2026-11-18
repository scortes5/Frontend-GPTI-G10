"""Páginas con sesión: inicio, lotes, ventas y usuarios."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

import api
import formularios
import sesion
from rutas.permisos import requiere_sesion, solo_admin

bp = Blueprint("panel", __name__)


@bp.get("/")
@requiere_sesion
def inicio():
    resumen = api.resumen()
    cultivos = sorted(resumen["kilos_por_cultivo"].items(), key=lambda par: par[1], reverse=True)
    maximo = max((kilos for _, kilos in cultivos), default=0)
    return render_template("inicio.html", resumen=resumen, cultivos=cultivos, maximo=maximo, **_clima_resumido())


def _clima_resumido() -> dict:
    """Tarjeta de clima en Inicio. Si el clima no está disponible, Inicio se muestra igual."""
    try:
        return {"clima": api.clima(), "sin_campo": False}
    except api.ErrorDeDatos as e:
        return {"clima": None, "sin_campo": e.status == 404}
    except api.BackendError:
        return {"clima": None, "sin_campo": False}


# ---------- Lotes ----------


def _pagina_lotes(valores=None, status=200):
    return render_template("lotes.html", lotes=api.listar_lotes(), valores=valores or {}), status


@bp.get("/lotes")
@requiere_sesion
def lotes():
    return _pagina_lotes()


@bp.post("/lotes")
@requiere_sesion
def crear_lote():
    datos, error = formularios.lote(request.form)
    if error:
        flash(error, "error")
        return _pagina_lotes(request.form, 400)
    try:
        lote = api.crear_lote(datos)
    except api.ErrorDeDatos as e:
        flash(f"No se pudo guardar el lote. {e}", "error")
        return _pagina_lotes(request.form, 400)
    flash(f"Lote {lote['codigo']} registrado. Guarda o imprime su código QR.", "ok")
    return redirect(url_for("panel.lote", codigo=lote["codigo"]))


@bp.get("/lotes/<codigo>")
@requiere_sesion
def lote(codigo):
    traza = api.trazabilidad(codigo)
    return render_template("lote.html", traza=traza, lote=traza["lote"], valores=traza["lote"])


@bp.post("/lotes/<codigo>")
@requiere_sesion
def editar_lote(codigo):
    datos, error = formularios.lote(request.form)
    if not error:
        try:
            api.actualizar_lote(codigo, datos)
        except api.ErrorDeDatos as e:
            error = f"No se pudo actualizar el lote. {e}"
    if error:
        flash(error, "error")
        traza = api.trazabilidad(codigo)
        return render_template("lote.html", traza=traza, lote=traza["lote"], valores=request.form), 400
    flash("Lote actualizado.", "ok")
    return redirect(url_for("panel.lote", codigo=codigo))


@bp.post("/lotes/<codigo>/eliminar")
@solo_admin
def eliminar_lote(codigo):
    if request.form.get("confirmar") != "si":
        flash("Marca la confirmación para eliminar el lote.", "error")
        return redirect(url_for("panel.lote", codigo=codigo))
    api.eliminar_lote(codigo)
    flash(f"Lote {codigo} eliminado junto con sus ventas.", "ok")
    return redirect(url_for("panel.lotes"))


# ---------- Ventas ----------


def _pagina_ventas(codigo: str | None, valores=None, status=200):
    lotes = api.listar_lotes()
    if not lotes:
        return render_template("ventas.html", lotes=[], lote=None, traza=None, valores={}), status
    codigos = [l["codigo"] for l in lotes]
    codigo = codigo if codigo in codigos else codigos[0]
    traza = api.trazabilidad(codigo)
    return (
        render_template("ventas.html", lotes=lotes, lote=traza["lote"], traza=traza, valores=valores or {}),
        status,
    )


@bp.get("/ventas")
@requiere_sesion
def ventas():
    return _pagina_ventas(request.args.get("codigo"))


@bp.post("/ventas/<codigo>")
@requiere_sesion
def registrar_venta(codigo):
    datos, error = formularios.venta(request.form)
    if not error:
        try:
            api.registrar_venta(codigo, datos)
        except api.ErrorDeDatos as e:
            error = f"No se pudo registrar la venta. {e}"
    if error:
        flash(error, "error")
        return _pagina_ventas(codigo, request.form, 400)
    flash("Venta registrada.", "ok")
    return redirect(url_for("panel.ventas", codigo=codigo))


# ---------- Usuarios (solo administrador) ----------


@bp.get("/usuarios")
@solo_admin
def usuarios():
    return render_template("usuarios.html", usuarios=api.listar_usuarios(), valores={})


@bp.post("/usuarios")
@solo_admin
def crear_usuario():
    datos, error = formularios.usuario_nuevo(request.form)
    if not error:
        try:
            api.crear_usuario(datos)
        except api.ErrorDeDatos as e:
            error = f"No se pudo crear el usuario. {e}"
    if error:
        flash(error, "error")
        valores = {k: v for k, v in request.form.items() if k != "clave"}
        return render_template("usuarios.html", usuarios=api.listar_usuarios(), valores=valores), 400
    flash(f"Usuario {datos['email']} creado. Entrégale su correo y contraseña inicial.", "ok")
    return redirect(url_for("panel.usuarios"))


@bp.post("/usuarios/<int:usuario_id>")
@solo_admin
def actualizar_usuario(usuario_id):
    rol = request.form.get("rol")
    if rol not in ("admin", "productor"):
        flash("Elige un rol.", "error")
        return redirect(url_for("panel.usuarios"))
    activo = request.form.get("activo") == "si"
    if usuario_id == sesion.usuario()["id"] and (rol != "admin" or not activo):
        flash("No puedes quitarte a ti mismo el acceso ni el rol de administrador.", "error")
        return redirect(url_for("panel.usuarios"))
    try:
        api.actualizar_usuario(usuario_id, {"rol": rol, "activo": activo})
    except api.ErrorDeDatos as e:
        flash(f"No se pudo actualizar el usuario. {e}", "error")
    else:
        flash("Usuario actualizado.", "ok")
    return redirect(url_for("panel.usuarios"))
