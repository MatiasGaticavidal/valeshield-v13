import streamlit as st
import pandas as pd
import os
from utils import ARCHIVO_PERSONAL, URL_NOMINA, limpiar_rut

def mostrar_modulo_personal(usuario_rol):
    st.title("👷 Gestión de Base de Personal")
    
    if usuario_rol == 'admin':
        t1, t2 = st.tabs(["📝 Registro / Búsqueda RUT", "📥 Sincronizar Maestra"])
        
        with t1:
            col_b1, col_b2 = st.columns([2,1])
            rut_bus = col_b1.text_input("Ingresar RUT para buscar", placeholder="12345678-9")
            
            if col_b2.button("🔍 Buscar en Maestra"):
                try:
                    df_nb = pd.read_csv(URL_NOMINA)
                    df_nb.columns = df_nb.columns.str.strip().str.upper()
                    res = df_nb[df_nb['RUT'].astype(str).apply(limpiar_rut) == limpiar_rut(rut_bus)]
                    if not res.empty:
                        st.session_state['trabajador_encontrado'] = res.iloc[0].to_dict()
                        st.success("✅ Trabajador encontrado en la nube.")
                    else:
                        st.error("❌ No encontrado.")
                except:
                    st.error("Error al conectar con la nómina.")

            with st.form("form_personal_modular", clear_on_submit=True):
                w = st.session_state.get('trabajador_encontrado', {})
                c1, c2 = st.columns(2)
                f_rut = c1.text_input("RUT", value=w.get('RUT', rut_bus))
                f_nom = c2.text_input("Nombre Completo", value=w.get('NOMBRE', ""))
                f_car = c1.text_input("Cargo", value=w.get('CARGO', ""))
                f_suc = c2.selectbox("Sucursal", ["ELECTROCOM VALDIVIA", "MCT VALDIVIA", "PLACA CENTRO VALDIVIA"], 
                                     index=0 if w.get('SUCURSAL') not in ["ELECTROCOM VALDIVIA", "MCT VALDIVIA", "PLACA CENTRO VALDIVIA"] else ["ELECTROCOM VALDIVIA", "MCT VALDIVIA", "PLACA CENTRO VALDIVIA"].index(w.get('SUCURSAL')))
                f_sex = st.selectbox("Sexo", ["MASCULINO", "FEMENINO"], index=0 if w.get('SEXO', '').upper() != 'FEMENINO' else 1)
                
                if st.form_submit_button("💾 Guardar localmente"):
                    nuevo_p = {"RUT": limpiar_rut(f_rut), "NOMBRE": f_nom, "CARGO": f_car, "SUCURSAL": f_suc, "SEXO": f_sex}
                    pd.DataFrame([nuevo_p]).to_csv(ARCHIVO_PERSONAL, mode='a', header=not os.path.exists(ARCHIVO_PERSONAL), index=False)
                    st.success("✅ Guardado en base local.")
                    if 'trabajador_encontrado' in st.session_state:
                        del st.session_state['trabajador_encontrado']
                    st.rerun()
        
        with t2:
            if st.button("🔄 Sincronizar TODA la Nómina"):
                try:
                    df_m = pd.read_csv(URL_NOMINA)
                    df_m.columns = df_m.columns.str.strip().str.upper()
                    df_m[["RUT", "NOMBRE", "CARGO", "SUCURSAL", "SEXO"]].dropna().to_csv(ARCHIVO_PERSONAL, index=False)
                    st.success("✅ Sincronización exitosa.")
                except:
                    st.error("Error en las columnas del Excel.")

    if os.path.exists(ARCHIVO_PERSONAL):
        st.dataframe(pd.read_csv(ARCHIVO_PERSONAL, encoding='latin1'), use_container_width=True)