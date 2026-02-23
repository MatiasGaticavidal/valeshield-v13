import streamlit as st
import pandas as pd
import os
import streamlit.components.v1 as components
from datetime import datetime
from utils import ARCHIVO_ACCIDENTES, ARCHIVO_CONFIG_MENSUAL, ARCHIVO_PERSONAL, calcular_hh_estimadas

def mostrar_modulo_estadisticas():
    st.markdown("### 📊 Panel de Control: Siniestralidad y Desempeño")
    
    lista_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    ano_actual = datetime.now().year

    # ==========================================
    # 1. BARRA DE FILTROS SUPERIOR
    # ==========================================
    with st.container(border=True):
        f1, f2, f3, f4, f5 = st.columns(5)
        filtro_ano = f1.selectbox("Año", [ano_actual, ano_actual-1, ano_actual-2])
        filtro_mes = f2.selectbox("Mes de Análisis", ["Año Completo"] + lista_meses, index=datetime.now().month)
        filtro_sexo = f3.selectbox("Sexo", ["Ambos", "Masculino", "Femenino"]) 
        filtro_sucursal = f4.selectbox("Sucursal", ["Todas", "ELECTROCOM VALDIVIA", "MCT VALDIVIA", "PLACA CENTRO VALDIVIA"])
        
        st.markdown("""<style>
            .bot-ver { background-color: #fff3e0; color: #e65100; border: 1px solid #ffb74d; }
            .bot-limpiar { background-color: #e3f2fd; color: #1565c0; border: 1px solid #64b5f6; }
        </style>""", unsafe_allow_html=True)
        
        c_btn1, c_btn2 = f5.columns(2)
        c_btn1.button("👁️ Ver", use_container_width=True)
        c_btn2.button("Limpiar", use_container_width=True)

   # ==========================================
    # 2. CARGA Y FILTRADO CRUZADO (NÓMINA + ACCIDENTES)
    # ==========================================
    # --- NUEVO: DICCIONARIO TRADUCTOR DE SUCURSALES ---
    mapeo_sucursales = {
        "ELECTROCOM VALDIVIA": "ECOM",
        "PLACA CENTRO VALDIVIA": "PLC",
        "MCT VALDIVIA": "MCT"
    }

    # A. Procesar Nómina de Personal
    df_personal = pd.DataFrame()
    total_trabajadores, hombres, mujeres = 0, 0, 0
    
    if os.path.exists(ARCHIVO_PERSONAL):
        # Aplicamos el escudo latin1 para los acentos
        df_personal = pd.read_csv(ARCHIVO_PERSONAL, encoding='latin1')
        df_personal.columns = [c.strip().upper() for c in df_personal.columns]
        
        # Filtro Sucursal en Personal (Ahora usa el diccionario)
        if filtro_sucursal != "Todas" and 'SUCURSAL' in df_personal.columns:
            palabra_clave = mapeo_sucursales.get(filtro_sucursal, "")
            df_personal = df_personal[df_personal['SUCURSAL'].str.upper() == palabra_clave]
            
        # Detección de Sexo en Personal
        col_sexo = next((col for col in df_personal.columns if 'SEXO' in col or 'GENERO' in col), None)
        if col_sexo:
            hombres = len(df_personal[df_personal[col_sexo].astype(str).str.upper().str.startswith('M', na=False)])
            mujeres = len(df_personal[df_personal[col_sexo].astype(str).str.upper().str.startswith('F', na=False)])
            
            # Filtro Sexo en Personal
            if filtro_sexo == "Masculino":
                df_personal = df_personal[df_personal[col_sexo].astype(str).str.upper().str.startswith('M', na=False)]
            elif filtro_sexo == "Femenino":
                df_personal = df_personal[df_personal[col_sexo].astype(str).str.upper().str.startswith('F', na=False)]

        total_trabajadores = len(df_personal)

    # B. Procesar Accidentes
    df_acc = pd.DataFrame()
    if os.path.exists(ARCHIVO_ACCIDENTES):
        # Aplicamos escudo latin1 aquí también por si acaso
        df_acc = pd.read_csv(ARCHIVO_ACCIDENTES, encoding='latin1')
        df_acc.columns = [c.strip().upper() for c in df_acc.columns]
        
        if 'FECHA' in df_acc.columns:
            df_acc['FECHA'] = pd.to_datetime(df_acc['FECHA'], errors='coerce')
            df_acc = df_acc[df_acc['FECHA'].dt.year == filtro_ano] 
            meses_map = {i+1: m for i, m in enumerate(lista_meses)}
            df_acc['MES_TXT'] = df_acc['FECHA'].dt.month.map(meses_map)

        # Filtro Sucursal en Accidentes (Usa el mismo diccionario)
        if filtro_sucursal != "Todas" and not df_acc.empty and 'SUCURSAL' in df_acc.columns:
            palabra_clave = mapeo_sucursales.get(filtro_sucursal, "")
            df_acc = df_acc[df_acc['SUCURSAL'].str.upper() == palabra_clave]

        # Filtro Sexo Cruzado (Solo muestra accidentes de los trabajadores filtrados en nómina)
        if filtro_sexo != "Ambos" and not df_acc.empty and not df_personal.empty and 'NOMBRE' in df_personal.columns:
            nombres_validos = df_personal['NOMBRE'].str.upper().tolist()
            df_acc = df_acc[df_acc['TRABAJADOR'].str.upper().isin(nombres_validos)]

    # C. Procesar Configuración (HH)
    df_cfg = pd.DataFrame()
    if os.path.exists(ARCHIVO_CONFIG_MENSUAL):
        df_cfg = pd.read_csv(ARCHIVO_CONFIG_MENSUAL)

    # ==========================================
    # 3. TARJETAS DE RESUMEN
    # ==========================================
    t1, t2, t3 = st.columns(3)
    with t1:
        st.info(f"**TRABAJADORES CENTRO**\n### {total_trabajadores}")
    with t2:
        st.success(f"**HOMBRES**\n### {hombres}")
    with t3:
        st.warning(f"**MUJERES**\n### {mujeres}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # 4. TABLA Y CÁLCULOS MENSUALES
    # ==========================================
    filas_tabla = []
    meses_transcurridos = datetime.now().month if filtro_ano == ano_actual else 12

    for i, mes in enumerate(lista_meses):
        idx_mes = i + 1
        
        # Dotación: Si hay filtro de Sexo, manda la nómina filtrada. Si no, busca en la configuración.
        x_trab = total_trabajadores if total_trabajadores > 0 else 75
        if filtro_sexo == "Ambos" and not df_cfg.empty and filtro_sucursal != "Todas":
            match = df_cfg[(df_cfg['Mes'] == mes) & (df_cfg['Sucursal'] == filtro_sucursal)]
            if not match.empty:
                x_trab = int(match.iloc[-1]['Trabajadores'])

        x_trab = 0 if idx_mes > meses_transcurridos else x_trab
        hh = 0 if idx_mes > meses_transcurridos else calcular_hh_estimadas(x_trab, mes)

        acc_ctp, acc_stp, acc_tray, dp = 0, 0, 0, 0
        if not df_acc.empty and 'MES_TXT' in df_acc.columns:
            datos_mes = df_acc[df_acc['MES_TXT'] == mes]
            acc_ctp = len(datos_mes[datos_mes['TIPO'].str.contains("CTP", case=False, na=False)])
            acc_stp = len(datos_mes[datos_mes['TIPO'].str.contains("STP|INCIDENTE", case=False, na=False)])
            acc_tray = len(datos_mes[datos_mes['TIPO'].str.contains("TRAYECTO", case=False, na=False)])
            
            for col in df_acc.columns:
                if 'DIAS' in col:
                    dp = datos_mes[col].sum()

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
            "HH_REAL": hh # Columna oculta para cálculos
        })

    df_tabla = pd.DataFrame(filas_tabla)

    # ==========================================
    # 5. ZONA CENTRAL: VISUALIZACIÓN
    # ==========================================
    col_tabla, col_analisis = st.columns([6, 4]) 

    # Totales para proyecciones
    total_ctp = df_tabla["ACC CTP"].sum()
    total_dp = df_tabla["DP"].sum()
    total_hh = df_tabla["HH_REAL"].sum()
    
    # Promedio de trabajadores solo considerando meses > 0
    meses_activos = df_tabla[df_tabla["X TRAB"] > 0]
    promedio_trab_anual = meses_activos["X TRAB"].mean() if not meses_activos.empty else 0

    with col_tabla:
        with st.container(border=True):
            st.markdown("##### Detalle mensual")
            # Ocultamos la HH_REAL en la vista
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
            # Cálculos de Proyección Exactos
            mes_corte_texto = lista_meses[meses_transcurridos-1] if meses_transcurridos > 0 else "N/A"
            
            mes_critico_idx = df_tabla['DP'].idxmax()
            mes_critico_nombre = df_tabla.loc[mes_critico_idx, 'MES']
            mes_critico_dp = df_tabla.loc[mes_critico_idx, 'DP']
            
            promedio_dias_acc = (total_dp / total_ctp) if total_ctp > 0 else 0
            
            # Proyecciones a 12 meses
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
    # 6. GRÁFICOS DE 12 MESES (FIJOS ENE-DIC)
    # ==========================================
    st.markdown("<br>", unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    
    # Obligamos al gráfico a mantener el orden de los 12 meses usando la columna MES como índice categórico
    df_graficos = df_tabla[['MES', 'ACC CTP', 'DP']].copy()
    df_graficos['MES'] = pd.Categorical(df_graficos['MES'], categories=lista_meses, ordered=True)
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
    # 7. BOTONES DE ACCIÓN (EXPORTAR PDF)
    # ==========================================
    st.markdown("---")
    b1, b2, b3 = st.columns([2, 2, 6])
    
    # Botón mágico para PDF
    if b1.button("📄 Generar PDF", type="primary", use_container_width=True):
        # Inyectamos JavaScript que le dice al navegador que abra la vista de impresión
        components.html(
            """
            <script>
            window.parent.print();
            </script>
            """,
            height=0
        )
        
    # Botón para salir del dashboard
    if b2.button("Cerrar Panel", use_container_width=True):
        st.session_state['opcion_actual'] = "Inicio"
        st.rerun()