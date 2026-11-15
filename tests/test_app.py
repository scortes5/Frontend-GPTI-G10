"""Pruebas del frontend Flask con el backend simulado (no requiere la API corriendo)."""
import re
from datetime import date, timedelta

import pytest

import api
from app import create_app, numero

PRODUCTORA = {"id": 2, "nombre": "María Antilef", "email": "maria@newen.cl", "rol": "productor", "activo": True}
ADMIN = {"id": 1, "nombre": "Directiva", "email": "admin@newen.cl", "rol": "admin", "activo": True}
LOTE = {
    "id": 1, "codigo": "L-ABC123", "productor": "María Antilef", "cultivo": "Papa nativa",
    "kilos": 500.0, "fecha_cosecha": "2026-11-01", "creado": "2026-11-01T10:00:00",
}
TRAZA = {"lote": LOTE, "kilos_vendidos": 120.0, "kilos_disponibles": 380.0, "ingresos": 180000.0,
         "ventas": [{"id": 1, "comprador": "Feria", "kilos": 120.0, "precio_por_kilo": 1500.0, "fecha": "2026-11-02", "creado": "x"}]}


@pytest.fixture
def backend(monkeypatch):
    """Reemplaza las llamadas HTTP al backend y registra lo que se envió."""
    llamadas = []

    def falso(nombre, resultado):
        def funcion(*args, **kwargs):
            llamadas.append((nombre, args))
            if isinstance(resultado, Exception):
                raise resultado
            return resultado(*args) if callable(resultado) else resultado
        monkeypatch.setattr(api, nombre, funcion)

    falso("login", {"access_token": "tok", "usuario": PRODUCTORA})
    falso("logout", None)
    falso("resumen", {"total_lotes": 1, "kilos_cosechados": 500.0, "kilos_vendidos": 120.0,
                      "kilos_disponibles": 380.0, "ingresos": 180000.0, "kilos_por_cultivo": {"Papa nativa": 500.0}})
    falso("listar_lotes", [LOTE])
    falso("trazabilidad", TRAZA)
    falso("crear_lote", lambda datos: {**LOTE, **datos})
    falso("actualizar_lote", lambda codigo, datos: {**LOTE, **datos})
    falso("registrar_venta", lambda codigo, datos: {"id": 2, **datos})
    falso("lote_publico", {k: LOTE[k] for k in ("codigo", "productor", "cultivo", "kilos", "fecha_cosecha")})
    falso("listar_usuarios", [ADMIN, PRODUCTORA])
    falso("clima", api.ErrorDeDatos("Aún no hay un campo registrado", 404))
    backend = type("Backend", (), {"llamadas": llamadas, "falso": staticmethod(falso)})
    return backend


@pytest.fixture
def cliente(backend):
    app = create_app({"TESTING": True, "SECRET_KEY": "pruebas", "TESTING_SIN_CSRF": True})
    return app.test_client()


def entrar(cliente, usuario=PRODUCTORA, backend=None):
    if backend:
        backend.falso("login", {"access_token": "tok", "usuario": usuario})
    return cliente.post("/login", data={"email": usuario["email"], "clave": "x"})


def test_formato_chileno():
    assert numero(12345.5, 1) == "12.345,5"
    assert numero(380.0, 1) == "380"
    assert numero(180000, 0) == "180.000"


def test_sin_sesion_redirige_al_login(cliente):
    respuesta = cliente.get("/lotes")
    assert respuesta.status_code == 302
    assert "/login" in respuesta.headers["Location"]


def test_login_e_inicio(cliente):
    assert entrar(cliente).status_code == 302
    html = cliente.get("/").get_data(as_text=True)
    assert "Resumen de tus lotes" in html
    assert "180.000" in html
    assert 'data-usuario-id="2"' in html


def test_login_no_redirige_fuera_del_sitio(cliente):
    respuesta = cliente.post("/login", data={"email": "a@b.cl", "clave": "x", "siguiente": "//malo.com"})
    assert respuesta.headers["Location"] == "/"


def test_registrar_lote_productor_usa_su_nombre(cliente, backend):
    entrar(cliente)
    hoy = date.today().isoformat()
    respuesta = cliente.post("/lotes", data={"productor": "Otro", "cultivo": "Ajo", "kilos": "12,5", "fecha_cosecha": hoy})
    assert respuesta.status_code == 302
    nombre, args = backend.llamadas[-1]
    assert nombre == "crear_lote"
    assert args[0] == {"productor": "María Antilef", "cultivo": "Ajo", "kilos": 12.5, "fecha_cosecha": hoy}


