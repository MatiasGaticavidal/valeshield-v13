import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import fitz  # PyMuPDF para manejar PDFs
import qrcode
from PIL import Image
import os

# ----------------------------------------------------
# 1. FUNCIÓN PRINCIPAL DEL MÓDULO (INTERFAZ VISUAL)
# ----------------------------------------------------
def mostrar_modulo_firmador(df_personal):
    st.markdown("## 🖋️ ShieldSign: Centro de Certificación Digital")
    st.markdown("Emisión y seguimiento de documentos con firma electrónica y sello QR.")
    
    # Pestañas de gestión
    tab_emitir, tab_seguimiento, tab_config = st.tabs(["📤 Emitir Documento", "📊 Seguimiento de Firmas", "⚙️ Mi Firma Digital"])
    
    with tab_emitir:
        st.markdown("### 1. Configurar Envío")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            archivo_subido = st.file_uploader("Sube el PDF base (ODI, Contrato, Charla)", type=['pdf'])
            
            # Selector de trabajador buscando en la base de personal
            if not df_personal.empty:
                opciones_trabajadores = df_personal['RUT'] + " - " + df_personal['NOMBRE']
                trabajador_sel = st.selectbox("Seleccionar Trabajador", ["Seleccione un trabajador..."] + opciones_trabajadores.tolist())
            else:
                st.warning("No hay base de personal cargada.")
                trabajador_sel = "Seleccione un trabajador..."

        with col2:
            fecha_limite = st.date_input("Fecha límite para firmar")
            tipo_doc = st.selectbox("Tipo de Documento", ["ODI / DAS", "Entrega de EPP", "Reglamento Interno", "Contrato / Anexo", "Otro"])
            
        if st.button("Generar Solicitud de Firma 🚀", type="primary", use_container_width=True):
            if archivo_subido and trabajador_sel != "Seleccione un trabajador...":
                # Generamos un ID único y corto
                token_unico = str(uuid.uuid4()).split('-')[0].upper()
                st.success(f"¡Solicitud creada! ID de Rastreo: **{token_unico}**")
                
                # LINK REAL DE VALESHIELD
                link_firma = f"https://valeshield-v13-vvhfbjz9nvddeysacj2pan.streamlit.app/?firmar={token_unico}"
                
                st.info(f"🔗 **Link para el trabajador:**\n{link_firma}")
                st.markdown("*Copia este link y envíalo por WhatsApp al trabajador.*")
            else:
                st.error("Debes subir un PDF y seleccionar un trabajador.")

    with tab_seguimiento:
        st.markdown("### Documentos en Proceso")
        st.info("Aquí se conectará la base de datos para ver quién falta por firmar y descargar los PDFs terminados.")

    with tab_config:
        st.markdown("### Configuración del Emisor")
        st.warning("Antes de emitir, debes registrar tu firma digital (Asesor) para que se estampe automáticamente junto a la del trabajador.")
        st.file_uploader("Sube una foto de tu firma (PNG sin fondo recomendado)", type=['png', 'jpg'])

# ----------------------------------------------------
# 2. MOTOR DE ESTAMPADO (LÓGICA MATEMÁTICA Y LEGAL)
# ----------------------------------------------------
def procesar_firma_y_sellar(canvas_image_data, token_firma):
    """Convierte el dibujo táctil, genera un QR y lo estampa en un PDF"""
    
    # 1. Convertir los datos táctiles de Streamlit en una imagen PNG real
    img = Image.fromarray(canvas_image_data.astype('uint8'), 'RGBA')
    ruta_firma = f"firma_{token_firma}.png"
    img.save(ruta_firma)
    
    # 2. Generar el Código QR de validación
    qr_data = f"https://valeshield-v13-vvhfbjz9nvddeysacj2pan.streamlit.app/?firmar={token_firma}"
    qr = qrcode.make(qr_data)
    ruta_qr = f"qr_{token_firma}.png"
    qr.save(ruta_qr)
    
    # 3. Crear el PDF (Por ahora, crearemos una hoja oficial en blanco para probar)
    ruta_salida = f"Documento_Firmado_{token_firma}.pdf"
    doc = fitz.open()
    pagina = doc.new_page()
    
    # Escribir el título y cuerpo del documento
    pagina.insert_text((50, 50), "DOCUMENTO LEGAL DE PREVENCION", fontsize=16, fontname="helv", color=(0.1, 0.2, 0.5))
    pagina.insert_text((50, 90), f"ID de Trazabilidad: {token_firma}", fontsize=10)
    pagina.insert_text((50, 130), "Yo, mediante la presente firma, confirmo la lectura y aprobacion", fontsize=11)
    pagina.insert_text((50, 150), "de los estandares de seguridad indicados por la empresa.", fontsize=11)
    
    # 4. Estampar la Firma (Coordenadas X, Y)
    rect_firma = fitz.Rect(50, 650, 250, 750)
    pagina.insert_image(rect_firma, filename=ruta_firma)
    pagina.insert_text((100, 760), "Firma del Trabajador", fontsize=10)
    
    # 5. Estampar el Código QR
    rect_qr = fitz.Rect(450, 650, 550, 750)
    pagina.insert_image(rect_qr, filename=ruta_qr)
    pagina.insert_text((440, 760), "Escanear para verificar validez", fontsize=8)
    
    # Guardar el PDF final
    doc.save(ruta_salida)
    doc.close()
    
    # 6. Limpiar las imágenes temporales por seguridad de datos
    os.remove(ruta_firma)
    os.remove(ruta_qr)
    
    return ruta_salida
