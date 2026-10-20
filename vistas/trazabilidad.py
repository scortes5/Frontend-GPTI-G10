"""Ficha del lote. El QR de cada lote apunta a /Trazabilidad?codigo=<codigo>.

Sin sesión (o si el lote es de otro productor) se muestra solo el origen del lote;
con permiso, también ventas, reporte por correo y recomendación.
"""
import streamlit as st

import api
import sesion

st.title("Trazabilidad de lote")


def mostrar_ficha_publica(lote: dict) -> None:
    st.subheader(f"{lote['cultivo']} · {lote['productor']}")
    datos, qr = st.columns([3, 1])
    with datos:
        st.write(f"**Código:** {lote['codigo']}")
        st.write(f"**Fecha de cosecha:** {lote['fecha_cosecha']}")
        st.metric("Kilos cosechados", f"{lote['kilos']:,.1f}")
    with qr:
        st.image(api.qr_url(lote["codigo"]), caption="Código QR del lote", width=180)


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


def envio_por_correo(codigo: str) -> None:
    st.subheader("Enviar reporte por correo")
    with st.form("reporte_correo", clear_on_submit=True):
        destinatario = st.text_input("Correo del destinatario", placeholder="auditor@cooperativa.cl")
        if not st.form_submit_button("Enviar reporte"):
            return
        if not destinatario.strip():
            st.warning("Ingresa un correo.")
            return
        try:
            api.enviar_reporte(codigo, destinatario.strip())
        except api.BackendError as e:
            st.error(f"No se pudo enviar el reporte. {e}")
            return
        st.success(f"Reporte enviado a {destinatario.strip()}.")


codigo = st.text_input("Código del lote", value=st.query_params.get("codigo", "")).strip()
if not codigo:
    st.info("Ingresa un código o escanea el QR del lote.")
    st.stop()

st.query_params["codigo"] = codigo
try:
    if sesion.activa():
        mostrar_ficha(api.trazabilidad(codigo))
        envio_por_correo(codigo)
        mostrar_recomendacion(codigo)
    else:
        mostrar_ficha_publica(api.lote_publico(codigo))
except api.AccesoDenegado:
    mostrar_ficha_publica(api.lote_publico(codigo))
except api.BackendError as e:
    st.error(str(e))
