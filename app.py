import streamlit as st
import streamlit_antd_components as sac 
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import os
import base64
from datetime import datetime

# ==========================================
# 🛡️ 1. CONFIGURACIÓN DE PÁGINA (SIEMPRE PRIMERO)
# ==========================================
st.set_page_config(
    page_title="ValeShield Pro",
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# ==========================================
# 📱 2. INYECCIÓN DE METADATOS PWA
# ==========================================
components.html(
    """
    <script>
    const manifest = {
      "name": "ValeShield Pro",
      "short_name": "ValeShield",
      "start_url": ".",
      "display": "standalone",
      "background_color": "#1E3A8A",
      "theme_color": "#1E3A8A",
      "description": "Sistema de Gestión de Riesgos Valdivia",
      "icons": [
        {
          "src": "https://cdn-icons-png.flaticon.com/512/1063/1063251.png",
          "sizes": "512x512",
          "type": "image/png"
        }
      ]
    };
    const stringManifest = JSON.stringify(manifest);
    const blob = new Blob([stringManifest], {type: 'application/json'});
    const manifestURL = URL.createObjectURL(blob);
    const link = document.createElement('link');
    link.rel = 'manifest';
    link.href = manifestURL;
    document.getElementsByTagName('head')[0].appendChild(link);
    </script>
    """,
    height=0,
)

# ==========================================
# 🕵️ FASE 4/5 SHIELDSIGN: MOTOR DE ESTAMPADO Y VISOR
# ==========================================
if "firmar" in st.query_params:
    from streamlit_drawable_canvas import st_canvas
    
    token_firma = st.query_params["firmar"]
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align: center; color: #1E3A8A;'>🖋️ Firma Digital ValeShield</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.info(f"📄 **Validación de Documento ID:** {token_firma}")
        
        # --- MISIÓN B: VISOR DE PDF INCORPORADO ---
        st.markdown("### 1. Revise el Documento")
        ruta_base = f"base_{token_firma}.pdf"
        
        if os.path.exists(ruta_base):
            # Leemos el PDF guardado previamente y lo mostramos
            with open(ruta_base, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
            
            # Incrustar el PDF usando un iframe adaptado
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}#toolbar=0&navpanes=0" width="100%" height="350" type="application/pdf" style="border: 1px solid #ccc; border-radius: 5px; margin-bottom: 20px;"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            st.warning("⚠️ El documento original se está procesando o no se encuentra disponible. Por favor avise a su jefatura.")
        
        st.markdown("### 2. Firme el Documento")
        st.markdown("Dibuje su firma en el recuadro inferior y presione Guardar.")
        
        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 0)",
            stroke_width=3,
            stroke_color="#000000",
            background_color="#f0f2f6",
            height=250,
            width=350,
            drawing_mode="freedraw",
            key="canvas_firma",
        )
        
        if st.button("Guardar Firma y Sellar Documento ✅", type="primary", use_container_width=True):
            if canvas_result.image_data is not None:
                if np.sum(canvas_result.image_data) > 0:
                    st.success("✅ ¡Firma capturada con éxito!")
                    st.info("🔄 Estampando firmas y generando certificado PDF...")
                    
                    from modules.firmador import procesar_firma_y_sellar
                    ruta_pdf, url_drive = procesar_firma_y_sellar(canvas_result.image_data, token_firma)
                    
                    st.balloons()
                    st.success("¡Documento legal generado y sellado!")
                    
                    if url_drive:
                        st.info("☁️ Documento respaldado automáticamente en su carpeta.")
                    
                    with open(ruta_pdf, "rb") as pdf_file:
                        st.download_button(
                            label="📥 Descargar Documento Firmado Oficial", 
                            data=pdf_file, 
                            file_name=ruta_pdf, 
                            mime="application/pdf", 
                            type="primary", 
                            use_container_width=True
                        )
                else:
                    st.error("⚠️ El lienzo está vacío. Debes dibujar tu firma.")
            else:
                st.error("⚠️ Error al capturar el lienzo.")
                
    st.stop()

