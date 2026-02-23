import streamlit as st
import pandas as pd
from datetime import datetime
import os
from utils import ARCHIVO_PREVENTIVOS, guardar_foto

def mostrar_modulo_preventivo(usuario_rol):
    st.title("🛡️ Informe de Prevención de Riesgos")
    
    if os.path.exists(ARCHIVO_PREVENTIVOS):
        st.dataframe(pd.read_csv(ARCHIVO_PREVENTIVOS, encoding='latin1', on_bad_lines='skip'), use_container_width=True)
    
    if usuario_rol == 'admin':
        st.markdown("---")
        st.subheader("📝 Registrar Hallazgo Preventivo")
        with st.form("form_preventivo_modular", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("📅 Fecha", datetime.now())
                sucursal = st.selectbox("🏢 Sucursal", ["ELECTROCOM VALDIVIA", "MCT VALDIVIA", "PLACA CENTRO VALDIVIA"])
                area = st.text_input("📍 Área Específica", placeholder="Ej: Taller, Bodega, Baños")
            with col2:
                riesgo = st.selectbox("⚠️ Nivel de Riesgo", ["Bajo", "Medio", "Alto", "Crítico 🚨"])
                tipo_p = st.radio("Tipo de Hallazgo", ["Condición Insegura", "Acción Insegura"], horizontal=True)

            titulo_p = st.text_input("📝 Título Corto", placeholder="Ej: Cable pelado en pasillo")
            desc_p = st.text_area("🔍 Descripción Detallada", placeholder="Relato detallado de la condición...")
            medida_p = st.text_area("🛠️ Medida Correctiva", placeholder="¿Qué se hizo o debe hacerse?")
            foto_p = st.file_uploader("📸 Evidencia Fotográfica", type=['png', 'jpg', 'jpeg'])
            
            if st.form_submit_button("💾 Guardar Reporte"):
                if titulo_p and desc_p:
                    ruta_f = guardar_foto(foto_p)
                    nuevo = {
                        "Fecha": fecha, "Sucursal": sucursal, "Área": area, 
                        "Riesgo": riesgo, "Tipo": tipo_p, "Título": titulo_p, 
                        "Descripción": desc_p, "Medida": medida_p, "Foto": ruta_f
                    }
                    pd.DataFrame([nuevo]).to_csv(ARCHIVO_PREVENTIVOS, mode='a', 
                                              header=not os.path.exists(ARCHIVO_PREVENTIVOS), 
                                              index=False)
                    st.success("✅ Reporte preventivo guardado.")
                    st.rerun()