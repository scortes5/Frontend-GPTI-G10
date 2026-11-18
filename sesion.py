"""Sesión del usuario en una cookie firmada de Flask (HttpOnly: el JavaScript no ve el token)."""
import hmac
import secrets

from flask import session

_TOKEN = "token"
_USUARIO = "usuario"
_CSRF = "csrf"


def iniciar(token: str, usuario: dict) -> None:
    session.clear()  # evita reutilizar una sesión previa (fijación de sesión)
    session[_TOKEN] = token
    session[_USUARIO] = usuario
    session[_CSRF] = secrets.token_urlsafe(32)
    session.permanent = True


def cerrar() -> None:
    session.pop(_TOKEN, None)
    session.pop(_USUARIO, None)
    session[_CSRF] = secrets.token_urlsafe(32)


def activa() -> bool:
    return _TOKEN in session


def token() -> str | None:
    return session.get(_TOKEN)


def usuario() -> dict | None:
    return session.get(_USUARIO)


def es_admin() -> bool:
    return activa() and usuario()["rol"] == "admin"


def csrf_token() -> str:
    if _CSRF not in session:
        session[_CSRF] = secrets.token_urlsafe(32)
    return session[_CSRF]


def csrf_valido(valor: str | None) -> bool:
    esperado = session.get(_CSRF)
    return bool(valor and esperado and hmac.compare_digest(valor, esperado))