# ==========================================
# 📦 3. IMPORTACIÓN DE MÓDULOS INTERNOS
# ==========================================
from utils import cargar_usuarios, limpiar_rut, ARCHIVO_SOPORTE, df_personal
from modules.accidentes import mostrar_modulo_accidentes
from modules.examenes import mostrar_modulo_examenes
from modules.preventivo import mostrar_modulo_preventivo
from modules.personal import mostrar_modulo_personal
from modules.soporte import mostrar_modulo_soporte
from modules.seguridad import mostrar_modulo_usuarios, mostrar_cambio_clave
from modules.estadisticas import mostrar_modulo_estadisticas
from modules.investigacion import mostrar_modulo_investigacion 
from modules.importador_mutual import mostrar_modulo_importador
from modules.firmador import mostrar_modulo_firmador 

if 'logueado' not in st.session_state: st.session_state['logueado'] = False
if 'opcion_actual' not in st.session_state: st.session_state['opcion_actual'] = "Inicio"

# ==========================================
# 🚪 4. LOGIN (ESTÉTICA MINIMALISTA)
# ==========================================
if not st.session_state['logueado']:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style='text-align: center;'>
                <h1 style='color: #1E3A8A;'>ValeShield</h1>
                <p style='color: gray;'>Sistema de Gestión de Riesgos v14.0</p>
            </div>
        """, unsafe_allow_html=True)
        
        with st.container(border=True):
            rut_in = st.text_input("Usuario (RUT)", placeholder="Ej: 12345678-9")
            pass_in = st.text_input("Contraseña", type="password")
            
            if st.button("Iniciar Sesión", type="primary", use_container_width=True):
                df_u = cargar_usuarios()
                user = df_u[(df_u['RUT'] == limpiar_rut(rut_in)) & (df_u['Clave'] == pass_in)]
                if not user.empty:
                    st.session_state.update({
                        'logueado': True, 
                        'usuario_nombre': user.iloc[0]['Nombre'], 
                        'usuario_rol': user.iloc[0]['Rol'], 
                        'usuario_rut': user.iloc[0]['RUT']
                    })
                    st.rerun()
                else:
                    st.error("❌ Acceso denegado.")
        
        if st.button("🆘 Reportar Problema de Acceso", use_container_width=True):
            st.session_state['sos_pre'] = True
            
    if st.session_state.get('sos_pre'):
        with st.form("sos_login"):
            det = st.text_area("Describa el problema:")
            if st.form_submit_button("Enviar"):
                pd.DataFrame([{"Fecha": datetime.now(), "Usuario": "INVITADO", "Detalle": det}]).to_csv(ARCHIVO_SOPORTE, mode='a', header=not os.path.exists(ARCHIVO_SOPORTE), index=False)
                st.success("Enviado."); st.session_state['sos_pre'] = False
    st.stop()

# ==========================================
# 🏠 5. MENÚ LATERAL PROFESIONAL
# ==========================================
with st.sidebar:
    st.markdown(f"""
        <div style='text-align: center; padding: 20px 0;'>
            <div style='width: 60px; height: 60px; background-color: #3b82f6; border-radius: 50%; margin: 0 auto; display: flex; align-items: center; justify-content: center; font-size: 24px; color: white;'>
                {st.session_state['usuario_nombre'][0]}
            </div>
            <h3 style='margin: 10px 0 0 0; font-size: 16px;'>{st.session_state['usuario_nombre']}</h3>
            <p style='color: #888; font-size: 12px; margin: 0;'>{st.session_state['usuario_rut']}</p>
        </div>
    """, unsafe_allow_html=True)

    items_menu = [
        sac.MenuItem('Inicio', icon='house-door-fill'),
        sac.MenuItem('Accidentabilidad', icon='activity', children=[
            sac.MenuItem('Estadísticas', icon='bar-chart-line-fill'),
            sac.MenuItem('Reporte Preventivo', icon='shield-check'),
            sac.MenuItem('Registro Accidentes', icon='bandaid-fill'),
            sac.MenuItem('Investigación de Accidentes', icon='search'),
            sac.MenuItem('Sincronizar Mutual', icon='cloud-arrow-up-fill'), 
        ]),
        sac.MenuItem('Base de Personal', icon='people-fill'),
        sac.MenuItem('Exámenes Ocupacionales', icon='heart-pulse-fill'),
        sac.MenuItem('ShieldSign (Firmas)', icon='pen-fill'),
        sac.MenuItem(type='divider'),
        sac.MenuItem('Configuración', type='group', children=[
            sac.MenuItem('Cambiar Clave', icon='key-fill'),
            sac.MenuItem('Solicitar Ayuda', icon='life-preserver'),
        ]),
    ]
    
    if st.session_state['usuario_rol'] == 'admin':
        items_menu.append(sac.MenuItem('Gestión Usuarios', icon='person-lines-fill'))

    opcion_seleccionada = sac.menu(
        items=items_menu, index=0, format_func='title', size='sm', indent=20, open_all=True, color='blue',
    )

    if opcion_seleccionada != st.session_state.get('opcion_actual_visual'):
        st.session_state['opcion_actual'] = opcion_seleccionada
        st.session_state['opcion_actual_visual'] = opcion_seleccionada

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Cerrar Sesión", icon="🚪", use_container_width=True):
        st.session_state['logueado'] = False
        st.rerun()

# ==========================================
# 🚀 6. CARGA ÚNICA DE MÓDULOS
# ==========================================
opcion = st.session_state['opcion_actual']

if opcion == "Inicio":
    st.title("Panel de Control General")
    st.info(f"Bienvenido al Sistema de Gestión Integrado, {st.session_state['usuario_nombre']}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Estado del Sistema", "Operativo", "v14.0")
    col2.metric("Sucursal Actual", "ELECTROCOM/MCT", "Valdivia")
    col3.metric("Días sin Accidentes", "Calculando...", "Ver Estadísticas")
    
    st.markdown("---")
    st.markdown("### 📌 Accesos Rápidos")
    c1, c2, c3 = st.columns(3)
    if c1.button("🚨 Reportar Accidente", use_container_width=True):
        st.session_state['opcion_actual'] = "Registro Accidentes"
        st.rerun()
    if c2.button("📊 Ver KPIs del Mes", use_container_width=True):
        st.session_state['opcion_actual'] = "Estadísticas"
        st.rerun()
    if c3.button("🖋️ Emitir Documento", use_container_width=True):
        st.session_state['opcion_actual'] = "ShieldSign (Firmas)"
        st.rerun()

elif opcion == "Estadísticas": mostrar_modulo_estadisticas()
elif opcion == "Reporte Preventivo": mostrar_modulo_preventivo(st.session_state['usuario_rol'])
elif opcion == "Registro Accidentes": mostrar_modulo_accidentes(st.session_state['usuario_rol'])
elif opcion == "Investigación de Accidentes": mostrar_modulo_investigacion()
elif opcion == "Sincronizar Mutual": mostrar_modulo_importador()
elif opcion == "Base de Personal": mostrar_modulo_personal(st.session_state['usuario_rol'])
elif opcion == "Exámenes Ocupacionales": mostrar_modulo_examenes()
elif opcion == "ShieldSign (Firmas)": mostrar_modulo_firmador(df_personal)
elif opcion == "Cambiar Clave": mostrar_cambio_clave(st.session_state['usuario_rut'])
elif opcion == "Solicitar Ayuda": mostrar_modulo_soporte(st.session_state['usuario_nombre'], st.session_state['usuario_rol'])
elif opcion == "Gestión Usuarios": mostrar_modulo_usuarios()
