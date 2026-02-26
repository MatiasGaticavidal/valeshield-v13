import streamlit as st
import pandas as pd
import os
import re
import gspread
import json
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
CARPETA_DRIVE_FIRMAS = "1cW67aI9ZHEC8zs78p1L1E6WNhXzCAVfS" # Tu carpeta oficial

# Constantes de Archivos
ARCHIVO_USUARIOS = "usuarios_sistema.csv"
ARCHIVO_PERSONAL = "base_personal.csv"
ARCHIVO_ACCIDENTES = "registro_accidentes.csv"
ARCHIVO_PREVENTIVOS = "reportes_dpr.csv"
ARCHIVO_SOPORTE = "soporte_tecnico.csv"
ARCHIVO_CONFIG_MENSUAL = "config_mensual_stats.csv"

# Link oficial de tu nómina
URL_NOMINA = "https://docs.google.com/spreadsheets/d/1Chr-v7yWMqM3oX2XHY9f2mf816ftrqe8-HqxuMRsyz0/export?format=csv"

# ==========================================
# 🛠️ FUNCIONES DE APOYO
# ==========================================
def limpiar_rut(rut_input):
    if not rut_input or pd.isna(rut_input): return "S/R"
    r = str(rut_input).replace(".", "").replace(" ", "").replace("-", "").strip().upper()
    if len(r) >= 2: return r[:-1] + "-" + r[-1]
    return r

def calcular_hh_estimadas(n_trabajadores, mes=""):
    mes_limpio = str(mes).strip().lower()
    horas_semanales = 42 if mes_limpio == "abril" else 44
    return n_trabajadores * horas_semanales * 4

def es_clave_segura(clave):
    if len(clave) < 8: return False, "⚠️ Mínimo 8 caracteres."
    if not re.search(r"\d", clave): return False, "⚠️ Falta un número."
    if not re.search(r"[A-Za-z]", clave): return False, "⚠️ Falta una letra."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", clave): return False, "⚠️ Falta un símbolo."
    return True, "✅ Clave segura."

def guardar_foto(foto_subida):
    if foto_subida is not None:
        carpeta = "evidencias_seguras"
        if not os.path.exists(carpeta): os.makedirs(carpeta)
        ruta = os.path.join(carpeta, foto_subida.name)
        with open(ruta, "wb") as f: f.write(foto_subida.getbuffer())
        return ruta
    return "Sin foto"

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

import math

def guardar_fila_nube(nueva_fila_dict, nombre_pestana):
    try:
        doc = conectar_google_sheets()
        if doc:
            hoja = doc.worksheet(nombre_pestana)
            
            # TRADUCTOR UNIVERSAL: Convierte cualquier dato problemático (NaN, NaT, Fechas) a texto puro
            valores_limpios = []
            for valor in nueva_fila_dict.values():
                if pd.isna(valor):  # Atrapa NaT de fechas o NaN de pandas
                    valores_limpios.append("")
                elif isinstance(valor, float) and math.isnan(valor):
                    valores_limpios.append("")
                else:
                    valores_limpios.append(str(valor).strip())
            
            # value_input_option='USER_ENTERED' obliga a Sheets a leerlo como si lo teclearas tú misma
            hoja.append_row(valores_limpios, value_input_option='USER_ENTERED')
            return True
        return False
    except Exception as e:
        # Esto nos dirá el motivo técnico exacto si Google lo vuelve a rechazar
        st.error(f"🚨 Error crítico al guardar en nube ({nombre_pestana}): {str(e)}")
        return False

def actualizar_estado_firma(token, url_drive):
    """Busca el documento pendiente en Sheets y lo marca como firmado"""
    try:
        doc = conectar_google_sheets()
        if doc:
            hoja = doc.worksheet("certificados")
            registros = hoja.get_all_records()
            for i, row in enumerate(registros):
                if str(row.get("ID_Documento")) == str(token):
                    hoja.update_cell(i + 2, 5, "Firmado") 
                    hoja.update_cell(i + 2, 7, datetime.now().strftime("%Y-%m-%d %H:%M:%S")) 
                    hoja.update_cell(i + 2, 8, url_drive)
                    return True
    except Exception as e:
        pass
    return False

def subir_pdf_drive(ruta_local, nombre_destino):
    """Sube el PDF firmado a la carpeta blindada de ValeShield en Drive"""
    try:
        credenciales_texto = st.secrets["GOOGLE_CREDENTIALS"]
        credenciales_dict = json.loads(credenciales_texto)
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
        return None

