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

# --- 1. MOTORES DE EXTRACCIÓN (IA + RESPALDO DE SEGURIDAD) ---

def limpiar_rut_estricto(rut_str):
    """Normaliza el RUT para comparaciones de identidad infalibles"""
    if not rut_str or pd.isna(rut_str): return ""
    return re.sub(r'[^0-9Kk]', '', str(rut_str)).upper()

def extraer_por_patrones(texto):
    """Escáner de respaldo si la IA falla (Regex)"""
    rut_match = re.search(r"RU-([\d\.\-Kk]+)", texto)
    vig_match = re.search(r"Vigencia Hasta.*?([\d]{2}[\.\-/][\d]{2}[\.\-/][\d]{4})", texto)
    nombre_match = re.search(r"Trabajador\(a\)\s*:\s*([A-ZÁÉÍÓÚÑ\s]+)(?:Edad|ID)", texto)
    
    res = {
        "rut": rut_match.group(1).strip() if rut_match else "N/A",
        "nombre": nombre_match.group(1).strip() if nombre_match else "N/A",
        "vigencia": "N/A",
        "condicion": "APTO" if "no evidencia alteraciones" in texto.lower() else "PENDIENTE",
        "cargo": "Extracción por Patrón",
        "sucursal": "MCT" if "MCT" in texto.upper() else "PLC" if "PLC" in texto.upper() else "ECOM"
    }
    
    if vig_match:
        f_raw = vig_match.group(1).replace('.', '-')
        try:
            res["vigencia"] = datetime.strptime(f_raw, "%d-%m-%Y").strftime("%Y-%m-%d")
        except: pass
    return res

