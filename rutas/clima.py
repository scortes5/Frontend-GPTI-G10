"""Dashboard de clima: ubicación del campo, datos de la estación Agromet más cercana, alertas
y recomendación con IA de qué tomar en consideración."""
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

import api
import formularios
import sesion
from rutas.permisos import requiere_sesion

bp = Blueprint("clima", __name__)

ANCHO, ALTO = 600, 180  # coordenadas internas del gráfico SVG


def _usuario_objetivo() -> int | None:
    """Un administrador puede ver el campo de otro socio con ?usuario=<id>."""
    if not sesion.es_admin():
        return None
    valor = request.values.get("usuario", "")
    return int(valor) if valor.isdigit() and int(valor) != sesion.usuario()["id"] else None


def grafico(serie: list[dict]) -> dict | None:
    """Coordenadas del gráfico de 48 h: línea de temperatura y barras de lluvia."""
    puntos = [m for m in serie if m.get("temperatura") is not None]
    if len(puntos) < 2:
        return None
    temps = [m["temperatura"] for m in puntos]
    tmin, tmax = min(temps), max(temps)
    margen = max(1.0, (tmax - tmin) * 0.15)
    abajo, arriba = tmin - margen, tmax + margen
    n = len(serie)

    def x(i):
        return round(i * ANCHO / (n - 1), 1)

    def y(t):
        return round(ALTO - (t - abajo) / (arriba - abajo) * ALTO, 1)

    indices = {id(m): i for i, m in enumerate(serie)}
    linea = " ".join(f"{x(indices[id(m)])},{y(m['temperatura'])}" for m in puntos)
    lluvia_max = max([m.get("precipitacion") or 0 for m in serie] + [2.0])
    ancho_barra = max(2.0, ANCHO / n - 2)
    barras = [
        {"x": round(x(i) - ancho_barra / 2, 1), "alto": round((m["precipitacion"] / lluvia_max) * ALTO * 0.45, 1), "ancho": round(ancho_barra, 1)}
        for i, m in enumerate(serie) if (m.get("precipitacion") or 0) > 0
    ]
    for b in barras:
        b["y"] = round(ALTO - b["alto"], 1)
    cero = y(0) if abajo < 0 < arriba else None
    etiquetas = []
    for i, m in enumerate(serie):
        hora = datetime.fromisoformat(m["fecha_hora"])
        if hora.hour % 12 == 0:
            etiquetas.append({"pos": round(100 * i / (n - 1), 2), "texto": hora.strftime("%d-%m %H:%M") if hora.hour == 0 else "12:00"})
    i_max = max(range(len(puntos)), key=lambda i: puntos[i]["temperatura"])
    i_min = min(range(len(puntos)), key=lambda i: puntos[i]["temperatura"])
    return {
        "ancho": ANCHO, "alto": ALTO, "linea": linea, "area": f"0,{ALTO} {linea} {ANCHO},{ALTO}",
        "barras": barras, "cero": cero, "etiquetas": etiquetas,
        "maxima": {"x": x(indices[id(puntos[i_max])]), "y": y(tmax), "t": tmax},
        "minima": {"x": x(indices[id(puntos[i_min])]), "y": y(tmin), "t": tmin},
        "lluvia_max": lluvia_max,
    }


def _pagina(recomendacion: dict | None = None, status: int = 200):
    usuario_id = _usuario_objetivo()
    campos = api.listar_campos() if sesion.es_admin() else []
    clima = campo = error_clima = None
    try:
        clima = api.clima(usuario_id)
        campo = clima["campo"]
    except api.ErrorDeDatos as e:
        if e.status != 404:
            raise
    except api.SinConexion:
        raise
    except api.BackendError as e:  # 503: Agromet no disponible. Igual se muestra el campo.
        error_clima = str(e)
        campo = api.mi_campo(usuario_id)
    return render_template(
        "clima.html", clima=clima, campo=campo, error_clima=error_clima, campos=campos,
        usuario_objetivo=usuario_id, propio=usuario_id is None, recomendacion=recomendacion,
        grafico=grafico(clima["serie"]) if clima else None, editar=request.args.get("editar") == "1",
        valores={},
    ), status


@bp.get("/clima")
@requiere_sesion
def clima():
    return _pagina()


@bp.post("/clima/campo")
@requiere_sesion
def guardar_campo():
    datos, error = formularios.campo(request.form)
    if not error:
        try:
            api.guardar_campo(datos)
        except api.ErrorDeDatos as e:
            error = f"No se pudo guardar el campo. {e}"
    if error:
        flash(error, "error")
        return redirect(url_for("clima.clima", editar=1))
    flash("Ubicación del campo guardada. Ya puedes ver el clima de la estación más cercana.", "ok")
    return redirect(url_for("clima.clima"))


@bp.post("/clima/recomendacion")
@requiere_sesion
def recomendacion():
    usuario_id = _usuario_objetivo()
    try:
        recomendacion = api.recomendacion_clima(usuario_id)
    except api.SinConexion:
        raise
    except api.BackendError as e:
        flash(f"No se pudo generar la recomendación. {e}", "error")
        return redirect(url_for("clima.clima", usuario=usuario_id or None))
    return _pagina(recomendacion=recomendacion)
