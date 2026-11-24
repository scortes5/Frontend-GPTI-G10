"""API JSON para la cola sin conexión (static/js/cola.js).

Los formularios que se pueden guardar sin señal (registrar lote, editar lote, registrar venta)
se envían aquí con fetch. Si no hay red, el navegador los guarda en IndexedDB y los reenvía
a estas mismas rutas cuando vuelve la conexión. La cookie de sesión autentica; el token del
backend sigue solo en el servidor.

Respuestas: 2xx listo · 401 hay que iniciar sesión (se reintenta después) · 4xx datos rechazados
(no se reintenta, el usuario decide) · 5xx servidor caído (se reintenta).

La cabecera X-Cola: 1 indica un reenvío desde la cola: no se deja un mensaje flash, porque el
aviso lo muestra el propio navegador.

X-Evento-Id y X-Evento-Creado (los pone el navegador al guardar el registro) se pasan al backend:
con ellas no se duplica un registro reenviado y se mide cuánto tardó en llegar (SC N°2).
"""
import re

from flask import Blueprint, flash, jsonify, request, url_for

import api
import formularios
import sesion
from rutas.permisos import requiere_sesion

bp = Blueprint("cola", __name__, url_prefix="/api")


def _datos():
    return request.get_json(silent=True) or {}


def _evento() -> dict | None:
    id_evento = request.headers.get("X-Evento-Id", "")
    if not re.fullmatch(r"[A-Za-z0-9-]{8,64}", id_evento):
        return None
    evento = {"X-Evento-Id": id_evento, "X-Cola": "1" if request.headers.get("X-Cola") == "1" else "0"}
    creado = request.headers.get("X-Evento-Creado", "")
    if creado.isdigit() and len(creado) <= 15:
        evento["X-Evento-Creado"] = creado
    return evento


def _avisar(mensaje: str) -> None:
    if request.headers.get("X-Cola") != "1":
        flash(mensaje, "ok")


def _invalido(error: str):
    return jsonify(detail=error), 422


@bp.get("/sesion")
def estado_sesion():
    """La cola pregunta quién está conectado antes de reenviar: solo se envía lo de ese usuario."""
    if not sesion.activa():
        return jsonify(detail="Inicia sesión para enviar lo pendiente.", csrf=sesion.csrf_token()), 401
    usuario = sesion.usuario()
    return jsonify(usuario_id=usuario["id"], nombre=usuario["nombre"], csrf=sesion.csrf_token())


@bp.post("/actividad")
@requiere_sesion
def actividad():
    """Botón «Seguir aquí» del aviso de inactividad: la sesión sigue abierta."""
    return "", 204


@bp.post("/lotes")
@requiere_sesion
def crear_lote():
    datos, error = formularios.lote(_datos())
    if error:
        return _invalido(error)
    lote = api.crear_lote(datos, _evento())
    _avisar(f"Lote {lote['codigo']} registrado. Guarda o imprime su código QR.")
    return jsonify(lote=lote, redirect=url_for("panel.lote", codigo=lote["codigo"])), 201


@bp.patch("/lotes/<codigo>")
@requiere_sesion
def editar_lote(codigo):
    datos, error = formularios.lote_edicion(_datos())
    if error:
        return _invalido(error)
    lote = api.actualizar_lote(codigo, datos, _evento())
    _avisar("Lote actualizado. El cambio quedó en el historial.")
    return jsonify(lote=lote, redirect=url_for("panel.lote", codigo=codigo))


@bp.post("/lotes/<codigo>/ventas")
@requiere_sesion
def registrar_venta(codigo):
    datos, error = formularios.venta(_datos())
    if error:
        return _invalido(error)
    venta = api.registrar_venta(codigo, datos, _evento())
    _avisar("Venta registrada.")
    return jsonify(venta=venta, redirect=url_for("panel.ventas", codigo=codigo)), 201


@bp.post("/lotes/<codigo>/entregas")
@requiere_sesion
def agregar_entrega(codigo):
    datos, error = formularios.entrega(_datos())
    if error:
        return _invalido(error)
    entrega = api.agregar_entrega(codigo, datos, _evento())
    _avisar("Entrega registrada.")
    return jsonify(entrega=entrega, redirect=url_for("panel.lote", codigo=codigo)), 201
