import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
import os
from utils import obtener_datos_nube, calcular_hh_estimadas, actualizar_hoja_completa, subir_pdf_drive

def mostrar_modulo_estadisticas():
    # --- CSS MÁGICO PARA IMPRESIÓN LIMPIA DE PDF ---
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
        
        st.markdown("""<style>
            .bot-ver { background-color: #fff3e0; color: #e65100; border: 1px solid #ffb74d; }
            .bot-limpiar { background-color: #e3f2fd; color: #1565c0; border: 1px solid #64b5f6; }
        </style>""", unsafe_allow_html=True)
        
        c_btn1, c_btn2 = f5.columns(2)
        c_btn1.button("👁️ Actualizar Datos", use_container_width=True)
        c_btn2.button("Limpiar Filtros", use_container_width=True)

    # ==========================================
    # 2. FUNCIONES DE TRADUCCIÓN FLEXIBLE
    # ==========================================
    def coincidencia_sucursal(valor_db, filtro):
        v = str(valor_db).upper()
        f = str(filtro).upper()
        if f == "TODAS": return True
        if "ECOM" in f and ("ECOM" in v or "ELECTROCOM" in v): return True
        if "PLC" in f and ("PLC" in v or "PLACA CENTRO" in v): return True
        if "MCT" in f and "MCT" in v: return True
        return f == v

    def coincidencia_sexo(valor_db, filtro):
        v = str(valor_db).upper()
        f = str(filtro).upper()
        if f == "AMBOS": return True
        if f == "MASCULINO" and ("MASC" in v or v == "M"): return True
        if f == "FEMENINO" and ("FEM" in v or v == "F"): return True
        return f == v

    # Traductor robusto de fechas (arregla las fechas rotas de Excel)
    def parsear_fecha_robusta(val):
        try:
            if str(val).isdigit() or (isinstance(val, float) and val > 10000):
                return pd.to_datetime('1899-12-30') + pd.to_timedelta(float(val), 'D')
            return pd.to_datetime(val, dayfirst=True)
        except:
            return pd.NaT

    # ==========================================
    # 3. CARGA Y FILTRADO CRUZADO
    # ==========================================
    df_personal = obtener_datos_nube("personal")
    total_trabajadores, hombres, mujeres = 0, 0, 0
    nombres_masculinos = []
    nombres_femeninos = []
    
    if not df_personal.empty:
        df_personal.columns = [str(c).strip().upper() for c in df_personal.columns]
        
        if 'ESTADO' in df_personal.columns:
            df_personal = df_personal[df_personal['ESTADO'].astype(str).str.upper() != 'FINIQUITADO']
        if 'SUCURSAL' in df_personal.columns:
            df_personal = df_personal[~df_personal['SUCURSAL'].astype(str).str.upper().str.contains('PRUEBAS')]
            df_personal = df_personal[df_personal['SUCURSAL'].apply(lambda x: coincidencia_sucursal(x, filtro_sucursal))]
            
        if 'SEXO' in df_personal.columns and 'NOMBRE' in df_personal.columns:
            hombres_df = df_personal[df_personal['SEXO'].apply(lambda x: coincidencia_sexo(x, "MASCULINO"))]
            mujeres_df = df_personal[df_personal['SEXO'].apply(lambda x: coincidencia_sexo(x, "FEMENINO"))]
            
            hombres = len(hombres_df)
            mujeres = len(mujeres_df)
            nombres_masculinos = hombres_df['NOMBRE'].astype(str).str.upper().tolist()
            nombres_femeninos = mujeres_df['NOMBRE'].astype(str).str.upper().tolist()
            
            df_personal = df_personal[df_personal['SEXO'].apply(lambda x: coincidencia_sexo(x, filtro_sexo))]

        total_trabajadores = len(df_personal)

    # --- PROCESAR ACCIDENTES (CON TRADUCTOR MUTUAL) ---
    df_acc_completo = obtener_datos_nube("accidentes")
    df_acc = df_acc_completo.copy() if not df_acc_completo.empty else pd.DataFrame()
    
    if not df_acc.empty:
        df_acc.columns = [str(c).strip().upper() for c in df_acc.columns]
        
        # Traductor de Columnas Mutual
        mapa_columnas = {
            'FECHA ACCIDENTE': 'FECHA', 'FECHA SINIESTRO': 'FECHA',
            'NOMBRE TRABAJADOR': 'TRABAJADOR', 'NOMBRES': 'TRABAJADOR',
            'CLASIFICACION': 'TIPO', 'TIPO ACCIDENTE': 'TIPO',
            'DIAS PERDIDOS': 'DIAS_PERDIDOS', 'DÍAS REPOSO': 'DIAS_PERDIDOS'
        }
        df_acc = df_acc.rename(columns=mapa_columnas)
        
        if 'ESTADO_REGISTRO' in df_acc.columns:
            df_acc = df_acc[df_acc['ESTADO_REGISTRO'].astype(str).str.upper() != 'INHABILITADO']

        if 'FECHA' in df_acc.columns:
            df_acc['FECHA_LIMPIA'] = df_acc['FECHA'].apply(parsear_fecha_robusta)
            df_acc = df_acc[df_acc['FECHA_LIMPIA'].dt.year == filtro_ano] 
            meses_map = {i+1: m for i, m in enumerate(lista_meses_completos)}
            df_acc['MES_TXT'] = df_acc['FECHA_LIMPIA'].dt.month.map(meses_map)

        if 'SUCURSAL' in df_acc.columns:
            df_acc = df_acc[df_acc['SUCURSAL'].apply(lambda x: coincidencia_sucursal(x, filtro_sucursal))]

        # Filtro de Sexo Suave (Solo excluye si estamos 100% seguros que no corresponde)
        if filtro_sexo != "Ambos" and 'TRABAJADOR' in df_acc.columns:
            def coincide_sexo_accidente(nombre_acc):
                n_acc = str(nombre_acc).upper().replace(',', '')
                lista_buscar = nombres_masculinos if filtro_sexo == "MASCULINO" else nombres_femeninos
                for n_pers in lista_buscar:
                    partes_acc = set(n_acc.split())
                    partes_pers = set(n_pers.replace(',', '').split())
                    # Si al menos 2 palabras coinciden (ej. Apellido y Nombre), es la misma persona
                    if len(partes_acc.intersection(partes_pers)) >= 2: return True
                return False
            
            df_acc = df_acc[df_acc['TRABAJADOR'].apply(coincide_sexo_accidente)]

    # ==========================================
    # 4. TARJETAS DE RESUMEN
    # ==========================================
    t1, t2, t3 = st.columns(3)
    t1.info(f"**DOTACIÓN ACTUAL FILTRADA**\n### {total_trabajadores}")
    t2.success(f"**HOMBRES (En Filtro)**\n### {hombres if filtro_sexo in ['Ambos', 'MASCULINO'] else 0}")
    t3.warning(f"**MUJERES (En Filtro)**\n### {mujeres if filtro_sexo in ['Ambos', 'FEMENINO'] else 0}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # 5. AJUSTE MANUAL DE DOTACIÓN
    # ==========================================
    with st.expander("⚙️ Editar Promedio de Trabajadores por Mes"):
        st.info("Ingresa los promedios manuales aquí. El sistema dará prioridad a estos números para el cálculo de tasas.")
        try:
            df_cfg = obtener_datos_nube("config_mensual")
            if df_cfg is None or df_cfg.empty:
                df_cfg = pd.DataFrame(columns=["AÑO", "MES", "SUCURSAL", "TRABAJADORES"])
        except:
            df_cfg = pd.DataFrame(columns=["AÑO", "MES", "SUCURSAL", "TRABAJADORES"])
            
        df_cfg.columns = [str(c).strip().upper() for c in df_cfg.columns]
        df_cfg_editado = st.data_editor(
            df_cfg, num_rows="dynamic", use_container_width=True,
            column_config={
                "AÑO": st.column_config.NumberColumn("Año", format="%d"),
                "MES": st.column_config.SelectboxColumn("Mes", options=lista_meses_completos),
                "SUCURSAL": st.column_config.SelectboxColumn("Sucursal", options=["Todas", "ECOM VALDIVIA", "MCT VALDIVIA", "PLC VALDIVIA"]),
                "TRABAJADORES": st.column_config.NumberColumn("N° Promedio Trabajadores", min_value=0, step=1)
            }, key="editor_config"
        )
        if st.button("💾 Guardar Ajustes Mensuales", type="primary"):
            if actualizar_hoja_completa(df_cfg_editado, "config_mensual"):
                st.success("✅ Historial actualizado.")
                st.rerun()

    # ==========================================
    # 6. TABLA Y CÁLCULOS MENSUALES
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
        if not df_acc.empty and 'MES_TXT' in df_acc.columns:
            datos_mes = df_acc[df_acc['MES_TXT'] == mes]
            
            if 'TIPO' in datos_mes.columns:
                acc_ctp = len(datos_mes[datos_mes['TIPO'].astype(str).str.contains("CTP|CON TIEMPO|REPOSO|TRABAJO", case=False, na=False)])
                acc_stp = len(datos_mes[datos_mes['TIPO'].astype(str).str.contains("STP|INCIDENTE|SIN TIEMPO", case=False, na=False)])
                acc_tray = len(datos_mes[datos_mes['TIPO'].astype(str).str.contains("TRAYECTO", case=False, na=False)])
            
            for col in datos_mes.columns:
                if 'DIAS' in col or 'DÍAS' in col:
                    dp += pd.to_numeric(datos_mes[col], errors='coerce').fillna(0).sum()

        tasa_acc = (acc_ctp / x_trab * 100) if x_trab > 0 else 0
        ind_frec = (acc_ctp / hh * 1000000) if hh > 0 else 0
        ind_grav = (dp / hh * 1000) if hh > 0 else 0

        filas_tabla.append({
            "MES": mes, "X TRAB": x_trab, "ACC CTP": acc_ctp, "ACC STP": acc_stp, "ACC TRAY": acc_tray,
            "DP": int(dp), "TASA ACC": round(tasa_acc, 2), "IND FRECI": round(ind_frec, 2), "IND GRAV": round(ind_grav, 2), "HH_REAL": hh 
        })

    df_tabla = pd.DataFrame(filas_tabla)

    # ==========================================
    # 7. VISUALIZACIÓN DE TABLA Y RESUMEN
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
    # 8. EXPEDIENTES Y CARGA DE DIAT / INVESTIGACIÓN
    # ==========================================
    st.markdown("---")
    st.markdown("### 📁 Expedientes de Accidentes Registrados")
    st.info("💡 Despliega cada accidente para adjuntar o descargar su **DIAT** y su **Investigación**.")

    if not df_acc.empty:
        # Validamos que existan las columnas de respaldo, si no, las creamos al vuelo
        if 'URL_DIAT' not in df_acc_completo.columns: df_acc_completo['URL_DIAT'] = ""
        if 'URL_INV' not in df_acc_completo.columns: df_acc_completo['URL_INV'] = ""

        for idx, row in df_acc.iterrows():
            trabajador = row.get('TRABAJADOR', 'Desconocido')
            fecha_str = row['FECHA_LIMPIA'].strftime('%d-%m-%Y') if pd.notna(row.get('FECHA_LIMPIA')) else "S/F"
            tipo = row.get('TIPO', 'S/I')
            
            with st.expander(f"🤕 {fecha_str} | {trabajador} | {tipo}"):
                c1, c2 = st.columns(2)
                
                # --- GESTOR DE DIAT ---
                url_diat = df_acc_completo.at[idx, 'URL_DIAT']
                if pd.isna(url_diat) or url_diat == "":
                    archivo_diat = c1.file_uploader("Subir DIAT Mutual (PDF)", type=['pdf'], key=f"diat_{idx}")
                    if archivo_diat:
                        with st.spinner("Subiendo DIAT..."):
                            nombre_temp = f"DIAT_{trabajador.replace(' ', '_')}.pdf"
                            with open(nombre_temp, "wb") as f: f.write(archivo_diat.getbuffer())
                            url = subir_pdf_drive(nombre_temp, nombre_temp)
                            if url:
                                df_acc_completo.at[idx, 'URL_DIAT'] = url
                                actualizar_hoja_completa(df_acc_completo, "accidentes")
                                os.remove(nombre_temp)
                                st.rerun()
                else:
                    c1.success("✅ DIAT Registrada")
                    c1.markdown(f"[📥 Ver / Descargar DIAT]({url_diat})")

                # --- GESTOR DE INVESTIGACIÓN INTERNA ---
                url_inv = df_acc_completo.at[idx, 'URL_INV']
                if pd.isna(url_inv) or url_inv == "":
                    archivo_inv = c2.file_uploader("Subir Investigación (PDF)", type=['pdf'], key=f"inv_{idx}")
                    if archivo_inv:
                        with st.spinner("Subiendo Investigación..."):
                            nombre_temp = f"INV_{trabajador.replace(' ', '_')}.pdf"
                            with open(nombre_temp, "wb") as f: f.write(archivo_inv.getbuffer())
                            url = subir_pdf_drive(nombre_temp, nombre_temp)
                            if url:
                                df_acc_completo.at[idx, 'URL_INV'] = url
                                actualizar_hoja_completa(df_acc_completo, "accidentes")
                                os.remove(nombre_temp)
                                st.rerun()
                else:
                    c2.success("✅ Investigación Registrada")
                    c2.markdown(f"[📥 Ver / Descargar Investigación]({url_inv})")
    else:
        st.success("✅ No hay accidentes registrados para los filtros seleccionados.")

    # ==========================================
    # 9. BOTONES DE ACCIÓN (EXPORTAR PDF)
    # ==========================================
    st.markdown("---")
    b1, b2, b3 = st.columns([2, 2, 6])
    
    if b1.button("📄 Imprimir / PDF Oficial", type="primary", use_container_width=True):
        components.html("<script>window.parent.print();</script>", height=0)
        
    if b2.button("Cerrar Panel", use_container_width=True):
        st.session_state['opcion_actual'] = "Inicio"
        st.rerun()
