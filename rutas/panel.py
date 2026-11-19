"""Páginas con sesión: inicio, lotes, entregas, ventas y usuarios."""
from datetime import date

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

import api
import formularios
import sesion
from rutas.permisos import requiere_sesion, solo_admin

bp = Blueprint("panel", __name__)


def _filtros(*campos: str) -> dict:
    """Filtros de la URL. Las fechas inválidas se ignoran; usuario_id solo lo usa un administrador."""
    filtros = {}
    for campo in campos:
        valor = request.args.get(campo, "").strip()
        if not valor:
            continue
        if campo in ("desde", "hasta"):
            try:
                valor = date.fromisoformat(valor).isoformat()
            except ValueError:
                continue
        if campo == "usuario_id" and not (sesion.es_admin() and valor.isdigit()):
            continue
        if campo == "estado" and valor not in ("vigente", "anulado"):
            continue
        filtros[campo] = valor[:80]
    return filtros


def _socios() -> list[dict]:
    """Para el filtro por socio del administrador. Si falla, el filtro simplemente no aparece."""
    if not sesion.es_admin():
        return []
    try:
        return [u for u in api.listar_usuarios() if u["rol"] == "productor"]
    except api.BackendError:
        return []


@bp.get("/")
@requiere_sesion
def inicio():
    filtros = _filtros("desde", "hasta", "cultivo", "usuario_id")
    resumen = api.resumen(filtros)
    cultivos = sorted(resumen["kilos_por_cultivo"].items(), key=lambda par: par[1], reverse=True)
    maximo = max((kilos for _, kilos in cultivos), default=0)
    return render_template(
        "inicio.html", resumen=resumen, cultivos=cultivos, maximo=maximo, filtros=filtros,
        socios=_socios(), **_clima_resumido(),
    )


def _clima_resumido() -> dict:
    """Tarjeta de clima en Inicio. Si el clima no está disponible, Inicio se muestra igual."""
    try:
        return {"clima": api.clima(), "sin_campo": False}
    except api.ErrorDeDatos as e:
        return {"clima": None, "sin_campo": e.status == 404}
    except api.BackendError:
        return {"clima": None, "sin_campo": False}


@bp.get("/ayuda")
@requiere_sesion
def ayuda():
    """Guía visual paso a paso para los socios (manual de usuario dentro de la app)."""
    return render_template("ayuda.html")


# ---------- Lotes ----------


def _pagina_lotes(valores=None, status=200):
    filtros = _filtros("desde", "hasta", "estado", "cultivo", "usuario_id")
    return render_template(
        "lotes.html", lotes=api.listar_lotes(filtros), valores=valores or {}, filtros=filtros, socios=_socios(),
    ), status


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


def _pagina_lote(codigo: str, valores=None, status=200):
    traza = api.trazabilidad(codigo)
    return render_template("lote.html", traza=traza, lote=traza["lote"], valores=valores or traza["lote"]), status


@bp.get("/lotes/<codigo>")
@requiere_sesion
def lote(codigo):
    return _pagina_lote(codigo)


@bp.post("/lotes/<codigo>")
@requiere_sesion
def editar_lote(codigo):
    datos, error = formularios.lote_edicion(request.form)
    if not error:
        try:
            api.actualizar_lote(codigo, datos)
        except api.ErrorDeDatos as e:
            error = f"No se pudo actualizar el lote. {e}"
    if error:
        flash(error, "error")
        return _pagina_lote(codigo, request.form, 400)
    flash("Lote actualizado. El cambio quedó en el historial.", "ok")
    return redirect(url_for("panel.lote", codigo=codigo))


@bp.post("/lotes/<codigo>/entregas")
@requiere_sesion
def agregar_entrega(codigo):
    datos, error = formularios.entrega(request.form)
    if not error:
        try:
            api.agregar_entrega(codigo, datos)
        except api.ErrorDeDatos as e:
            error = f"No se pudo registrar la entrega. {e}"
    if error:
        flash(error, "error")
    else:
        flash("Entrega registrada.", "ok")
    return redirect(url_for("panel.lote", codigo=codigo))


