import streamlit as st
import pandas as pd
from utils import guardar_fila_nube, limpiar_rut, obtener_datos_nube, actualizar_hoja_completa, fusionar_nominas

def mostrar_modulo_personal(rol_usuario):
    st.markdown("## 👥 Nómina Maestra de Personal")
    st.markdown("Gestión centralizada de trabajadores para ELECTROCOM, MCT y subcontratos.")

    # Obtenemos la base actual directamente desde la nube (Única Fuente de Verdad)
    df_personal = obtener_datos_nube("personal")

    tab_lista, tab_manual, tab_masivo = st.tabs(["📋 Base Actual", "👤 Ingreso Individual", "📂 Carga Masiva (Excel)"])

    # --- PESTAÑA 1: VISUALIZACIÓN ---
    with tab_lista:
        if not df_personal.empty:
            st.dataframe(df_personal, use_container_width=True, hide_index=True)
            st.info(f"Dotación total activa: **{len(df_personal)} trabajadores** (Calculado automáticamente)")
        else:
            st.warning("La base de personal está vacía o no se pudo conectar.")

    # --- PESTAÑA 2: INGRESO MANUAL ---
    with tab_manual:
        st.markdown("### Ingreso Rápido de Trabajador")
        with st.form("form_ingreso_personal"):
            col1, col2 = st.columns(2)
            rut_nuevo = col1.text_input("RUT (Ej: 12345678-9)")
            nombre_nuevo = col2.text_input("Nombre Completo")
            
            col3, col4 = st.columns(2)
            sucursales = [
                "ELECTROCOM - Valdivia", 
                "ELECTROCOM - Paillaco", 
                "MCT", 
                "Placa Centro", 
                "00 - Prevención (Pruebas)", 
                "Subcontrato / Externo"
            ]
            sucursal_nueva = col3.selectbox("Sucursal / Centro de Costo", sucursales)
            cargo_nuevo = col4.text_input("Cargo")

            if st.form_submit_button("Guardar Trabajador", type="primary", use_container_width=True):
                if rut_nuevo and nombre_nuevo:
                    nuevo_registro = {
                        "RUT": limpiar_rut(rut_nuevo),
                        "NOMBRE": nombre_nuevo.upper(),
                        "SUCURSAL": sucursal_nueva,
                        "CARGO": cargo_nuevo.upper()
                    }
                    if guardar_fila_nube(nuevo_registro, "personal"):
                        st.success("✅ Trabajador agregado a la Nómina Maestra exitosamente.")
                        # Recargamos la página para que aparezca al instante en la lista
                        st.rerun() 
                else:
                    st.error("⚠️ Los campos RUT y Nombre son obligatorios.")

    # --- PESTAÑA 3: IMPORTADOR MASIVO ---
    with tab_masivo:
        st.markdown("### 📥 Importador de Nómina (Excel / CSV)")
        st.info("💡 Tu archivo debe contener al menos estas columnas en la primera fila: **RUT, NOMBRE, SUCURSAL, CARGO**")
        
        archivo_nomina = st.file_uploader("Sube tu archivo de Excel o CSV aquí", type=['xlsx', 'csv'])
        
        if archivo_nomina is not None:
            try:
                # Leer el archivo dependiendo de su formato
                if archivo_nomina.name.endswith('.csv'):
                    df_subido = pd.read_csv(archivo_nomina)
                else:
                    df_subido = pd.read_excel(archivo_nomina)
                    
                st.markdown("#### 👁️ Vista Previa de los Datos (Primeras 5 filas):")
                st.dataframe(df_subido.head(5), use_container_width=True)
                
                if st.button("🔄 Fusionar y Actualizar Nómina Maestra", type="primary", use_container_width=True):
                    with st.spinner("Procesando archivo, limpiando RUTs y buscando duplicados..."):
                        # Ejecutamos las dos funciones maestras de utils.py
                        df_fusionado = fusionar_nominas(df_personal, df_subido)
                        
                        if actualizar_hoja_completa(df_fusionado, "personal"):
                            st.success("✅ ¡Nómina Maestra actualizada correctamente! Sin datos duplicados.")
                            st.balloons()
                            st.rerun()
            except Exception as e:
                st.error(f"⚠️ Error al leer el archivo. Revisa que el formato sea correcto. Detalle técnico: {e}")
