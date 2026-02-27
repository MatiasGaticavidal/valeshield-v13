import streamlit as st
import pandas as pd
from datetime import datetime
import PyPDF2
import json
import re
import os
import time
import google.generativeai as genai

# Importamos herramientas clave desde tu utils.py
from utils import obtener_datos_nube, guardar_fila_nube, actualizar_hoja_completa, subir_pdf_drive

# --- 1. MOTORES DE EXTRACCIÓN Y VALIDACIÓN ---

def limpiar_rut_estricto(rut_str):
    if not rut_str or pd.isna(rut_str): return ""
    return re.sub(r'[^0-9Kk]', '', str(rut_str)).upper()

def extraer_por_patrones(texto):
    """Escáner de Emergencia por si falla la IA"""
    rut_match = re.search(r"RU-([\d\.\-Kk]+)", texto)
    vig_match = re.search(r"Vigencia Hasta.*?([\d]{2}[\.\-/][\d]{2}[\.\-/][\d]{4})", texto)
    res = {
        "rut": rut_match.group(1).strip() if rut_match else "N/A",
        "vigencia": "N/A",
        "condicion": "APTO" if "no evidencia alteraciones" in texto.lower() else "PENDIENTE",
    }
    if vig_match:
        f_raw = vig_match.group(1).replace('.', '-')
        try:
            res["vigencia"] = datetime.strptime(f_raw, "%d-%m-%Y").strftime("%Y-%m-%d")
        except: pass
    return res

