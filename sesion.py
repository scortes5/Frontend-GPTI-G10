"""Sesión del usuario en una cookie firmada de Flask (HttpOnly: el JavaScript no ve el token)."""
import hmac
import secrets
import time

from flask import session

_TOKEN = "token"
_USUARIO = "usuario"
_CSRF = "csrf"
_ACTIVIDAD = "actividad"  # última vez (segundos) que la persona usó la app


def iniciar(token: str, usuario: dict) -> None:
    session.clear()  # evita reutilizar una sesión previa (fijación de sesión)
    session[_TOKEN] = token
    session[_USUARIO] = usuario
    session[_CSRF] = secrets.token_urlsafe(32)
    session[_ACTIVIDAD] = time.time()
    session.permanent = True


def cerrar() -> None:
    session.pop(_TOKEN, None)
    session.pop(_USUARIO, None)
    session.pop(_ACTIVIDAD, None)
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


def inactiva(minutos: int) -> bool:
    """True si pasaron más de `minutos` desde la última actividad."""
    ultima = session.get(_ACTIVIDAD)
    return ultima is not None and time.time() - ultima > minutos * 60


def registrar_actividad() -> None:
    session[_ACTIVIDAD] = time.time()


def actualizar_usuario(cambios: dict) -> None:
    """Refleja en la sesión un cambio del propio nombre o correo."""
    if activa():
        session[_USUARIO] = {**usuario(), **cambios}