def test_lote_con_fecha_futura_se_rechaza(cliente):
    entrar(cliente)
    manana = (date.today() + timedelta(days=1)).isoformat()
    respuesta = cliente.post("/lotes", data={"cultivo": "Ajo", "kilos": "10", "fecha_cosecha": manana})
    assert respuesta.status_code == 400
    assert "no puede ser futura" in respuesta.get_data(as_text=True)


def test_api_cola_crea_lote_y_devuelve_redireccion(cliente):
    entrar(cliente)
    respuesta = cliente.post("/api/lotes", json={"cultivo": "Ajo", "kilos": "10", "fecha_cosecha": "2026-11-01"},
                             headers={"X-Cola": "1"})
    assert respuesta.status_code == 201
    assert respuesta.json["redirect"] == "/lotes/L-ABC123"


def test_api_cola_sin_sesion_responde_401(cliente):
    assert cliente.post("/api/lotes", json={}).status_code == 401
    assert cliente.get("/api/sesion").status_code == 401


def test_api_cola_datos_invalidos_responde_422(cliente):
    entrar(cliente)
    respuesta = cliente.post("/api/lotes/L-ABC123/ventas", json={"comprador": "", "kilos": "5"})
    assert respuesta.status_code == 422
    assert "comprador" in respuesta.json["detail"]


def test_api_cola_regla_de_negocio_responde_409(cliente, backend):
    entrar(cliente)
    backend.falso("registrar_venta", api.ErrorDeDatos("No hay kilos suficientes", 409))
    respuesta = cliente.post("/api/lotes/L-ABC123/ventas",
                             json={"comprador": "Feria", "kilos": "999", "precio_por_kilo": "100", "fecha": "2026-11-02"})
    assert respuesta.status_code == 409
    assert respuesta.json["detail"] == "No hay kilos suficientes"


def test_api_cola_backend_caido_responde_503(cliente, backend):
    entrar(cliente)
    backend.falso("crear_lote", api.SinConexion("sin red"))
    respuesta = cliente.post("/api/lotes", json={"cultivo": "Ajo", "kilos": "10", "fecha_cosecha": "2026-11-01"})
    assert respuesta.status_code == 503  # la cola lo reintentará


def test_sesion_entrega_usuario_y_csrf(cliente):
    entrar(cliente)
    datos = cliente.get("/api/sesion").json
    assert datos["usuario_id"] == 2 and datos["csrf"]


def test_trazabilidad_publica_por_qr(cliente):
    html = cliente.get("/Trazabilidad?codigo=L-ABC123").get_data(as_text=True)
    assert "Origen registrado" in html
    assert "Feria" not in html  # sin sesión no se muestran ventas


def test_trazabilidad_con_sesion_muestra_ventas(cliente):
    entrar(cliente)
    html = cliente.get("/trazabilidad?codigo=L-ABC123").get_data(as_text=True)
    assert "Feria" in html and "380 kg" in html


def test_productor_no_entra_a_usuarios(cliente):
    entrar(cliente)
    assert cliente.get("/usuarios").status_code == 302


def test_admin_ve_usuarios(cliente, backend):
    entrar(cliente, ADMIN, backend)
    html = cliente.get("/usuarios").get_data(as_text=True)
    assert "maria@newen.cl" in html


def test_pwa(cliente):
    sw = cliente.get("/sw.js")
    assert sw.status_code == 200 and sw.headers["Service-Worker-Allowed"] == "/"
    assert "importScripts" in sw.get_data(as_text=True)
    manifiesto = cliente.get("/manifest.webmanifest")
    assert manifiesto.mimetype == "application/manifest+json"
    assert manifiesto.json["start_url"] == "/"
    offline = cliente.get("/offline").get_data(as_text=True)
    assert "Sin conexión" in offline


def test_paginas_con_avisos_no_se_guardan_offline(cliente):
    entrar(cliente)
    cliente.post("/lotes", data={"cultivo": "Ajo", "kilos": "10", "fecha_cosecha": "2026-11-01"})
    respuesta = cliente.get("/lotes/L-ABC123")
    assert respuesta.headers.get("X-Con-Avisos") == "1"
    assert cliente.get("/lotes/L-ABC123").headers.get("X-Con-Avisos") is None


def test_csrf_obligatorio(backend):
    app = create_app({"TESTING": True, "SECRET_KEY": "pruebas"})
    cliente = app.test_client()
    pagina = cliente.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf" value="([^"]+)"', pagina).group(1)
    assert cliente.post("/login", data={"email": "a@b.cl", "clave": "x"}).status_code == 302  # rechazado
    assert cliente.post("/api/lotes", json={}).status_code == 403
    respuesta = cliente.post("/login", data={"email": "a@b.cl", "clave": "x", "csrf": token})
    assert respuesta.status_code == 302 and respuesta.headers["Location"] == "/"
