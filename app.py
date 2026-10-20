"""Punto de entrada: arma el menú según la sesión y el rol del usuario."""
import streamlit as st

import api
import sesion

st.set_page_config(page_title="AgroTracker", layout="wide")

ROL_VISIBLE = {"admin": "Administrador", "productor": "Productor"}

trazabilidad = st.Page("vistas/trazabilidad.py", title="Trazabilidad", url_path="Trazabilidad")

if not sesion.activa():
    paginas = [st.Page("vistas/login.py", title="Iniciar sesión", default=True), trazabilidad]
else:
    paginas = [
        st.Page("vistas/inicio.py", title="Inicio", default=True),
        st.Page("vistas/lotes.py", title="Lotes", url_path="Lotes"),
        st.Page("vistas/ventas.py", title="Ventas", url_path="Ventas"),
        trazabilidad,
    ]
    if sesion.es_admin():
        paginas.append(st.Page("vistas/usuarios.py", title="Usuarios", url_path="Usuarios"))
    usuario = sesion.usuario()
    with st.sidebar:
        st.write(f"**{usuario['nombre']}**")
        st.caption(ROL_VISIBLE[usuario["rol"]])
        if st.button("Cerrar sesión"):
            try:
                api.logout()  # revoca el token en el backend
            except api.BackendError:
                pass  # si ya expiró o no hay conexión, igual se cierra la sesión local
            sesion.cerrar()
            st.rerun()

st.navigation(paginas).run()