def analizar_pdf_mutual(texto_pdf):
    """Cerebro IA con respaldo garantizado"""
    # Si no hay llave, saltamos directo al escáner de emergencia
    if "GOOGLE_API_KEY" not in st.secrets:
        return extraer_por_patrones(texto_pdf)
        
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        modelo = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Eres experto en Prevención de Riesgos. Extrae estos datos en JSON puro:
        "rut" (tras RU-), "vigencia" (tras Vigencia Hasta en YYYY-MM-DD), "condicion" (APTO/NO APTO).
        TEXTO: {texto_pdf[:4000]}
        """
        respuesta = modelo.generate_content(prompt)
        res_text = respuesta.text.strip()
        if "{" in res_text:
            res_text = res_text[res_text.find("{"):res_text.rfind("}")+1]
        datos = json.loads(res_text)
        
        if datos.get('vigencia'):
            f_cl = re.sub(r'[^0-9\-\./]', '', str(datos['vigencia'])).replace('.', '-')
            for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
                try:
                    datos['vigencia'] = datetime.strptime(f_cl, fmt).strftime("%Y-%m-%d")
                    break
                except: continue
        return datos
    except Exception:
        # Si la IA falla por cualquier error de conexión, usamos el escáner manual
        return extraer_por_patrones(texto_pdf)

# --- 2. SEMÁFORO VISUAL ---

def calcular_estado(fecha_val, condicion):
    if str(condicion).upper() in ["NO APTO", "PENDIENTE", "RECHAZADO"]:
        return "⚫ RECHAZADO", 0
    try:
        f_str = str(fecha_val).strip()
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y'):
            try:
                vigencia = datetime.strptime(f_str, fmt).date()
                break
            except: continue
        dias = (vigencia - datetime.now().date()).days
        if dias < 0: return "🔴 VENCIDO", dias
        return ("🟠 POR VENCER" if dias <= 30 else "🟢 VIGENTE"), dias
    except:
        return "⚠️ ERROR FECHA", 0

def aplicar_colores(val):
    estilos = {'VIGENTE': '#d4edda', 'POR VENCER': '#fff3cd', 'VENCIDO': '#f8d7da', 'RECHAZADO': '#e2e3e5'}
    for k, color in estilos.items():
        if k in str(val): return f'background-color: {color}; color: black;'
    return ''

# --- 3. MÓDULO PRINCIPAL ---

def mostrar_modulo_examenes():
    st.header("🩺 Control de Exámenes Ocupacionales")
    
    df_nube = obtener_datos_nube("examenes")
    if not df_nube.empty:
        df = df_nube.copy()
        df.columns = [c.upper().strip() for c in df.columns]
        rename_map = {'NOMBRE':'Nombre', 'CARGO':'Cargo', 'SUCURSAL':'Sucursal', 'TIPO_EXAMEN':'Categoría', 'VENCIMIENTO':'Vigencia', 'ESTADO':'Estado_Original'}
        df = df.rename(columns=rename_map)
        df['Días por Vencer'] = df.apply(lambda r: calcular_estado(r.get('Vigencia',''), r.get('Estado_Original','APTO'))[1], axis=1)
        df['Estado'] = df.apply(lambda r: calcular_estado(r.get('Vigencia',''), r.get('Estado_Original','APTO'))[0], axis=1)
        st.session_state.db_examenes = df
    else:
        st.session_state.db_examenes = pd.DataFrame()

    st.divider()

    db = st.session_state.get('db_examenes', pd.DataFrame())
    if not db.empty:
        cats = sorted(db['Categoría'].dropna().unique())
        tabs = st.tabs([f"📋 {c}" for c in cats] + ["🌍 Ver Todo"])
        cols_v = ['RUT', 'Nombre', 'Cargo', 'Sucursal', 'Vigencia', 'Estado', 'Días por Vencer']

        for i, cat in enumerate(cats):
            with tabs[i]:
                df_cat = db[db['Categoría'] == cat].sort_values('Días por Vencer')
                st.dataframe(df_cat[cols_v].style.applymap(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)
                
                with st.expander(f"📎 Renovar Vigencia / Adjuntar Respaldo para {cat}"):
                    t_sel = st.selectbox("Seleccionar Trabajador:", df_cat['Nombre'].tolist(), key=f"s_{i}")
                    f_ren = st.file_uploader("Subir Certificado Renovado (PDF)", type=['pdf'], key=f"f_{i}")
                    
                    if f_ren and st.button("💾 Validar Identidad y Actualizar", key=f"b_{i}", type="primary"):
                        with st.spinner("Analizando documento..."):
                            
                            # 1. INTENTAMOS LEER EL TEXTO DEL PDF
                            lector = PyPDF2.PdfReader(f_ren)
                            # Usamos un filtro para ignorar páginas vacías/imágenes
                            texto_ren = " ".join([p.extract_text() for p in lector.pages if p.extract_text()])
                            
                            # 🔍 RAYOS X FASE 1: Verificamos si es una imagen
                            st.info(f"🔍 **RAYOS X:** El sistema logró leer **{len(texto_ren)}** caracteres del PDF.")
                            
                            if len(texto_ren) < 50:
                                st.error("❌ EL PDF ESTÁ EN BLANCO O ES UNA IMAGEN ESCANEADA. El sistema no puede extraer texto de fotos. Por favor sube el PDF digital original.")
                            else:
                                datos_pdf = analizar_pdf_mutual(texto_ren)
                                
                                if datos_pdf:
                                    rut_nomina = df_cat[df_cat['Nombre'] == t_sel]['RUT'].values[0]
                                    rut_pdf_limpio = limpiar_rut_estricto(datos_pdf.get('rut', ''))
                                    rut_nom_limpio = limpiar_rut_estricto(rut_nomina)
                                    
                                    # 🔍 RAYOS X FASE 2: Identidad
                                    st.write(f"RUT Base de Datos: `{rut_nom_limpio}` | RUT en PDF: `{rut_pdf_limpio}` | Fecha: `{datos_pdf.get('vigencia')}`")
                                    
                                    if rut_pdf_limpio == rut_nom_limpio and rut_pdf_limpio != "":
                                        
                                        ruta_temp = f"temp_{rut_nom_limpio}.pdf"
                                        with open(ruta_temp, "wb") as f:
                                            f.write(f_ren.getbuffer())
                                            
                                        nombre_drive = f"Examen_{rut_nom_limpio}_{datetime.now().strftime('%Y%m%d')}.pdf"
                                        link_drive = subir_pdf_drive(ruta_temp, nombre_drive)
                                        if os.path.exists(ruta_temp): os.remove(ruta_temp)
                                        
                                        df_master = st.session_state.db_examenes.copy()
                                        idx = df_master.index[df_master['RUT'] == rut_nomina].tolist()[0]
                                        df_master.at[idx, 'Vigencia'] = datos_pdf['vigencia']
                                        df_master.at[idx, 'Estado_Original'] = datos_pdf['condicion']
                                        df_master.at[idx, 'URL_PDF'] = link_drive if link_drive else "Error Drive"
                                        df_master.at[idx, 'FECHA_SUBIDA'] = datetime.now().strftime("%Y-%m-%d")
                                        
                                        df_save = df_master.rename(columns={
                                            'Nombre':'NOMBRE', 'Cargo':'CARGO', 'Sucursal':'SUCURSAL', 
                                            'Categoría':'TIPO_EXAMEN', 'Vigencia':'VENCIMIENTO', 'Estado_Original':'ESTADO'
                                        })
                                        
                                        cols_finales = ['RUT', 'NOMBRE', 'CARGO', 'SUCURSAL', 'TIPO_EXAMEN', 'VENCIMIENTO', 'ESTADO', 'URL_PDF', 'FECHA_SUBIDA']
                                        for c in cols_finales:
                                            if c not in df_save.columns: df_save[c] = "N/A"
                                        
                                        if actualizar_hoja_completa(df_save[cols_finales].fillna("N/A"), "examenes"):
                                            st.success(f"✅ ¡Guardado Exitoso en Google Sheets!")
                                            st.cache_data.clear()
                                            time.sleep(2)
                                            st.rerun()
                                        else:
                                            st.error("❌ Google Sheets rechazó el guardado.")
                                    else:
                                        st.error("❌ ERROR DE IDENTIDAD: Los RUTs no coinciden.")
                                else:
                                    st.error("❌ ERROR DE IA: No se pudieron extraer datos lógicos del texto.")
    else:
        st.info("No hay datos cargados.")
