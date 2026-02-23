import streamlit as st
import pandas as pd
import os
from utils import ARCHIVO_USUARIOS, ARCHIVO_ACCIDENTES, cargar_usuarios, es_clave_segura, limpiar_rut, generar_pdf_accidentes

def mostrar_modulo_pdf():
    st.title("📄 Generador de Informes Mensuales")
    if os.path.exists(ARCHIVO_ACCIDENTES):
        df = pd.read_csv(ARCHIVO_ACCIDENTES)
        c1, c2 = st.columns(2)
        mes = c1.selectbox("Seleccionar Mes", range(1, 13))
        anio = c2.number_input("Año", value=2026)
        if st.button("🖨️ Generar Informe PDF"):
            path = generar_pdf_accidentes(df, f"{mes}/{anio}")
            with open(path, "rb") as f:
                st.download_button("📥 Descargar Reporte", f, file_name=path)

def mostrar_modulo_usuarios():
    st.title("👥 Gestión de Usuarios (Admin)")
    df_u = cargar_usuarios()
    st.dataframe(df_u[['RUT', 'Nombre', 'Rol']], use_container_width=True)
    with st.form("nuevo_u"):
        st.subheader("➕ Crear Nuevo Usuario")
        c1, c2 = st.columns(2)
        nr = c1.text_input("RUT")
        nn = c2.text_input("Nombre Completo")
        nc = c1.text_input("Clave Inicial", type="password")
        rl = c2.selectbox("Rol", ["visita", "admin"])
        if st.form_submit_button("💾 Crear"):
            if nr and nn and es_clave_segura(nc)[0]:
                pd.concat([df_u, pd.DataFrame([{"RUT": limpiar_rut(nr), "Nombre": nn, "Clave": nc, "Rol": rl}])]).to_csv(ARCHIVO_USUARIOS, index=False)
                st.success("✅ Usuario creado."); st.rerun()

def mostrar_cambio_clave(usuario_rut):
    st.title("🔐 Seguridad de Cuenta")
    with st.form("f_clave"):
        ca = st.text_input("Clave Actual", type="password")
        cn = st.text_input("Nueva Clave", type="password")
        if st.form_submit_button("Actualizar Contraseña"):
            valido, msg = es_clave_segura(cn)
            if valido:
                df = cargar_usuarios()
                idx = df[df['RUT'] == usuario_rut].index[0]
                if df.at[idx, 'Clave'] == ca:
                    df.at[idx, 'Clave'] = cn; df.to_csv(ARCHIVO_USUARIOS, index=False)
                    st.success("✅ Clave actualizada con éxito.")
                else: st.error("❌ La clave actual es incorrecta.")
            else: st.error(msg)