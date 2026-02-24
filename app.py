import streamlit as st
import streamlit_antd_components as sac # La nueva librería visual
from utils import cargar_usuarios, limpiar_rut, ARCHIVO_SOPORTE
# Importación de Módulos
from modules.accidentes import mostrar_modulo_accidentes
from modules.examenes import mostrar_modulo_examenes
from modules.preventivo import mostrar_modulo_preventivo
from modules.personal import mostrar_modulo_personal
from modules.soporte import mostrar_modulo_soporte
from modules.seguridad import mostrar_modulo_usuarios, mostrar_cambio_clave
from modules.estadisticas import mostrar_modulo_estadisticas
from modules.investigacion import mostrar_modulo_investigacion # Nuevo Módulo
from modules.importador_mutual import mostrar_modulo_importador
import pandas as pd
import os
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA PARA PWA ---
st.set_page_config(
    page_title="ValeShield Pro",
    page_icon="🛡️", # Puedes cambiar esto por la URL de un logo cuadrado después
    layout="wide",
    initial_sidebar_state="collapsed" # En el celular es mejor que el menú empiece cerrado
)
# Inicialización de estados
if 'logueado' not in st.session_state: st.session_state['logueado'] = False
if 'opcion_actual' not in st.session_state: st.session_state['opcion_actual'] = "Inicio"

# ==========================================
# 🚪 LOGIN (ESTÉTICA MINIMALISTA)
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
# 🏠 MENÚ LATERAL PROFESIONAL (ANTD STYLE)
# ==========================================
with st.sidebar:
    # 1. PERFIL DE USUARIO
    st.markdown(f"""
        <div style='text-align: center; padding: 20px 0;'>
            <div style='width: 60px; height: 60px; background-color: #3b82f6; border-radius: 50%; margin: 0 auto; display: flex; align-items: center; justify-content: center; font-size: 24px; color: white;'>
                {st.session_state['usuario_nombre'][0]}
            </div>
            <h3 style='margin: 10px 0 0 0; font-size: 16px;'>{st.session_state['usuario_nombre']}</h3>
            <p style='color: #888; font-size: 12px; margin: 0;'>{st.session_state['usuario_rut']}</p>
        </div>
    """, unsafe_allow_html=True)

    # 2. DEFINICIÓN DE ITEMS DEL MENÚ
    items_menu = [
        sac.MenuItem('Inicio', icon='house-door-fill'),
        
        sac.MenuItem('Accidentabilidad', icon='activity', children=[
            sac.MenuItem('Estadísticas', icon='bar-chart-line-fill'),
            sac.MenuItem('Reporte Preventivo', icon='shield-check'),
            sac.MenuItem('Registro Accidentes', icon='bandaid-fill'),
            sac.MenuItem('Investigación de Accidentes', icon='search'),
            sac.MenuItem('Sincronizar Mutual', icon='cloud-arrow-up-fill'), # <--- AGREGAR AQUÍ
        ]),
        
        sac.MenuItem('Base de Personal', icon='people-fill'),

        sac.MenuItem('Exámenes Ocupacionales', icon='heart-pulse-fill'),
        
        sac.MenuItem(type='divider'),
        
        sac.MenuItem('Configuración', type='group', children=[
            sac.MenuItem('Cambiar Clave', icon='key-fill'),
            sac.MenuItem('Solicitar Ayuda', icon='life-preserver'),
        ]),
    ]
    
    if st.session_state['usuario_rol'] == 'admin':
        items_menu.append(sac.MenuItem('Gestión Usuarios', icon='person-lines-fill'))

    # 3. RENDERIZADO DEL MENÚ
    opcion_seleccionada = sac.menu(
        items=items_menu,
        index=0,
        format_func='title',
        size='sm',
        indent=20,
        open_all=True,
        color='blue',
    )

    if opcion_seleccionada != st.session_state.get('opcion_actual_visual'):
        st.session_state['opcion_actual'] = opcion_seleccionada
        st.session_state['opcion_actual_visual'] = opcion_seleccionada

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Cerrar Sesión", icon="🚪", use_container_width=True):
        st.session_state['logueado'] = False
        st.rerun()

# ==========================================
# 🚀 CARGA ÚNICA DE MÓDULOS (Lógica Limpia)
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
    c1, c2 = st.columns(2)
    if c1.button("🚨 Reportar Accidente Ahora", use_container_width=True):
        st.session_state['opcion_actual'] = "Registro Accidentes"
        st.rerun()
    if c2.button("📊 Ver KPIs del Mes", use_container_width=True):
        st.session_state['opcion_actual'] = "Estadísticas"
        st.rerun()

elif opcion == "Estadísticas":
    mostrar_modulo_estadisticas()

elif opcion == "Reporte Preventivo":
    mostrar_modulo_preventivo(st.session_state['usuario_rol'])

elif opcion == "Registro Accidentes":
    mostrar_modulo_accidentes(st.session_state['usuario_rol'])

elif opcion == "Investigación de Accidentes":
    mostrar_modulo_investigacion()

elif opcion == "Sincronizar Mutual": 
    mostrar_modulo_importador()

elif opcion == "Base de Personal":
    mostrar_modulo_personal(st.session_state['usuario_rol'])

elif opcion == "Exámenes Ocupacionales":
    mostrar_modulo_examenes()

elif opcion == "Cambiar Clave":
    mostrar_cambio_clave(st.session_state['usuario_rut'])

elif opcion == "Solicitar Ayuda":
    mostrar_modulo_soporte(st.session_state['usuario_nombre'], st.session_state['usuario_rol'])

elif opcion == "Gestión Usuarios":
    mostrar_modulo_usuarios()

