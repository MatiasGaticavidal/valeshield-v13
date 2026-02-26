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
from utils import obtener_datos_nube, actualizar_hoja_completa

# --- 1. LÓGICA DE EXTRACCIÓN CON IA (TU CÓDIGO INTACTO) ---
def extraer_texto_pdf(archivo_pdf):
    lector = PyPDF2.PdfReader(archivo_pdf)
    texto = ""
    for pagina in lector.pages:
        texto += pagina.extract_text()
    return texto

def analizar_pdf_mutual(texto_pdf):
    prompt = f"""
    ERES UN ASISTENTE EXPERTO EN PREVENCIÓN DE RIESGOS.
    Analiza el siguiente texto extraído de un Informe de Evaluación Ocupacional de la Mutual de Seguridad:
    
    TEXTO DEL PDF:
    {texto_pdf}
    
    Extrae la siguiente información y responde ÚNICAMENTE en formato JSON:
    1. "nombre": Nombre completo del trabajador.
    2. "rut": RUT del trabajador.
    3. "sucursal": Identifica si pertenece a "Electrocom", "Placa Centro" o "MCT".
    4. "cargo": Cargo evaluado (ej. Operario Bodega, Conductor, etc.).
    5. "vigencia": La fecha exacta del campo "Vigencia Hasta" en formato YYYY-MM-DD.
    6. "condicion": Si el texto dice "no evidencia alteraciones que impidan", pon "APTO". Si dice "evidencia alteraciones que contraindican" o similar, pon "NO APTO".
    
    FORMATO ESPERADO:
    {{
      "nombre": "Juan Perez",
      "rut": "12345678-9",
      "sucursal": "MCT",
      "cargo": "Operador Grúa",
      "vigencia": "2027-10-21",
      "condicion": "APTO"
    }}
    """
    
    for intento in range(3):
        try:
            modelo = genai.GenerativeModel('gemini-2.5-flash')
            respuesta = modelo.generate_content(prompt)
            txt = re.sub(r'```json\s*|```', '', respuesta.text).strip()
            return json.loads(txt)
        except ResourceExhausted:
            if intento < 2:
                time.sleep(30)
            else:
                return None
        except Exception as e:
            return None

# --- 2. LÓGICA DE SEMAFORIZACIÓN ---
def calcular_estado(fecha_vigencia_str, condicion):
    if str(condicion).upper() == "NO APTO":
        return "⚫ RECHAZADO", 0
    
    try:
        try:
            vigencia = datetime.strptime(fecha_vigencia_str, '%d-%m-%Y').date()
        except:
            vigencia = datetime.strptime(fecha_vigencia_str, '%Y-%m-%d').date()
            
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