# ==========================================
# 📊 CARGA DE DATOS MAESTROS Y PDF
# ==========================================
@st.cache_data(ttl=600)
def cargar_bases_maestras():
    # 1. CARGA DE PERSONAL (CORREGIDO: Lee directo desde la URL de nómina oficial)
    try:
        personal = pd.read_csv(URL_NOMINA)
    except Exception as e:
        # Respaldo en caso de que la URL falle
        personal = obtener_datos_nube("personal")

    if not personal.empty:
        # Estandarizamos las columnas para que coincidan con todo el sistema
        personal.columns = [c.strip().upper() for c in personal.columns]
        if 'RUT' in personal.columns:
            personal['RUT'] = personal['RUT'].apply(limpiar_rut)
            personal = personal.drop_duplicates(subset=['RUT'], keep='first')
            
        # Parche de seguridad por si la columna en el CSV se llama "NOMBRES" en vez de "NOMBRE"
        if 'NOMBRES' in personal.columns and 'NOMBRE' not in personal.columns:
            personal.rename(columns={'NOMBRES': 'NOMBRE'}, inplace=True)
    
    # 2. CARGA DE EXÁMENES
    examenes = obtener_datos_nube("examenes")
    if not examenes.empty:
        examenes.columns = [c.strip().upper() for c in examenes.columns]
        if 'RUT' in examenes.columns:
            examenes['RUT'] = examenes['RUT'].apply(limpiar_rut)
            examenes = examenes.drop_duplicates(subset=['RUT', 'TIPO_EXAMEN'], keep='first')
        
    return personal, examenes

def cargar_usuarios():
    if not os.path.exists(ARCHIVO_USUARIOS):
        df = pd.DataFrame([{"RUT": "ADMIN", "Nombre": "Administrador", "Clave": "Admin@1234", "Rol": "admin"}])
        df.to_csv(ARCHIVO_USUARIOS, index=False)
        return df
    return pd.read_csv(ARCHIVO_USUARIOS, dtype=str)

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'VALESHIELD - Reporte de Seguridad', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generar_pdf_accidentes(df_filtrado, mes_anio):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Reporte Mensual: {mes_anio}", ln=1, align='L')
    pdf.ln(5)
    pdf.set_fill_color(230, 230, 230)
    headers = ["Fecha", "Trabajador", "Sucursal", "Tipo", "Lugar"]
    widths = [25, 55, 45, 35, 30]
    for h, w in zip(headers, widths): pdf.cell(w, 10, h, 1, 0, 'C', 1)
    pdf.ln()
    pdf.set_font("Arial", size=8)
    for _, row in df_filtrado.iterrows():
        pdf.cell(25, 10, str(row.get('Fecha', '')), 1)
        pdf.cell(55, 10, str(row.get('Trabajador', ''))[:30], 1)
        pdf.cell(45, 10, str(row.get('Sucursal', ''))[:25], 1)
        pdf.cell(35, 10, str(row.get('Tipo', '')), 1)
        pdf.cell(30, 10, str(row.get('Lugar', ''))[:20], 1)
        pdf.ln()
    nombre = f"ValeShield_Reporte_{mes_anio.replace('/', '_')}.pdf"
    pdf.output(nombre)
    return nombre

df_personal, df_examenes = cargar_bases_maestras()

# ==========================================
# 🔄 FUNCIONES NUEVAS: CARGA MASIVA Y NÓMINA V15.2
# ==========================================
def actualizar_hoja_completa(df, nombre_pestana):
    """Sobrescribe toda una pestaña con un DataFrame nuevo (Ideal para nóminas masivas)"""
    try:
        doc = conectar_google_sheets()
        if doc:
            hoja = doc.worksheet(nombre_pestana)
            hoja.clear() # Limpiamos los datos antiguos de la pantalla
            # Convertimos el DataFrame a lista de listas para subirlo a la nube en 1 segundo
            datos_a_subir = [df.columns.values.tolist()] + df.fillna("").astype(str).values.tolist()
            hoja.update(values=datos_a_subir, range_name='A1')
            return True
        return False
    except Exception as e:
        st.error(f"Error al sincronizar nómina masiva en la nube: {e}")
        return False

def fusionar_nominas(df_existente, df_nueva):
    """Cruza la nómina antigua con el Excel nuevo. Actualiza existentes y agrega nuevos por RUT."""
    # Estandarizamos las columnas a mayúsculas
    df_nueva.columns = [str(c).strip().upper() for c in df_nueva.columns]
    
    # Aseguramos que el RUT sea la llave maestra y esté limpio
    df_nueva['RUT'] = df_nueva['RUT'].apply(limpiar_rut)
    df_nueva = df_nueva.drop_duplicates(subset=['RUT'], keep='last')
    
    if df_existente.empty:
        return df_nueva
        
    df_existente['RUT'] = df_existente['RUT'].apply(limpiar_rut)
    
    # Establecemos el RUT como índice para que Python sepa a quién actualizar
    df_existente.set_index('RUT', inplace=True)
    df_nueva.set_index('RUT', inplace=True)
    
    # Actualizamos los datos de los que ya existen (ej. si le cambiaste la sucursal en el Excel)
    df_existente.update(df_nueva) 
    
    # Encontramos los RUTs que son totalmente nuevos (contrataciones) y los agregamos
    ruts_nuevos = df_nueva.index.difference(df_existente.index)
    if not ruts_nuevos.empty:
        df_existente = pd.concat([df_existente, df_nueva.loc[ruts_nuevos]])
        
    # Devolvemos el formato a la normalidad
    df_existente.reset_index(inplace=True)
    return df_existente



