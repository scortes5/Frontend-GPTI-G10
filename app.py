import streamlit as st

import api

st.set_page_config(page_title="AgroTracker", page_icon="🌱", layout="wide")
st.title("🌱 AgroTracker")
st.caption("Trazabilidad y gestión de cosecha · Cooperativa Newen al Sur")

try:
    api.health()
    lotes = api.listar_lotes()
except api.BackendError:
    st.error(f"No se pudo conectar al backend en {api.BACKEND_URL}")
    st.stop()

col1, col2 = st.columns(2)
col1.metric("Lotes registrados", len(lotes))
col2.metric("Kilos cosechados", f"{sum(l['kilos'] for l in lotes):,.1f}")

st.info("Usa el menú lateral para registrar y consultar lotes.")
