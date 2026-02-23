import streamlit as st
import pandas as pd
from utils import obtener_datos_nube, limpiar_rut

def mostrar_modulo_importador():
    st.markdown("## 📥 Sincronización con Mutual (Valdivia)")
    st.info("Sube la nómina de accidentados descargada de la Mutual para procesar los datos de Valdivia.")

    # 1. Carga previa de personal para el cruce de datos
    with st.spinner("Verificando base de datos de personal..."):
        df_personal = obtener_datos_nube("personal")
    
    # Creamos un conjunto de RUTs conocidos para búsqueda rápida
    ruts_conocidos = []
    if not df_personal.empty:
        df_personal.columns = [c.strip().upper() for c in df_personal.columns]
        ruts_conocidos = df_personal['RUT'].apply(limpiar_rut).tolist()

    archivo_subido = st.file_uploader("Arrastra aquí el archivo de la Mutual (.csv o .xlsx)", type=['csv', 'xlsx'])

    if archivo_subido:
        try:
            # Leer el archivo según su extensión
            if archivo_subido.name.endswith('.csv'):
                df_mutual = pd.read_csv(archivo_subido)
            else:
                df_mutual = pd.read_excel(archivo_subido)

            # --- PROCESAMIENTO INTELIGENTE ---
            
            # 1. Filtro estricto por Valdivia (como en la columna de tu archivo)
            df_valdivia = df_mutual[df_mutual['Centro de atención Mutual'].str.contains('VALDIVIA', na=False, case=False)].copy()

            if df_valdivia.empty:
                st.warning("⚠️ No se encontraron registros correspondientes a la sede VALDIVIA en este archivo.")
                return

            # 2. Unión de campos (RUT y Nombre Completo)
            df_valdivia['RUT_GEN'] = df_valdivia['Rut Trabajador'].astype(str) + "-" + df_valdivia['Dígito Rut trabajador'].astype(str)
            df_valdivia['NOMBRE_GEN'] = (
                df_valdivia['Nombre trabajador'] + " " + 
                df_valdivia['Apellido paterno trabajador'] + " " + 
                df_valdivia['Apellido materno trabajador']
            ).str.title()

            # 3. Mapeo a las columnas de interés que definimos
            columnas_interes = {
                'Fecha de ingreso': 'FECHA INGRESO',
                'NOMBRE_GEN': 'NOMBRE',
                'RUT_GEN': 'RUT',
                'Motivo de denuncia': 'ACCIDENTE',
                'Estado de Calificación': 'ESTADO',
                'Días reposo': 'DIAS PERDIDOS',
                'Resolución de Calificación': 'RESOLUCION'
            }
            
            df_final = df_valdivia[list(columnas_interes.keys())].rename(columns=columnas_interes)

            # 4. Verificación de existencia en el sistema
            def chequear_existencia(rut):
                rut_l = limpiar_rut(rut)
                return "✅ En Sistema" if rut_l in ruts_conocidos else "❌ No Registrado"

            df_final['REGISTRO'] = df_final['RUT'].apply(chequear_existencia)

            # --- MOSTRAR RESULTADOS ---
            st.success(f"Se procesaron {len(df_final)} accidentes de Valdivia.")
            
            # Estilo para resaltar los no registrados
            def color_registro(val):
                color = '#ffcccc' if val == "❌ No Registrado" else ''
                return f'background-color: {color}'

            st.dataframe(
                df_final.style.applymap(color_registro, subset=['REGISTRO']),
                use_container_width=True,
                hide_index=True
            )

            # Botón de acción (Solo informativo por ahora hasta conectar el guardado)
            if st.button("Procesar y Sincronizar con Google Sheets", type="primary"):
                st.warning("Función de escritura en desarrollo. Verifica los 'No Registrados' antes de subir.")

        except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")