import streamlit as st
import pandas as pd
from datetime import datetime
import PyPDF2
import json
import re
import os
from google.api_core.exceptions import ResourceExhausted
import time
import google.generativeai as genai
from utils import obtener_datos_nube, guardar_fila_nube, actualizar_hoja_completa

# --- 1. LÓGICA DE EXTRACCIÓN CON IA (INTACTA) ---
def extraer_texto_pdf(archivo_pdf):
    lector = PyPDF2.PdfReader(archivo_pdf)
    texto = ""
    for pagina in lector.pages:
        texto += pagina.extract_text()
    return texto

def analizar_pdf_mutual(texto_pdf):
    # Limpiamos caracteres extraños que ensucian el texto del PDF
    texto_input = texto_pdf.replace('"', '').replace("'", "")
    
    prompt = f"""
    ERES UN ASISTENTE EXPERTO EN PREVENCIÓN DE RIESGOS.
    Analiza el siguiente texto de un examen de la Mutual de Seguridad:
    
    TEXTO:
    {texto_input}
    
    INSTRUCCIONES CRÍTICAS:
    1. Busca el nombre después de 'Trabajador(a) :'.
    2. Busca el RUT después de 'RU-'.
    3. Busca la fecha después de 'Vigencia Hasta'. Ignora si hay dos puntos al final como '2027:'.
    4. El formato de fecha DEBE ser YYYY-MM-DD.
    5. Si dice 'no evidencia alteraciones que impidan', la condicion es 'APTO'.
    
    Responde ÚNICAMENTE un JSON puro, sin bloques de código ```, con esta estructura:
    {{
      "nombre": "NOMBRE COMPLETO",
      "rut": "RUT",
      "sucursal": "ECOM o MCT o PLC",
      "cargo": "CARGO",
      "vigencia": "YYYY-MM-DD",
      "condicion": "APTO o NO APTO"
    }}
    """
    
    for intento in range(3):
        try:
            modelo = genai.GenerativeModel('gemini-1.5-flash') # Usamos 1.5-flash por estabilidad
            respuesta = modelo.generate_content(prompt)
            
            # Limpieza extrema de la respuesta para asegurar JSON puro
            limpio = respuesta.text.strip()
            if "{" in limpio:
                limpio = limpio[limpio.find("{"):limpio.rfind("}")+1]
            
            datos = json.loads(limpio)
            
            # Limpieza manual de la fecha por si la IA dejó el ":"
            if 'vigencia' in datos:
                datos['vigencia'] = datos['vigencia'].replace(':', '').strip()
                
            return datos
        except Exception as e:
            if intento == 2:
                st.error(f"Error técnico en IA: {e}")
            time.sleep(1)
    return None

# --- 2. LÓGICA DE SEMAFORIZACIÓN ---
def calcular_estado(fecha_vigencia_str, condicion):
    if str(condicion).upper() == "NO APTO":
        return "⚫ RECHAZADO", 0
    
    try:
        try:
            vigencia = datetime.strptime(str(fecha_vigencia_str).strip(), '%d-%m-%Y').date()
        except:
            vigencia = datetime.strptime(str(fecha_vigencia_str).strip(), '%Y-%m-%d').date()
            
        hoy = datetime.now().date()
        dias_restantes = (vigencia - hoy).days
        
        if dias_restantes < 0:
            return "🔴 VENCIDO", dias_restantes
        elif dias_restantes <= 30:
            return "🟠 POR VENCER", dias_restantes
        else:
            return "🟢 VIGENTE", dias_restantes
    except:
        return "⚠️ ERROR FECHA", 0

def aplicar_colores(val):
    color = ''
    if 'VIGENTE' in str(val):
        color = 'background-color: #d4edda; color: #155724;'
    elif 'POR VENCER' in str(val):
        color = 'background-color: #fff3cd; color: #856404;'
    elif 'VENCIDO' in str(val):
        color = 'background-color: #f8d7da; color: #721c24;'
    elif 'RECHAZADO' in str(val) or 'NO APTO' in str(val):
        color = 'background-color: #e2e3e5; color: #383d41;'
    return color

# --- NUEVO: TRADUCTOR UNIVERSAL DE COLUMNAS ---
def normalizar_columnas(df_crudo):
    """Obliga a que las columnas se llamen exactamente como las necesita el sistema, sin importar cómo vengan"""
    df = df_crudo.copy()
    # Pasamos todo a mayúsculas para que no haya errores de tipeo
    df.columns = [str(c).upper().strip() for c in df.columns]
    
    # Diccionario de traducción (Si encuentra VENCIMIENTO, lo llama Vigencia, etc.)
    mapeo = {
        'RUT': 'RUT', 'NOMBRE': 'Nombre', 'CARGO': 'Cargo', 'SUCURSAL': 'Sucursal',
        'TIPO_EXAMEN': 'Categoría', 'CATEGORIA': 'Categoría', 'CATEGORÍA': 'Categoría',
        'VENCIMIENTO': 'Vigencia', 'VIGENCIA': 'Vigencia', 'ESTADO': 'Estado_Original'
    }
    df = df.rename(columns=mapeo)
    
    # Si falta alguna columna vital, la crea en blanco para que no colapse el sistema
    columnas_vitales = ['RUT', 'Nombre', 'Cargo', 'Sucursal', 'Categoría', 'Vigencia', 'Estado_Original']
    for col in columnas_vitales:
        if col not in df.columns:
            df[col] = "N/A"
            
    return df

