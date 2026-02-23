import streamlit as st
import pandas as pd
import os
from datetime import datetime
from utils import ARCHIVO_SOPORTE

def mostrar_modulo_soporte(usuario_nombre, usuario_rol):
    st.title("🆘 Centro de Ayuda y Soporte SOS")
    
    if usuario_rol == 'admin' and os.path.exists(ARCHIVO_SOPORTE):
        st.subheader("📥 Tickets de Soporte Pendientes")
        st.dataframe(pd.read_csv(ARCHIVO_SOPORTE), use_container_width=True)
        if st.button("Limpiar historial de soporte"):
            os.remove(ARCHIVO_SOPORTE)
            st.rerun()
    
    st.subheader("📝 Crear nuevo reporte de falla")
    with st.form("form_soporte_v13", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tipo_f = st.selectbox("¿Qué falló?", ["Error visual", "Botón no funciona", "Error al cargar datos", "Otro"])
            urgencia = st.select_slider("Nivel de Urgencia", options=["Baja", "Media", "Alta", "CRÍTICA 🚨"])
        with col2:
            modulo = st.selectbox("¿En qué sección ocurrió?", ["Login", "Preventivo", "Personal", "Accidentes", "Informes", "Otro"])
            
        detalle = st.text_area("Describa qué pasó exactamente:")
        
        if st.form_submit_button("🚀 Enviar Reporte al Administrador"):
            if detalle:
                nuevo_t = {
                    "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Usuario": usuario_nombre,
                    "Modulo": modulo,
                    "Tipo": tipo_f,
                    "Urgencia": urgencia,
                    "Detalle": detalle
                }
                pd.DataFrame([nuevo_t]).to_csv(ARCHIVO_SOPORTE, mode='a', header=not os.path.exists(ARCHIVO_SOPORTE), index=False)
                st.success("✅ Alerta enviada. Matías revisará el caso pronto.")
                st.balloons()