# --- 3. INTERFAZ DEL MÓDULO ---
def mostrar_modulo_examenes():
    st.header("🩺 Control de Exámenes Ocupacionales")
    st.markdown("Plataforma automatizada para el control de vigencias y lectura inteligente de informes Mutual.")
    
    # --- CONEXIÓN A GOOGLE SHEETS / RESCATE DE DATOS ---
    with st.spinner("Conectando a base de datos..."):
        try:
            # Busca exactamente la pestaña 'examenes'
            df_nube = obtener_datos_nube("examenes")
            
            if not df_nube.empty:
                df = df_nube.copy()
                df = df.rename(columns={
                    'NOMBRE': 'Nombre', 
                    'CARGO': 'Cargo', 
                    'SUCURSAL': 'Sucursal', 
                    'TIPO_EXAMEN': 'Categoría', 
                    'VENCIMIENTO': 'Vigencia',
                    'ESTADO': 'Estado_Original'
                })
                df['Días por Vencer'] = df.apply(lambda row: calcular_estado(str(row['Vigencia']), row.get('Estado_Original', 'APTO'))[1], axis=1)
                df['Estado'] = df.apply(lambda row: calcular_estado(str(row['Vigencia']), row.get('Estado_Original', 'APTO'))[0], axis=1)
                st.session_state.db_examenes = df
            else:
                # SI FALLA LA NUBE, CARGA EL CSV ORIGINAL PARA QUE NO DESAPAREZCA LA PANTALLA
                st.warning("No se encontraron datos en Google Sheets. Cargando matriz local de respaldo...")
                ruta_examenes = "base_examenes.csv"
                if os.path.exists(ruta_examenes):
                    df = pd.read_csv(ruta_examenes, sep=None, engine='python', encoding='latin1')
                    df = df.rename(columns={'Tipo_Examen': 'Categoría', 'Vencimiento': 'Vigencia', 'Estado': 'Estado_Original'})
                    df['Días por Vencer'] = df.apply(lambda row: calcular_estado(str(row['Vigencia']), row.get('Estado_Original', 'APTO'))[1], axis=1)
                    df['Estado'] = df.apply(lambda row: calcular_estado(str(row['Vigencia']), row.get('Estado_Original', 'APTO'))[0], axis=1)
                    st.session_state.db_examenes = df
                else:
                    st.session_state.db_examenes = pd.DataFrame(columns=['RUT', 'Nombre', 'Cargo', 'Sucursal', 'Categoría', 'Vigencia', 'Días por Vencer', 'Estado'])
        except Exception as e:
            st.error(f"Error crítico al cargar datos: {e}")
            st.session_state.db_examenes = pd.DataFrame()

    # --- PANTALLA PRINCIPAL ---
    df = st.session_state.db_examenes
    if not df.empty:
        categorias = df['Categoría'].dropna().unique()
        nombres_pestanas = [f"📋 {cat}" for cat in categorias] + ["🌍 Ver Todo"]
        tabs = st.tabs(nombres_pestanas)
        
        for i, cat in enumerate(categorias):
            with tabs[i]:
                df_cat = df[df['Categoría'] == cat].copy()
                df_cat = df_cat.sort_values(by='Días por Vencer', ascending=True)
                
                vencidos = len(df_cat[df_cat['Estado'].str.contains('VENCIDO', na=False)])
                if vencidos > 0:
                    st.error(f"⚠️ Alerta: Tienes {vencidos} exámenes vencidos en esta categoría.")
                
                # MOSTRAR TABLA
                columnas_mostrar = ['RUT', 'Nombre', 'Cargo', 'Sucursal', 'Categoría', 'Vigencia', 'Estado', 'Días por Vencer']
                st.dataframe(df_cat[columnas_mostrar].style.map(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)

                # --- GESTOR DE RESPALDOS (EL QUE ACTUALIZA EN VIVO) ---
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander(f"📎 Renovar / Adjuntar Respaldo PDF para trabajador en {cat}"):
                    col_sel, col_up = st.columns([1, 1])
                    with col_sel:
                        trabajador = st.selectbox(f"Seleccionar Trabajador:", df_cat['Nombre'].tolist(), key=f"sel_{cat}")
                    with col_up:
                        pdf_respaldo = st.file_uploader("Subir NUEVO Informe Mutual (PDF)", type=['pdf'], key=f"up_{cat}")
                    
                    if st.button("💾 Guardar Evidencia y Renovar Fecha", key=f"btn_{cat}", type="primary"):
                        if pdf_respaldo is not None:
                            with st.spinner("🤖 Analizando nuevo documento con IA y sincronizando..."):
                                if not os.path.exists("respaldos_mutual"):
                                    os.makedirs("respaldos_mutual")
                                rut_trabajador = df_cat[df_cat['Nombre'] == trabajador]['RUT'].values[0]
                                nombre_archivo = f"respaldos_mutual/{rut_trabajador}_Respaldo_{cat}.pdf".replace(" ", "_")
                                
                                with open(nombre_archivo, "wb") as f:
                                    f.write(pdf_respaldo.getbuffer())
                                
                                texto_nuevo = extraer_texto_pdf(pdf_respaldo)
                                datos_nuevos = analizar_pdf_mutual(texto_nuevo)
                                
                                if datos_nuevos and datos_nuevos.get('vigencia'):
                                    estado_semaforo, dias_nuevos = calcular_estado(datos_nuevos['vigencia'], datos_nuevos['condicion'])
                                    
                                    # Actualizar registro en memoria
                                    idx = st.session_state.db_examenes.index[st.session_state.db_examenes['RUT'] == rut_trabajador].tolist()[0]
                                    st.session_state.db_examenes.at[idx, 'Vigencia'] = datos_nuevos['vigencia']
                                    st.session_state.db_examenes.at[idx, 'Estado_Original'] = datos_nuevos.get('condicion', 'APTO')
                                    st.session_state.db_examenes.at[idx, 'Estado'] = estado_semaforo
                                    st.session_state.db_examenes.at[idx, 'Días por Vencer'] = dias_nuevos
                                    
                                    # Preparar para nube
                                    df_para_nube = st.session_state.db_examenes.copy()
                                    df_para_nube = df_para_nube.rename(columns={
                                        'Nombre': 'NOMBRE', 'Cargo': 'CARGO', 'Sucursal': 'SUCURSAL', 
                                        'Categoría': 'TIPO_EXAMEN', 'Vigencia': 'VENCIMIENTO', 'Estado_Original': 'ESTADO'
                                    })
                                    columnas_a_borrar = [col for col in ['Días por Vencer', 'Estado'] if col in df_para_nube.columns]
                                    df_para_nube = df_para_nube.drop(columns=columnas_a_borrar)
                                    
                                    # Sincronizar
                                    if actualizar_hoja_completa(df_para_nube, "examenes"):
                                        st.success(f"✅ ¡Éxito! Respaldo guardado y vigencia de {trabajador} renovada hasta {datos_nuevos['vigencia']}.")
                                        st.balloons()
                                        st.cache_data.clear()
                                        time.sleep(2)
                                        st.rerun() # F5 AUTOMÁTICO
                                    else:
                                        st.error("❌ Error al guardar en la nube.")
                                else:
                                    st.error("⚠️ La IA no pudo extraer la nueva fecha.")
                        else:
                            st.warning("⚠️ Selecciona un archivo PDF primero.")
        
        with tabs[-1]:
            df_all = df.sort_values(by='Días por Vencer', ascending=True)
            columnas_mostrar = ['RUT', 'Nombre', 'Cargo', 'Sucursal', 'Categoría', 'Vigencia', 'Estado', 'Días por Vencer']
            st.dataframe(df_all[columnas_mostrar].style.map(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)
    else:
        st.info("La matriz general está vacía. Asegúrate de tener datos en la pestaña 'examenes' de Google Sheets.")