def _anular(accion, mensaje_ok: str, destino: str):
    datos, error = formularios.anulacion(request.form)
    if not error:
        try:
            accion(datos["motivo"])
        except api.ErrorDeDatos as e:
            error = f"No se pudo anular. {e}"
    flash(error or mensaje_ok, "error" if error else "ok")
    return redirect(destino)


@bp.post("/lotes/<codigo>/anular")
@requiere_sesion
def anular_lote(codigo):
    return _anular(lambda motivo: api.anular_lote(codigo, motivo),
                   f"Lote {codigo} anulado. Sigue en el historial, pero ya no cuenta en los indicadores.",
                   url_for("panel.lote", codigo=codigo))


@bp.post("/lotes/<codigo>/entregas/<int:entrega_id>/anular")
@requiere_sesion
def anular_entrega(codigo, entrega_id):
    return _anular(lambda motivo: api.anular_entrega(codigo, entrega_id, motivo), "Entrega anulada.",
                   url_for("panel.lote", codigo=codigo))


@bp.post("/lotes/<codigo>/ventas/<int:venta_id>/anular")
@requiere_sesion
def anular_venta(codigo, venta_id):
    destino = request.form.get("volver") == "ventas" and url_for("panel.ventas", codigo=codigo) or url_for("panel.lote", codigo=codigo)
    return _anular(lambda motivo: api.anular_venta(codigo, venta_id, motivo),
                   "Venta anulada. Sus kilos vuelven a estar disponibles.", destino)


@bp.get("/lotes/<codigo>/reporte.<formato>")
@requiere_sesion
def reporte(codigo, formato):
    if formato not in ("pdf", "csv"):
        return render_template("error.html", mensaje="Formato de reporte no disponible."), 404
    contenido = api.reporte(codigo, formato)
    tipo = "application/pdf" if formato == "pdf" else "text/csv; charset=utf-8"
    respuesta = Response(contenido, content_type=tipo)
    respuesta.headers["Content-Disposition"] = f'attachment; filename="lote_{codigo}.{formato}"'
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


# ---------- Ventas ----------


def _pagina_ventas(codigo: str | None, valores=None, status=200):
    lotes = api.listar_lotes({"estado": "vigente"})
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
    creado = None
    if not error:
        try:
            creado = api.crear_usuario(datos)
        except api.ErrorDeDatos as e:
            error = f"No se pudo crear el usuario. {e}"
    if error:
        flash(error, "error")
        valores = {k: v for k, v in request.form.items() if k != "clave"}
        return render_template("usuarios.html", usuarios=api.listar_usuarios(), valores=valores), 400
    if creado.get("credenciales_enviadas"):
        flash(f"Usuario creado. Le enviamos su correo y contraseña a {datos['email']}.", "ok")
    else:
        flash(f"Usuario {datos['email']} creado, pero no se pudo enviar el correo con sus credenciales. "
              "Pídele que use «¿Olvidaste tu contraseña?» para crear una.", "aviso")
    return redirect(url_for("panel.usuarios"))


@bp.post("/usuarios/<int:usuario_id>")
@solo_admin
def actualizar_usuario(usuario_id):
    propio = usuario_id == sesion.usuario()["id"]
    formulario = request.form.to_dict()
    if propio:  # el propio administrador no puede quitarse el rol ni el acceso
        formulario.update(rol="admin", activo="si")
    cambios, error = formularios.usuario_edicion(formulario)
    if not error:
        if propio:
            cambios.pop("rol"), cambios.pop("activo")
        try:
            actualizado = api.actualizar_usuario(usuario_id, cambios)
        except api.ErrorDeDatos as e:
            error = f"No se pudo actualizar el usuario. {e}"
        else:
            if propio:
                sesion.actualizar_usuario({"nombre": actualizado["nombre"], "email": actualizado["email"]})
    flash(error or "Usuario actualizado.", "error" if error else "ok")
    return redirect(url_for("panel.usuarios"))
