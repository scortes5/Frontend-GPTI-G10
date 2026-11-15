from functools import wraps

from flask import flash, jsonify, redirect, request, url_for

import sesion


def requiere_sesion(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not sesion.activa():
            if request.path.startswith("/api/"):
                return jsonify(detail="Inicia sesión para continuar."), 401
            return redirect(url_for("auth.login", siguiente=request.full_path))
        return vista(*args, **kwargs)

    return envoltura


def solo_admin(vista):
    @requiere_sesion
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not sesion.es_admin():
            flash("Esa sección es solo para la directiva.", "error")
            return redirect(url_for("panel.inicio"))
        return vista(*args, **kwargs)

    return envoltura


def destino_seguro(valor: str | None, defecto: str) -> str:
    """Solo rutas internas: evita que ?siguiente= lleve a otro sitio."""
    if valor and valor.startswith("/") and not valor.startswith("//") and "\\" not in valor:
        return valor
    return defecto
