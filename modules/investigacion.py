import streamlit as st
import pandas as pd
import os
from utils import limpiar_rut
from modules.cerebro_conexion import encender_ia
from modules.cerebro_logica import generar_prompt_paso1_filtro, generar_prompt_paso2_arbol, generar_prompt_paso3_medidas, limpiar_respuesta_ia
from modules.cerebro_archivo import guardar_investigacion_local

cerebro_con = encender_ia()

def mostrar_modulo_investigacion():
    st.markdown("## 🕵️‍♂️ Investigación de Accidentes (Metodología SUSESO/OIT)")
    st.caption("Valentin Shield v12.0 - Pipeline de Análisis en 3 Fases")
    
    if 'res_ia' not in st.session_state:
        st.session_state.res_ia = None

    with st.container(border=True):
        rut_in = st.text_input("Ingrese RUT del Accidentado", placeholder="12.345.678-9")
        relato = st.text_area("Relato de los Hechos (Punto 6):", height=150)
        
        if st.button("🧠 Ejecutar Pipeline de Análisis SUSESO", type="primary", use_container_width=True):
            if not relato:
                st.warning("Ingrese un relato para analizar.")
                return
            
            if cerebro_con:
                resultado_final = {}
                # --- PASO 1: FILTRO ---
                with st.spinner("Paso 1/3: Aplicando Filtro de Hechos del Relato..."):
                    r1 = cerebro_con.generate_content(generar_prompt_paso1_filtro(relato))
                    datos1 = limpiar_respuesta_ia(r1.text)
                    resultado_final.update(datos1)
                
                # --- PASO 2: ÁRBOL ---
                if datos1 and 'hechos' in datos1:
                    with st.spinner("Paso 2/3: Construyendo Árbol de Causas (Tamiz Lógico)..."):
                        r2 = cerebro_con.generate_content(generar_prompt_paso2_arbol(datos1['hechos']))
                        datos2 = limpiar_respuesta_ia(r2.text)
                        resultado_final.update(datos2)
                
                # --- PASO 3: MEDIDAS ---
                if 'causa_raiz' in resultado_final:
                    with st.spinner("Paso 3/3: Buscando Código SUSESO y Definiendo Medidas..."):
                        r3 = cerebro_con.generate_content(generar_prompt_paso3_medidas(resultado_final['causa_raiz']))
                        datos3 = limpiar_respuesta_ia(r3.text)
                        resultado_final.update(datos3)

                st.session_state.res_ia = resultado_final
            else:
                st.error("Error de conexión con la IA.")

    res = st.session_state.res_ia
    if res:
        st.markdown("---")
        t1, t2, t3 = st.tabs(["📊 1. Filtro de Hechos del Relato", "🌳 2. Árbol de Causas", "🎯 3. Medidas Correctivas/Preventivas"])
        
        with t1:
            st.markdown("### Clasificación de Objetividad")
            st.markdown(f"<div style='background:#f8f9fa; padding:15px; border-radius:10px; border-left: 5px solid #ccc;'>{res.get('relato_marcado', '')}</div>", unsafe_allow_html=True)
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("🟢 **HECHOS**")
                for h in res.get('hechos', []): st.write(f"- {h}")
            with c2:
                st.markdown("🟡 **INTERPRETACIONES**")
                for i in res.get('interpretaciones', []): st.write(f"- {i}")
            with c3:
                st.markdown("🔴 **JUICIOS**")
                for j in res.get('juicios', []): st.write(f"- {j}")
            
        with t2:
            st.markdown("### Diagrama Lógico de Antecedentes")
            st.caption("🔵 Círculo: Variación | 🟦 Cuadrado: Hecho Permanente (Estado)")
            if res.get('dot_code'):
                st.graphviz_chart(res.get('dot_code'))
            
        with t3:
            st.markdown("### Administración de la Información")
            c_izq, c_der = st.columns(2)
            with c_izq:
                st.error(f"**Causa Raíz Principal:**\n{res.get('causa_raiz', '')}")
                st.info(f"**Código SUSESO (Anexo I):**\n{res.get('codigo_suseso', 'No determinado')}")
            with c_der:
                st.warning(f"**Medida Correctora:**\n{res.get('medida_correctora', '')}")
                st.success(f"**FPA y Medida Preventiva:**\n{res.get('fpa_y_preventiva', '')}")
            
            st.markdown("---")
            with st.form("f_final"):
                st.markdown("**Registro Oficial Valentin Shield**")
                medida_final = st.text_area("Acción Correctiva Final a Registrar:", value=res.get('medida_correctora', ''))
                responsable = st.text_input("Responsable de Ejecución y Plazo:")
                if st.form_submit_button("💾 Guardar y Archivar Investigación"):
                    if rut_in:
                        ruta = guardar_investigacion_local(limpiar_rut(rut_in), res)
                        if "Error" not in ruta:
                            st.success(f"✅ ¡Investigación Archivada! Carpeta: {ruta}")
                            st.balloons()
                        else:
                            st.error(ruta)
                    else:
                        st.error("Debe ingresar un RUT para guardar.")