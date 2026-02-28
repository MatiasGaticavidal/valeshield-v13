import streamlit as st
import pandas as pd
from utils import guardar_fila_nube, limpiar_rut, obtener_datos_nube, actualizar_hoja_completa, fusionar_nominas

def mostrar_modulo_personal(rol_usuario):
    st.markdown("## 👥 Nómina Maestra de Personal")
    st.markdown("Gestión centralizada de trabajadores para estadísticas y módulos.")

    # 1. Obtenemos la base actual
    df_personal = obtener_datos_nube("personal")

    # 2. BLINDAJE Y TRADUCTOR DE DATOS ANTIGUOS
    if not df_personal.empty:
        df_personal.columns = [str(c).strip().upper() for c in df_personal.columns]
        
        # Traducimos el Sexo antiguo ("Masculino") al nuevo formato ("MASCULINO")
        if 'SEXO' in df_personal.columns:
            df_personal['SEXO'] = df_personal['SEXO'].astype(str).str.upper().str.strip()
            
        # Traducimos las sucursales antiguas a las nuevas opciones oficiales
        if 'SUCURSAL' in df_personal.columns:
            df_personal['SUCURSAL'] = df_personal['SUCURSAL'].astype(str).str.upper().str.strip()
            mapeo_sucursales = {
                "ECOM": "ECOM VALDIVIA",
                "ELECTROCOM": "ECOM VALDIVIA",
                "ELECTROCOM VALDIVIA": "ECOM VALDIVIA",
                "MCT": "MCT VALDIVIA",
                "PLC": "PLC VALDIVIA",
                "PLACA CENTRO": "PLC VALDIVIA",
                "NAN": ""
            }
            df_personal['SUCURSAL'] = df_personal['SUCURSAL'].replace(mapeo_sucursales)
    else:
        df_personal = pd.DataFrame(columns=["RUT", "NOMBRE", "SUCURSAL", "CARGO", "SEXO", "ESTADO"])

    # Verificamos que existan todas las columnas
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
        
        # Filtro matemático
        df_activos = df_personal[
            (df_personal['ESTADO'] == 'Activo') & 
            (df_personal['SUCURSAL'] != 'PREVENCION (PRUEBAS)')
        ]
        
        st.metric("Dotación Real Activa (Para Estadísticas Oficiales)", len(df_activos))

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
                        "ESTADO": "Activo"
                    }
                    if guardar_fila_nube(nuevo_registro, "personal"):
                        st.success("✅ Trabajador agregado exitosamente.")
                        st.rerun() 
                else:
                    st.error("⚠️ Los campos RUT y Nombre son obligatorios.")

    # --- PESTAÑA 3: IMPORTADOR MASIVO ---
    with tab_masivo:
        import re
        import time
        
        # --- INICIO DEL PUENTE TALANA ---
        st.markdown("### 📥 Puente Talana (Carga Directa Inteligente)")
        st.info("💡 Ve a Talana, selecciona las filas de los trabajadores, cópialas (Ctrl+C) y pégalas aquí (Ctrl+V).")

        if 'talana_paso' not in st.session_state:
            st.session_state.talana_paso = 1
            st.session_state.talana_nuevos = []

        if st.session_state.talana_paso == 1:
            texto_pegado = st.text_area("Pega los datos copiados de Talana aquí:", height=150, placeholder="Ej: \n14280603-7\nAguero Morales, Daniella... \t Jefe \t Plc. Valdivia")
            
            if st.button("🔍 Escanear y Detectar", type="primary") and texto_pegado:
                nuevos_trabajadores = []
                lineas = texto_pegado.split('\n')
                ultimo_rut_visto = ""
                
                for linea in lineas:
                    linea = linea.strip()
                    if not linea: continue
                    
                    # 1. Capturar el RUT que Talana deja huérfano en la línea de arriba
                    es_rut = re.search(r"^(\d{7,8}-[\dkK])$", linea, re.IGNORECASE)
                    if es_rut:
                        ultimo_rut_visto = es_rut.group(1).upper()
                        continue
                        
                    # 2. Capturar la línea principal de datos (Ignoramos el encabezado si lo pegaste por error)
                    if '\t' in linea and "Persona" not in linea and "Gerencia" not in linea:
                        partes = linea.split('\t')
                        
                        if len(partes) >= 3:
                            nombre = partes[0].strip().upper()
                            cargo = partes[1].strip().upper()
                            sucursal_raw = partes[2].strip().lower()
                            
                            # Validar el RUT (Usamos el que memorizó arriba, o lo buscamos si vino en esta misma línea)
                            rut_puro = ultimo_rut_visto
                            if len(partes) > 3 and re.search(r"\d{7,8}-[\dkK]", str(partes[3])):
                                rut_puro = re.search(r"\d{7,8}-[\dkK]", str(partes[3])).group(0).upper()
                                
                            if rut_puro and nombre:
                                # Traductor automático de sucursales oficiales
                                if "ecom" in sucursal_raw or "electrocom" in sucursal_raw: sucursal = "ECOM VALDIVIA"
                                elif "mct" in sucursal_raw: sucursal = "MCT VALDIVIA"
                                elif "plc" in sucursal_raw or "placa" in sucursal_raw: sucursal = "PLC VALDIVIA"
                                else: sucursal = "ECOM VALDIVIA" # Por defecto si no coincide
                                
                                # Asegurar que no se repitan en esta misma carga
                                if not any(t['RUT'] == rut_puro for t in nuevos_trabajadores):
                                    nuevos_trabajadores.append({
                                        "RUT": rut_puro, "NOMBRE": nombre, "SUCURSAL": sucursal,
                                        "CARGO": cargo, "SEXO": "Seleccionar", "ESTADO": "Activo"
                                    })
                                
                                # Limpiamos la memoria del RUT para el siguiente trabajador
                                ultimo_rut_visto = "" 
                
                if nuevos_trabajadores:
                    st.session_state.talana_nuevos = nuevos_trabajadores
                    st.session_state.talana_paso = 2
                    st.rerun()
                else:
                    st.error("❌ No detecté datos. Asegúrate de copiar las filas completas de Talana.")

        # PASO 2: MESA DE VALIDACIÓN DE SEXO
        elif st.session_state.talana_paso == 2:
            df_nuevos = pd.DataFrame(st.session_state.talana_nuevos)
            st.success(f"✅ ¡He detectado {len(df_nuevos)} trabajadores desde Talana!")
            st.warning("⚠️ Paso Final: Selecciona el sexo de cada trabajador en la tabla para habilitar el guardado.")
            
            df_editado = st.data_editor(
                df_nuevos,
                column_config={
                    "SEXO": st.column_config.SelectboxColumn("Sexo (Obligatorio)", options=["Seleccionar", "MASCULINO", "FEMENINO"], required=True),
                    "RUT": st.column_config.TextColumn(disabled=True),
                    "NOMBRE": st.column_config.TextColumn(disabled=True),
                    "CARGO": st.column_config.TextColumn(disabled=True),
                    "SUCURSAL": st.column_config.TextColumn(disabled=True),
                    "ESTADO": None # Oculto en la vista
                },
                hide_index=True, use_container_width=True
            )
            
            faltan_sexo = len(df_editado[df_editado['SEXO'] == "Seleccionar"])
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ Descartar todo y volver"):
                    st.session_state.talana_paso = 1
                    st.rerun()
            with col2:
                if faltan_sexo > 0:
                    st.button(f"Falta definir sexo en {faltan_sexo} trabajadores", disabled=True, use_container_width=True)
                else:
                    if st.button("💾 Confirmar Carga Definitiva", type="primary", use_container_width=True):
                        with st.spinner("Sincronizando nómina en la nube..."):
                            df_existente = obtener_datos_nube("personal")
                            df_final = fusionar_nominas(df_existente, df_editado)
                            
                            if actualizar_hoja_completa(df_final, "personal"):
                                st.success("🎉 ¡Nómina actualizada exitosamente!")
                                st.session_state.talana_paso = 1
                                st.cache_data.clear()
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Error al guardar en Google Sheets.")
        # --- FIN DEL PUENTE TALANA ---
