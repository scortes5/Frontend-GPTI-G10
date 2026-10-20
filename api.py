"""Funciones para hablar con el backend."""
import os

from dotenv import load_dotenv

import sesion

load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


class BackendError(Exception):
    """El backend no respondió o devolvió un error. El mensaje es apto para mostrar al usuario."""


class SesionExpirada(BackendError):
    """El token ya no es válido: hay que volver a iniciar sesión."""


class AccesoDenegado(BackendError):
    """El usuario no tiene permiso para este recurso (por ejemplo, un lote de otro productor)."""


def _request(method: str, path: str, **kwargs):
    import requests

    headers = {"Authorization": f"Bearer {sesion.token()}"} if sesion.activa() else {}
    try:
        response = requests.request(method, f"{BACKEND_URL}{path}", headers=headers, timeout=30, **kwargs)
    except requests.RequestException as e:
        raise BackendError("No se pudo conectar al backend.") from e

    if response.status_code == 401 and sesion.activa():
        sesion.cerrar()
        raise SesionExpirada("Tu sesión expiró. Vuelve a iniciar sesión.")
    if response.status_code == 403:
        raise AccesoDenegado(_mensaje_de_error(response))
    if not response.ok:
        raise BackendError(_mensaje_de_error(response))
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
    return f"Error del backend ({response.status_code})."


def health() -> dict:
    return _request("GET", "/health")


def login(email: str, clave: str) -> dict:
    return _request("POST", "/auth/login", json={"email": email, "clave": clave})


def listar_lotes() -> list[dict]:
    return _request("GET", "/lotes")


def crear_lote(data: dict) -> dict:
    return _request("POST", "/lotes", json=data)


def actualizar_lote(codigo: str, cambios: dict) -> dict:
    return _request("PATCH", f"/lotes/{codigo}", json=cambios)


def eliminar_lote(codigo: str) -> None:
    _request("DELETE", f"/lotes/{codigo}")


def listar_ventas(codigo: str) -> list[dict]:
    return _request("GET", f"/lotes/{codigo}/ventas")


def registrar_venta(codigo: str, data: dict) -> dict:
    return _request("POST", f"/lotes/{codigo}/ventas", json=data)


def lote_publico(codigo: str) -> dict:
    return _request("GET", f"/publico/lotes/{codigo}")


def trazabilidad(codigo: str) -> dict:
    return _request("GET", f"/lotes/{codigo}/trazabilidad")


def recomendacion(codigo: str) -> str:
    return _request("GET", f"/lotes/{codigo}/recomendacion")["texto"]


def enviar_reporte(codigo: str, destinatario: str) -> None:
    _request("POST", f"/lotes/{codigo}/reporte", json={"destinatario": destinatario})


def resumen() -> dict:
    return _request("GET", "/dashboard/resumen")


def listar_usuarios() -> list[dict]:
    return _request("GET", "/usuarios")


def crear_usuario(data: dict) -> dict:
    return _request("POST", "/usuarios", json=data)


def actualizar_usuario(usuario_id: int, cambios: dict) -> dict:
    return _request("PATCH", f"/usuarios/{usuario_id}", json=cambios)


def qr_url(codigo: str) -> str:
    return f"{BACKEND_URL}/lotes/{codigo}/qr"
