import streamlit as st
import pandas as pd
from utils import guardar_fila_nube, limpiar_rut, obtener_datos_nube, actualizar_hoja_completa, fusionar_nominas

def mostrar_modulo_personal(rol_usuario):
    st.markdown("## 👥 Nómina Maestra de Personal")
    st.markdown("Gestión centralizada de trabajadores para estadísticas y módulos.")

    # 1. Obtenemos la base actual desde tu Google Sheets
    df_personal = obtener_datos_nube("personal")

    # 2. BLINDAJE DE COLUMNAS (Para no perder tu información antigua)
    if not df_personal.empty:
        # Convertimos todas las columnas a mayúsculas internamente para que coincidan siempre
        df_personal.columns = [str(c).strip().upper() for c in df_personal.columns]
    else:
        df_personal = pd.DataFrame(columns=["RUT", "NOMBRE", "SUCURSAL", "CARGO", "SEXO", "ESTADO"])

    # Verificamos que existan todas las columnas obligatorias, si no, las creamos para los nuevos
    for col in ["RUT", "NOMBRE", "SUCURSAL", "CARGO", "SEXO", "ESTADO"]:
        if col not in df_personal.columns:
            if col == "ESTADO":
                df_personal[col] = "Activo"
            else:
                df_personal[col] = ""

    tab_lista, tab_manual, tab_masivo = st.tabs(["📋 Base Actual", "👤 Ingreso Individual", "📂 Carga Masiva (Excel)"])

    # --- PESTAÑA 1: VISUALIZACIÓN Y EDICIÓN ---
    with tab_lista:
        st.markdown("### Directorio de Personal Activo e Inactivo")
        st.info("💡 **Tip de Admin:** Haz doble clic en la columna **ESTADO** o **SUCURSAL** de cualquier trabajador para editarlo. Luego presiona Guardar abajo.")
        
        # Filtro matemático: Excluimos pruebas y finiquitados del conteo oficial
        df_activos = df_personal[
            (df_personal['ESTADO'] == 'Activo') & 
            (df_personal['SUCURSAL'] != 'PREVENCION (PRUEBAS)')
        ]
        
        # Métrica limpia
        st.metric("Dotación Real Activa (Para Estadísticas Oficiales)", len(df_activos))

        # Tabla interactiva (Data Editor)
        df_editado = st.data_editor(
            df_personal,
            column_config={
                "ESTADO": st.column_config.SelectboxColumn(
                    "Estado Laboral",
                    help="Cambia a Finiquitado para excluir de las estadísticas",
                    options=["Activo", "Finiquitado"],
                    required=True
                ),
                "SUCURSAL": st.column_config.SelectboxColumn(
                    "Sucursal",
                    options=["ECOM VALDIVIA", "PLC VALDIVIA", "MCT VALDIVIA", "PREVENCION (PRUEBAS)", "CONTRATISTAS/EXTERNOS"]
                ),
                "SEXO": st.column_config.SelectboxColumn(
                    "Sexo",
                    options=["MASCULINO", "FEMENINO"]
                )
            },
            use_container_width=True,
            hide_index=True,
            key="editor_personal"
        )

        if st.button("💾 Guardar Cambios en la Tabla", type="primary"):
            if actualizar_hoja_completa(df_editado, "personal"):
                st.success("✅ Base de datos actualizada con éxito.")
                st.rerun()

    # --- PESTAÑA 2: INGRESO MANUAL ---
    with tab_manual:
        st.markdown("### Ingreso Rápido de Trabajador")
        with st.form("form_ingreso_personal"):
            col1, col2 = st.columns(2)
            rut_nuevo = col1.text_input("RUT (Ej: 12345678-9)")
            nombre_nuevo = col2.text_input("Nombre Completo")
            
            col3, col4, col5 = st.columns([2, 2, 1])
            sucursales = [
                "ECOM VALDIVIA", 
                "PLC VALDIVIA", 
                "MCT VALDIVIA", 
                "PREVENCION (PRUEBAS)", 
                "CONTRATISTAS/EXTERNOS"
            ]
            sucursal_nueva = col3.selectbox("Centro de Costo", sucursales)
            cargo_nuevo = col4.text_input("Cargo")
            sexo_nuevo = col5.selectbox("Sexo", ["MASCULINO", "FEMENINO"])

            if st.form_submit_button("Guardar Trabajador", type="primary", use_container_width=True):
                if rut_nuevo and nombre_nuevo:
                    nuevo_registro = {
                        "RUT": limpiar_rut(rut_nuevo),
                        "NOMBRE": nombre_nuevo.upper(),
                        "SUCURSAL": sucursal_nueva,
                        "CARGO": cargo_nuevo.upper(),
                        "SEXO": sexo_nuevo,
                        "ESTADO": "Activo" # Entra activo por defecto
                    }
                    if guardar_fila_nube(nuevo_registro, "personal"):
                        st.success("✅ Trabajador agregado exitosamente.")
                        st.rerun() 
                else:
                    st.error("⚠️ Los campos RUT y Nombre son obligatorios.")

    # --- PESTAÑA 3: IMPORTADOR MASIVO ---
    with tab_masivo:
        st.markdown("### 📥 Importador de Nómina (Excel / CSV)")
        st.info("💡 Tu archivo debe contener estas columnas exactas: **RUT, NOMBRE, SUCURSAL, CARGO, SEXO**")
        
        archivo_nomina = st.file_uploader("Sube tu archivo de Excel o CSV aquí", type=['xlsx', 'csv'])
        
        if archivo_nomina is not None:
            try:
                if archivo_nomina.name.endswith('.csv'):
                    df_subido = pd.read_csv(archivo_nomina)
                else:
                    df_subido = pd.read_excel(archivo_nomina)
                    
                # Blindaje: Normalizamos las columnas del archivo subido
                df_subido.columns = [str(c).strip().upper() for c in df_subido.columns]

                # Si el excel no trae columna ESTADO, se la agregamos como Activo a todos
                if 'ESTADO' not in df_subido.columns:
                    df_subido['ESTADO'] = 'Activo'

                st.markdown("#### 👁️ Vista Previa de los Datos:")
                st.dataframe(df_subido.head(3), use_container_width=True)
                
                if st.button("🔄 Fusionar y Actualizar Nómina Maestra", type="primary", use_container_width=True):
                    with st.spinner("Procesando archivo y limpiando datos..."):
                        df_fusionado = fusionar_nominas(df_personal, df_subido)
                        if actualizar_hoja_completa(df_fusionado, "personal"):
                            st.success("✅ ¡Nómina Maestra actualizada correctamente!")
                            st.balloons()
                            st.rerun()
            except Exception as e:
                st.error(f"⚠️ Error al leer el archivo. Detalle técnico: {e}")
