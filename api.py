"""Funciones para hablar con el backend."""
import os

from dotenv import load_dotenv

load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


class BackendError(Exception):
    """El backend no respondió o devolvió un error."""


def _request(method: str, path: str, **kwargs):
    import requests

    try:
        response = requests.request(method, f"{BACKEND_URL}{path}", timeout=10, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise BackendError(str(e)) from e


def health() -> dict:
    return _request("GET", "/health")


def listar_lotes() -> list[dict]:
    return _request("GET", "/lotes")


def crear_lote(data: dict) -> dict:
    return _request("POST", "/lotes", json=data)


def qr_url(codigo: str) -> str:
    return f"{BACKEND_URL}/lotes/{codigo}/qr"
