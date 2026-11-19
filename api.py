"""Funciones para hablar con el backend. Se llaman desde el servidor Flask: el token nunca llega al navegador."""
import os
from urllib.parse import quote

import requests
from dotenv import load_dotenv

import sesion

load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


class BackendError(Exception):
    """El backend no respondió o devolvió un error. El mensaje es apto para mostrar al usuario."""

    status = 502


class SinConexion(BackendError):
    """No se pudo llegar al backend (caído o sin red)."""

    status = 503


class SesionExpirada(BackendError):
    """El token ya no es válido: hay que volver a iniciar sesión."""

    status = 401


class AccesoDenegado(BackendError):
    """El usuario no tiene permiso para este recurso (por ejemplo, un lote de otro productor)."""

    status = 403


class ErrorDeDatos(BackendError):
    """El backend rechazó los datos (validación, regla de negocio, no encontrado)."""

    def __init__(self, mensaje: str, status: int):
        super().__init__(mensaje)
        self.status = status


def _respuesta(method: str, path: str, evento: dict | None = None, **kwargs) -> requests.Response:
    headers = {"Authorization": f"Bearer {sesion.token()}"} if sesion.activa() else {}
    headers.update(evento or {})  # X-Evento-*: identifican un registro de la cola sin conexión
    try:
        response = requests.request(method, f"{BACKEND_URL}{path}", headers=headers, timeout=30, **kwargs)
    except requests.RequestException as e:
        raise SinConexion("No se pudo conectar con el servidor. Intenta de nuevo en unos minutos.") from e

    if response.status_code == 401 and sesion.activa():
        sesion.cerrar()
        raise SesionExpirada("Tu sesión expiró. Vuelve a iniciar sesión.")
    if response.status_code == 403:
        raise AccesoDenegado(_mensaje_de_error(response))
    if 400 <= response.status_code < 500:
        raise ErrorDeDatos(_mensaje_de_error(response), response.status_code)
    if not response.ok:
        raise BackendError(_mensaje_de_error(response))
    return response


def _request(method: str, path: str, **kwargs):
    response = _respuesta(method, path, **kwargs)
    return response.json() if response.content else None


def _mensaje_de_error(response) -> str:
    try:
        detalle = response.json().get("detail")
    except ValueError:
        detalle = None
    if isinstance(detalle, str):
        return detalle
    if isinstance(detalle, list):
        return "Datos inválidos: " + "; ".join(error.get("msg", "") for error in detalle)
    return f"Error del servidor ({response.status_code})."


def _segmento(valor) -> str:
    """Codifica un valor para usarlo dentro de una ruta: '../usuarios' no puede cambiar el endpoint."""
    return quote(str(valor), safe="")


def health() -> dict:
    return _request("GET", "/health")


def login(email: str, clave: str) -> dict:
    return _request("POST", "/auth/login", json={"email": email, "clave": clave})


def logout() -> None:
    _request("POST", "/auth/logout")


def solicitar_codigo(email: str) -> str:
    return _request("POST", "/auth/recuperar", json={"email": email})["detail"]


def restablecer_clave(email: str, codigo: str, clave_nueva: str) -> None:
    _request("POST", "/auth/restablecer", json={"email": email, "codigo": codigo, "clave_nueva": clave_nueva})


def _sin_vacios(filtros: dict | None) -> dict:
    return {k: v for k, v in (filtros or {}).items() if v not in (None, "")}


def listar_lotes(filtros: dict | None = None) -> list[dict]:
    """Filtros: desde, hasta (fecha de cosecha), estado, cultivo y usuario_id (solo administrador)."""
    return _request("GET", "/lotes", params=_sin_vacios(filtros))


def obtener_lote(codigo: str) -> dict:
    return _request("GET", f"/lotes/{_segmento(codigo)}")


def crear_lote(data: dict, evento: dict | None = None) -> dict:
    return _request("POST", "/lotes", json=data, evento=evento)


def actualizar_lote(codigo: str, cambios: dict, evento: dict | None = None) -> dict:
    return _request("PATCH", f"/lotes/{_segmento(codigo)}", json=cambios, evento=evento)


