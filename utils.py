import streamlit as st
import pandas as pd
import os
import re
import gspread
from fpdf import FPDF
from google.oauth2.service_account import Credentials

# CONFIGURACIÓN NUBE
ARCHIVO_JSON = "valeshield-nube-6f1e07a93916.json" 
NOMBRE_SHEET = "Base_Datos_ValeShield"

def conectar_google_sheets():
    """Establece la conexión maestra con tu Google Drive"""
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(ARCHIVO_JSON, scopes=scope)
    client = gspread.authorize(creds)
    return client.open(NOMBRE_SHEET)

def obtener_datos_nube(nombre_pestana):
    """Lee datos desde Google Sheets y los devuelve como DataFrame"""
    try:
        doc = conectar_google_sheets()
        hoja = doc.worksheet(nombre_pestana)
        datos = hoja.get_all_records()
        return pd.DataFrame(datos)
    except Exception as e:
        st.error(f"Error al leer nube en {nombre_pestana}: {e}")
        return pd.DataFrame()

def guardar_fila_nube(nueva_fila_dict, nombre_pestana):
    """Guarda una nueva entrada al final de la hoja en la nube"""
    try:
        doc = conectar_google_sheets()
        hoja = doc.worksheet(nombre_pestana)
        # Convertimos el diccionario a una lista de valores
        valores = list(nueva_fila_dict.values())
        hoja.append_row(valores)
        return True
    except Exception as e:
        st.error(f"Error crítico al guardar en nube: {e}")
        return False

# --- CARGA DE DATOS OPTIMIZADA ---
@st.cache_data(ttl=600)  # Guarda los datos en memoria por 10 minutos
def cargar_bases_maestras():
    """Descarga personal y exámenes desde la nube solo cuando es necesario"""
    personal = obtener_datos_nube("personal")
    if not personal.empty:
        personal['RUT'] = personal['RUT'].apply(limpiar_rut)
    
    # También cargamos los exámenes que mencionaste
    examenes = obtener_datos_nube("examenes")
    if not examenes.empty:
        examenes['RUT'] = examenes['RUT'].apply(limpiar_rut)
        
    return personal, examenes

# Ejecutamos la carga (esto es lo que usarás en tus módulos)
df_personal, df_examenes = cargar_bases_maestras()

# --- CONSTANTES ---
ARCHIVO_USUARIOS = "usuarios_sistema.csv"
ARCHIVO_PERSONAL = "base_personal.csv"
ARCHIVO_ACCIDENTES = "registro_accidentes.csv"
ARCHIVO_PREVENTIVOS = "reportes_dpr.csv"
ARCHIVO_SOPORTE = "soporte_tecnico.csv"
ARCHIVO_CONFIG_MENSUAL = "config_mensual_stats.csv" # Nueva para estadísticas
URL_NOMINA = "https://docs.google.com/spreadsheets/d/1Chr-v7yWMqM3oX2XHY9f2mf816ftrqe8-HqxuMRsyz0/export?format=csv"

# --- FUNCIONES DE APOYO ---
def calcular_hh_estimadas(n_trabajadores, mes=""):
    """
    Calcula HH según la Ley 40 Horas (Chile).
    - Abril: 42 horas semanales.
    - Resto de los meses: 44 horas semanales.
    """
    # Limpiamos el texto del mes por si acaso
    mes_limpio = str(mes).strip().lower()
    
    if mes_limpio == "abril":
        horas_semanales = 42
    else:
        horas_semanales = 44
        
    # Fórmula: Trabajadores * Horas Semanales * 4 Semanas
    return n_trabajadores * horas_semanales * 4

def limpiar_rut(rut_input):
    if not rut_input: return ""
    r = str(rut_input).replace(".", "").replace(" ", "").strip().upper()
    if len(r) >= 8 and "-" not in r:
        r = r[:-1] + "-" + r[-1]
    return r

def es_clave_segura(clave):
    if len(clave) < 8: return False, "⚠️ Mínimo 8 caracteres."
    if not re.search(r"\d", clave): return False, "⚠️ Falta un número."
    if not re.search(r"[A-Za-z]", clave): return False, "⚠️ Falta una letra."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", clave): return False, "⚠️ Falta un símbolo."
    return True, "✅ Clave segura."

def cargar_usuarios():
    if not os.path.exists(ARCHIVO_USUARIOS):
        df = pd.DataFrame([{"RUT": "ADMIN", "Nombre": "Administrador", "Clave": "Admin@1234", "Rol": "admin"}])
        df.to_csv(ARCHIVO_USUARIOS, index=False)
        return df
    return pd.read_csv(ARCHIVO_USUARIOS, dtype=str)

def guardar_foto(foto_subida):
    if foto_subida is not None:
        carpeta = "evidencias_seguras"
        if not os.path.exists(carpeta): os.makedirs(carpeta)
        ruta = os.path.join(carpeta, foto_subida.name)
        with open(ruta, "wb") as f: f.write(foto_subida.getbuffer())
        return ruta
    return "Sin foto"

# --- CLASE PDF ---
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
    for h, w in zip(headers, widths):
        pdf.cell(w, 10, h, 1, 0, 'C', 1)
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

