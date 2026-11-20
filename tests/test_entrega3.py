"""Funciones de la entrega 3: entregas y anulaciones, reportes, filtros, usuarios con RUT,
cierre de sesión por inactividad, métrica de la cola y datos usados por la IA."""
import time
from datetime import date

import pytest

import api
import formularios
from tests.test_app import ADMIN, PRODUCTORA, RESUMEN, TRAZA, backend, cliente, entrar  # noqa: F401


def test_inicio_muestra_ventas_entregas_y_tiempo_de_la_cola(cliente):
    entrar(cliente)
    html = cliente.get("/").get_data(as_text=True)
    assert "1 venta" in html and "1 entrega" in html
    assert "Tiempo promedio de llegada" in html and "5 min" in html  # 330 s
    assert "2 de 4" in html


def test_filtros_del_inicio_llegan_al_backend(cliente, backend):
    entrar(cliente, ADMIN, backend)
    backend.falso("listar_usuarios", [ADMIN, PRODUCTORA])
    cliente.get("/?desde=2026-10-01&hasta=no-es-fecha&cultivo=Papa&usuario_id=2")
    nombre, args = [l for l in backend.llamadas if l[0] == "resumen"][-1]
    assert args[0] == {"desde": "2026-10-01", "cultivo": "Papa", "usuario_id": "2"}


def test_productor_no_filtra_por_otro_socio(cliente, backend):
    entrar(cliente)
    cliente.get("/lotes?usuario_id=1&estado=anulado")
    assert [l for l in backend.llamadas if l[0] == "listar_lotes"][-1][1][0] == {"estado": "anulado"}


def test_pagina_del_lote_muestra_entregas_e_historial(cliente):
    entrar(cliente)
    html = cliente.get("/lotes/L-ABC123").get_data(as_text=True)
    assert "Entregas de cosecha" in html
    assert "Faltaba el predio" in html
    assert "reporte.pdf" in html and "reporte.csv" in html
    assert "Anular lote" in html


def test_editar_lote_exige_motivo(cliente, backend):
    entrar(cliente)
    datos = {"cultivo": "Ajo", "fecha_cosecha": "2026-11-01"}
    assert cliente.post("/lotes/L-ABC123", data=datos).status_code == 400
    assert cliente.post("/lotes/L-ABC123", data={**datos, "motivo": "Cultivo mal escrito"}).status_code == 302
    assert backend.llamadas[-1][1][1]["motivo"] == "Cultivo mal escrito"


def test_agregar_entrega(cliente, backend):
    entrar(cliente)
    cliente.post("/lotes/L-ABC123/entregas", data={"kilos": "40", "fecha": date.today().isoformat(), "calidad": "segunda"})
    nombre, args = backend.llamadas[-1]
    assert nombre == "agregar_entrega" and args[1]["calidad"] == "segunda" and args[1]["kilos"] == 40


def test_anular_venta_pide_motivo(cliente, backend):
    entrar(cliente)
    backend.falso("anular_venta", {})
    cliente.post("/lotes/L-ABC123/ventas/1/anular", data={"motivo": ""})
    assert not [l for l in backend.llamadas if l[0] == "anular_venta"]
    cliente.post("/lotes/L-ABC123/ventas/1/anular", data={"motivo": "Comprador desistió"})
    assert backend.llamadas[-1] == ("anular_venta", ("L-ABC123", 1, "Comprador desistió"))


def test_descarga_de_reportes(cliente, backend):
    entrar(cliente)
    backend.falso("reporte", lambda codigo, formato: b"%PDF-1.4 ..." if formato == "pdf" else b"registro;fecha")
    pdf = cliente.get("/lotes/L-ABC123/reporte.pdf")
    csv = cliente.get("/lotes/L-ABC123/reporte.csv")
    assert pdf.mimetype == "application/pdf" and "attachment" in pdf.headers["Content-Disposition"]
    assert csv.mimetype == "text/csv"
    assert cliente.get("/lotes/L-ABC123/reporte.exe").status_code == 404


def test_ficha_publica_muestra_entregas_sin_precios(cliente):
    html = cliente.get("/Trazabilidad?codigo=L-ABC123").get_data(as_text=True)
    assert "Entregas de cosecha" in html and "El Roble" in html
    assert "$" not in html and "Feria" not in html


@pytest.mark.parametrize("rut, valido", [("12.345.678-5", "12.345.678-5"), ("123456785", "12.345.678-5"), ("10000013-k", "10.000.013-K")])
def test_rut_valido(rut, valido):
    assert formularios.rut_valido(rut) == valido


