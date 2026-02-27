import streamlit as st
import pandas as pd
from datetime import datetime
import PyPDF2
import json
import re
import os
import time
import google.generativeai as genai

# Importamos herramientas desde tu utils.py intacto
from utils import obtener_datos_nube, guardar_fila_nube, actualizar_hoja_completa, subir_pdf_drive

# --- 1. MOTORES DE EXTRACCIÓN Y VALIDACIÓN ---

def limpiar_rut_estricto(rut_str):
    if not rut_str or pd.isna(rut_str): return ""
    return re.sub(r'[^0-9Kk]', '', str(rut_str)).upper()

def extraer_por_patrones(texto):
    """Cazador de Emergencia (Regex)"""
    rut_match = re.search(r"([\d]{7,8}[\-]?[\dKk])", texto)
    vig_match = re.search(r"Vigencia Hasta.*?([\d]{2}[\.\-/][\d]{2}[\.\-/][\d]{4})", texto)
    nombre_match = re.search(r"Trabajador\(a\)\s*:\s*([A-ZÁÉÍÓÚÑ\s]+)(?:Edad|ID|RUT)", texto)
    
    res = {
        "nombre": nombre_match.group(1).strip() if nombre_match else "Nombre no detectado",
        "cargo": "Por definir",
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
    """Cerebro IA mejorado para extraer Nombres, Cargos y RUTs"""
    if "GOOGLE_API_KEY" not in st.secrets:
        return extraer_por_patrones(texto_pdf)
        
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        modelo = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Eres experto en Prevención de Riesgos. Extrae estos datos del certificado médico en JSON puro:
        - "nombre": Nombre completo del trabajador evaluado.
        - "cargo": El cargo o puesto de trabajo que indica el documento.
        - "rut": El RUT del TRABAJADOR evaluado. Búscalo en todo el texto, ignora el RUT de la empresa empleadora.
        - "vigencia": Fecha tras 'Vigencia Hasta' en formato YYYY-MM-DD.
        - "condicion": 'APTO' o 'NO APTO'.
        TEXTO: {texto_pdf[:4500]}
        """
        respuesta = modelo.generate_content(prompt)
        res_text = respuesta.text.strip()
        
        if "{" in res_text:
            res_text = res_text[res_text.find("{"):res_text.rfind("}")+1]
        datos = json.loads(res_text)
        
        # PLAN B PARA EL RUT
        if not datos.get('rut') or datos.get('rut') == "N/A" or datos.get('rut').strip() == "":
            cazador = re.search(r"([\d]{7,8}[\-]?[\dKk])", texto_pdf)
            if cazador:
                ruts_encontrados = re.findall(r"([\d]{7,8}[\-]?[\dKk])", texto_pdf)
                for r in ruts_encontrados:
                    if not r.startswith("7"):
                        datos['rut'] = r
                        break

        # Limpieza de fecha rebelde
        if datos.get('vigencia'):
            f_cl = re.sub(r'[^0-9\-\./]', '', str(datos['vigencia'])).replace('.', '-')
            for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
                try:
                    datos['vigencia'] = datetime.strptime(f_cl, fmt).strftime("%Y-%m-%d")
                    break
                except: continue
                
        # Aseguramos que existan las llaves de nombre y cargo
        if 'nombre' not in datos: datos['nombre'] = "Nombre no detectado"
        if 'cargo' not in datos: datos['cargo'] = "Por definir"
        
        return datos
    except Exception:
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
    
    # --- CARGA DE DATOS ---
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
        st.session_state.db_examenes = pd.DataFrame(columns=['RUT', 'Nombre', 'Cargo', 'Sucursal', 'Categoría', 'Vigencia', 'Estado_Original', 'URL_PDF', 'FECHA_SUBIDA'])

    # --- PANEL NUEVO: ALTA DE TRABAJADOR ---
    with st.expander("➕ Ingresar Nuevo Examen (Trabajador no registrado)", expanded=False):
        st.info("Sube el PDF de la Mutual. La Inteligencia Artificial extraerá el RUT, Nombre y Vigencia automáticamente.")
        
        col_s, col_t = st.columns(2)
        with col_s:
            sucursal_nueva = st.selectbox("Asignar a Sucursal:", ["Electrocom", "MCT", "Placa Centro"])
        with col_t:
            # LÓGICA DE LISTA DESPLEGABLE INTELIGENTE
            categorias_actuales = []
            if not st.session_state.db_examenes.empty and 'Categoría' in st.session_state.db_examenes.columns:
                categorias_actuales = sorted(st.session_state.db_examenes['Categoría'].dropna().unique().tolist())
            
            opciones_examen = categorias_actuales + ["➕ Crear nuevo tipo..."]
            seleccion_examen = st.selectbox("Tipo de Examen:", opciones_examen)
            
            if seleccion_examen == "➕ Crear nuevo tipo...":
                tipo_examen_nuevo = st.text_input("Escribe el nuevo tipo de examen:")
            else:
                tipo_examen_nuevo = seleccion_examen
            
        f_nuevo = st.file_uploader("Subir PDF de Mutual", type=['pdf'], key="new_pdf_worker")
        
        if f_nuevo and st.button("🚀 Extraer Datos y Agregar a la Nómina", type="primary"):
            if not tipo_examen_nuevo:
                st.warning("⚠️ Debes seleccionar o escribir el Tipo de Examen antes de procesar.")
            else:
                with st.spinner("Valentin Shield está leyendo el nuevo certificado..."):
                    lector = PyPDF2.PdfReader(f_nuevo)
                    texto_nuevo = " ".join([p.extract_text() for p in lector.pages if p.extract_text()])
                    
                    if len(texto_nuevo) < 50:
                        st.error("❌ EL PDF ESTÁ EN BLANCO O ES UNA IMAGEN ESCANEADA.")
                    else:
                        datos_extraidos = analizar_pdf_mutual(texto_nuevo)
                        
                        if datos_extraidos and datos_extraidos.get('rut') != "N/A":
                            rut_limpio_nuevo = limpiar_rut_estricto(datos_extraidos['rut'])
                            
                            db_actual = st.session_state.db_examenes
                            duplicado = db_actual[(db_actual['RUT'].apply(limpiar_rut_estricto) == rut_limpio_nuevo) & (db_actual['Categoría'].str.lower() == tipo_examen_nuevo.strip().lower())]
                            
                            if not duplicado.empty:
                                st.error(f"⚠️ El trabajador con RUT {datos_extraidos['rut']} ya tiene un examen de '{tipo_examen_nuevo}' registrado. Usa el panel de abajo para renovarlo.")
                            else:
                                ruta_temp_new = f"temp_new_{rut_limpio_nuevo}.pdf"
                                with open(ruta_temp_new, "wb") as f:
                                    f.write(f_nuevo.getbuffer())
                                    
                                nombre_drive_new = f"Examen_{rut_limpio_nuevo}_{datetime.now().strftime('%Y%m%d')}.pdf"
                                link_drive_new = subir_pdf_drive(ruta_temp_new, nombre_drive_new)
                                if os.path.exists(ruta_temp_new): os.remove(ruta_temp_new)

                                nueva_fila = {
                                    'RUT': datos_extraidos['rut'],
                                    'NOMBRE': datos_extraidos['nombre'].upper(),
                                    'CARGO': datos_extraidos['cargo'].upper(),
                                    'SUCURSAL': sucursal_nueva,
                                    'TIPO_EXAMEN': tipo_examen_nuevo.title(),
                                    'VENCIMIENTO': datos_extraidos['vigencia'],
                                    'ESTADO': datos_extraidos['condicion'],
                                    'URL_PDF': link_drive_new if link_drive_new else "Error Drive",
                                    'FECHA_SUBIDA': datetime.now().strftime("%Y-%m-%d")
                                }
                                
                                df_nueva_fila = pd.DataFrame([nueva_fila])
                                df_master = st.session_state.db_examenes.copy()
                                df_master = df_master.rename(columns={
                                    'Nombre':'NOMBRE', 'Cargo':'CARGO', 'Sucursal':'SUCURSAL', 
                                    'Categoría':'TIPO_EXAMEN', 'Vigencia':'VENCIMIENTO', 'Estado_Original':'ESTADO'
                                })
                                
                                cols_finales = ['RUT', 'NOMBRE', 'CARGO', 'SUCURSAL', 'TIPO_EXAMEN', 'VENCIMIENTO', 'ESTADO', 'URL_PDF', 'FECHA_SUBIDA']
                                df_master = df_master[cols_finales] if not df_master.empty else pd.DataFrame(columns=cols_finales)
                                
                                df_final = pd.concat([df_master, df_nueva_fila], ignore_index=True)
                                
                                if actualizar_hoja_completa(df_final.fillna("N/A"), "examenes"):
                                    st.success(f"✅ ¡{datos_extraidos['nombre']} ha sido agregado exitosamente a la nómina!")
                                    st.balloons()
                                    st.cache_data.clear()
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error("❌ Google Sheets rechazó el guardado.")
                        else:
                            st.error("❌ La IA no pudo detectar el RUT en este documento nuevo.")

    st.divider()

    # --- TABLAS Y RENOVACIÓN ---
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
                            
                            lector = PyPDF2.PdfReader(f_ren)
                            texto_ren = " ".join([p.extract_text() for p in lector.pages if p.extract_text()])
                            
                            if len(texto_ren) < 50:
                                st.error("❌ EL PDF ESTÁ EN BLANCO O ES UNA IMAGEN ESCANEADA.")
                            else:
                                datos_pdf = analizar_pdf_mutual(texto_ren)
                                
                                if datos_pdf:
                                    rut_nomina = df_cat[df_cat['Nombre'] == t_sel]['RUT'].values[0]
                                    rut_pdf_limpio = limpiar_rut_estricto(datos_pdf.get('rut', ''))
                                    rut_nom_limpio = limpiar_rut_estricto(rut_nomina)
                                    
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
                                        st.error("❌ ERROR DE IDENTIDAD: Los RUTs no coinciden o no se encontró en el PDF.")
                                else:
                                    st.error("❌ ERROR DE IA: No se pudieron extraer datos lógicos del texto.")
    else:
        st.info("No hay datos cargados.")
