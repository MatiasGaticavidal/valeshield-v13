import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import fitz  
import qrcode
from PIL import Image
import os
from utils import guardar_fila_nube, subir_pdf_drive, actualizar_estado_firma

def mostrar_modulo_firmador(df_personal):
    st.markdown("## 🖋️ ShieldSign: Centro de Certificación Digital")
    st.markdown("Emisión y seguimiento de documentos con firma electrónica y sello QR.")
    
    tab_emitir, tab_seguimiento, tab_config = st.tabs(["📤 Emitir Documento", "📊 Seguimiento de Firmas", "⚙️ Mi Firma Digital"])
    
    with tab_emitir:
        st.markdown("### 1. Configurar Envío")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            archivo_subido = st.file_uploader("Sube el PDF base (ODI, Contrato, Charla)", type=['pdf'])
            
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
                token_unico = str(uuid.uuid4()).split('-')[0].upper()
                
                # FASE 4: Guardamos el PDF que tú subiste para que el trabajador lo use luego
                with open(f"base_{token_unico}.pdf", "wb") as f:
                    f.write(archivo_subido.getbuffer())
                    
                st.success(f"¡Solicitud creada! ID de Rastreo: **{token_unico}**")
                link_firma = f"https://valeshield-v13-vvhfbjz9nvddeysacj2pan.streamlit.app/?firmar={token_unico}"
                
                # FASE 4: Registramos el estado "Pendiente" en Google Sheets
                rut_t = trabajador_sel.split(" - ")[0]
                fila_pendiente = {
                    "ID_Documento": token_unico,
                    "Fecha_Emision": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "RUT_Trabajador": rut_t,
                    "Nombre_Documento": tipo_doc,
                    "Estado": "Pendiente",
                    "Link_Firma": link_firma,
                    "Fecha_Firma": "",
                    "URL_Drive": ""
                }
                guardar_fila_nube(fila_pendiente, "certificados")
                
                st.info(f"🔗 **Link para el trabajador:**\n{link_firma}")
                st.markdown("*Copia este link y envíalo por WhatsApp al trabajador.*")
            else:
                st.error("Debes subir un PDF y seleccionar un trabajador.")

    with tab_seguimiento:
        st.markdown("### Documentos en Proceso")
        st.info("Revisa Google Sheets (pestaña 'certificados') para ver el estado en tiempo real.")

    with tab_config:
        st.markdown("### Configuración del Emisor")
        st.file_uploader("Sube una foto de tu firma (PNG sin fondo recomendado)", type=['png', 'jpg'])

def procesar_firma_y_sellar(canvas_image_data, token_firma):
    # 1. Preparar imágenes de firma y QR
    img = Image.fromarray(canvas_image_data.astype('uint8'), 'RGBA')
    ruta_firma = f"firma_{token_firma}.png"
    img.save(ruta_firma)
    
    qr_data = f"https://valeshield-v13-vvhfbjz9nvddeysacj2pan.streamlit.app/?firmar={token_firma}"
    qr = qrcode.make(qr_data)
    ruta_qr = f"qr_{token_firma}.png"
    qr.save(ruta_qr)
    
    # 2. Usar el PDF ORIGINAL
    ruta_base = f"base_{token_firma}.pdf"
    ruta_salida = f"Documento_Firmado_{token_firma}.pdf"
    
    if os.path.exists(ruta_base):
        doc = fitz.open(ruta_base)
    else:
        doc = fitz.open()
        doc.new_page()

    # 3. Estampado de Precisión Matemática
    for i in range(len(doc)):
        pagina = doc[i]
        w = pagina.rect.width   # Ancho de la hoja
        h = pagina.rect.height  # Alto de la hoja
        
        # A. ESTAMPAR QR EN TODAS LAS PÁGINAS (Esquina Inferior Derecha - Tamaño 50x50)
        rect_qr = fitz.Rect(w - 65, h - 65, w - 15, h - 15)
        pagina.insert_image(rect_qr, filename=ruta_qr)
        # Texto miniatura del ID debajo del QR
        pagina.insert_text((w - 65, h - 10), f"ID: {token_firma}", fontsize=6, color=(0.5, 0.5, 0.5))
        
        # B. ESTAMPAR FIRMA SÓLO EN LA ÚLTIMA PÁGINA (Esquina Inferior Izquierda - Tamaño Discreto)
        if i == len(doc) - 1:
            rect_firma = fitz.Rect(40, h - 70, 140, h - 20)
            pagina.insert_image(rect_firma, filename=ruta_firma)
            pagina.insert_text((40, h - 10), "Firma Digital Trabajador", fontsize=7, color=(0.5, 0.5, 0.5))
    
    doc.save(ruta_salida)
    doc.close()
    
    # 4. Subir a Google Drive y Actualizar Sheets
    url_drive = subir_pdf_drive(ruta_salida, ruta_salida)
    if url_drive:
        actualizar_estado_firma(token_firma, url_drive)
    
    # Limpiar basura del servidor
    os.remove(ruta_firma)
    os.remove(ruta_qr)
    
    return ruta_salida, url_drive