def test_crear_usuario_con_rut_invalido(cliente, backend):
    entrar(cliente, ADMIN, backend)
    respuesta = cliente.post("/usuarios", data={"nombre": "Pedro", "email": "p@coop.cl", "rut": "12.345.678-9", "rol": "productor"})
    assert respuesta.status_code == 400
    assert "dígito verificador" in respuesta.get_data(as_text=True)


def test_crear_usuario_sin_clave_avisa_el_envio_por_correo(cliente, backend):
    entrar(cliente, ADMIN, backend)
    backend.falso("crear_usuario", {"id": 3, "credenciales_enviadas": True})
    cliente.post("/usuarios", data={"nombre": "Pedro", "email": "p@coop.cl", "rut": "12.345.678-5", "rol": "productor"})
    assert backend.llamadas[-1][1][0] == {"nombre": "Pedro", "email": "p@coop.cl", "rut": "12.345.678-5", "rol": "productor"}
    assert "Le enviamos su correo y contraseña" in cliente.get("/usuarios").get_data(as_text=True)


def test_editar_nombre_y_correo_de_un_socio(cliente, backend):
    entrar(cliente, ADMIN, backend)
    backend.falso("actualizar_usuario", lambda usuario_id, cambios: {**PRODUCTORA, **cambios})
    cliente.post("/usuarios/2", data={"nombre": "María Antilef Pérez", "email": "maria@coop.cl", "rol": "productor", "activo": "si"})
    assert backend.llamadas[-1] == ("actualizar_usuario", (2, {"nombre": "María Antilef Pérez", "email": "maria@coop.cl", "rol": "productor", "activo": True}))


def test_admin_edita_su_nombre_sin_perder_el_rol(cliente, backend):
    entrar(cliente, ADMIN, backend)
    backend.falso("actualizar_usuario", lambda usuario_id, cambios: {**ADMIN, **cambios})
    cliente.post("/usuarios/1", data={"nombre": "Directiva Newen", "email": "admin@newen.cl", "rol": "productor"})
    assert backend.llamadas[-1][1][1] == {"nombre": "Directiva Newen", "email": "admin@newen.cl"}
    assert "Directiva Newen" in cliente.get("/").get_data(as_text=True)


def test_sesion_se_cierra_tras_30_minutos_sin_uso(cliente, backend):
    entrar(cliente)
    assert cliente.get("/lotes").status_code == 200
    with cliente.session_transaction() as s:
        s["actividad"] = time.time() - 31 * 60
    respuesta = cliente.get("/lotes")
    assert respuesta.status_code == 302 and "/login" in respuesta.headers["Location"]
    assert ("logout", ()) in backend.llamadas
    assert cliente.get("/lotes").status_code == 302  # ya no hay sesión


def test_la_cola_en_segundo_plano_no_mantiene_viva_la_sesion(cliente):
    entrar(cliente)
    with cliente.session_transaction() as s:
        s["actividad"] = time.time() - 20 * 60
    cliente.get("/api/sesion")
    with cliente.session_transaction() as s:
        assert time.time() - s["actividad"] > 19 * 60


def test_api_cola_pasa_el_id_y_la_hora_del_registro(cliente, backend):
    entrar(cliente)
    hoy = date.today().isoformat()
    cliente.post("/api/lotes", json={"cultivo": "Ajo", "kilos": "5", "fecha_cosecha": hoy},
                 headers={"X-Evento-Id": "1b2c3d4e-aaaa", "X-Evento-Creado": "1763990000000", "X-Cola": "1"})
    nombre, args = backend.llamadas[-1]
    assert nombre == "crear_lote"
    assert args[1] == {"X-Evento-Id": "1b2c3d4e-aaaa", "X-Cola": "1", "X-Evento-Creado": "1763990000000"}


def test_api_cola_descarta_ids_raros(cliente, backend):
    entrar(cliente)
    cliente.post("/api/lotes", json={"cultivo": "Ajo", "kilos": "5", "fecha_cosecha": date.today().isoformat()},
                 headers={"X-Evento-Id": "../../x"})
    assert backend.llamadas[-1][1][1] is None


def test_recomendacion_muestra_los_datos_usados(cliente, backend):
    entrar(cliente)
    backend.falso("recomendacion", {
        "id": 1, "tipo": "lote", "lote_codigo": "L-ABC123", "proveedor": "gemini", "creado": "2026-11-20T08:00:00",
        "texto": "- Vender esta semana", "consultas_restantes": 3,
        "datos_usados": [{"dato": "Kilos disponibles", "valor": "380 kg"}],
    })
    html = cliente.post("/trazabilidad/L-ABC123/recomendacion").get_data(as_text=True)
    assert "Datos que se usaron" in html and "380 kg" in html and "Te quedan 3 consultas" in html
