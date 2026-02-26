import streamlit as st
import pandas as pd
from utils import obtener_datos_nube, limpiar_rut, guardar_fila_nube, cargar_bases_maestras
from datetime import datetime

def mostrar_modulo_importador():
    st.markdown("## 📥 Sincronización con Mutual (Valdivia)")
    st.info("Sube la nómina de la Mutual para actualizar tu registro de accidentes.")

    # ========================================================
    # 1. EL DESTRUCTOR DE CACHÉ INVISIBLE (La Clave)
    # ========================================================
    # Esto obliga a ValeShield a leer el Google Sheets en vivo siempre
    st.cache_data.clear()

    # 2. Carga de bases de forma segura y directa
    with st.spinner("Descargando memoria en vivo desde Google Sheets..."):
        try:
            df_personal, _ = cargar_bases_maestras()
            # 🛡️ EL GUARDIA: Descargamos los accidentes reales que ya están guardados
            df_accidentes_existentes = obtener_datos_nube("Accidentes")
        except Exception as e:
            st.error(f"Error al conectar con la base de datos: {e}")
            df_personal = pd.DataFrame()
            df_accidentes_existentes = pd.DataFrame()

    # 3. Creamos la "Lista Negra" de duplicados (RUT + Fecha) súper blindada
    firmas_existentes = set()
    if not df_accidentes_existentes.empty:
        df_accidentes_existentes.columns = [str(c).upper().strip() for c in df_accidentes_existentes.columns]
        
        col_rut = next((c for c in df_accidentes_existentes.columns if 'RUT' in c), None)
        col_fecha = next((c for c in df_accidentes_existentes.columns if 'FECHA' in c), None)
        
        if col_rut and col_fecha:
            for _, rx in df_accidentes_existentes.iterrows():
                r_limpio = limpiar_rut(str(rx[col_rut]))
                fecha_raw = str(rx[col_fecha]).strip().split(" ")[0]
                
                # Traductor universal de fechas para la lista negra
                try:
                    f_dt = pd.to_datetime(fecha_raw, dayfirst=True, errors='coerce')
                    f_str = f_dt.strftime("%Y-%m-%d") if pd.notna(f_dt) else fecha_raw
                except:
                    f_str = fecha_raw
                
                firmas_existentes.add(f"{r_limpio}_{f_str}")

    archivo_subido = st.file_uploader("Subir nómina (.csv o .xlsx)", type=['csv', 'xlsx'])

    if archivo_subido:
        try:
            # Lectura del archivo
            if archivo_subido.name.endswith('.csv'):
                df_m = pd.read_csv(archivo_subido)
            else:
                df_m = pd.read_excel(archivo_subido)
            
            # FILTRO VALDIVIA
            df_v = df_m[df_m['Centro de atención Mutual'].str.contains('VALDIVIA', na=False, case=False)].copy()

            if df_v.empty:
                st.warning("⚠️ No se encontraron registros de Valdivia en este archivo.")
                return

            # PROCESAMIENTO DE DATOS
            df_v['RUT_CORRECTO'] = (df_v['Rut Trabajador'].astype(str) + "-" + df_v['Dígito Rut trabajador'].astype(str)).apply(limpiar_rut)
            df_v['NOMBRE_FULL'] = (df_v['Nombre trabajador'] + " " + df_v['Apellido paterno trabajador']).str.title()

            dict_sucursales = {}
            if not df_personal.empty:
                df_personal.columns = [c.upper() for c in df_personal.columns]
                dict_sucursales = df_personal.set_index('RUT')['SUCURSAL'].to_dict()

            registros_para_subir = []
            
            for _, row in df_v.iterrows():
                rut = row['RUT_CORRECTO']
                sucursal = dict_sucursales.get(rut, "DESCONOCIDA")
                
                # 🛡️ VALIDACIÓN CONTRA DUPLICADOS (Cruce de la Mutual vs Lista Negra)
                fecha_raw_mut = str(row['Fecha de ingreso']).split(" ")[0]
                try:
                    f_dt_mut = pd.to_datetime(fecha_raw_mut, dayfirst=True, errors='coerce')
                    fecha_comp = f_dt_mut.strftime("%Y-%m-%d") if pd.notna(f_dt_mut) else fecha_raw_mut
                except:
                    fecha_comp = fecha_raw_mut
                    
                firma_actual = f"{rut}_{fecha_comp}"
                
                # Clasificador de estado
                if firma_actual in firmas_existentes:
                    estado_reg = "⚠️ Ya Existe (Duplicado)"
                elif sucursal != "DESCONOCIDA":
                    estado_reg = "✅ Registrado"
                else:
                    estado_reg = "❌ No Registrado"
                
                nuevo_dato = {
                    "Fecha": fecha_raw_mut,
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
                
                registros_para_subir.append({**nuevo_dato, "REGISTRO": estado_reg})

            df_previa = pd.DataFrame(registros_para_subir)
            
            st.write(f"### Vista Previa ({len(df_previa)} accidentes evaluados)")
            
            # Mostrar tabla con colores inteligentes
            def color_filas(val):
                if val == "❌ No Registrado": return 'background-color: #ffcccc'  
                if val == "⚠️ Ya Existe (Duplicado)": return 'background-color: #ffe6cc' 
                return ''

            try:
                st.dataframe(df_previa[['Fecha', 'RUT', 'Trabajador', 'Sucursal', 'REGISTRO']].style.map(color_filas, subset=['REGISTRO']), use_container_width=True, hide_index=True)
            except AttributeError:
                st.dataframe(df_previa[['Fecha', 'RUT', 'Trabajador', 'Sucursal', 'REGISTRO']].style.applymap(color_filas, subset=['REGISTRO']), use_container_width=True, hide_index=True)

            # BOTÓN DE ACCIÓN
            col_btn, _ = st.columns([1, 2])
            if col_btn.button("🚀 Sincronizar con Google Sheets", type="primary", use_container_width=True):
                # 🛑 EL BOTÓN SOLO TOMA LOS "✅ Registrado"
                solo_conocidos = [r for r in registros_para_subir if r['REGISTRO'] == "✅ Registrado"]
                
                if not solo_conocidos:
                    st.error("No hay registros nuevos válidos para subir (Todos son duplicados o no encontrados).")
                else:
                    progreso = st.progress(0)
                    exitos = 0
                    for i, reg in enumerate(solo_conocidos):
                        dato_final = {k: v for k, v in reg.items() if k != "REGISTRO"}
                        if guardar_fila_nube(dato_final, "Accidentes"):
                            exitos += 1
                        progreso.progress((i + 1) / len(solo_conocidos))
                    
                    st.success(f"✅ ¡Excelente! Se sincronizaron {exitos} accidentes nuevos en la pestaña 'Accidentes'.")
                    st.cache_data.clear() # Limpiamos la caché de nuevo por seguridad
                    st.balloons()

        except Exception as e:
            st.error(f"Hubo un problema al procesar el archivo: {e}")