# --- 3. INTERFAZ DEL MÓDULO ---
def mostrar_modulo_examenes():
    st.header("🩺 Control de Exámenes Ocupacionales")
    st.markdown("Plataforma automatizada para el control de vigencias y lectura inteligente de informes Mutual.")
    
    # --- CONEXIÓN A DATOS (NUBE + RESPALDO LOCAL CSV) ---
    with st.spinner("Cargando base de datos de trabajadores..."):
        try:
            df_nube = obtener_datos_nube("examenes")
            if not df_nube.empty:
                df = normalizar_columnas(df_nube)
            else:
                # SI LA NUBE FALLA O ESTÁ VACÍA, CARGA TU CSV HISTÓRICO SÍ O SÍ
                ruta_examenes = "base_examenes.csv"
                if os.path.exists(ruta_examenes):
                    df_csv = pd.read_csv(ruta_examenes, sep=None, engine='python', encoding='latin1')
                    df = normalizar_columnas(df_csv)
                else:
                    df = pd.DataFrame(columns=['RUT', 'Nombre', 'Cargo', 'Sucursal', 'Categoría', 'Vigencia', 'Estado_Original'])
            
            # Recalculamos semáforos en vivo
            if not df.empty:
                df['Días por Vencer'] = df.apply(lambda row: calcular_estado(str(row['Vigencia']), str(row['Estado_Original']))[1], axis=1)
                df['Estado'] = df.apply(lambda row: calcular_estado(str(row['Vigencia']), str(row['Estado_Original']))[0], axis=1)
            
            st.session_state.db_examenes = df
            
        except Exception as e:
            st.error(f"Error crítico al cargar datos: {e}")
            st.session_state.db_examenes = pd.DataFrame()

    # --- BOTÓN PARA AÑADIR NUEVOS TRABAJADORES (RECUPERADO) ---
    with st.expander("➕ Subir Nuevo Examen Ocupacional (Añadir Trabajador)", expanded=False):
        st.info("Sube el PDF oficial de la Mutual. El sistema extraerá las fechas y agregará al trabajador a la base.")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            categoria_select = st.selectbox("Asignar a Categoría:", [
                "Chofer", "Grua Horquilla", "Dimensionado", "Enchapado", "Trabajo en Altura"
            ])
            
        with col2:
            archivo_subido = st.file_uploader("Adjuntar Informe (PDF)", type=['pdf'], key="nuevo_trabajador")
            
        if archivo_subido is not None:
            if st.button("🧠 Procesar con Valentin Shield"):
                with st.spinner("Leyendo PDF y analizando conclusiones médicas..."):
                    texto = extraer_texto_pdf(archivo_subido)
                    datos_extraidos = analizar_pdf_mutual(texto)
                    
                    if datos_extraidos:
                        nuevo_registro_nube = {
                            "RUT": datos_extraidos.get('rut', 'N/A'),
                            "NOMBRE": datos_extraidos.get('nombre', 'N/A'),
                            "CARGO": datos_extraidos.get('cargo', 'N/A'),
                            "SUCURSAL": datos_extraidos.get('sucursal', 'N/A'),
                            "TIPO_EXAMEN": categoria_select,
                            "VENCIMIENTO": datos_extraidos.get('vigencia', 'N/A'),
                            "ESTADO": datos_extraidos.get('condicion', 'APTO'),
                            "URL_PDF": "Respaldo IA",
                            "FECHA_SUBIDA": datetime.now().strftime("%Y-%m-%d")
                        }
                        
                        if guardar_fila_nube(nuevo_registro_nube, "examenes"):
                            st.success(f"✅ ¡Trabajador {nuevo_registro_nube['NOMBRE']} agregado con éxito!")
                            st.balloons()
                            st.cache_data.clear()
                            time.sleep(2) # F5 Automático
                            st.rerun()
                        else:
                            st.error("Error al guardar en Google Sheets.")
                    else:
                        st.error("No se pudo extraer la información del PDF.")

    st.divider()

    # --- PANTALLA PRINCIPAL (PESTAÑAS) ---
    df = st.session_state.db_examenes
    if not df.empty:
        categorias = df['Categoría'].dropna().unique()
        nombres_pestanas = [f"📋 {cat}" for cat in categorias] + ["🌍 Ver Todo"]
        tabs = st.tabs(nombres_pestanas)
        
        # AQUÍ ESTÁN LAS COLUMNAS EXACTAS QUE SE VAN A MOSTRAR, ASEGURANDO LA VIGENCIA
        columnas_mostrar = ['RUT', 'Nombre', 'Cargo', 'Sucursal', 'Categoría', 'Vigencia', 'Estado', 'Días por Vencer']
        
        for i, cat in enumerate(categorias):
            with tabs[i]:
                df_cat = df[df['Categoría'] == cat].copy()
                df_cat = df_cat.sort_values(by='Días por Vencer', ascending=True)
                
                vencidos = len(df_cat[df_cat['Estado'].str.contains('VENCIDO', na=False)])
                if vencidos > 0:
                    st.error(f"⚠️ Alerta: Tienes {vencidos} exámenes vencidos en esta categoría.")
                
                # MOSTRAR TABLA CON FECHA DE VIGENCIA GARANTIZADA
                try:
                    st.dataframe(df_cat[columnas_mostrar].style.map(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)
                except AttributeError:
                    st.dataframe(df_cat[columnas_mostrar].style.applymap(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)

                # --- GESTOR DE RESPALDOS (RENOVAR FECHA PARA TRABAJADORES EXISTENTES) ---
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander(f"📎 Renovar Vigencia PDF para trabajador en {cat}"):
                    col_sel, col_up = st.columns([1, 1])
                    with col_sel:
                        trabajador = st.selectbox(f"Seleccionar Trabajador:", df_cat['Nombre'].tolist(), key=f"sel_{cat}")
                    with col_up:
                        pdf_respaldo = st.file_uploader("Subir NUEVO Informe Mutual (PDF)", type=['pdf'], key=f"up_{cat}")
                    
                    if st.button("💾 Renovar Fecha y Actualizar Nube", key=f"btn_{cat}", type="primary"):
                        if pdf_respaldo is not None:
                            with st.spinner("🤖 Analizando renovación con IA..."):
                                if not os.path.exists("respaldos_mutual"):
                                    os.makedirs("respaldos_mutual")
                                rut_trabajador = df_cat[df_cat['Nombre'] == trabajador]['RUT'].values[0]
                                nombre_archivo = f"respaldos_mutual/{rut_trabajador}_Respaldo_{cat}.pdf".replace(" ", "_")
                                
                                with open(nombre_archivo, "wb") as f:
                                    f.write(pdf_respaldo.getbuffer())
                                
                                texto_nuevo = extraer_texto_pdf(pdf_respaldo)
                                datos_nuevos = analizar_pdf_mutual(texto_nuevo)
                                
                                if datos_nuevos and datos_nuevos.get('vigencia'):
                                    df_para_nube = st.session_state.db_examenes.copy()
                                    idx = df_para_nube.index[df_para_nube['RUT'] == rut_trabajador].tolist()[0]
                                    df_para_nube.at[idx, 'Vigencia'] = datos_nuevos['vigencia']
                                    df_para_nube.at[idx, 'Estado_Original'] = datos_nuevos.get('condicion', 'APTO')
                                    
                                    # TRADUCCIÓN INVERSA PARA GOOGLE SHEETS
                                    df_para_nube = df_para_nube.rename(columns={
                                        'Nombre': 'NOMBRE', 'Cargo': 'CARGO', 'Sucursal': 'SUCURSAL', 
                                        'Categoría': 'TIPO_EXAMEN', 'Vigencia': 'VENCIMIENTO', 'Estado_Original': 'ESTADO'
                                    })
                                    columnas_a_borrar = [col for col in ['Días por Vencer', 'Estado'] if col in df_para_nube.columns]
                                    df_para_nube = df_para_nube.drop(columns=columnas_a_borrar).fillna("")
                                    
                                    if actualizar_hoja_completa(df_para_nube, "examenes"):
                                        st.success(f"✅ ¡Vigencia de {trabajador} renovada hasta {datos_nuevos['vigencia']}!")
                                        st.balloons()
                                        st.cache_data.clear()
                                        time.sleep(2) # F5 AUTOMÁTICO
                                        st.rerun() 
                                    else:
                                        st.error("❌ Error al guardar en la nube.")
                                else:
                                    st.error("⚠️ La IA no pudo extraer la nueva fecha.")
                        else:
                            st.warning("⚠️ Selecciona un archivo PDF primero.")
        
        with tabs[-1]:
            df_all = df.sort_values(by='Días por Vencer', ascending=True)
            try:
                st.dataframe(df_all[columnas_mostrar].style.map(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)
            except AttributeError:
                st.dataframe(df_all[columnas_mostrar].style.applymap(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)
    else:
        st.info("La matriz general está vacía. Asegúrate de tener datos en la pestaña 'examenes' o en tu archivo CSV.")

