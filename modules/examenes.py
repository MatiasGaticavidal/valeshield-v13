import streamlit as st
import pandas as pd
import os
import re
import gspread
import json
import math
from fpdf import FPDF
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from datetime import datetime

# ==========================================
# 🛡️ CONFIGURACIÓN NUBE Y CONSTANTES
# ==========================================
ARCHIVO_JSON = "valeshield-nube-6f1e07a93916.json"
NOMBRE_SHEET = "Base_Datos_ValeShield"
CARPETA_DRIVE_FIRMAS = "1cW67aI9ZHEC8zs78p1L1E6WNhXzCAVfS" 

ARCHIVO_USUARIOS = "usuarios_sistema.csv"
ARCHIVO_PERSONAL = "base_personal.csv"
ARCHIVO_SOPORTE = "soporte_tecnico.csv"
URL_NOMINA = "https://docs.google.com/spreadsheets/d/1Chr-v7yWMqM3oX2XHY9f2mf816ftrqe8-HqxuMRsyz0/export?format=csv"

# ==========================================
# 🛠️ FUNCIONES DE APOYO
# ==========================================
def limpiar_rut(rut_input):
    if not rut_input or pd.isna(rut_input): return "S/R"
    r = str(rut_input).replace(".", "").replace(" ", "").replace("-", "").strip().upper()
    if len(r) >= 2: return r[:-1] + "-" + r[-1]
    return r

# ==========================================
# ☁️ CONEXIÓN Y GESTIÓN DE NUBE (SHEETS Y DRIVE)
# ==========================================
def conectar_google_sheets():
    try:
        credenciales_texto = st.secrets["GOOGLE_CREDENTIALS"]
        credenciales_dict = json.loads(credenciales_texto)
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(credenciales_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client.open(NOMBRE_SHEET)
    except Exception as e:
        st.error(f"Error de conexión a la nube: {e}")
        return None

def obtener_datos_nube(nombre_pestana):
    try:
        doc = conectar_google_sheets()
        if doc:
            hoja = doc.worksheet(nombre_pestana)
            datos = hoja.get_all_records()
            return pd.DataFrame(datos)
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def guardar_fila_nube(nueva_fila_dict, nombre_pestana):
    try:
        doc = conectar_google_sheets()
        if doc:
            hoja = doc.worksheet(nombre_pestana)
            valores_limpios = []
            for valor in nueva_fila_dict.values():
                if pd.isna(valor) or (isinstance(valor, float) and math.isnan(valor)):
                    valores_limpios.append("")
                else:
                    valores_limpios.append(str(valor).strip())
            hoja.append_row(valores_limpios, value_input_option='USER_ENTERED')
            return True
        return False
    except Exception as e:
        st.error(f"Error al guardar en nube ({nombre_pestana}): {str(e)}")
        return False

def actualizar_hoja_completa(df, nombre_pestana):
    """Sobrescribe toda la pestaña garantizando las columnas exactas"""
    try:
        doc = conectar_google_sheets()
        if doc:
            hoja = doc.worksheet(nombre_pestana)
            hoja.clear() 
            datos_a_subir = [df.columns.values.tolist()] + df.fillna("").astype(str).values.tolist()
            hoja.update(values=datos_a_subir, range_name='A1')
            return True
        return False
    except Exception as e:
        st.error(f"Error al sincronizar datos masivos: {e}")
        return False

def subir_pdf_drive(ruta_local, nombre_destino):
    """Sube el PDF a Drive y devuelve el link público"""
    try:
        credenciales_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        scope = ["https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(credenciales_dict, scopes=scope)
        servicio = build('drive', 'v3', credentials=creds)

        file_metadata = {'name': nombre_destino, 'parents': [CARPETA_DRIVE_FIRMAS]}
        media = MediaFileUpload(ruta_local, mimetype='application/pdf')
        file = servicio.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        
        try:
            servicio.permissions().create(fileId=file.get('id'), body={'type': 'anyone', 'role': 'reader'}).execute()
        except: pass
        
        return file.get('webViewLink')
    except Exception as e:
        st.error(f"Error al subir a Drive: {e}")
        return None

# Carga inicial para app.py
@st.cache_data(ttl=600)
def cargar_bases_maestras():
    try:
        personal = pd.read_csv(URL_NOMINA)
    except:
        personal = obtener_datos_nube("personal")
    if not personal.empty:
        personal.columns = [c.strip().upper() for c in personal.columns]
        if 'RUT' in personal.columns:
            personal['RUT'] = personal['RUT'].apply(limpiar_rut)
            personal = personal.drop_duplicates(subset=['RUT'], keep='first')
            
    examenes = obtener_datos_nube("examenes")
    if not examenes.empty:
        examenes.columns = [c.strip().upper() for c in examenes.columns]
        if 'RUT' in examenes.columns:
            examenes['RUT'] = examenes['RUT'].apply(limpiar_rut)
            
    return personal, examenes

df_personal, df_examenes = cargar_bases_maestras()
