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
        st.markdown("### 📥 Puente Talana (Auditor Inteligente)")
        st.info("💡 Pega a todos los trabajadores (Ctrl+V). El sistema actualizará a los antiguos automáticamente y solo te pedirá datos de los nuevos.")

        if 'talana_paso' not in st.session_state:
            st.session_state.talana_paso = 1
            st.session_state.talana_nuevos = []
            st.session_state.talana_actualizaciones = []

        if st.session_state.talana_paso == 1:
            texto_pegado = st.text_area("Pega los datos copiados de Talana aquí:", height=150, placeholder="Ej: \n14280603-7\nAguero Morales, Daniella... \t Jefe \t Plc. Valdivia\nSi")
            
            if st.button("🔍 Auditar Nómina", type="primary") and texto_pegado:
                with st.spinner("Escaneando y comparando con la base de datos actual..."):
                    # 1. LECTURA BLINDADA DE LA BASE EXISTENTE
                    df_existente = obtener_datos_nube("personal")
                    ruts_existentes = []
                    if not df_existente.empty:
                        # Forzamos que los títulos de tu Sheets se lean en mayúsculas sin espacios
                        df_existente.columns = [str(c).strip().upper() for c in df_existente.columns]
                        if 'RUT' in df_existente.columns:
                            # Limpiamos los RUTs de la base para que la comparación sea perfecta
                            ruts_existentes = [limpiar_rut(str(r)) for r in df_existente['RUT'].dropna().tolist()]

                    trabajadores_procesados = {}
                    lineas = texto_pegado.split('\n')
                    ultimo_rut = ""
                    
                    for linea in lineas:
                        linea = linea.strip()
                        if not linea: continue
                        
                        # A. Captura RUT huérfano (Línea superior)
                        es_rut = re.search(r"^(\d{7,8}-[\dkK])$", linea, re.IGNORECASE)
                        if es_rut:
                            ultimo_rut = limpiar_rut(es_rut.group(1))
                            continue
                            
                        # B. Captura estado Vigente (Línea inferior: "Si" / "No")
                        if linea.lower() in ["si", "sí", "no"]:
                            estado_vigencia = "Activo" if linea.lower() in ["si", "sí"] else "Finiquitado"
                            if ultimo_rut and ultimo_rut in trabajadores_procesados:
                                trabajadores_procesados[ultimo_rut]["ESTADO"] = estado_vigencia
                            continue
                            
                        # C. Captura línea principal (Nombre, Cargo, Sucursal)
                        if '\t' in linea and "Persona" not in linea and "Gerencia" not in linea:
                            partes = linea.split('\t')
                            if len(partes) >= 3:
                                nombre = partes[0].strip().upper()
                                cargo = partes[1].strip().upper()
                                sucursal_raw = partes[2].strip().lower()
                                
                                rut_puro = ultimo_rut
                                if len(partes) > 3:
                                    rut_match = re.search(r"\d{7,8}-[\dkK]", str(partes[3]))
                                    if rut_match:
                                        rut_puro = limpiar_rut(rut_match.group(0))
                                        ultimo_rut = rut_puro
                                    
                                if rut_puro and nombre:
                                    # Traductor de sucursales a formato Maestro
                                    if "ecom" in sucursal_raw or "electrocom" in sucursal_raw: sucursal = "ECOM VALDIVIA"
                                    elif "mct" in sucursal_raw: sucursal = "MCT VALDIVIA"
                                    elif "plc" in sucursal_raw or "placa" in sucursal_raw: sucursal = "PLC VALDIVIA"
                                    else: sucursal = "ECOM VALDIVIA"
                                    
                                    trabajadores_procesados[rut_puro] = {
                                        "RUT": rut_puro, "NOMBRE": nombre, "SUCURSAL": sucursal,
                                        "CARGO": cargo, "ESTADO": "Activo" 
                                    }
                    
                    # 4. Filtro Inteligente: Separar Nuevos de Existentes
                    nuevos = []
                    actualizaciones = []
                    
                    for rut, datos in trabajadores_procesados.items():
                        if rut in ruts_existentes:
                            actualizaciones.append(datos) # Ya existe, lo mandamos a actualizar en silencio
                        else:
                            datos["SEXO"] = "Seleccionar"
                            nuevos.append(datos)          # Es nuevo, lo mandamos a la mesa de Sexo
                    
                    st.session_state.talana_actualizaciones = actualizaciones
                    
                    # Si hay trabajadores NUEVOS
                    if nuevos:
                        st.session_state.talana_nuevos = nuevos
                        st.session_state.talana_paso = 2
                        st.rerun()
                        
                    # Si NO hay nuevos, pero SÍ copiamos gente que ya estaba
                    elif actualizaciones:
                        df_actualizaciones = pd.DataFrame(actualizaciones)
                        df_final = fusionar_nominas(df_existente, df_actualizaciones)
                        if actualizar_hoja_completa(df_final, "personal"):
                            st.success(f"✅ ¡Todo en orden! No hay trabajadores nuevos. Se actualizaron en silencio los cargos, sucursales y vigencias de {len(actualizaciones)} trabajadores.")
                            st.balloons()
                            st.cache_data.clear()
                            time.sleep(3)
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar en Google Sheets.")
                    else:
                        st.error("❌ No detecté datos válidos. Asegúrate de copiar las filas completas.")

        # PASO 2: MESA DE VALIDACIÓN DE SEXO (SOLO PARA TRABAJADORES NUEVOS)
        elif st.session_state.talana_paso == 2:
            df_nuevos = pd.DataFrame(st.session_state.talana_nuevos)
            num_viejos = len(st.session_state.talana_actualizaciones)
            
            st.success(f"✅ ¡He detectado **{len(df_nuevos)} trabajadores NUEVOS**!")
            if num_viejos > 0:
                st.info(f"🔄 (Además, actualizaré los datos y el estado Vigente de los {num_viejos} trabajadores que ya estaban en el sistema).")
                
            st.warning("⚠️ Paso Final: Selecciona el Sexo solo de los trabajadores nuevos para guardar.")
            
            df_editado = st.data_editor(
                df_nuevos,
                column_config={
                    "SEXO": st.column_config.SelectboxColumn("Sexo (Obligatorio)", options=["Seleccionar", "MASCULINO", "FEMENINO"], required=True),
                    "RUT": st.column_config.TextColumn(disabled=True),
                    "NOMBRE": st.column_config.TextColumn(disabled=True),
                    "CARGO": st.column_config.TextColumn(disabled=True),
                    "SUCURSAL": st.column_config.TextColumn(disabled=True),
                    "ESTADO": None 
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
                    if st.button("💾 Confirmar e Ingresar a Nómina Maestra", type="primary", use_container_width=True):
                        with st.spinner("Sincronizando nómina en la nube..."):
                            df_existente = obtener_datos_nube("personal")
                            df_existente.columns = [str(c).strip().upper() for c in df_existente.columns]
                            
                            if st.session_state.talana_actualizaciones:
                                df_act = pd.DataFrame(st.session_state.talana_actualizaciones)
                                df_existente = fusionar_nominas(df_existente, df_act)
                                
                            df_final = fusionar_nominas(df_existente, df_editado)
                            
                            if actualizar_hoja_completa(df_final, "personal"):
                                st.success("🎉 ¡Base de Datos Maestra actualizada exitosamente!")
                                st.session_state.talana_paso = 1
                                st.cache_data.clear()
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Error al guardar en Google Sheets.")
        # --- FIN DEL PUENTE TALANA ---
