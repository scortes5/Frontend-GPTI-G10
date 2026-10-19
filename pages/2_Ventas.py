from datetime import date

import streamlit as st

import api

st.set_page_config(page_title="Ventas · AgroTracker", page_icon="🌱", layout="wide")
st.title("Ventas")


def formulario_venta(lote: dict, kilos_disponibles: float) -> None:
    with st.form(f"venta_{lote['codigo']}", clear_on_submit=True):
        st.subheader("Registrar venta")
        comprador = st.text_input("Comprador")
        kilos = st.number_input("Kilos vendidos", min_value=0.0, max_value=kilos_disponibles, step=0.5)
        precio = st.number_input("Precio por kilo ($)", min_value=0.0, step=50.0)
        fecha = st.date_input(
            "Fecha de venta",
            value=date.today(),
            min_value=date.fromisoformat(lote["fecha_cosecha"]),
            max_value=date.today(),
        )
        if not st.form_submit_button("Registrar"):
            return
        if not comprador.strip() or kilos <= 0 or precio <= 0:
            st.warning("Completa todos los campos.")
            return
        venta = {"comprador": comprador, "kilos": kilos, "precio_por_kilo": precio, "fecha": fecha.isoformat()}
        try:
            api.registrar_venta(lote["codigo"], venta)
        except api.BackendError as e:
            st.error(f"No se pudo registrar la venta. {e}")
            return
        st.success("Venta registrada.")
        st.rerun()


try:
    lotes = api.listar_lotes()
except api.BackendError:
    st.error("No se pudo conectar al backend.")
    st.stop()

if not lotes:
    st.write("Primero registra un lote.")
    st.stop()

lote = st.selectbox("Lote", lotes, format_func=lambda l: f"{l['codigo']} · {l['cultivo']} · {l['productor']}")
traza = api.trazabilidad(lote["codigo"])

col1, col2, col3 = st.columns(3)
col1.metric("Kilos del lote", f"{lote['kilos']:,.1f}")
col2.metric("Kilos disponibles", f"{traza['kilos_disponibles']:,.1f}")
col3.metric("Ingresos", f"${traza['ingresos']:,.0f}")

if traza["kilos_disponibles"] > 0:
    formulario_venta(lote, traza["kilos_disponibles"])
else:
    st.info("Este lote ya no tiene kilos disponibles.")

st.subheader("Ventas del lote")
if traza["ventas"]:
    st.dataframe(traza["ventas"], width="stretch", hide_index=True)
else:
    st.write("Este lote aún no tiene ventas.")
