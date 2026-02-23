import streamlit as st
import pandas as pd
import os
from datetime import datetime
# Importamos las nuevas funciones de la nube desde utils
from utils import ARCHIVO_ACCIDENTES, ARCHIVO_PERSONAL, limpiar_rut, guardar_fila_nube, obtener_datos_nube

def cargar_nombres_personal():
    """Carga la nómina desde la nube para el autocompletado"""
    df = obtener_datos_nube("Personal")
    if not df.empty:
        # Limpiar espacios y estandarizar columnas
        df.columns = [c.strip().upper() for c in df.columns]
        if 'RUT' in df.columns and 'NOMBRE' in df.columns:
            return dict(zip(df['RUT'].apply(limpiar_rut), df['NOMBRE']))
    return {}

def mostrar_modulo_accidentes(rol):
    st.markdown("## 🏥 Registro y Control de Accidentes (Cloud Sync)")
    
    # Cargar diccionario de personal desde la nube
    dict_personal = cargar_nombres_personal()

    tab1, tab2 = st.tabs(["📝 Registrar Nuevo Accidente", "📂 Historial en la Nube"])

    with tab1:
        with st.form("form_accidente", clear_on_submit=True):
            st.markdown("### 1. Datos del Evento")
            col1, col2, col3 = st.columns(3)
            fecha = col1.date_input("Fecha del Accidente")
            hora = col2.time_input("Hora del Accidente")
            sucursal = col3.selectbox("Sucursal", ["ELECTROCOM VALDIVIA", "MCT VALDIVIA", "PLACA CENTRO VALDIVIA", "TERRENO/EXTERNO"])
            
            st.markdown("### 2. Datos del Trabajador")
            col_b1, col_b2 = st.columns([1, 2])
            rut_busqueda = col_b1.text_input("Buscar por RUT (Ej: 12345678-9)")
            
            nombre_sugerido = ""
            if rut_busqueda:
                rut_limpio = limpiar_rut(rut_busqueda)
                nombre_sugerido = dict_personal.get(rut_limpio, "")
                if nombre_sugerido:
                    col_b1.success("✅ Trabajador encontrado")
                else:
                    col_b1.warning("⚠️ RUT no en Base de Datos Cloud")
            
            trabajador = col_b2.text_input("Nombre del Trabajador", value=nombre_sugerido)
            
            col_ant1, col_ant2 = st.columns(2)
            antiguedad_empresa = col_ant1.number_input("Antigüedad en el empleo (meses)", min_value=0, step=1)
            antiguedad_cargo = col_ant2.number_input("Tiempo en el cargo actual (meses)", min_value=0, step=1)

            st.markdown("### 3. Clasificación y Daños")
            col4, col5 = st.columns(2)
            tipo_accidente = col4.selectbox("Tipo de Accidente", [
                "Accidente CTP (Con Tiempo Perdido)", 
                "Accidente STP (Sin Tiempo Perdido)", 
                "Accidente de Trayecto",
                "Incidente / Cuasi Accidente",
                "Enfermedad Profesional"
            ])
            dias_perdidos = col5.number_input("Días Perdidos (Estimados/Reales)", min_value=0, step=1)
            
            col6, col7 = st.columns(2)
            parte_cuerpo = col6.text_input("Parte del cuerpo lesionada")
            tipo_lesion = col7.text_input("Tipo de lesión")
            
            st.markdown("### 4. Relato y Acciones Inmediatas")
            relato = st.text_area("Relato de lo ocurrido (Detalle completo)")
            acciones = st.text_area("Acciones inmediatas tomadas")
            
            submit = st.form_submit_button("💾 Guardar y Sincronizar con Google Drive", type="primary", use_container_width=True)

            if submit:
                if not trabajador or not relato:
                    st.error("❌ Por favor completa el Nombre del Trabajador y el Relato.")
                else:
                    # Estructura completa de la v12.0
                    nuevo_accidente = {
                        "Fecha": fecha.strftime("%Y-%m-%d"),
                        "Hora": hora.strftime("%H:%M"),
                        "Sucursal": sucursal,
                        "RUT": limpiar_rut(rut_busqueda) if rut_busqueda else "S/R",
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
                    
                    with st.spinner("Subiendo reporte a la nube..."):
                        exito = guardar_fila_nube(nuevo_accidente, "Accidentes")
                    
                    if exito:
                        st.success(f"✅ ¡Excelente Matías! Accidente de {trabajador} guardado en la nube.")
                        st.balloons()
                    else:
                        st.error("❌ Error de conexión. El registro quedó solo en memoria.")

    with tab2:
        st.markdown("### 📂 Base de Datos en Tiempo Real (Google Sheets)")
        with st.spinner("Obteniendo registros desde la nube..."):
            df_mostrar = obtener_datos_nube("Accidentes")
        
        if not df_mostrar.empty:
            # Filtros rápidos
            c_f1, c_f2 = st.columns(2)
            f_suc = c_f1.selectbox("Filtrar por Sucursal", ["Todas"] + list(df_mostrar['Sucursal'].unique()))
            f_tipo = c_f2.selectbox("Filtrar por Tipo", ["Todos"] + list(df_mostrar['Tipo'].unique()))
            
            df_filtrado = df_mostrar.copy()
            if f_suc != "Todas": df_filtrado = df_filtrado[df_filtrado['Sucursal'] == f_suc]
            if f_tipo != "Todos": df_filtrado = df_filtrado[df_filtrado['Tipo'] == f_tipo]
            
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
            
            # Exportación
            csv = df_filtrado.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Reporte Consolidado (CSV)",
                data=csv,
                file_name=f"valeshield_nube_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("No hay registros en la nube o la conexión está fallando.")