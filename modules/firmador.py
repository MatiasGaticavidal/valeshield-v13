import streamlit as st
import pandas as pd
from datetime import datetime
import uuid

# Esta función la verá el administrador (Tú)
def mostrar_modulo_firmador(df_personal):
    st.markdown("## 🖋️ ShieldSign: Centro de Certificación Digital")
    st.markdown("Emisión y seguimiento de documentos con firma electrónica y sello QR.")
    
    # Pestañas de gestión
    tab_emitir, tab_seguimiento, tab_config = st.tabs(["📤 Emitir Documento", "📊 Seguimiento de Firmas", "⚙️ Mi Firma Digital"])
    
    with tab_emitir:
        st.markdown("### 1. Configurar Envío")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            archivo_subido = st.file_uploader("Sube el PDF base (ODI, Contrato, Charla)", type=['pdf'])
            
            # Selector de trabajador buscando en la base de personal
            if not df_personal.empty:
                opciones_trabajadores = df_personal['RUT'] + " - " + df_personal['NOMBRE']
                trabajador_sel = st.selectbox("Seleccionar Trabajador", ["Seleccione un trabajador..."] + opciones_trabajadores.tolist())
            else:
                st.warning("No hay base de personal cargada.")
                trabajador_sel = "Seleccione un trabajador..."

        with col2:
            fecha_limite = st.date_input("Fecha límite para firmar")
            tipo_doc = st.selectbox("Tipo de Documento", ["ODI / DAS", "Entrega de EPP", "Reglamento Interno", "Contrato / Anexo", "Otro"])
            
        if st.button("Generar Solicitud de Firma 🚀", type="primary", use_container_width=True):
            if archivo_subido and trabajador_sel != "Seleccione un trabajador...":
                # Generamos un ID único y corto
                token_unico = str(uuid.uuid4()).split('-')[0].upper()
                st.success(f"¡Solicitud creada! ID de Rastreo: **{token_unico}**")
                
                # Simulamos el link que enviaremos
                link_firma = f"https://tu-app.streamlit.app/?firmar={token_unico}"
                
                st.info(f"🔗 **Link para el trabajador:**\n{link_firma}")
                st.markdown("*Copia este link y envíalo por WhatsApp al trabajador.*")
                
                # Aquí a futuro insertaremos en Google Sheets la fila en estado "Pendiente"
            else:
                st.error("Debes subir un PDF y seleccionar un trabajador.")

    with tab_seguimiento:
        st.markdown("### Documentos en Proceso")
        st.info("Aquí se conectará la base de datos para ver quién falta por firmar y descargar los PDFs terminados.")
        # Aquí conectaremos el DataFrame de la pestaña 'certificados'

    with tab_config:
        st.markdown("### Configuración del Emisor")
        st.warning("Antes de emitir, debes registrar tu firma digital (Asesor) para que se estampe automáticamente junto a la del trabajador.")
        st.file_uploader("Sube una foto de tu firma (PNG sin fondo recomendado)", type=['png', 'jpg'])