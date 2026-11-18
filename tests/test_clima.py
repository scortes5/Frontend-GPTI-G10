"""Dashboard de clima con el backend simulado."""
from datetime import datetime, timedelta

import pytest

import api
from rutas.clima import grafico
from tests.test_app import ADMIN, backend, cliente, entrar  # noqa: F401  (fixtures)

CAMPO = {"usuario_id": 2, "productor": "María Antilef", "nombre": "Parcela Los Robles",
         "latitud": -38.74, "longitud": -72.6, "actualizado": "2026-11-15T10:00:00"}
INICIO = datetime(2026, 11, 13, 17)
SERIE = [{"fecha_hora": (INICIO + timedelta(hours=i)).isoformat(), "temperatura": 5 + (i % 24) * 0.5 - 4,
          "humedad": 80, "precipitacion": 1.0 if i in (3, 4) else 0, "viento": 12} for i in range(48)]
CLIMA = {
    "campo": CAMPO,
    "estacion": {"id": 644, "nombre": "Taplon", "institucion": "INIA", "comuna": "Padre Las Casas",
                 "region": "Araucanía", "latitud": -38.83, "longitud": -72.5, "distancia_km": 13.1},
    "fuente": "simulado",
    "actual": SERIE[-1],
    "resumen_24h": {"temperatura_min": -0.5, "temperatura_max": 12.5, "precipitacion": 2.0, "humedad_media": 80, "viento_max": 12},
    "serie": SERIE,
    "alertas": [{"nivel": "alta", "titulo": "Helada", "detalle": "La mínima llegó a -0.5 °C."}],
}


@pytest.fixture
def con_clima(backend):  # noqa: F811
    backend.falso("clima", CLIMA)
    backend.falso("mi_campo", CAMPO)
    backend.falso("listar_campos", [CAMPO])
    backend.falso("recomendacion_clima", "- **Helada:** cubre los almácigos esta noche")
    return backend


def test_dashboard_de_clima(cliente, con_clima):  # noqa: F811
    entrar(cliente)
    html = cliente.get("/clima").get_data(as_text=True)
    assert "Parcela Los Robles" in html and "Taplon" in html and "13,1 km" in html
    assert "openstreetmap.org/export/embed.html" in html
    assert "Helada" in html and "Datos de ejemplo" in html
    assert "grafico__linea" in html


def test_sin_campo_muestra_formulario(cliente, backend):  # noqa: F811
    backend.falso("clima", api.ErrorDeDatos("Aún no hay un campo registrado", 404))
    entrar(cliente)
    html = cliente.get("/clima").get_data(as_text=True)
    assert "¿Dónde está tu campo?" in html and "Usar mi ubicación actual" in html


def test_agromet_caido_muestra_el_campo_y_el_error(cliente, con_clima):  # noqa: F811
    con_clima.falso("clima", api.BackendError("Agromet rechazó la consulta"))
    entrar(cliente)
    respuesta = cliente.get("/clima")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "Agromet rechazó la consulta" in html and "Parcela Los Robles" in html


def test_guardar_campo_valida_y_envia(cliente, con_clima):  # noqa: F811
    con_clima.falso("guardar_campo", lambda datos: {**CAMPO, **datos})
    entrar(cliente)
    malo = cliente.post("/clima/campo", data={"nombre": "X", "latitud": "40,4", "longitud": "-3,7"})
    assert malo.status_code == 302 and "editar=1" in malo.headers["Location"]
    bueno = cliente.post("/clima/campo", data={"nombre": "Los Robles", "latitud": "-38,74", "longitud": "-72.6"})
    assert bueno.status_code == 302
    assert con_clima.llamadas[-1] == ("guardar_campo", ({"nombre": "Los Robles", "latitud": -38.74, "longitud": -72.6},))


def test_recomendacion_clima(cliente, con_clima):  # noqa: F811
    entrar(cliente)
    html = cliente.post("/clima/recomendacion").get_data(as_text=True)
    assert "<strong>Helada:</strong> cubre los almácigos" in html


def test_admin_ve_campo_de_otro_socio(cliente, con_clima):  # noqa: F811
    entrar(cliente, ADMIN, con_clima)
    html = cliente.get("/clima?usuario=2").get_data(as_text=True)
    assert "Clima del campo de María Antilef" in html
    assert ("clima", (2,)) in con_clima.llamadas


def test_productor_no_puede_pedir_otro_usuario(cliente, con_clima):  # noqa: F811
    entrar(cliente)
    cliente.get("/clima?usuario=1")
    assert ("clima", (None,)) in con_clima.llamadas


def test_inicio_muestra_resumen_del_clima(cliente, con_clima):  # noqa: F811
    entrar(cliente)
    html = cliente.get("/").get_data(as_text=True)
    assert "clima-mini" in html and "Helada" in html


def test_grafico_tiene_escala_y_etiquetas():
    g = grafico(SERIE)
    assert g["minima"]["t"] == min(m["temperatura"] for m in SERIE)
    assert g["cero"] is not None  # hubo temperaturas bajo cero
    assert len(g["barras"]) == 2 and g["etiquetas"]
