import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
from utils import obtener_datos_nube, calcular_hh_estimadas, actualizar_hoja_completa

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
    
    ano_actual = datetime.now().year # 2026
    mes_actual = datetime.now().month
    lista_meses_completos = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    # Filtro Dinámico de Meses: Solo muestra hasta el mes actual
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

    # ==========================================
    # 3. CARGA Y FILTRADO CRUZADO
    # ==========================================
    df_personal = obtener_datos_nube("personal")
    total_trabajadores, hombres, mujeres = 0, 0, 0
    
    if not df_personal.empty:
        df_personal.columns = [str(c).strip().upper() for c in df_personal.columns]
        
        # Excluir inactivos y sucursal de pruebas
        if 'ESTADO' in df_personal.columns:
            df_personal = df_personal[df_personal['ESTADO'].astype(str).str.upper() != 'FINIQUITADO']
        if 'SUCURSAL' in df_personal.columns:
            df_personal = df_personal[~df_personal['SUCURSAL'].astype(str).str.upper().str.contains('PRUEBAS')]

        # Filtro Sucursal
        if 'SUCURSAL' in df_personal.columns:
            df_personal = df_personal[df_personal['SUCURSAL'].apply(lambda x: coincidencia_sucursal(x, filtro_sucursal))]
            
        # Conteo de Sexo Total en esa sucursal
        if 'SEXO' in df_personal.columns:
            hombres = len(df_personal[df_personal['SEXO'].apply(lambda x: coincidencia_sexo(x, "MASCULINO"))])
            mujeres = len(df_personal[df_personal['SEXO'].apply(lambda x: coincidencia_sexo(x, "FEMENINO"))])
            
            # Filtro Sexo
            df_personal = df_personal[df_personal['SEXO'].apply(lambda x: coincidencia_sexo(x, filtro_sexo))]

        total_trabajadores = len(df_personal)

    # Procesar Accidentes
    df_acc = obtener_datos_nube("accidentes")
    if not df_acc.empty:
        df_acc.columns = [str(c).strip().upper() for c in df_acc.columns]
        
        if 'ESTADO_REGISTRO' in df_acc.columns:
            df_acc = df_acc[df_acc['ESTADO_REGISTRO'].astype(str).str.upper() != 'INHABILITADO']

        if 'FECHA' in df_acc.columns:
            df_acc['FECHA'] = pd.to_datetime(df_acc['FECHA'], errors='coerce')
            df_acc = df_acc[df_acc['FECHA'].dt.year == filtro_ano] 
            meses_map = {i+1: m for i, m in enumerate(lista_meses_completos)}
            df_acc['MES_TXT'] = df_acc['FECHA'].dt.month.map(meses_map)

        if 'SUCURSAL' in df_acc.columns:
            df_acc = df_acc[df_acc['SUCURSAL'].apply(lambda x: coincidencia_sucursal(x, filtro_sucursal))]

        if filtro_sexo != "Ambos" and not df_personal.empty and 'NOMBRE' in df_personal.columns:
            nombres_validos = df_personal['NOMBRE'].str.upper().tolist()
            if 'TRABAJADOR' in df_acc.columns:
                df_acc = df_acc[df_acc['TRABAJADOR'].astype(str).str.upper().isin(nombres_validos)]

    # ==========================================
    # 4. TARJETAS DE RESUMEN
    # ==========================================
    t1, t2, t3 = st.columns(3)
    with t1:
        st.info(f"**DOTACIÓN ACTUAL FILTRADA**\n### {total_trabajadores}")
    with t2:
        st.success(f"**HOMBRES (En Filtro)**\n### {hombres if filtro_sexo in ['Ambos', 'MASCULINO'] else 0}")
    with t3:
        st.warning(f"**MUJERES (En Filtro)**\n### {mujeres if filtro_sexo in ['Ambos', 'FEMENINO'] else 0}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # 5. AJUSTE MANUAL DE DOTACIÓN MENSUAL (HISTORIAL)
    # ==========================================
    st.markdown("### ⚙️ Ajuste de Historial de Dotación")
    with st.expander("📝 Editar Promedio de Trabajadores por Mes"):
        st.info("Ingresa los promedios manuales aquí. El sistema dará prioridad a estos números para el cálculo de tasas del mes correspondiente.")
        
        # Intentamos obtener la configuración, si no existe o hay error, creamos un DataFrame vacío
        try:
            df_cfg = obtener_datos_nube("config_mensual")
            if df_cfg is None or df_cfg.empty:
                df_cfg = pd.DataFrame(columns=["AÑO", "MES", "SUCURSAL", "TRABAJADORES"])
        except:
            df_cfg = pd.DataFrame(columns=["AÑO", "MES", "SUCURSAL", "TRABAJADORES"])
            
        df_cfg.columns = [str(c).strip().upper() for c in df_cfg.columns]
        
        df_cfg_editado = st.data_editor(
            df_cfg,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "AÑO": st.column_config.NumberColumn("Año", format="%d"),
                "MES": st.column_config.SelectboxColumn("Mes", options=lista_meses_completos),
                "SUCURSAL": st.column_config.SelectboxColumn("Sucursal", options=["Todas", "ECOM VALDIVIA", "MCT VALDIVIA", "PLC VALDIVIA"]),
                "TRABAJADORES": st.column_config.NumberColumn("N° Promedio Trabajadores", min_value=0, step=1)
            },
            key="editor_config_mensual"
        )
        
        if st.button("💾 Guardar Ajustes Mensuales", type="primary"):
            if actualizar_hoja_completa(df_cfg_editado, "config_mensual"):
                st.success("✅ Historial actualizado. Recargando panel...")
                st.rerun()

    # ==========================================
    # 6. TABLA Y CÁLCULOS MENSUALES
    # ==========================================
    filas_tabla = []
    meses_transcurridos = mes_actual if filtro_ano == ano_actual else 12

    for i, mes in enumerate(lista_meses_completos):
        idx_mes = i + 1
        x_trab = total_trabajadores # Por defecto usa la foto actual
        
        # BÚSQUEDA DE HISTORIAL: Si escribiste un promedio en la tabla de arriba, lo usa.
        if not df_cfg_editado.empty:
            mask = (
                (df_cfg_editado['AÑO'].astype(str) == str(filtro_ano)) &
                (df_cfg_editado['MES'].astype(str).str.upper() == mes.upper()) &
                (df_cfg_editado['SUCURSAL'].astype(str).str.upper() == filtro_sucursal.upper())
            )
            match = df_cfg_editado[mask]
            if not match.empty:
                try:
                    x_trab = int(pd.to_numeric(match.iloc[-1]['TRABAJADORES'], errors='coerce'))
                except:
                    pass

        x_trab = 0 if idx_mes > meses_transcurridos else x_trab
        hh = 0 if idx_mes > meses_transcurridos else calcular_hh_estimadas(x_trab, mes)

        acc_ctp, acc_stp, acc_tray, dp = 0, 0, 0, 0
        if not df_acc.empty and 'MES_TXT' in df_acc.columns:
            datos_mes = df_acc[df_acc['MES_TXT'] == mes]
            
            if 'TIPO' in datos_mes.columns:
                acc_ctp = len(datos_mes[datos_mes['TIPO'].astype(str).str.contains("CTP", case=False, na=False)])
                acc_stp = len(datos_mes[datos_mes['TIPO'].astype(str).str.contains("STP|INCIDENTE", case=False, na=False)])
                acc_tray = len(datos_mes[datos_mes['TIPO'].astype(str).str.contains("TRAYECTO", case=False, na=False)])
            
            for col in datos_mes.columns:
                if 'DIAS' in col:
                    dp = pd.to_numeric(datos_mes[col], errors='coerce').fillna(0).sum()

        tasa_acc = (acc_ctp / x_trab * 100) if x_trab > 0 else 0
        ind_frec = (acc_ctp / hh * 1000000) if hh > 0 else 0
        ind_grav = (dp / hh * 1000) if hh > 0 else 0

        filas_tabla.append({
            "MES": mes,
            "X TRAB": x_trab,
            "ACC CTP": acc_ctp,
            "ACC STP": acc_stp,
            "ACC TRAY": acc_tray,
            "DP": int(dp),
            "TASA ACC": round(tasa_acc, 2),
            "IND FRECI": round(ind_frec, 2),
            "IND GRAV": round(ind_grav, 2),
            "HH_REAL": hh 
        })

    df_tabla = pd.DataFrame(filas_tabla)

    # ==========================================
    # 7. ZONA CENTRAL: VISUALIZACIÓN
    # ==========================================
    col_tabla, col_analisis = st.columns([6, 4]) 

    total_ctp = df_tabla["ACC CTP"].sum()
    total_dp = df_tabla["DP"].sum()
    total_hh = df_tabla["HH_REAL"].sum()
    
    meses_activos = df_tabla[df_tabla["X TRAB"] > 0]
    promedio_trab_anual = meses_activos["X TRAB"].mean() if not meses_activos.empty else 0

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
            with rc1:
                st.info(f"**ACT (ACC CTP)**\n\n{total_ctp} / --")
                st.success(f"**DP (Días P.)**\n\n{total_dp} / --")
            with rc2:
                tasa_acum = (total_ctp/promedio_trab_anual*100) if promedio_trab_anual > 0 else 0
                st.warning(f"**TASA ACC**\n\n{round(tasa_acum,2)}% / --")
                if_acum = (total_ctp/total_hh*1000000) if total_hh > 0 else 0
                st.error(f"**IND FRECI**\n\n{round(if_acum,2)} / --")

        with st.container(border=True):
            st.markdown("##### Proyección anual (Datos Reales)")
            mes_corte_texto = lista_meses_completos[meses_transcurridos-1] if meses_transcurridos > 0 else "N/A"
            
            if df_tabla['DP'].sum() > 0:
                mes_critico_idx = df_tabla['DP'].idxmax()
                mes_critico_nombre = df_tabla.loc[mes_critico_idx, 'MES']
                mes_critico_dp = df_tabla.loc[mes_critico_idx, 'DP']
            else:
                mes_critico_nombre = "Ninguno"
                mes_critico_dp = 0
            
            promedio_dias_acc = (total_dp / total_ctp) if total_ctp > 0 else 0
            
            factor_proy = 12 / meses_transcurridos if meses_transcurridos > 0 else 0
            proy_act = int(round(total_ctp * factor_proy))
            proy_dp = int(round(total_dp * factor_proy))
            proy_hh = total_hh * factor_proy
            
            proy_tasa = (proy_act / promedio_trab_anual * 100) if promedio_trab_anual > 0 else 0
            proy_if = (proy_act / proy_hh * 1000000) if proy_hh > 0 else 0
            proy_ig = (proy_dp / proy_hh * 1000) if proy_hh > 0 else 0
            
            st.caption(f"Corte: {mes_corte_texto} ({meses_transcurridos} meses transcurridos)")
            st.markdown(f"""
            - **Mes crítico (DP):** {mes_critico_nombre} con {mes_critico_dp} días
            - **Promedio días por accidente:** {promedio_dias_acc:.2f}
            - **Proyección ACT anual:** {proy_act}
            - **Proyección DP anual:** {proy_dp}
            - **Proyección Tasa ACC:** {proy_tasa:.2f}%
            - **Proyección IND FRECI:** {proy_if:.2f}
            - **Proyección IND GRAV:** {proy_ig:.2f}
            """)

    # ==========================================
    # 8. GRÁFICOS DE MESES ACTIVOS
    # ==========================================
    st.markdown("<br>", unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    
    df_graficos = df_tabla[['MES', 'ACC CTP', 'DP']].copy()
    df_graficos['MES'] = pd.Categorical(df_graficos['MES'], categories=lista_meses_completos, ordered=True)
    df_graficos = df_graficos.set_index('MES')

    with g1:
        with st.container(border=True):
            st.markdown("##### Accidentes por mes (CTP)")
            st.bar_chart(df_graficos['ACC CTP'], color="#5c6bc0") 

    with g2:
        with st.container(border=True):
            st.markdown("##### Días perdidos por mes")
            st.line_chart(df_graficos['DP'], color="#ffa726") 

    # ==========================================
    # 9. TABLA RESUMEN DE ACCIDENTES (EXPEDIENTE)
    # ==========================================
    st.markdown("---")
    st.markdown("### 📋 Listado Oficial de Accidentes Registrados")
    st.info("💡 Este listado responde a los filtros aplicados arriba.")
    
    if not df_acc.empty:
        columnas_deseadas = ['FECHA', 'TRABAJADOR', 'SUCURSAL', 'TIPO', 'DIAS_PERDIDOS', 'ESTADO_REGISTRO']
        columnas_existentes = [col for col in columnas_deseadas if col in df_acc.columns]
        st.dataframe(df_acc[columnas_existentes], use_container_width=True, hide_index=True)
    else:
        st.success("✅ No hay accidentes registrados para los filtros seleccionados.")

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
