import streamlit as st
import pandas as pd
import os
from datetime import datetime
# Importación de funciones maestras desde tu archivo utils.py
from utils import ARCHIVO_ACCIDENTES, ARCHIVO_PERSONAL, limpiar_rut, guardar_fila_nube, obtener_datos_nube

def cargar_datos_personal_completo():
    """Descarga la nómina desde la nube: RUT, Nombre y Sucursal"""
    # Usamos "personal" en minúsculas como está en tu pestaña de Google Sheets
    df = obtener_datos_nube("personal")
    if not df.empty:
        # Estandarizamos encabezados a Mayúsculas para evitar errores de lectura
        df.columns = [c.strip().upper() for c in df.columns]
        if 'RUT' in df.columns:
            # Creamos diccionario indexado por RUT para búsqueda instantánea
            return df.set_index(df['RUT'].apply(limpiar_rut))[['NOMBRE', 'SUCURSAL']].to_dict('index')
    return {}

def mostrar_modulo_accidentes(rol):
    st.markdown("## 🏥 Registro y Control de Accidentes (v14.0 Cloud)")
    
    # 1. Cargar base de datos completa de trabajadores
    dict_personal = cargar_datos_personal_completo()
    
    # Lista oficial de sucursales (Exactamente como las dejaste en el Sheets)
    opciones_sucursal = ["ELECTROCOM", "MCT", "PLACA CENTRO", "TERRENO/EXTERNO"]

    # --- BLOQUE DE IDENTIFICACIÓN (Fuera del form para reactividad inmediata) ---
    st.markdown("### 🔍 Identificación del Trabajador")
    rut_busqueda = st.text_input("Ingrese RUT del Trabajador (Ej: 12345678-9)", placeholder="Escriba aquí para auto-completar...")
    
    nombre_sugerido = ""
    indice_sucursal = 0 # Por defecto apunta a ELECTROCOM

    if rut_busqueda:
        rut_limpio = limpiar_rut(rut_busqueda)
        info_trabajador = dict_personal.get(rut_limpio)
        
        if info_trabajador:
            nombre_sugerido = info_trabajador.get('NOMBRE', "")
            # Limpiamos el texto de la sucursal que viene del Sheets
            suc_base = str(info_trabajador.get('SUCURSAL', "")).strip().upper()
            
            # Lógica de salto automático de sucursal
            if suc_base in opciones_sucursal:
                indice_sucursal = opciones_sucursal.index(suc_base)
            elif "ECOM" in suc_base: # Por si acaso dice ELECTROCOM VALDIVIA o ECOM
                indice_sucursal = 0
            elif "MCT" in suc_base:
                indice_sucursal = 1
            elif "PLACA" in suc_base:
                indice_sucursal = 2
                
            st.success(f"✅ **{nombre_sugerido}** detectado en base de datos (**{suc_base}**)")
        else:
            st.warning("⚠️ RUT no encontrado. Si es un trabajador nuevo, regístralo primero en la pestaña 'personal' del Sheets.")

    # --- PESTAÑAS DE TRABAJO ---
    tab1, tab2 = st.tabs(["📝 Formulario de Registro", "📂 Historial en la Nube"])

    with tab1:
        with st.form("form_accidente_v14_final", clear_on_submit=True):
            st.markdown("### 1. Datos del Evento")
            col_f, col_h, col_s = st.columns(3)
            fecha = col_f.date_input("Fecha del Accidente")
            hora = col_h.time_input("Hora del Accidente")
            # El index=indice_sucursal es lo que hace que el selector cambie solo
            sucursal_evento = col_s.selectbox("Sucursal del Siniestro", opciones_sucursal, index=indice_sucursal)
            
            st.markdown("### 2. Información del Accidentado")
            # El nombre se auto-rellena con lo encontrado arriba
            trabajador = st.text_input("Nombre Completo del Trabajador", value=nombre_sugerido)
            
            col_ant1, col_ant2 = st.columns(2)
            antiguedad_empresa = col_ant1.number_input("Antigüedad en la empresa (meses)", min_value=0, step=1)
            antiguedad_cargo = col_ant2.number_input("Tiempo en el cargo actual (meses)", min_value=0, step=1)

            st.markdown("### 3. Clasificación y Gravedad")
            col_t, col_d = st.columns(2)
            tipo_accidente = col_t.selectbox("Tipo de Accidente", [
                "Accidente CTP (Con Tiempo Perdido)", 
                "Accidente STP (Sin Tiempo Perdido)", 
                "Accidente de Trayecto",
                "Incidente / Cuasi Accidente",
                "Enfermedad Profesional"
            ])
            dias_perdidos = col_d.number_input("Días Perdidos (Estimados)", min_value=0, step=1)
            
            col_p, col_l = st.columns(2)
            parte_cuerpo = col_p.text_input("Parte del cuerpo lesionada")
            tipo_lesion = col_l.text_input("Tipo de lesión (Fractura, esguince, etc.)")
            
            st.markdown("### 4. Relato y Acciones (Estructura v12.0)")
            relato = st.text_area("Relato de lo ocurrido (Detalle completo)", help="Describe qué estaba haciendo y cómo ocurrió.")
            acciones = st.text_area("Acciones inmediatas tomadas", help="Primeras medidas de control aplicadas.")
            
            submit = st.form_submit_button("💾 Guardar y Sincronizar Reporte", type="primary", use_container_width=True)

            if submit:
                if not trabajador or not relato or not rut_busqueda:
                    st.error("❌ Los campos RUT, Nombre y Relato son obligatorios.")
                else:
                    # Construcción del registro para Google Sheets
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
                    
                    with st.spinner("Enviando reporte a la nube..."):
                        # Se guarda en la pestaña 'Accidentes' de tu Google Sheets
                        exito = guardar_fila_nube(nuevo_registro, "Accidentes")
                    
                    if exito:
                        st.success(f"✅ ¡Excelente Matías! Reporte de {trabajador} sincronizado con éxito.")
                        st.balloons()
                    else:
                        st.error("❌ Error de sincronización. Verifica tu conexión o el archivo JSON.")

    with tab2:
        st.markdown("### 📂 Base de Datos en Tiempo Real")
        with st.spinner("Cargando registros históricos..."):
            df_historial = obtener_datos_nube("Accidentes")
        
        if not df_historial.empty:
            st.dataframe(df_historial, use_container_width=True, hide_index=True)
        else:
            st.info("No hay accidentes registrados aún en la pestaña 'Accidentes'.")
