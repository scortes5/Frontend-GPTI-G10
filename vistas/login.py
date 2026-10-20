import streamlit as st

import api
import sesion

st.title("AgroTracker")
st.caption("Trazabilidad y gestión de cosecha · Cooperativa Newen al Sur")

with st.form("login"):
    st.subheader("Iniciar sesión")
    email = st.text_input("Correo")
    clave = st.text_input("Contraseña", type="password")
    if st.form_submit_button("Entrar", type="primary"):
        try:
            respuesta = api.login(email.strip(), clave)
        except api.BackendError as e:
            st.error(str(e))
        else:
            sesion.iniciar(respuesta["access_token"], respuesta["usuario"])
            st.rerun()

st.info("¿Escaneaste un QR? Abre **Trazabilidad** en el menú para ver el origen del lote.")
