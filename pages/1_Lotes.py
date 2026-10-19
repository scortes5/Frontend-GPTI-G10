from datetime import date

import streamlit as st

import api

st.set_page_config(page_title="Lotes · AgroTracker", layout="wide")
st.title("Lotes")


def describir(lote: dict) -> str:
    return f"{lote['codigo']} · {lote['cultivo']} · {lote['productor']}"


def formulario_registro() -> None:
    with st.form("nuevo_lote", clear_on_submit=True):
        st.subheader("Registrar lote")
        productor = st.text_input("Productor")
        cultivo = st.text_input("Cultivo")
        kilos = st.number_input("Kilos", min_value=0.0, step=0.5)
        fecha = st.date_input("Fecha de cosecha", value=date.today(), max_value=date.today())
        if not st.form_submit_button("Guardar"):
            return
        if not productor.strip() or not cultivo.strip() or kilos <= 0:
            st.warning("Completa todos los campos.")
            return
        try:
            lote = api.crear_lote(
                {"productor": productor, "cultivo": cultivo, "kilos": kilos, "fecha_cosecha": fecha.isoformat()}
            )
        except api.BackendError as e:
            st.error(f"No se pudo guardar el lote. {e}")
            return
        st.success(f"Lote {lote['codigo']} registrado.")
        st.image(api.qr_url(lote["codigo"]), width=180)


def formulario_edicion(lote: dict) -> None:
    with st.form(f"editar_{lote['codigo']}"):
        productor = st.text_input("Productor", value=lote["productor"])
        cultivo = st.text_input("Cultivo", value=lote["cultivo"])
        kilos = st.number_input("Kilos", min_value=0.0, step=0.5, value=float(lote["kilos"]))
        fecha = st.date_input(
            "Fecha de cosecha", value=date.fromisoformat(lote["fecha_cosecha"]), max_value=date.today()
        )
        if not st.form_submit_button("Guardar cambios"):
            return
        cambios = {"productor": productor, "cultivo": cultivo, "kilos": kilos, "fecha_cosecha": fecha.isoformat()}
        try:
            api.actualizar_lote(lote["codigo"], cambios)
        except api.BackendError as e:
            st.error(f"No se pudo actualizar el lote. {e}")
            return
        st.success("Lote actualizado.")
        st.rerun()


def eliminacion(lote: dict) -> None:
    confirmado = st.checkbox("Confirmo que quiero eliminar este lote y sus ventas")
    if st.button("Eliminar lote", type="primary", disabled=not confirmado):
        try:
            api.eliminar_lote(lote["codigo"])
        except api.BackendError as e:
            st.error(f"No se pudo eliminar el lote. {e}")
            return
        st.rerun()


formulario_registro()

st.subheader("Historial")
try:
    lotes = api.listar_lotes()
except api.BackendError:
    st.error("No se pudo conectar al backend.")
    st.stop()

if not lotes:
    st.write("Aún no hay lotes registrados.")
    st.stop()

st.dataframe(lotes, width="stretch", hide_index=True)

st.subheader("Editar o eliminar")
seleccionado = st.selectbox("Lote", lotes, format_func=describir)
formulario_edicion(seleccionado)
eliminacion(seleccionado)
