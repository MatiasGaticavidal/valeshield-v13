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

# --- 1. LÓGICA DE EXTRACCIÓN CON IA ---
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
        # Ajuste para leer formatos como DD-MM-YYYY que vienen de tu CSV
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

# --- 3. INTERFAZ DEL MÓDULO (FUSIONADA) ---
def mostrar_modulo_examenes():
    st.header("🩺 Control de Exámenes Ocupacionales")
    st.markdown("Plataforma automatizada para el control de vigencias y lectura inteligente de informes Mutual.")
    
    # --- CARGA INICIAL DESDE TU CSV ---
    if 'db_examenes' not in st.session_state:
        ruta_examenes = "base_examenes.csv"
        if os.path.exists(ruta_examenes):
            df = pd.read_csv(ruta_examenes, sep=None, engine='python', encoding='latin1')
            # Renombramos columnas para que coincidan con la lógica de tu uploader
            df = df.rename(columns={'Tipo_Examen': 'Categoría', 'Vencimiento': 'Vigencia'})
            
            # Calculamos los días por vencer para los datos antiguos
            df['Días por Vencer'] = df.apply(lambda row: calcular_estado(str(row['Vigencia']), row['Estado'])[1], axis=1)
            
            st.session_state.db_examenes = df
        else:
            st.session_state.db_examenes = pd.DataFrame(columns=[
                'RUT', 'Nombre', 'Cargo', 'Sucursal', 'Categoría', 'Vigencia', 'Días por Vencer', 'Estado'
            ])
    
    # --- PANEL DE INGRESO (LECTOR PDF) ---
    with st.expander("➕ Subir Nuevo Examen Ocupacional (PDF)", expanded=False):
        st.info("Sube el PDF oficial de la Mutual. El sistema extraerá las fechas y la condición automáticamente.")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            categoria_select = st.selectbox("Asignar a Categoría:", [
                "Chofer", "Grua Horquilla", "Dimensionado", "Enchapado", "Trabajo en Altura"
            ])
            
        with col2:
            archivo_subido = st.file_uploader("Adjuntar Informe (PDF)", type=['pdf'])
            
        if archivo_subido is not None:
            if st.button("🧠 Procesar con Valentin Shield"):
                with st.spinner("Leyendo PDF y analizando conclusiones médicas..."):
                    texto = extraer_texto_pdf(archivo_subido)
                    datos_extraidos = analizar_pdf_mutual(texto)
                    
                    if datos_extraidos:
                        estado, dias = calcular_estado(datos_extraidos['vigencia'], datos_extraidos['condicion'])
                        
                        st.success("¡Extracción exitosa!")
                        
                        nuevo_registro = {
                            'RUT': datos_extraidos.get('rut', 'N/A'),
                            'Nombre': datos_extraidos.get('nombre', 'N/A'),
                            'Cargo': datos_extraidos.get('cargo', 'N/A'),
                            'Sucursal': datos_extraidos.get('sucursal', 'N/A'),
                            'Categoría': categoria_select,
                            'Vigencia': datos_extraidos.get('vigencia', 'N/A'),
                            'Días por Vencer': dias,
                            'Estado': estado
                        }
                        
                        df_actual = st.session_state.db_examenes
                        if nuevo_registro['RUT'] in df_actual['RUT'].values:
                            idx = df_actual.index[df_actual['RUT'] == nuevo_registro['RUT']].tolist()[0]
                            st.session_state.db_examenes.loc[idx] = nuevo_registro
                            st.info("Registro actualizado correctamente.")
                        else:
                            st.session_state.db_examenes = pd.concat([df_actual, pd.DataFrame([nuevo_registro])], ignore_index=True)
                            st.info("Nuevo trabajador ingresado a la matriz.")
                    else:
                        st.error("No se pudo extraer la información. Revisa el formato del PDF.")

    st.divider()

    # --- VISUALIZACIÓN POR CATEGORÍAS (PESTAÑAS AUTOMÁTICAS) ---
    df = st.session_state.db_examenes
    if not df.empty:
        categorias = df['Categoría'].dropna().unique()
        # Creamos pestañas dinámicas más una para "Ver Todo"
        nombres_pestanas = [f"📋 {cat}" for cat in categorias] + ["🌍 Ver Todo"]
        tabs = st.tabs(nombres_pestanas)
        
        for i, cat in enumerate(categorias):
            with tabs[i]:
                df_cat = df[df['Categoría'] == cat].copy()
                df_cat = df_cat.sort_values(by='Días por Vencer', ascending=True)
                
                vencidos = len(df_cat[df_cat['Estado'].str.contains('VENCIDO', na=False)])
                if vencidos > 0:
                    st.error(f"⚠️ Alerta: Tienes {vencidos} exámenes vencidos en esta categoría.")
                
                st.dataframe(df_cat.style.map(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)

# --- NUEVO: GESTOR DE RESPALDOS POR PESTAÑA ---
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander(f"📎 Adjuntar Respaldo PDF para trabajador en {cat}"):
                    col_sel, col_up = st.columns([1, 1])
                    with col_sel:
                        trabajador = st.selectbox(f"Seleccionar Trabajador:", df_cat['Nombre'].tolist(), key=f"sel_{cat}")
                    with col_up:
                        pdf_respaldo = st.file_uploader("Subir PDF de Mutual", type=['pdf'], key=f"up_{cat}")
                    
                    if st.button("💾 Guardar Evidencia", key=f"btn_{cat}"):
                        if pdf_respaldo is not None:
                            # 1. Creamos la carpeta de respaldos si no existe
                            if not os.path.exists("respaldos_mutual"):
                                os.makedirs("respaldos_mutual")
                            
                            # 2. Obtenemos el RUT para nombrar el archivo correctamente
                            rut_trabajador = df_cat[df_cat['Nombre'] == trabajador]['RUT'].values[0]
                            nombre_archivo = f"respaldos_mutual/{rut_trabajador}_Respaldo_{cat}.pdf".replace(" ", "_")
                            
                            # 3. Guardamos el PDF físicamente en tu carpeta
                            with open(nombre_archivo, "wb") as f:
                                f.write(pdf_respaldo.getbuffer())
                            
                            st.success(f"✅ ¡Respaldo guardado correctamente para {trabajador}! Archivo protegido.")
                        else:
                            st.warning("⚠️ Por favor, selecciona un archivo PDF primero.")
                
        with tabs[-1]: # La última pestaña es "Ver Todo"
            df_all = df.sort_values(by='Días por Vencer', ascending=True)
            st.dataframe(df_all.style.map(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)
    else:
        st.info("La matriz general está vacía. Asegúrate de que base_examenes.csv esté en la carpeta.")