import streamlit as st
import pandas as pd
from datetime import datetime
import PyPDF2
import json
import re
import os
import time
import google.generativeai as genai
from utils import obtener_datos_nube, guardar_fila_nube, actualizar_hoja_completa

# --- 1. CONFIGURACIÓN Y LÓGICA DE EXTRACCIÓN ---

def limpiar_rut_estricto(rut_str):
    """Limpia RUT de puntos, guiones y espacios para comparaciones 100% seguras"""
    if not rut_str or pd.isna(rut_str): return ""
    return re.sub(r'[^0-9Kk]', '', str(rut_str)).upper()

def analizar_pdf_mutual(texto_pdf):
    """Cerebro de IA optimizado para detectar fechas rebeldes y RUTs"""
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        else:
            st.error("Falta configuración de API Key en Secrets.")
            return None
            
        prompt = f"""
        ERES UN EXPERTO EN PREVENCIÓN DE RIESGOS. 
        Analiza el texto y extrae UNICAMENTE un JSON puro:
        1. "nombre": Nombre completo.
        2. "rut": RUT después de 'RU-'.
        3. "vigencia": Fecha tras 'Vigencia Hasta' (formato YYYY-MM-DD). Limpia ":" o "." al final.
        4. "condicion": 'APTO' o 'NO APTO'.
        5. "sucursal": 'Electrocom', 'MCT' o 'Placa Centro'.
        6. "cargo": Cargo del trabajador.

        TEXTO:
        {texto_pdf[:4500]}
        """
        
        # Usamos 1.5-flash por ser el más compatible con la versión v1beta de la API
        modelo = genai.GenerativeModel('gemini-1.5-flash')
        respuesta = modelo.generate_content(prompt)
        res_text = respuesta.text.strip()
        
        # Limpieza de bloque de código markdown si existe
        if "```" in res_text:
            res_text = re.sub(r'```(?:json)?|```', '', res_text).strip()
        
        # Encontrar el objeto JSON
        inicio = res_text.find("{")
        fin = res_text.rfind("}")
        if inicio != -1 and fin != -1:
            datos = json.loads(res_text[inicio:fin+1])
            
            # Limpieza profunda de la fecha (Tratamiento especial para "2027:")
            if 'vigencia' in datos and datos['vigencia']:
                raw_f = re.sub(r'[^0-9\-\./]', '', str(datos['vigencia']))
                raw_f = raw_f.replace('.', '-')
                # Intentar normalizar formatos comunes a YYYY-MM-DD
                for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
                    try:
                        datos['vigencia'] = datetime.strptime(raw_f, fmt).strftime("%Y-%m-%d")
                        break
                    except: continue
            return datos
    except Exception as e:
        st.error(f"Error en motor IA: {e}")
        return None

# --- 2. GESTIÓN DE COLORES Y SEMÁFORO ---

def calcular_estado(fecha_val, condicion):
    if str(condicion).upper() in ["NO APTO", "PENDIENTE", "RECHAZADO"]:
        return "⚫ RECHAZADO", 0
    try:
        f_str = str(fecha_val).strip()
        for fmt in ('%Y-%m-%d', '%d-%m-%Y'):
            try:
                vigencia = datetime.strptime(f_str, fmt).date()
                break
            except: continue
        
        dias = (vigencia - datetime.now().date()).days
        if dias < 0: return "🔴 VENCIDO", dias
        if dias <= 30: return "🟠 POR VENCER", dias
        return "🟢 VIGENTE", dias
    except:
        return "⚠️ ERROR FECHA", 0

def aplicar_colores(val):
    estilos = {'VIGENTE': '#d4edda', 'POR VENCER': '#fff3cd', 'VENCIDO': '#f8d7da', 'RECHAZADO': '#e2e3e5'}
    for k, color in estilos.items():
        if k in str(val): return f'background-color: {color}; color: black;'
    return ''

# --- 3. INTERFAZ Y PROCESOS DE GUARDADO ---

