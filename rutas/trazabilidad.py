"""Ficha del lote. El QR de cada lote apunta a /Trazabilidad?codigo=<codigo>.

Sin sesión (o si el lote es de otro productor) se muestra solo el origen del lote;
con permiso, también ventas, reporte por correo y recomendación con IA.
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for

import api
import sesion
from rutas.permisos import requiere_sesion

bp = Blueprint("trazabilidad", __name__)


def _ficha(codigo: str, recomendacion: str | None = None, status: int = 200):
    if not codigo:
        return render_template("trazabilidad.html", codigo="", traza=None, publico=None), status
    traza = publico = None
    try:
        if sesion.activa():
            traza = api.trazabilidad(codigo)
        else:
            publico = api.lote_publico(codigo)
    except api.AccesoDenegado:
        publico = api.lote_publico(codigo)
    except api.ErrorDeDatos as e:
        if e.status != 404:
            raise
        flash(f"No encontramos un lote con el código «{codigo}».", "error")
        return render_template("trazabilidad.html", codigo=codigo, traza=None, publico=None), 404
    return (
        render_template("trazabilidad.html", codigo=codigo, traza=traza, publico=publico, recomendacion=recomendacion),
        status,
    )


@bp.get("/trazabilidad")
@bp.get("/Trazabilidad")  # ruta que ya tienen impresa los QR generados
def ficha():
    return _ficha(request.args.get("codigo", "").strip())


@bp.post("/trazabilidad/<codigo>/reporte")
@requiere_sesion
def enviar_reporte(codigo):
    destinatario = request.form.get("destinatario", "").strip()
    if not destinatario:
        flash("Escribe el correo del destinatario.", "error")
    else:
        try:
            api.enviar_reporte(codigo, destinatario)
        except api.ErrorDeDatos as e:
            flash(f"No se pudo enviar el reporte. {e}", "error")
        else:
            flash(f"Reporte enviado a {destinatario}.", "ok")
    return redirect(url_for("trazabilidad.ficha", codigo=codigo))


@bp.post("/trazabilidad/<codigo>/recomendacion")
@requiere_sesion
def recomendacion(codigo):
    try:
        texto = api.recomendacion(codigo)
    except api.ErrorDeDatos as e:
        flash(f"No se pudo generar la recomendación. {e}", "error")
        return redirect(url_for("trazabilidad.ficha", codigo=codigo))
    except api.SinConexion:
        raise
    except api.BackendError as e:  # p. ej. 503 del proveedor de IA
        flash(f"No se pudo generar la recomendación. {e}", "error")
        return redirect(url_for("trazabilidad.ficha", codigo=codigo))
    return _ficha(codigo, recomendacion=texto)
