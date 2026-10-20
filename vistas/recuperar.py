"""Recuperar contraseña en dos pasos: pedir un código por correo y usarlo para crear una clave nueva."""
import streamlit as st

import api

st.title("Recuperar contraseña")

_EMAIL = "recuperacion_email"


def paso_pedir_codigo() -> None:
    with st.form("pedir_codigo"):
        st.write("Escribe el correo de tu cuenta y te enviaremos un código de 6 dígitos.")
        email = st.text_input("Correo")
        if not st.form_submit_button("Enviar código", type="primary"):
            return
        if not email.strip():
            st.warning("Ingresa tu correo.")
            return
        try:
            api.solicitar_codigo(email.strip())
        except api.BackendError as e:
            st.error(str(e))
            return
        st.session_state[_EMAIL] = email.strip()
        st.rerun()


def paso_crear_clave(email: str) -> None:
    st.success(f"Si {email} está registrado, te llegó un código. Revisa también la carpeta de spam.")
    with st.form("crear_clave"):
        codigo = st.text_input("Código de 6 dígitos", max_chars=6)
        clave = st.text_input("Nueva contraseña (mínimo 8 caracteres)", type="password")
        confirmacion = st.text_input("Repite la nueva contraseña", type="password")
        if not st.form_submit_button("Cambiar contraseña", type="primary"):
            return
        if not (codigo.isdigit() and len(codigo) == 6):
            st.warning("El código tiene 6 dígitos.")
            return
        if len(clave) < 8 or clave != confirmacion:
            st.warning("Las contraseñas deben coincidir y tener al menos 8 caracteres.")
            return
        try:
            api.restablecer_clave(email, codigo, clave)
        except api.BackendError as e:
            st.error(str(e))
            return
        st.session_state.pop(_EMAIL)
        st.session_state["clave_restablecida"] = True
        st.rerun()

    if st.button("Pedir otro código"):
        st.session_state.pop(_EMAIL)
        st.rerun()


if st.session_state.pop("clave_restablecida", False):
    st.success("Tu contraseña cambió. Ya puedes iniciar sesión.")
    st.page_link("vistas/login.py", label="Ir a iniciar sesión")
elif _EMAIL in st.session_state:
    paso_crear_clave(st.session_state[_EMAIL])
else:
    paso_pedir_codigo()
