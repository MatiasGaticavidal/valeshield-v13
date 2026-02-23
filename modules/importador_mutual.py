import streamlit as st
import pandas as pd
from utils import obtener_datos_nube, limpiar_rut, guardar_fila_nube
from datetime import datetime

def mostrar_modulo_importador():
    st.markdown("## 📥 Sincronización con Mutual (Valdivia)")
    st.info("Sube la nómina de la Mutual para actualizar tu registro de accidentes.")

    # 1. Carga de bases necesarias
    with st.spinner("Cargando bases maestras..."):
        df_personal, _ = st.cache_data.get_entry("cargar_bases_maestras")() # Usamos la función de utils
        # Si por alguna razón falla el cache, llamamos directo
        if df_personal is None or df_personal.empty:
            df_personal = obtener_datos_nube("personal")

    archivo_subido = st.file_uploader("Subir nómina (.csv o .xlsx)", type=['csv', 'xlsx'])

    if archivo_subido:
        try:
            df_m = pd.read_csv(archivo_subido) if archivo_subido.name.endswith('.csv') else pd.read_excel(archivo_subido)
            
            # FILTRO VALDIVIA
            df_v = df_m[df_m['Centro de atención Mutual'].str.contains('VALDIVIA', na=False, case=False)].copy()

            if df_v.empty:
                st.warning("No hay datos de Valdivia.")
                return

            # PROCESAMIENTO
            df_v['RUT_CORRECTO'] = (df_v['Rut Trabajador'].astype(str) + "-" + df_v['Dígito Rut trabajador'].astype(str)).apply(limpiar_rut)
            df_v['NOMBRE_FULL'] = (df_v['Nombre trabajador'] + " " + df_v['Apellido paterno trabajador']).str.title()

            # Diccionario de personal para cruce de Sucursal
            dict_sucursales = df_personal.set_index('RUT')['SUCURSAL'].to_dict() if not df_personal.empty else {}

            registros_para_subir = []
            
            for _, row in df_v.iterrows():
                rut = row['RUT_CORRECTO']
                sucursal = dict_sucursales.get(rut, "DESCONOCIDA")
                
                estado_reg = "✅ Registrado" if sucursal != "DESCONOCIDA" else "❌ No Registrado"
                
                # Preparamos el formato exacto de tu Google Sheets (v12.0)
                nuevo_dato = {
                    "Fecha": str(row['Fecha de ingreso']).split(" ")[0],
                    "Hora": "00:00", # La mutual no siempre da la hora exacta del evento
                    "Sucursal": sucursal,
                    "RUT": rut,
                    "Trabajador": row['NOMBRE_FULL'],
                    "Antiguedad_Empresa": 0,
                    "Antiguedad_Cargo": 0,
                    "Tipo": row['Motivo de denuncia'],
                    "Dias_Perdidos": row['Días reposo'],
                    "Parte_Cuerpo": "Ver Resolución",
                    "Tipo_Lesion": "Ver Resolución",
                    "Relato": f"Sincronizado desde Mutual. Resolución: {row['Resolución de Calificación']}",
                    "Acciones": "Pendiente revisión por DPR",
                    "Estado": row['Estado de Calificación']
                }
                
                registros_para_subir.append({**nuevo_dato, "REGISTRO": estado_reg})

            df_previa = pd.DataFrame(registros_para_subir)
            
            # Mostrar tabla al usuario
            st.dataframe(df_previa[['Fecha', 'RUT', 'Trabajador', 'Sucursal', 'REGISTRO']], use_container_width=True, hide_index=True)

            # BOTÓN DE ACCIÓN FINAL
            if st.button("🚀 Sincronizar Accidentes de Valdivia", type="primary"):
                solo_conocidos = [r for r in registros_para_subir if r['REGISTRO'] == "✅ Registrado"]
                
                if not solo_conocidos:
                    st.error("No hay trabajadores registrados para sincronizar. Agregalos primero a la pestaña 'personal'.")
                else:
                    progreso = st.progress(0)
                    exitos = 0
                    for i, reg in enumerate(solo_conocidos):
                        # Quitamos la columna 'REGISTRO' antes de subir a Sheets
                        dato_final = {k: v for k, v in reg.items() if k != "REGISTRO"}
                        if guardar_fila_nube(dato_final, "Accidentes"):
                            exitos += 1
                        progreso.progress((i + 1) / len(solo_conocidos))
                    
                    st.success(f"✅ ¡Proceso Terminado! Se sincronizaron {exitos} accidentes con éxito.")
                    if len(solo_conocidos) < len(registros_para_subir):
                        st.warning(f"Se omitieron {len(registros_para_subir) - len(solo_conocidos)} registros porque los trabajadores no estaban en tu base de datos.")

        except Exception as e:
            st.error(f"Error técnico: {e}")
