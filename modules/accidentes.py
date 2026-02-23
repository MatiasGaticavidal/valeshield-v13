import streamlit as st
import pandas as pd
import os
from datetime import datetime
# Importamos las funciones desde utils.py
from utils import ARCHIVO_ACCIDENTES, ARCHIVO_PERSONAL, limpiar_rut, guardar_fila_nube, obtener_datos_nube

def cargar_datos_personal_completo():
    """Descarga la nómina desde la nube y prepara el diccionario de búsqueda"""
    # 1. Llamamos a la función que ya existe en utils
    df = obtener_datos_nube("personal") 
    
    if not df.empty:
        # 2. Estandarizamos encabezados
        df.columns = [c.strip().upper() for c in df.columns]
        if 'RUT' in df.columns:
            # 3. Creamos el diccionario con Nombre y Sucursal
            return df.set_index(df['RUT'].apply(limpiar_rut))[['NOMBRE', 'SUCURSAL']].to_dict('index')
    return {}

def mostrar_modulo_accidentes(rol):
    st.markdown("## 🏥 Registro y Control de Accidentes (v14.0 Cloud Sync)")
    
    # Cargar base de datos para autocompletado
    dict_personal = cargar_datos_personal_completo()
    
    # Sucursales oficiales de ELECTROCOM
    opciones_sucursal = ["ELECTROCOM", "MCT", "PLACA CENTRO", "TERRENO/EXTERNO"]

    # --- BÚSQUEDA REACTIVA (Fuera del Form) ---
    st.markdown("### 🔍 Identificación del Trabajador")
    rut_busqueda = st.text_input("Ingrese RUT del Trabajador (Ej: 12345678-9)")
    
    nombre_sugerido = ""
    indice_sucursal = 0 # Por defecto apunta a ELECTROCOM

    if rut_busqueda:
        rut_limpio = limpiar_rut(rut_busqueda)
        info = dict_personal.get(rut_limpio)
        
        if info:
            nombre_sugerido = info.get('NOMBRE', "")
            suc_base = str(info.get('SUCURSAL', "")).strip().upper()
            
            # Saltamos automáticamente a la sucursal correcta
            if suc_base in opciones_sucursal:
                indice_sucursal = opciones_sucursal.index(suc_base)
            elif "ECOM" in suc_base: indice_sucursal = 0
            elif "MCT" in suc_base: indice_sucursal = 1
            elif "PLACA" in suc_base: indice_sucursal = 2
                
            st.success(f"✅ Detectado: **{nombre_sugerido}** de sucursal **{suc_base}**")
        else:
            st.warning("⚠️ RUT no encontrado en la base de datos cloud.")

    # --- PESTAÑAS DE TRABAJO ---
    tab1, tab2 = st.tabs(["📝 Registrar Nuevo Accidente", "📂 Historial en la Nube"])

    with tab1:
        with st.form("form_accidente_v14_final", clear_on_submit=True):
            st.markdown("### 1. Datos del Evento")
            col_f, col_h, col_s = st.columns(3)
            fecha = col_f.date_input("Fecha del Accidente")
            hora = col_h.time_input("Hora del Accidente")
            # El index=indice_sucursal hace la magia
            sucursal_evento = col_s.selectbox("Sucursal del Siniestro", opciones_sucursal, index=indice_sucursal)
            
            st.markdown("### 2. Información del Accidentado")
            trabajador = st.text_input("Nombre del Trabajador", value=nombre_sugerido)
            
            col_ant1, col_ant2 = st.columns(2)
            antiguedad_empresa = col_ant1.number_input("Antigüedad en la empresa (meses)", min_value=0, step=1)
            antiguedad_cargo = col_ant2.number_input("Tiempo en el cargo actual (meses)", min_value=0, step=1)

            st.markdown("### 3. Clasificación y Daños")
            col_t, col_d = st.columns(2)
            tipo_accidente = col_t.selectbox("Tipo de Accidente", [
                "Accidente CTP (Con Tiempo Perdido)", 
                "Accidente STP (Sin Tiempo Perdido)", 
                "Accidente de Trayecto",
                "Incidente / Cuasi Accidente",
                "Enfermedad Profesional"
            ])
            dias_perdidos = col_d.number_input("Días Perdidos Estimados", min_value=0, step=1)
            
            col_p, col_l = st.columns(2)
            parte_cuerpo = col_p.text_input("Parte del cuerpo lesionada")
            tipo_lesion = col_l.text_input("Tipo de lesión")
            
            st.markdown("### 4. Relato y Acciones (Estructura v12.0)")
            relato = st.text_area("Relato de lo ocurrido (Detalle completo)")
            acciones = st.text_area("Acciones inmediatas tomadas")
            
            submit = st.form_submit_button("💾 Guardar y Sincronizar", type="primary", use_container_width=True)

            if submit:
                if not trabajador or not relato or not rut_busqueda:
                    st.error("❌ Los campos RUT, Nombre y Relato son obligatorios.")
                else:
                    nuevo_registro = {
                        "Fecha": fecha.strftime("%Y-%m-%d"),
                        "Hora": hora.strftime("%H:%M"),
                        "Sucursal": sucursal_evento,
                        "RUT": limpiar_rut(rut_busqueda),
                        "Trabajador": trabajador,
                        "Antiguedad_Empresa": antiguedad_empresa,
                        "Antiguedad_Cargo": antiguedad_cargo,
                        "Tipo": tipo_accidente,
                        "Dias_Perdidos": dias_perdidos,
                        "Parte_Cuerpo": parte_cuerpo,
                        "Tipo_Lesion": tipo_lesion,
                        "Relato": relato,
                        "Acciones": acciones,
                        "Estado": "Pendiente Investigación"
                    }
                    
                    with st.spinner("Sincronizando..."):
                        exito = guardar_fila_nube(nuevo_registro, "Accidentes")
                    
                    if exito:
                        st.success(f"✅ Reporte de {trabajador} guardado en Google Sheets.")
                        st.balloons()
                    else:
                        st.error("❌ Error de conexión con la nube.")

    with tab2:
        st.markdown("### 📂 Base de Datos en Tiempo Real")
        df_historial = obtener_datos_nube("Accidentes")
        if not df_historial.empty:
            st.dataframe(df_historial, use_container_width=True, hide_index=True)
