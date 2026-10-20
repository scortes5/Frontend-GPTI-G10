"""Gestión de usuarios: solo la ve el administrador (el menú no la muestra a productores)."""
import streamlit as st

import api

st.title("Usuarios")

ROLES = {"productor": "Productor", "admin": "Administrador"}


def formulario_nuevo_usuario() -> None:
    with st.form("nuevo_usuario", clear_on_submit=True):
        st.subheader("Crear usuario")
        nombre = st.text_input("Nombre")
        email = st.text_input("Correo")
        clave = st.text_input("Contraseña inicial (mínimo 8 caracteres)", type="password")
        rol = st.selectbox("Rol", list(ROLES), format_func=ROLES.get)
        if not st.form_submit_button("Crear"):
            return
        if not nombre.strip() or not email.strip() or len(clave) < 8:
            st.warning("Completa nombre, correo y una contraseña de al menos 8 caracteres.")
            return
        try:
            api.crear_usuario({"nombre": nombre, "email": email.strip(), "clave": clave, "rol": rol})
        except api.BackendError as e:
            st.error(f"No se pudo crear el usuario. {e}")
            return
        st.success(f"Usuario {email.strip()} creado.")
        st.rerun()


def edicion(usuario: dict) -> None:
    with st.form(f"usuario_{usuario['id']}"):
        rol = st.selectbox("Rol", list(ROLES), index=list(ROLES).index(usuario["rol"]), format_func=ROLES.get)
        activo = st.checkbox("Puede iniciar sesión", value=usuario["activo"])
        if not st.form_submit_button("Guardar cambios"):
            return
        try:
            api.actualizar_usuario(usuario["id"], {"rol": rol, "activo": activo})
        except api.BackendError as e:
            st.error(f"No se pudo actualizar el usuario. {e}")
            return
        st.success("Usuario actualizado.")
        st.rerun()


formulario_nuevo_usuario()

st.subheader("Usuarios registrados")
try:
    usuarios = api.listar_usuarios()
except api.BackendError as e:
    st.error(str(e))
    st.stop()

st.dataframe(
    [{"Nombre": u["nombre"], "Correo": u["email"], "Rol": ROLES[u["rol"]], "Activo": u["activo"]} for u in usuarios],
    width="stretch",
    hide_index=True,
)

st.subheader("Cambiar rol o acceso")
seleccionado = st.selectbox("Usuario", usuarios, format_func=lambda u: f"{u['nombre']} · {u['email']}")
edicion(seleccionado)