def mostrar_modulo_examenes():
    st.header("🩺 Control de Exámenes Ocupacionales")
    
    # --- CARGA Y NORMALIZACIÓN ---
    with st.spinner("Sincronizando con Google Sheets..."):
        df_nube = obtener_datos_nube("examenes")
        if not df_nube.empty:
            df = df_nube.copy()
            df.columns = [c.upper().strip() for c in df.columns]
            # Mapeo universal de columnas
            rename_map = {
                'NOMBRE':'Nombre', 'CARGO':'Cargo', 'SUCURSAL':'Sucursal', 
                'TIPO_EXAMEN':'Categoría', 'VENCIMIENTO':'Vigencia', 'ESTADO':'Estado_Original'
            }
            df = df.rename(columns=rename_map)
            df['Días por Vencer'] = df.apply(lambda r: calcular_estado(r.get('Vigencia',''), r.get('Estado_Original','APTO'))[1], axis=1)
            df['Estado'] = df.apply(lambda r: calcular_estado(r.get('Vigencia',''), r.get('Estado_Original','APTO'))[0], axis=1)
            st.session_state.db_examenes = df
        else:
            st.session_state.db_examenes = pd.DataFrame()

    # --- A. PANEL DE ALTA NUEVA (AÑADIR TRABAJADOR) ---
    with st.expander("➕ Subir Nuevo Examen Ocupacional (Alta de Trabajador)"):
        f_new = st.file_uploader("Subir PDF Mutual", type=['pdf'], key="new_worker")
        if f_new and st.button("🧠 Procesar con Valentin Shield"):
            with st.spinner("Analizando documento..."):
                lector = PyPDF2.PdfReader(f_new)
                texto = " ".join([p.extract_text() for p in lector.pages])
                res = analizar_pdf_mutual(texto)
                if res:
                    nueva_f = {
                        "RUT": res['rut'], "NOMBRE": res['nombre'], "CARGO": res['cargo'], 
                        "SUCURSAL": res.get('sucursal', 'MCT'), "TIPO_EXAMEN": "Ocupacional", 
                        "VENCIMIENTO": res['vigencia'], "ESTADO": res['condicion'], 
                        "URL_PDF": "N/A", "FECHA_SUBIDA": datetime.now().strftime("%Y-%m-%d")
                    }
                    if guardar_fila_nube(nueva_f, "examenes"):
                        st.success(f"✅ {res['nombre']} ingresado con éxito."); time.sleep(1); st.rerun()

    st.divider()

    # --- B. PANEL DE CATEGORÍAS Y RENOVACIÓN VALIDADA ---
    db = st.session_state.get('db_examenes', pd.DataFrame())
    if not db.empty:
        cats = sorted(db['Categoría'].dropna().unique())
        tabs = st.tabs([f"📋 {c}" for c in cats] + ["🌍 Ver Todo"])
        cols_v = ['RUT', 'Nombre', 'Cargo', 'Sucursal', 'Vigencia', 'Estado', 'Días por Vencer']

        for i, cat in enumerate(cats):
            with tabs[i]:
                df_cat = db[db['Categoría'] == cat].sort_values('Días por Vencer')
                st.dataframe(df_cat[cols_v].style.applymap(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)
                
                # --- ACTUALIZADOR CON VALIDACIÓN DE RUT ---
                with st.expander(f"📎 Renovar Vigencia / Actualizar PDF para {cat}"):
                    t_sel = st.selectbox("Trabajador en Nómina:", df_cat['Nombre'].tolist(), key=f"s_{i}")
                    f_renov = st.file_uploader("Subir Certificado de Mutual", type=['pdf'], key=f"f_{i}")
                    
                    if f_renov and st.button("💾 Validar y Sincronizar", key=f"b_{i}", type="primary"):
                        with st.spinner("Validando identidad..."):
                            lector = PyPDF2.PdfReader(f_renov)
                            texto_renov = " ".join([p.extract_text() for p in lector.pages])
                            datos_pdf = analizar_pdf_mutual(texto_renov)
                            
                            if datos_pdf:
                                rut_nomina = df_cat[df_cat['Nombre'] == t_sel]['RUT'].values[0]
                                
                                # VALIDACIÓN ESTRICTA DE IDENTIDAD
                                if limpiar_rut_estricto(datos_pdf['rut']) == limpiar_rut_estricto(rut_nomina):
                                    # 1. Guardado físico de respaldo
                                    if not os.path.exists("respaldos_mutual"): os.makedirs("respaldos_mutual")
                                    with open(f"respaldos_mutual/{limpiar_rut_estricto(rut_nomina)}.pdf", "wb") as f:
                                        f.write(f_renov.getbuffer())
                                    
                                    # 2. Actualización de datos
                                    df_master = st.session_state.db_examenes.copy()
                                    idx = df_master.index[df_master['RUT'] == rut_nomina].tolist()[0]
                                    df_master.at[idx, 'Vigencia'] = datos_pdf['vigencia']
                                    df_master.at[idx, 'Estado_Original'] = datos_pdf['condicion']
                                    
                                    # 3. ESCUDO DE COLUMNAS PARA SHEETS
                                    df_save = df_master.rename(columns={
                                        'Nombre':'NOMBRE', 'Cargo':'CARGO', 'Sucursal':'SUCURSAL', 
                                        'Categoría':'TIPO_EXAMEN', 'Vigencia':'VENCIMIENTO', 'Estado_Original':'ESTADO'
                                    })
                                    # Garantizamos las 9 columnas exactas
                                    cols_finales = ['RUT', 'NOMBRE', 'CARGO', 'SUCURSAL', 'TIPO_EXAMEN', 'VENCIMIENTO', 'ESTADO', 'URL_PDF', 'FECHA_SUBIDA']
                                    for c in cols_finales:
                                        if c not in df_save.columns: df_save[c] = "N/A"
                                    
                                    if actualizar_hoja_completa(df_save[cols_finales].fillna("N/A"), "examenes"):
                                        st.success(f"✅ ¡Vigencia de {t_sel} actualizada al {datos_pdf['vigencia']}!"); time.sleep(1.5); st.rerun()
                                else:
                                    st.error(f"❌ ERROR DE IDENTIDAD: El RUT del PDF ({datos_pdf['rut']}) no coincide con el seleccionado ({rut_nomina}).")
        
        # Pestaña "Ver Todo"
        with tabs[-1]:
            st.dataframe(db[cols_v].sort_values('Días por Vencer').style.applymap(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)
    else:
        st.info("La base de datos está vacía. Inicia agregando trabajadores con el botón superior.")
