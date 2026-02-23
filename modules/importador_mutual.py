import streamlit as st
import pandas as pd
from utils import obtener_datos_nube, limpiar_rut, guardar_fila_nube, cargar_bases_maestras
from datetime import datetime

def mostrar_modulo_importador():
    st.markdown("## 📥 Sincronización con Mutual (Valdivia)")
    st.info("Sube la nómina de la Mutual para actualizar tu registro de accidentes.")

    # 1. Carga de bases de forma segura y directa
    with st.spinner("Cargando base de personal..."):
        try:
            # Llamamos a la función normal, el caché de Streamlit hace el resto
            df_personal, _ = cargar_bases_maestras()
        except Exception as e:
            st.error(f"Error al conectar con la base de personal: {e}")
            df_personal = pd.DataFrame()

    archivo_subido = st.file_uploader("Subir nómina (.csv o .xlsx)", type=['csv', 'xlsx'])

    if archivo_subido:
        try:
            # Lectura del archivo
            if archivo_subido.name.endswith('.csv'):
                df_m = pd.read_csv(archivo_subido)
            else:
                df_m = pd.read_excel(archivo_subido)
            
            # FILTRO VALDIVIA (Basado en tu columna real)
            df_v = df_m[df_m['Centro de atención Mutual'].str.contains('VALDIVIA', na=False, case=False)].copy()

            if df_v.empty:
                st.warning("⚠️ No se encontraron registros de Valdivia en este archivo.")
                return

            # PROCESAMIENTO DE DATOS
            df_v['RUT_CORRECTO'] = (df_v['Rut Trabajador'].astype(str) + "-" + df_v['Dígito Rut trabajador'].astype(str)).apply(limpiar_rut)
            df_v['NOMBRE_FULL'] = (df_v['Nombre trabajador'] + " " + df_v['Apellido paterno trabajador']).str.title()

            # Creamos diccionario de sucursales para el cruce
            dict_sucursales = {}
            if not df_personal.empty:
                # Aseguramos que las columnas existan
                df_personal.columns = [c.upper() for c in df_personal.columns]
                dict_sucursales = df_personal.set_index('RUT')['SUCURSAL'].to_dict()

            registros_para_subir = []
            
            for _, row in df_v.iterrows():
                rut = row['RUT_CORRECTO']
                sucursal = dict_sucursales.get(rut, "DESCONOCIDA")
                
                estado_reg = "✅ Registrado" if sucursal != "DESCONOCIDA" else "❌ No Registrado"
                
                # Estructura v12.0 para el Sheets
                nuevo_dato = {
                    "Fecha": str(row['Fecha de ingreso']).split(" ")[0],
                    "Hora": "00:00",
                    "Sucursal": sucursal,
                    "RUT": rut,
                    "Trabajador": row['NOMBRE_FULL'],
                    "Antiguedad_Empresa": 0,
                    "Antiguedad_Cargo": 0,
                    "Tipo": row['Motivo de denuncia'],
                    "Dias_Perdidos": row['Días reposo'],
                    "Parte_Cuerpo": "Ver Resolución Mutual",
                    "Tipo_Lesion": "Ver Resolución Mutual",
                    "Relato": f"Importado de Mutual. Siniestro: {row.get('Número de siniestro', 'S/N')}",
                    "Acciones": "Revisión pendiente por Prevención de Riesgos",
                    "Estado": row['Estado de Calificación']
                }
                
                # Guardamos con la marca de registro para mostrar en la tabla
                registros_para_subir.append({**nuevo_dato, "REGISTRO": estado_reg})

            df_previa = pd.DataFrame(registros_para_subir)
            
            st.write(f"### Vista Previa ({len(df_previa)} accidentes)")
            
            # Mostrar tabla con colores
            def color_filas(val):
                return 'background-color: #ffcccc' if val == "❌ No Registrado" else ''

            st.dataframe(
                df_previa[['Fecha', 'RUT', 'Trabajador', 'Sucursal', 'REGISTRO']].style.applymap(color_filas, subset=['REGISTRO']),
                use_container_width=True,
                hide_index=True
            )

            # BOTÓN DE ACCIÓN
            col_btn, _ = st.columns([1, 2])
            if col_btn.button("🚀 Sincronizar con Google Sheets", type="primary", use_container_width=True):
                # Solo subimos los que tienen sucursal conocida
                solo_conocidos = [r for r in registros_para_subir if r['REGISTRO'] == "✅ Registrado"]
                
                if not solo_conocidos:
                    st.error("No hay registros válidos para subir. Los trabajadores deben estar en la base de personal.")
                else:
                    progreso = st.progress(0)
                    exitos = 0
                    for i, reg in enumerate(solo_conocidos):
                        # Limpiamos la columna auxiliar 'REGISTRO' antes de subir
                        dato_final = {k: v for k, v in reg.items() if k != "REGISTRO"}
                        if guardar_fila_nube(dato_final, "Accidentes"):
                            exitos += 1
                        progreso.progress((i + 1) / len(solo_conocidos))
                    
                    st.success(f"✅ ¡Excelente! Se sincronizaron {exitos} accidentes nuevos en la pestaña 'Accidentes'.")
                    st.balloons()

        except Exception as e:
            st.error(f"Hubo un problema al procesar el archivo: {e}")