def anular_lote(codigo: str, motivo: str) -> dict:
    return _request("POST", f"/lotes/{_segmento(codigo)}/anular", json={"motivo": motivo})


def agregar_entrega(codigo: str, data: dict, evento: dict | None = None) -> dict:
    return _request("POST", f"/lotes/{_segmento(codigo)}/entregas", json=data, evento=evento)


def anular_entrega(codigo: str, entrega_id: int, motivo: str) -> dict:
    return _request("POST", f"/lotes/{_segmento(codigo)}/entregas/{_segmento(entrega_id)}/anular", json={"motivo": motivo})


def anular_venta(codigo: str, venta_id: int, motivo: str) -> dict:
    return _request("POST", f"/lotes/{_segmento(codigo)}/ventas/{_segmento(venta_id)}/anular", json={"motivo": motivo})


def reporte(codigo: str, formato: str) -> bytes:
    """PDF o CSV del lote. Pasa por Flask: el token del backend no llega al navegador."""
    return _respuesta("GET", f"/lotes/{_segmento(codigo)}/reporte.{'pdf' if formato == 'pdf' else 'csv'}").content


def listar_ventas(codigo: str) -> list[dict]:
    return _request("GET", f"/lotes/{_segmento(codigo)}/ventas")


def registrar_venta(codigo: str, data: dict, evento: dict | None = None) -> dict:
    return _request("POST", f"/lotes/{_segmento(codigo)}/ventas", json=data, evento=evento)


def lote_publico(codigo: str) -> dict:
    return _request("GET", f"/publico/lotes/{_segmento(codigo)}")


def trazabilidad(codigo: str) -> dict:
    return _request("GET", f"/lotes/{_segmento(codigo)}/trazabilidad")


def recomendacion(codigo: str) -> dict:
    """Texto, datos usados, proveedor y consultas que quedan hoy."""
    return _request("GET", f"/lotes/{_segmento(codigo)}/recomendacion")


def recomendaciones_lote(codigo: str) -> list[dict]:
    return _request("GET", f"/lotes/{_segmento(codigo)}/recomendaciones")


def recomendaciones(limite: int = 20) -> list[dict]:
    return _request("GET", "/recomendaciones", params={"limite": limite})


def enviar_reporte(codigo: str, destinatario: str) -> None:
    _request("POST", f"/lotes/{_segmento(codigo)}/reporte", json={"destinatario": destinatario})


def resumen(filtros: dict | None = None) -> dict:
    """Filtros: desde, hasta, cultivo y usuario_id (socio, solo administrador)."""
    return _request("GET", "/dashboard/resumen", params=_sin_vacios(filtros))


def listar_usuarios() -> list[dict]:
    return _request("GET", "/usuarios")


def crear_usuario(data: dict) -> dict:
    return _request("POST", "/usuarios", json=data)


def actualizar_usuario(usuario_id: int, cambios: dict) -> dict:
    return _request("PATCH", f"/usuarios/{_segmento(usuario_id)}", json=cambios)


def qr_png(codigo: str) -> bytes:
    """PNG del QR del lote (público). Se sirve a través de Flask para que el service worker lo guarde."""
    return _respuesta("GET", f"/lotes/{_segmento(codigo)}/qr").content


def _consulta_usuario(usuario_id) -> dict:
    return {"usuario_id": usuario_id} if usuario_id else {}


def mi_campo(usuario_id: int | None = None) -> dict:
    return _request("GET", "/campo", params=_consulta_usuario(usuario_id))


def guardar_campo(data: dict) -> dict:
    return _request("PUT", "/campo", json=data)


def listar_campos() -> list[dict]:
    return _request("GET", "/campos")


def clima(usuario_id: int | None = None) -> dict:
    return _request("GET", "/clima", params=_consulta_usuario(usuario_id))


def recomendacion_clima(usuario_id: int | None = None) -> dict:
    return _request("GET", "/clima/recomendacion", params=_consulta_usuario(usuario_id))
