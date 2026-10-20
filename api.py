"""Funciones para hablar con el backend."""
import os

from dotenv import load_dotenv

load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


class BackendError(Exception):
    """El backend no respondió o devolvió un error. El mensaje es apto para mostrar al usuario."""


def _request(method: str, path: str, **kwargs):
    import requests

    try:
        response = requests.request(method, f"{BACKEND_URL}{path}", timeout=30, **kwargs)
    except requests.RequestException as e:
        raise BackendError("No se pudo conectar al backend.") from e

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


def trazabilidad(codigo: str) -> dict:
    return _request("GET", f"/lotes/{codigo}/trazabilidad")


def recomendacion(codigo: str) -> str:
    return _request("GET", f"/lotes/{codigo}/recomendacion")["texto"]


def enviar_reporte(codigo: str, destinatario: str) -> None:
    _request("POST", f"/lotes/{codigo}/reporte", json={"destinatario": destinatario})


def resumen() -> dict:
    return _request("GET", "/dashboard/resumen")


def qr_url(codigo: str) -> str:
    return f"{BACKEND_URL}/lotes/{codigo}/qr"
