"""Ficha pública del lote. El QR de cada lote apunta a /Trazabilidad?codigo=<codigo>."""
import streamlit as st

import api

st.set_page_config(page_title="Trazabilidad · AgroTracker", layout="wide")
st.title("Trazabilidad de lote")


def mostrar_ficha(traza: dict) -> None:
    lote = traza["lote"]
    st.subheader(f"{lote['cultivo']} · {lote['productor']}")

    datos, qr = st.columns([3, 1])
    with datos:
        st.write(f"**Código:** {lote['codigo']}")
        st.write(f"**Fecha de cosecha:** {lote['fecha_cosecha']}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Kilos cosechados", f"{lote['kilos']:,.1f}")
        col2.metric("Kilos vendidos", f"{traza['kilos_vendidos']:,.1f}")
        col3.metric("Kilos disponibles", f"{traza['kilos_disponibles']:,.1f}")
    with qr:
        st.image(api.qr_url(lote["codigo"]), caption="Código QR del lote", width=180)

    st.subheader("Ventas")
    if traza["ventas"]:
        st.dataframe(traza["ventas"], width="stretch", hide_index=True)
    else:
        st.write("Este lote aún no tiene ventas.")


def mostrar_recomendacion(codigo: str) -> None:
    st.subheader("Recomendación agronómica")
    if not st.button("Generar recomendación con IA"):
        return
    with st.spinner("Generando recomendación..."):
        try:
            st.markdown(api.recomendacion(codigo))
        except api.BackendError as e:
            st.error(f"No se pudo generar la recomendación. {e}")


codigo = st.text_input("Código del lote", value=st.query_params.get("codigo", "")).strip()
if not codigo:
    st.info("Ingresa un código o escanea el QR del lote.")
    st.stop()

st.query_params["codigo"] = codigo
try:
    traza = api.trazabilidad(codigo)
except api.BackendError as e:
    st.error(str(e))
    st.stop()

mostrar_ficha(traza)
mostrar_recomendacion(codigo)
