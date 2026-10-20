"""Sesión del usuario en Streamlit (una por pestaña del navegador, nunca compartida)."""
import streamlit as st

_CLAVE = "sesion"


def iniciar(token: str, usuario: dict) -> None:
    st.session_state[_CLAVE] = {"token": token, "usuario": usuario}


def cerrar() -> None:
    st.session_state.pop(_CLAVE, None)


def activa() -> bool:
    return _CLAVE in st.session_state


def token() -> str | None:
    return st.session_state[_CLAVE]["token"] if activa() else None


def usuario() -> dict:
    return st.session_state[_CLAVE]["usuario"]


def es_admin() -> bool:
    return activa() and usuario()["rol"] == "admin"
