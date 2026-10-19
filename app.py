import streamlit as st

import api

st.set_page_config(page_title="AgroTracker", page_icon="🌱", layout="wide")
st.title("🌱 AgroTracker")
st.caption("Trazabilidad y gestión de cosecha · Cooperativa Newen al Sur")

try:
    resumen = api.resumen()
except api.BackendError:
    st.error(f"No se pudo conectar al backend en {api.BACKEND_URL}")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Lotes registrados", resumen["total_lotes"])
col2.metric("Kilos cosechados", f"{resumen['kilos_cosechados']:,.1f}")
col3.metric("Kilos disponibles", f"{resumen['kilos_disponibles']:,.1f}")
col4.metric("Ingresos por ventas", f"${resumen['ingresos']:,.0f}")

st.subheader("Kilos cosechados por cultivo")
if resumen["kilos_por_cultivo"]:
    st.bar_chart(resumen["kilos_por_cultivo"], x_label="Cultivo", y_label="Kilos")
else:
    st.write("Aún no hay cosechas registradas.")

st.info("Usa el menú lateral para registrar lotes y ventas o consultar la trazabilidad.")