def analizar_pdf_mutual(texto_pdf):
    """Intenta procesar con IA, si falla usa el Escáner de Respaldo"""
    try:
        # Configuración de API
        if "GOOGLE_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
            modelo = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            Eres un experto en Prevención de Riesgos. Extrae estos datos en JSON puro:
            "nombre", "rut" (tras RU-), "sucursal" (ECOM/MCT/PLC), "cargo", 
            "vigencia" (tras Vigencia Hasta en YYYY-MM-DD), "condicion" (APTO/NO APTO).
            TEXTO: {texto_pdf[:4000]}
            """
            
            respuesta = modelo.generate_content(prompt)
            res_text = respuesta.text.strip()
            if "{" in res_text:
                res_text = res_text[res_text.find("{"):res_text.rfind("}")+1]
            datos = json.loads(res_text)
            
            # Limpieza de fecha rebelde (ej: 2027:)
            if datos.get('vigencia'):
                f_cl = re.sub(r'[^0-9\-\./]', '', str(datos['vigencia'])).replace('.', '-')
                for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
                    try:
                        datos['vigencia'] = datetime.strptime(f_cl, fmt).strftime("%Y-%m-%d")
                        break
                    except: continue
            return datos
    except Exception:
        # SI LA IA FALLA, EL SISTEMA USA EL ESCÁNER DE RESPALDO
        return extraer_por_patrones(texto_pdf)
    return None

# --- 2. SEMÁFORO Y LÓGICA VISUAL ---

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
    
    # Sincronización de Datos
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

    # A. PANEL DE ALTA NUEVA (Añadir Trabajador)
    with st.expander("➕ Subir Nuevo Examen Ocupacional (Alta de Trabajador)"):
        f_new = st.file_uploader("Subir PDF de Mutual", type=['pdf'], key="new_w")
        if f_new and st.button("🧠 Procesar Nuevo Registro"):
            lector = PyPDF2.PdfReader(f_new)
            texto = " ".join([p.extract_text() for p in lector.pages])
            res = analizar_pdf_mutual(texto)
            if res:
                nueva_f = {"RUT": res['rut'], "NOMBRE": res['nombre'], "CARGO": res['cargo'], "SUCURSAL": res.get('sucursal','MCT'), "TIPO_EXAMEN": "Ocupacional", "VENCIMIENTO": res['vigencia'], "ESTADO": res['condicion'], "URL_PDF": "N/A", "FECHA_SUBIDA": datetime.now().strftime("%Y-%m-%d")}
                if guardar_fila_nube(nueva_f, "examenes"):
                    st.success(f"✅ {res['nombre']} registrado."); time.sleep(1); st.rerun()

    st.divider()

    # B. TABLAS Y ACTUALIZACIÓN CON VALIDACIÓN DE RUT
    db = st.session_state.get('db_examenes', pd.DataFrame())
    if not db.empty:
        cats = sorted(db['Categoría'].dropna().unique())
        tabs = st.tabs([f"📋 {c}" for c in cats] + ["🌍 Ver Todo"])
        cols_v = ['RUT', 'Nombre', 'Cargo', 'Sucursal', 'Vigencia', 'Estado', 'Días por Vencer']

        for i, cat in enumerate(cats):
            with tabs[i]:
                df_cat = db[db['Categoría'] == cat].sort_values('Días por Vencer')
                st.dataframe(df_cat[cols_v].style.applymap(aplicar_colores, subset=['Estado']), use_container_width=True, hide_index=True)
                
                # --- MOTOR DE RENOVACIÓN CON VALIDACIÓN DE IDENTIDAD ---
                with st.expander(f"📎 Renovar Vigencia / Adjuntar Respaldo para {cat}"):
                    t_sel = st.selectbox("Seleccionar Trabajador:", df_cat['Nombre'].tolist(), key=f"s_{i}")
                    f_ren = st.file_uploader("Subir Certificado Renovado", type=['pdf'], key=f"f_{i}")
                    
                    if f_ren and st.button("💾 Validar Identidad y Actualizar", key=f"b_{i}", type="primary"):
                        with st.spinner("Validando RUT en documento..."):
                            lector = PyPDF2.PdfReader(f_ren)
                            texto_ren = " ".join([p.extract_text() for p in lector.pages])
                            datos_pdf = analizar_pdf_mutual(texto_ren)
                            
                            if datos_pdf:
                                rut_nomina = df_cat[df_cat['Nombre'] == t_sel]['RUT'].values[0]
                                
                                # COMPARACIÓN ESTRICTA DE RUT
                                if limpiar_rut_estricto(datos_pdf['rut']) == limpiar_rut_estricto(rut_nomina):
                                    # Guardar respaldo físico
                                    if not os.path.exists("respaldos_mutual"): os.makedirs("respaldos_mutual")
                                    with open(f"respaldos_mutual/{limpiar_rut_estricto(rut_nomina)}.pdf", "wb") as f:
                                        f.write(f_ren.getbuffer())
                                    
                                    # Actualizar base de datos
                                    df_master = st.session_state.db_examenes.copy()
                                    idx = df_master.index[df_master['RUT'] == rut_nomina].tolist()[0]
                                    df_master.at[idx, 'Vigencia'] = datos_pdf['vigencia']
                                    df_master.at[idx, 'Estado_Original'] = datos_pdf['condicion']
                                    
                                    # Escudo Anti-Borrado de Columnas
                                    df_save = df_master.rename(columns={'Nombre':'NOMBRE', 'Cargo':'CARGO', 'Sucursal':'SUCURSAL', 'Categoría':'TIPO_EXAMEN', 'Vigencia':'VENCIMIENTO', 'Estado_Original':'ESTADO'})
                                    cols_finales = ['RUT', 'NOMBRE', 'CARGO', 'SUCURSAL', 'TIPO_EXAMEN', 'VENCIMIENTO', 'ESTADO', 'URL_PDF', 'FECHA_SUBIDA']
                                    for c in cols_finales:
                                        if c not in df_save.columns: df_save[c] = "N/A"
                                    
                                    if actualizar_hoja_completa(df_save[cols_finales].fillna("N/A"), "examenes"):
                                        st.success(f"✅ ¡Identidad Confirmada! Vigencia de {t_sel} actualizada."); time.sleep(1.5); st.rerun()
                                else:
                                    st.error(f"❌ ERROR DE IDENTIDAD: El RUT del PDF ({datos_pdf['rut']}) no coincide con el seleccionado ({rut_nomina}).")
    else:
        st.info("Inicia agregando trabajadores con el botón superior.")
