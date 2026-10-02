from datetime import date

import streamlit as st

import api

st.set_page_config(page_title="Lotes · AgroTracker", page_icon="🌱", layout="wide")
st.title("Lotes")

with st.form("nuevo_lote", clear_on_submit=True):
    st.subheader("Registrar lote")
    productor = st.text_input("Productor")
    cultivo = st.text_input("Cultivo")
    kilos = st.number_input("Kilos", min_value=0.0, step=0.5)
    fecha = st.date_input("Fecha de cosecha", value=date.today())
    if st.form_submit_button("Guardar"):
        if not productor or not cultivo or kilos <= 0:
            st.warning("Completa todos los campos.")
        else:
            try:
                lote = api.crear_lote(
                    {"productor": productor, "cultivo": cultivo, "kilos": kilos, "fecha_cosecha": fecha.isoformat()}
                )
                st.success(f"Lote {lote['codigo']} registrado.")
                st.image(api.qr_url(lote["codigo"]), width=180)
            except api.BackendError:
                st.error("No se pudo guardar el lote.")

st.subheader("Historial")
try:
    lotes = api.listar_lotes()
except api.BackendError:
    st.error("No se pudo conectar al backend.")
    st.stop()

if lotes:
    st.dataframe(lotes, width="stretch", hide_index=True)
else:
    st.write("Aún no hay lotes registrados.")
