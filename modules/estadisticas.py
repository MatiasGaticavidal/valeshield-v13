import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
import os
import re
from utils import obtener_datos_nube, calcular_hh_estimadas, actualizar_hoja_completa, subir_pdf_drive

def mostrar_modulo_estadisticas():
    # --- CSS PARA IMPRESIÓN LIMPIA DE PDF ---
    st.markdown("""
        <style>
        @media print {
            section[data-testid="stSidebar"] { display: none !important; }
            header[data-testid="stHeader"] { display: none !important; }
            .stApp { margin-top: -50px !important; }
            button { display: none !important; }
            div[data-testid="stExpander"] { display: none !important; }
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("### 📊 Panel de Control: Siniestralidad y Desempeño")
    
    ano_actual = datetime.now().year
    mes_actual = datetime.now().month
    lista_meses_completos = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    lista_meses_permitidos = lista_meses_completos[:mes_actual]

    # ==========================================
    # 1. BARRA DE FILTROS SUPERIOR
    # ==========================================
    with st.container(border=True):
        f1, f2, f3, f4, f5 = st.columns(5)
        filtro_ano = f1.selectbox("Año", [2026, 2027, 2028])
        filtro_mes = f2.selectbox("Mes de Análisis", ["Año Completo"] + lista_meses_permitidos, index=0)
        filtro_sexo = f3.selectbox("Sexo", ["Ambos", "MASCULINO", "FEMENINO"]) 
        filtro_sucursal = f4.selectbox("Sucursal", ["Todas", "ECOM VALDIVIA", "MCT VALDIVIA", "PLC VALDIVIA"])
        
        c_btn1, c_btn2 = f5.columns(2)
        c_btn1.button("👁️ Actualizar Datos", use_container_width=True)
        c_btn2.button("Limpiar Filtros", use_container_width=True)

    # ==========================================
    # 2. FUNCIONES DE LIMPIEZA EXTREMA (REGEX)
    # ==========================================
    def coincidencia_sucursal(valor_db, filtro):
        v = str(valor_db).upper().strip()
        f = str(filtro).upper().strip()
        if f == "TODAS": return True
        if "ECOM" in f and ("ECOM" in v or "ELECTROCOM" in v): return True
        if "PLC" in f and ("PLC" in v or "PLACA CENTRO" in v): return True
        if "MCT" in f and "MCT" in v: return True
        return f == v

    def coincidencia_sexo(valor_db, filtro):
        v = str(valor_db).upper().strip()
        f = str(filtro).upper().strip()
        if f == "AMBOS": return True
        if f == "MASCULINO" and ("MASC" in v or v == "M"): return True
        if f == "FEMENINO" and ("FEM" in v or v == "F"): return True
        return f == v

    def parsear_fecha_invencible(val):
        """ Extrae solo la fecha pura, ignorando horas pegadas como 04-02-202600:00 """
        if pd.isna(val) or str(val).strip() in ["", "NAN", "NAT"]: 
            return pd.NaT
        val_str = str(val).strip()
        
        # Si es un número de serie de Excel
        if val_str.replace('.', '', 1).isdigit() and float(val_str) > 10000:
            return pd.to_datetime('1899-12-30') + pd.to_timedelta(float(val_str), unit='D')
            
        # Láser Regex: Busca un patrón de fecha DD-MM-YYYY o YYYY-MM-DD
        match = re.search(r'(\d{2,4}[-/]\d{1,2}[-/]\d{2,4})', val_str)
        if match:
            clean_date = match.group(1)
            return pd.to_datetime(clean_date, dayfirst=True, errors='coerce')
            
        return pd.to_datetime(val_str, dayfirst=True, errors='coerce')

    def encontrar_columna(df, opciones):
        # Búsqueda exacta
        for op in opciones:
            for col in df.columns:
                if str(col).strip().upper() == op: return col
        # Búsqueda parcial si falla la exacta
        for op in opciones:
            for col in df.columns:
                if op in str(col).strip().upper(): return col
        return None

    # ==========================================
    # 3. CARGA DE NÓMINA MAESTRA
    # ==========================================
    df_personal_bruto = obtener_datos_nube("personal")
    df_personal = df_personal_bruto.copy() if not df_personal_bruto.empty else pd.DataFrame()
    total_trabajadores, hombres, mujeres = 0, 0, 0
    
    if not df_personal.empty:
        df_personal.columns = [str(c).strip().upper() for c in df_personal.columns]
        
        if 'ESTADO' in df_personal.columns:
            df_personal = df_personal[df_personal['ESTADO'].astype(str).str.upper() != 'FINIQUITADO']
        if 'SUCURSAL' in df_personal.columns:
            df_personal = df_personal[~df_personal['SUCURSAL'].astype(str).str.upper().str.contains('PRUEBAS')]
            df_personal = df_personal[df_personal['SUCURSAL'].apply(lambda x: coincidencia_sucursal(x, filtro_sucursal))]
            
        if 'SEXO' in df_personal.columns:
            hombres = len(df_personal[df_personal['SEXO'].apply(lambda x: coincidencia_sexo(x, "MASCULINO"))])
            mujeres = len(df_personal[df_personal['SEXO'].apply(lambda x: coincidencia_sexo(x, "FEMENINO"))])
            df_personal = df_personal[df_personal['SEXO'].apply(lambda x: coincidencia_sexo(x, filtro_sexo))]

        total_trabajadores = len(df_personal)

    # ==========================================
    # 4. CARGA DE ACCIDENTES (MOTOR INTELIGENTE)
    # ==========================================
    df_acc_completo = obtener_datos_nube("accidentes")
    df_acc = df_acc_completo.copy() if not df_acc_completo.empty else pd.DataFrame()
    
    if not df_acc.empty:
        df_acc['IDX_ORIGINAL'] = df_acc.index 
        
        # Encontrar columnas clave usando Inteligencia
        col_fecha = encontrar_columna(df_acc, ['FECHA ACCIDENTE', 'FECHA SINIESTRO', 'FECHA'])
        col_trab = encontrar_columna(df_acc, ['TRABAJADOR', 'NOMBRE', 'AFECTADO']) 
        col_tipo = encontrar_columna(df_acc, ['TIPO ACCIDENTE', 'CLASIFICACION', 'CALIFICACION', 'TIPO'])
        col_dias = encontrar_columna(df_acc, ['DIAS PERDIDOS', 'DÍAS REPOSO', 'DIAS'])
        col_suc = encontrar_columna(df_acc, ['SUCURSAL', 'CENTRO', 'FAENA'])
        col_sex = encontrar_columna(df_acc, ['SEXO', 'GENERO'])

        # Normalizar Datos en columnas seguras
        df_acc['FECHA_NORM'] = df_acc[col_fecha] if col_fecha else pd.NaT
        df_acc['TRABAJADOR_NORM'] = df_acc[col_trab].astype(str) if col_trab else "DESCONOCIDO"
        df_acc['TIPO_NORM'] = df_acc[col_tipo].astype(str).upper() if col_tipo else "ACCIDENTE"
        df_acc['DIAS_NORM'] = pd.to_numeric(df_acc[col_dias], errors='coerce').fillna(0) if col_dias else 0
        df_acc['SUC_NORM'] = df_acc[col_suc].astype(str).upper() if col_suc else "S/I"
        df_acc['SEX_NORM'] = df_acc[col_sex].astype(str).upper() if col_sex else "S/I"

        # Eliminar Rechazados o Inhabilitados buscando en cualquier columna
        df_acc = df_acc[~df_acc.apply(lambda row: row.astype(str).str.upper().str.contains('RECHAZADO|INHABILITADO').any(), axis=1)]

        # Limpiar Fecha Invencible
        df_acc['FECHA_DT'] = df_acc['FECHA_NORM'].apply(parsear_fecha_invencible)
        
        # Filtrar Año 2026 (y guardamos los que no tengan fecha para diagnosticarlos abajo)
        df_acc = df_acc[(df_acc['FECHA_DT'].dt.year == filtro_ano) | (df_acc['FECHA_DT'].isna())]
        
        meses_map = {i+1: m for i, m in enumerate(lista_meses_completos)}
        df_acc['MES_TXT'] = df_acc['FECHA_DT'].dt.month.map(meses_map).fillna("S/F")

        # Cruce para robar Sucursal y Sexo de la base si no vienen en la mutual
        def forzar_cruce(row):
            n_acc = str(row['TRABAJADOR_NORM']).upper().replace(',', '').replace('.', '').strip()
            if not df_personal_bruto.empty and 'NOMBRE' in df_personal_bruto.columns:
                for _, p_row in df_personal_bruto.iterrows():
                    n_pers = str(p_row.get('NOMBRE', '')).upper().replace(',', '').replace('.', '').strip()
                    if n_acc in n_pers or n_pers in n_acc:
                        return pd.Series([str(p_row.get('SUCURSAL', 'S/I')), str(p_row.get('SEXO', 'S/I'))])
            return pd.Series([row['SUC_NORM'], row['SEX_NORM']])

        df_acc[['SUC_CRUZADA', 'SEX_CRUZADO']] = df_acc.apply(forzar_cruce, axis=1)
        df_acc['SUCURSAL_FINAL'] = df_acc.apply(lambda r: r['SUC_CRUZADA'] if r['SUC_NORM'] in ['NAN', 'S/I', 'NONE', ''] else r['SUC_NORM'], axis=1)
        df_acc['SEXO_FINAL'] = df_acc.apply(lambda r: r['SEX_CRUZADO'] if r['SEX_NORM'] in ['NAN', 'S/I', 'NONE', ''] else r['SEX_NORM'], axis=1)

        # Filtros Maestros Finales
        df_acc = df_acc[df_acc['SUCURSAL_FINAL'].apply(lambda x: coincidencia_sucursal(x, filtro_sucursal))]
        df_acc = df_acc[df_acc['SEXO_FINAL'].apply(lambda x: coincidencia_sexo(x, filtro_sexo))]

    # ==========================================
    # 5. TARJETAS DE RESUMEN
    # ==========================================
    t1, t2, t3 = st.columns(3)
    t1.info(f"**DOTACIÓN ACTUAL FILTRADA**\n### {total_trabajadores}")
    t2.success(f"**HOMBRES (En Filtro)**\n### {hombres if filtro_sexo in ['Ambos', 'MASCULINO'] else 0}")
    t3.warning(f"**MUJERES (En Filtro)**\n### {mujeres if filtro_sexo in ['Ambos', 'FEMENINO'] else 0}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # 6. AJUSTE MANUAL DE DOTACIÓN
    # ==========================================
    with st.expander("⚙️ Editar Promedio de Trabajadores por Mes"):
        st.info("Ingresa los promedios manuales aquí.")
        try:
            df_cfg = obtener_datos_nube("config_mensual")
            if df_cfg is None or df_cfg.empty: df_cfg = pd.DataFrame(columns=["AÑO", "MES", "SUCURSAL", "TRABAJADORES"])
        except: df_cfg = pd.DataFrame(columns=["AÑO", "MES", "SUCURSAL", "TRABAJADORES"])
            
        df_cfg.columns = [str(c).strip().upper() for c in df_cfg.columns]
        df_cfg_editado = st.data_editor(
            df_cfg, num_rows="dynamic", use_container_width=True,
            column_config={
                "AÑO": st.column_config.NumberColumn("Año", format="%d"),
                "MES": st.column_config.SelectboxColumn("Mes", options=lista_meses_completos),
                "SUCURSAL": st.column_config.SelectboxColumn("Sucursal", options=["Todas", "ECOM VALDIVIA", "MCT VALDIVIA", "PLC VALDIVIA"]),
                "TRABAJADORES": st.column_config.NumberColumn("N° Promedio", min_value=0, step=1)
            }, key="editor_config"
        )
        if st.button("💾 Guardar Ajustes Mensuales", type="primary"):
            if actualizar_hoja_completa(df_cfg_editado, "config_mensual"):
                st.success("✅ Historial actualizado.")
                st.rerun()

    # ==========================================
    # 7. TABLA Y CÁLCULOS MENSUALES
    # ==========================================
    filas_tabla = []
    meses_transcurridos = mes_actual if filtro_ano == ano_actual else 12

    for i, mes in enumerate(lista_meses_completos):
        idx_mes = i + 1
        x_trab = total_trabajadores 
        
        if not df_cfg_editado.empty:
            mask = ((df_cfg_editado['AÑO'].astype(str) == str(filtro_ano)) & (df_cfg_editado['MES'].astype(str).str.upper() == mes.upper()) & (df_cfg_editado['SUCURSAL'].astype(str).str.upper() == filtro_sucursal.upper()))
            match = df_cfg_editado[mask]
            if not match.empty:
                try: x_trab = int(pd.to_numeric(match.iloc[-1]['TRABAJADORES'], errors='coerce'))
                except: pass

        x_trab = 0 if idx_mes > meses_transcurridos else x_trab
        hh = 0 if idx_mes > meses_transcurridos else calcular_hh_estimadas(x_trab, mes)

        acc_ctp, acc_stp, acc_tray, dp = 0, 0, 0, 0
        
        if not df_acc.empty:
            datos_mes = df_acc[df_acc['MES_TXT'] == mes]
            for _, acc_row in datos_mes.iterrows():
                tipo_str = str(acc_row['TIPO_NORM']).upper()
                dias_perdidos = float(acc_row['DIAS_NORM'])
                
                # Clasificación Quirúrgica
                if "TRAYECTO" in tipo_str:
                    acc_tray += 1
                    dp += dias_perdidos
                elif "ENFERMEDAD" in tipo_str or "EP" in tipo_str:
                    pass # Enfermedades van por otro carril, no suman a Tasa CTP
                else:
                    if dias_perdidos > 0 or "CTP" in tipo_str or "CON TIEMPO" in tipo_str:
                        acc_ctp += 1
                    elif dias_perdidos == 0 or "STP" in tipo_str or "SIN TIEMPO" in tipo_str or "INCIDENTE" in tipo_str:
                        acc_stp += 1
                    else:
                        acc_ctp += 1 
                    dp += dias_perdidos

        tasa_acc = (acc_ctp / x_trab * 100) if x_trab > 0 else 0
        ind_frec = (acc_ctp / hh * 1000000) if hh > 0 else 0
        ind_grav = (dp / hh * 1000) if hh > 0 else 0

        filas_tabla.append({
            "MES": mes, "X TRAB": x_trab, "ACC CTP": acc_ctp, "ACC STP": acc_stp, "ACC TRAY": acc_tray,
            "DP": int(dp), "TASA ACC": round(tasa_acc, 2), "IND FRECI": round(ind_frec, 2), "IND GRAV": round(ind_grav, 2), "HH_REAL": hh 
        })

    df_tabla = pd.DataFrame(filas_tabla)

    # ==========================================
    # 8. VISUALIZACIÓN DE TABLA Y RESUMEN
    # ==========================================
    col_tabla, col_analisis = st.columns([6, 4]) 
    total_ctp, total_dp, total_hh = df_tabla["ACC CTP"].sum(), df_tabla["DP"].sum(), df_tabla["HH_REAL"].sum()
    promedio_trab_anual = df_tabla[df_tabla["X TRAB"] > 0]["X TRAB"].mean() if not df_tabla[df_tabla["X TRAB"] > 0].empty else 0

    with col_tabla:
        with st.container(border=True):
            st.markdown("##### Detalle mensual")
            st.dataframe(df_tabla.drop(columns=["HH_REAL"]), hide_index=True, use_container_width=True)
            st.markdown("**Totales Acumulados**")
            c_t1, c_t2, c_t3 = st.columns(3)
            c_t1.metric("Total ACC CTP", total_ctp)
            c_t2.metric("Total Días Perdidos", total_dp)
            c_t3.metric("I.F. Acumulado", round((total_ctp/total_hh*1000000) if total_hh > 0 else 0, 2))

    with col_analisis:
        with st.container(border=True):
            st.markdown("##### Resumen comparativo")
            c_comp1, c_comp2 = st.columns(2)
            c_comp1.selectbox("Año a comparar", [ano_actual-1], disabled=True)
            c_comp2.selectbox("Mes a comparar", [filtro_mes], disabled=True)
            
            rc1, rc2 = st.columns(2)
            rc1.info(f"**ACT (ACC CTP)**\n\n{total_ctp} / --")
            rc1.success(f"**DP (Días P.)**\n\n{total_dp} / --")
            rc2.warning(f"**TASA ACC**\n\n{round((total_ctp/promedio_trab_anual*100) if promedio_trab_anual > 0 else 0,2)}% / --")
            rc2.error(f"**IND FRECI**\n\n{round((total_ctp/total_hh*1000000) if total_hh > 0 else 0,2)} / --")

    # ==========================================
    # 9. EXPEDIENTES Y MODO DE DEPURACIÓN
    # ==========================================
    st.markdown("---")
    st.markdown("### 📁 Expedientes de Accidentes Registrados")
    
    if not df_acc.empty:
        st.info("💡 Despliega cada accidente para adjuntar o descargar su **DIAT** y su **Investigación**.")
        if 'URL_DIAT' not in df_acc_completo.columns: df_acc_completo['URL_DIAT'] = ""
        if 'URL_INV' not in df_acc_completo.columns: df_acc_completo['URL_INV'] = ""

        for _, row in df_acc.iterrows():
            idx = row['IDX_ORIGINAL']
            trabajador = row['TRABAJADOR_NORM']
            fecha_str = row['FECHA_DT'].strftime('%d-%m-%Y') if pd.notna(row['FECHA_DT']) else "S/F"
            tipo = row['TIPO_NORM']
            suc_final = row['SUCURSAL_FINAL']
            
            with st.expander(f"🤕 {fecha_str} | {trabajador} | {suc_final} | Días: {row['DIAS_NORM']}"):
                c1, c2 = st.columns(2)
                
                url_diat = str(df_acc_completo.at[idx, 'URL_DIAT']) if 'URL_DIAT' in df_acc_completo.columns else ""
                if pd.isna(url_diat) or url_diat == "" or url_diat == "nan":
                    archivo_diat = c1.file_uploader("Subir DIAT Mutual (PDF)", type=['pdf'], key=f"diat_{idx}")
                    if archivo_diat:
                        with st.spinner("Subiendo..."):
                            nombre_temp = f"DIAT_{trabajador.replace(' ', '_')}.pdf"
                            with open(nombre_temp, "wb") as f: f.write(archivo_diat.getbuffer())
                            url = subir_pdf_drive(nombre_temp, nombre_temp)
                            if url:
                                df_acc_completo.at[idx, 'URL_DIAT'] = url
                                actualizar_hoja_completa(df_acc_completo, "accidentes")
                                os.remove(nombre_temp)
                                st.rerun()
                else:
                    c1.success("✅ DIAT Registrada"); c1.markdown(f"[📥 Descargar DIAT]({url_diat})")

                url_inv = str(df_acc_completo.at[idx, 'URL_INV']) if 'URL_INV' in df_acc_completo.columns else ""
                if pd.isna(url_inv) or url_inv == "" or url_inv == "nan":
                    archivo_inv = c2.file_uploader("Subir Investigación (PDF)", type=['pdf'], key=f"inv_{idx}")
                    if archivo_inv:
                        with st.spinner("Subiendo..."):
                            nombre_temp = f"INV_{trabajador.replace(' ', '_')}.pdf"
                            with open(nombre_temp, "wb") as f: f.write(archivo_inv.getbuffer())
                            url = subir_pdf_drive(nombre_temp, nombre_temp)
                            if url:
                                df_acc_completo.at[idx, 'URL_INV'] = url
                                actualizar_hoja_completa(df_acc_completo, "accidentes")
                                os.remove(nombre_temp)
                                st.rerun()
                else:
                    c2.success("✅ Investigación Registrada"); c2.markdown(f"[📥 Descargar]({url_inv})")
    else:
        st.warning("⚠️ No hay accidentes procesados para el filtro actual.")

    # ==========================================
    # 10. BOTONES DE ACCIÓN (EXPORTAR PDF)
    # ==========================================
    st.markdown("---")
    b1, b2, b3 = st.columns([2, 2, 6])
    
    if b1.button("📄 Imprimir / PDF Oficial", type="primary", use_container_width=True):
        components.html("<script>window.parent.print();</script>", height=0)
        
    if b2.button("Cerrar Panel", use_container_width=True):
        st.session_state['opcion_actual'] = "Inicio"
        st.rerun()
