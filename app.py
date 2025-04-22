# app.py
import streamlit as st
from datetime import datetime, date, timedelta
import psycopg2
import os
import hashlib
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import time
import plotly.graph_objects as go

st.set_page_config(page_title="Caja Carnicería", layout="wide")
load_dotenv()

# ---------- FUNCIONES AUXILIARES ----------
def calcular_vuelto():
    if st.session_state.dinero_entregado_key > 0 and st.session_state.monto_compra_key > 0:
        st.session_state.vuelto_calculado = round(st.session_state.dinero_entregado_key - st.session_state.monto_compra_key, 2)
    else:
        st.session_state.vuelto_calculado = 0.0

# ---------- CONFIGURACIÓN DE USUARIOS ----------
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

usuarios = {
    "dueno": {"password": make_hashes("1234"), "rol": "dueño"},
    "cajero1": {"password": make_hashes("1234"), "rol": "cajero"},
    "cajero2": {"password": make_hashes("1234"), "rol": "cajero"},
}

# ---------- CONEXIÓN A LA BASE DE DATOS ----------
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT", 5432)
    )

# ---------- FUNCIONES DE BASE DE DATOS ----------
def registrar_venta(sucursal, monto, metodo_pago, entregado, vuelto, ingreso, deuda, cliente_fiado=None, telefono_fiado=None):
    conn = None
    try:
        # Convertir valores a float y redondear a 2 decimales
        monto = round(float(monto), 2)
        entregado = round(float(entregado), 2)
        vuelto = round(float(vuelto), 2)
        ingreso = round(float(ingreso), 2)
        deuda = round(float(deuda), 2)
        
        # Establecer conexión
        conn = get_connection()
        cur = conn.cursor()
        
        # Query de inserción
        query = """
            INSERT INTO ventas 
            (sucursal, monto, metodo_pago, entregado, vuelto, ingreso, deuda, fecha, cliente_fiado, telefono_fiado)
            VALUES 
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        
        # Valores para la inserción
        valores = (
            sucursal,
            monto,
            metodo_pago,
            entregado,
            vuelto,
            ingreso,
            deuda,
            datetime.now(),
            cliente_fiado,
            telefono_fiado
        )
        
        # Ejecutar la inserción
        cur.execute(query, valores)
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"Error al registrar la venta: {str(e)}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if conn:
            conn.close()

def crear_tabla_empleados():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS empleados (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                sucursal VARCHAR(50) NOT NULL,
                sueldo_base DECIMAL(10,2) NOT NULL,
                activo BOOLEAN DEFAULT TRUE,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    except Exception as e:
        st.error(f"Error al crear tabla empleados: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

# Llamar a la función para crear la tabla al inicio
crear_tabla_empleados()

# ---------- LOGIN ----------
if not st.session_state.get("logueado"):
    st.title("Login - Sistema de Caja")
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type='password')
    sucursal = st.selectbox("Sucursal", ["Sucursal Centro", "Sucursal Norte"])

    if st.button("Acceder"):
        if username in usuarios:
            user_info = usuarios[username]
            if check_hashes(password, user_info["password"]):
                st.session_state["logueado"] = True
                st.session_state["usuario"] = username
                st.session_state["rol"] = user_info["rol"]
                st.session_state["sucursal"] = sucursal
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        else:
            st.error("Usuario no registrado")
    st.stop()

# ---------- CIERRE DE SESIÓN ----------
st.sidebar.markdown(f"👤 Usuario: **{st.session_state['usuario']}**")
if st.sidebar.button("🔒 Cerrar sesión"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ---------- INTERFAZ DUEÑO ----------
if st.session_state.get("rol") == "dueño":
    st.sidebar.title("📂 Menú de navegación")
    vista = st.sidebar.radio("Seleccionar vista", 
                           ["📊 Dashboard", "📝 Registro de Operaciones", "💰 Cierre de caja"], 
                           format_func=lambda x: x.split(' ', 1)[1])

    if vista == "📊 Dashboard":
        st.title("📊 Panel de Control")
        
        # Selector de mes
        meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        
        mes_actual = datetime.now().month
        año_actual = datetime.now().year
        
        mes_seleccionado = st.selectbox(
            "Seleccionar Mes",
            options=list(meses.keys()),
            format_func=lambda x: meses[x],
            index=mes_actual - 1
        )
        
        # Calcular primer y último día del mes seleccionado
        primer_dia = date(año_actual, mes_seleccionado, 1)
        if mes_seleccionado == 12:
            ultimo_dia = date(año_actual + 1, 1, 1) - timedelta(days=1)
        else:
            ultimo_dia = date(año_actual, mes_seleccionado + 1, 1) - timedelta(days=1)
            
        # Calcular primer y último día del mes anterior
        if mes_seleccionado == 1:
            primer_dia_anterior = date(año_actual - 1, 12, 1)
            ultimo_dia_anterior = date(año_actual, 1, 1) - timedelta(days=1)
        else:
            primer_dia_anterior = date(año_actual, mes_seleccionado - 1, 1)
            ultimo_dia_anterior = primer_dia - timedelta(days=1)

        # Conexión a la base de datos
        conn = get_connection()
        cur = conn.cursor()

        # ---------- CARDS DE COMPARACIÓN VS MES ANTERIOR ----------
        st.subheader("📈 Comparativa vs Mes Anterior")
        col1, col2, col3, col4 = st.columns(4)

        # Ventas del mes seleccionado por sucursal
        cur.execute("""
            SELECT 
                sucursal,
                CAST(SUM(ingreso) AS FLOAT) as total_ventas
            FROM ventas
            WHERE DATE(fecha) >= %s AND DATE(fecha) <= %s
            GROUP BY sucursal
            ORDER BY total_ventas DESC
        """, (primer_dia, ultimo_dia))
        ventas_totales = {row[0]: row[1] for row in cur.fetchall()}
        
        # Ventas del mes anterior por sucursal
        cur.execute("""
            SELECT 
                sucursal,
                CAST(SUM(ingreso) AS FLOAT) as total_ventas
            FROM ventas
            WHERE DATE(fecha) >= %s AND DATE(fecha) <= %s
            GROUP BY sucursal
        """, (primer_dia_anterior, ultimo_dia_anterior))
        ventas_mes_anterior = {row[0]: row[1] for row in cur.fetchall()}

        # Egresos del mes seleccionado por sucursal
        cur.execute("""
            SELECT 
                sucursal,
                CAST(SUM(monto) AS FLOAT) as total_egresos
            FROM egresos 
            WHERE DATE(fecha) >= %s AND DATE(fecha) <= %s
            GROUP BY sucursal
        """, (primer_dia, ultimo_dia))
        egresos_mes_actual = {row[0]: row[1] for row in cur.fetchall()}
        
        # Egresos del mes anterior por sucursal
        cur.execute("""
            SELECT 
                sucursal,
                CAST(SUM(monto) AS FLOAT) as total_egresos
            FROM egresos
            WHERE DATE(fecha) >= %s AND DATE(fecha) <= %s
            GROUP BY sucursal
        """, (primer_dia_anterior, ultimo_dia_anterior))
        egresos_mes_anterior = {row[0]: row[1] for row in cur.fetchall()}
        
        # Mostrar cards con comparativas
        with col1:
            ventas_total_centro = float(ventas_totales.get("Sucursal Centro", 0))
            ventas_anterior_centro = float(ventas_mes_anterior.get("Sucursal Centro", 0))
            diff_porcentaje_centro = ((ventas_total_centro - ventas_anterior_centro) / ventas_anterior_centro * 100) if ventas_anterior_centro > 0 else 0
            
            st.metric(
                "Ventas Centro",
                f"${ventas_total_centro:,.2f}",
                f"{diff_porcentaje_centro:+.1f}% vs mes anterior",
                delta_color="normal" if diff_porcentaje_centro >= 0 else "inverse"
            )
            
        with col2:
            ventas_total_norte = float(ventas_totales.get("Sucursal Norte", 0))
            ventas_anterior_norte = float(ventas_mes_anterior.get("Sucursal Norte", 0))
            diff_porcentaje_norte = ((ventas_total_norte - ventas_anterior_norte) / ventas_anterior_norte * 100) if ventas_anterior_norte > 0 else 0
            
            st.metric(
                "Ventas Norte",
                f"${ventas_total_norte:,.2f}",
                f"{diff_porcentaje_norte:+.1f}% vs mes anterior",
                delta_color="normal" if diff_porcentaje_norte >= 0 else "inverse"
            )
            
        with col3:
            egresos_actual_centro = float(egresos_mes_actual.get("Sucursal Centro", 0))
            egresos_anterior_centro = float(egresos_mes_anterior.get("Sucursal Centro", 0))
            diff_egresos_centro = egresos_actual_centro - egresos_anterior_centro
            diff_porcentaje_egresos_centro = (diff_egresos_centro / egresos_anterior_centro * 100) if egresos_anterior_centro > 0 else 0
            
            st.metric(
                "Egresos Centro",
                f"${egresos_actual_centro:,.2f}",
                f"{diff_porcentaje_egresos_centro:+.1f}% vs mes anterior",
                delta_color="inverse" if diff_porcentaje_egresos_centro >= 0 else "normal"
            )
            
        with col4:
            egresos_actual_norte = float(egresos_mes_actual.get("Sucursal Norte", 0))
            egresos_anterior_norte = float(egresos_mes_anterior.get("Sucursal Norte", 0))
            diff_egresos_norte = egresos_actual_norte - egresos_anterior_norte
            diff_porcentaje_egresos_norte = (diff_egresos_norte / egresos_anterior_norte * 100) if egresos_anterior_norte > 0 else 0
            
            st.metric(
                "Egresos Norte",
                f"${egresos_actual_norte:,.2f}",
                f"{diff_porcentaje_egresos_norte:+.1f}% vs mes anterior",
                delta_color="inverse" if diff_porcentaje_egresos_norte >= 0 else "normal"
            )

        # ---------- GRÁFICOS DE ANÁLISIS ----------
        st.subheader("📊 Análisis de Ventas")

        # 1. Tabla de movimientos por día de la semana
        st.write("### Movimientos por Día")
        
        # Consulta SQL para obtener los movimientos por día
        cur.execute("""
            WITH DatosVentas AS (
                SELECT 
                    CASE EXTRACT(DOW FROM fecha)::INT
                        WHEN 1 THEN 'Lunes'
                        WHEN 2 THEN 'Martes'
                        WHEN 3 THEN 'Miércoles'
                        WHEN 4 THEN 'Jueves'
                        WHEN 5 THEN 'Viernes'
                        WHEN 6 THEN 'Sábado'
                        WHEN 0 THEN 'Domingo'
                    END AS dia_semana,
                    COUNT(*) as cantidad_ventas,
                    CAST(SUM(monto) AS FLOAT) as monto_total,
                    CAST(SUM(ingreso) AS FLOAT) as ingreso_real,
                    CAST(SUM(deuda) AS FLOAT) as deuda_total,
                    CAST(AVG(monto) AS FLOAT) as promedio_venta
                FROM ventas
                WHERE DATE(fecha) >= %s AND DATE(fecha) <= %s
                GROUP BY EXTRACT(DOW FROM fecha)::INT
                ORDER BY EXTRACT(DOW FROM fecha)::INT
            )
            SELECT * FROM DatosVentas;
        """, (primer_dia, ultimo_dia))
        datos_diarios = cur.fetchall()
        
        if datos_diarios:
            # Crear DataFrame
            df_diario = pd.DataFrame(datos_diarios, 
                                   columns=["Día", "Cant. Ventas", "Monto Total", 
                                          "Ingreso Real", "Deuda", "Promedio"])
            
            # Formatear las columnas numéricas
            columnas_moneda = ["Monto Total", "Ingreso Real", "Deuda", "Promedio"]
            for col in columnas_moneda:
                df_diario[col] = df_diario[col].apply(lambda x: f"${x:,.2f}")
            
            # Crear tres columnas para mejor visualización
            col1, col2, col3 = st.columns([2,1,1])
            
            with col1:
                # Mostrar la tabla con estilo
                st.dataframe(
                    df_diario,
                    column_config={
                        "Día": st.column_config.TextColumn("📅 Día de la Semana"),
                        "Cant. Ventas": st.column_config.NumberColumn("📊 Cant. Ventas"),
                        "Monto Total": st.column_config.TextColumn("💰 Monto Total"),
                        "Ingreso Real": st.column_config.TextColumn("💵 Ingreso Real"),
                        "Deuda": st.column_config.TextColumn("📝 Deuda"),
                        "Promedio": st.column_config.TextColumn("📈 Promedio")
                    },
                    hide_index=True,
                    width=800
                )
            
            # Calcular y mostrar estadísticas adicionales
            with col2:
                st.markdown("#### 📊 Resumen")
                # Calcular totales generales de ventas por sucursal
                cur.execute("""
                    SELECT 
                        sucursal,
                        CAST(SUM(ingreso) AS FLOAT) as ingreso_total
                    FROM ventas
                    WHERE DATE(fecha) >= %s AND DATE(fecha) <= %s
                    GROUP BY sucursal
                    ORDER BY ingreso_total DESC;
                """, (primer_dia, ultimo_dia))
                totales_sucursal = cur.fetchall()
                
                # Mostrar totales
                for sucursal, total in totales_sucursal:
                    st.metric(
                        f"💰 Total {sucursal}", 
                        f"${total:,.2f}"
                    )
                
                # Calcular total general
                total_general = sum(total for _, total in totales_sucursal)
                st.metric("💰 Total General", f"${total_general:,.2f}")

            with col3:
                st.markdown("#### 🏆 Mejores Días")
                # Encontrar el día con más ingresos
                mejor_dia_ingresos = max(datos_diarios, key=lambda x: x[3])  # Usando ingreso real
                st.info(f"Mayor Ingreso:\n{mejor_dia_ingresos[0]}\n${mejor_dia_ingresos[3]:,.2f}")
                
                # Encontrar el día con más ventas
                mejor_dia_ventas = max(datos_diarios, key=lambda x: x[1])
                st.success(f"Más Ventas:\n{mejor_dia_ventas[0]}\n{mejor_dia_ventas[1]} ventas")
        else:
            st.info("No hay ingresos registrados para mostrar.")

        st.markdown("---")  # Línea divisoria

        # 2. Tabla de ingresos por método de pago
        st.write("### Movimientos por Método de Pago")
        
        # Consulta SQL para movimientos por método de pago
        cur.execute("""
            WITH DatosPago AS (
                SELECT 
                    COALESCE(metodo_pago, 'Sin especificar') as metodo_pago,
                    COUNT(id) as cantidad_ventas,
                    CAST(SUM(monto) AS FLOAT) as monto_total,
                    CAST(SUM(ingreso) AS FLOAT) as ingreso_real,
                    CAST(SUM(deuda) AS FLOAT) as deuda_pendiente,
                    CAST(AVG(monto) AS FLOAT) as promedio_venta
                FROM ventas
                WHERE metodo_pago != 'Cierre'
                AND DATE(fecha) >= %s AND DATE(fecha) <= %s
                GROUP BY metodo_pago
                HAVING COUNT(id) > 0
                ORDER BY monto_total DESC
            )
            SELECT * FROM DatosPago;
        """, (primer_dia, ultimo_dia))
        datos_metodos = cur.fetchall()
        
        if datos_metodos:
            # Crear DataFrame
            df_metodos = pd.DataFrame(datos_metodos, 
                                    columns=["Método de Pago", "Cantidad", "Monto Total", 
                                           "Ingreso Real", "Deuda Pendiente", "Promedio"])
            
            # Crear columnas para la visualización
            col1, col2 = st.columns([2,1])
            
            with col1:
                # Formatear las columnas numéricas para la tabla
                df_display = df_metodos.copy()
                for col in ["Monto Total", "Ingreso Real", "Deuda Pendiente", "Promedio"]:
                    df_display[col] = df_display[col].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(
                    df_display,
                    column_config={
                        "Método de Pago": st.column_config.TextColumn("💳 Método de Pago"),
                        "Cantidad": st.column_config.NumberColumn("📊 Cant. Ventas"),
                        "Monto Total": st.column_config.TextColumn("💰 Monto Total"),
                        "Ingreso Real": st.column_config.TextColumn("💵 Ingreso Real"),
                        "Deuda Pendiente": st.column_config.TextColumn("📝 Deuda"),
                        "Promedio": st.column_config.TextColumn("📈 Promedio")
                    },
                    hide_index=True,
                    width=800
                )
            
            with col2:
                st.markdown("#### 📊 Análisis")
                # Calcular totales
                total_ingreso = df_metodos["Ingreso Real"].sum()
                total_deuda = df_metodos["Deuda Pendiente"].sum()
                total_general = total_ingreso + total_deuda
                
                st.metric("💰 Total Ingresos", f"${total_ingreso:,.2f}")
                st.metric("📝 Deuda Pendiente", f"${total_deuda:,.2f}")
                st.metric("💵 Total General", f"${total_general:,.2f}")
                
                # Método más usado
                metodo_principal = df_metodos.iloc[0]
                st.metric(
                    "Método más usado",
                    metodo_principal["Método de Pago"],
                    f"{metodo_principal['Cantidad']} ventas"
                )
        else:
            st.info("No hay datos de métodos de pago para mostrar.")

        # 3. Tabla de ventas mensuales
        st.markdown("---")
        st.write("### Movimientos Mensuales")
        cur.execute("""
            WITH DatosMensuales AS (
                SELECT 
                    DATE_TRUNC('month', fecha)::DATE as mes,
                    COUNT(id) as cantidad_ventas,
                    CAST(SUM(ingreso) AS FLOAT) as monto_total,
                    CAST(SUM(ingreso) AS FLOAT) as ingreso_real,
                    CAST(SUM(deuda) AS FLOAT) as deuda_pendiente,
                    CAST(SUM(CASE WHEN metodo_pago = 'Efectivo' THEN ingreso ELSE 0 END) AS FLOAT) as total_efectivo,
                    CAST(SUM(CASE WHEN metodo_pago IN ('Mercado Pago', 'Cuenta DNI') THEN ingreso ELSE 0 END) AS FLOAT) as total_digital,
                    CAST(AVG(ingreso) AS FLOAT) as promedio_venta
                FROM ventas
                WHERE fecha >= CURRENT_DATE - INTERVAL '12 months'
                AND metodo_pago != 'Cierre'
                GROUP BY DATE_TRUNC('month', fecha)::DATE
                ORDER BY mes DESC
            )
            SELECT * FROM DatosMensuales;
        """)
        datos_mensuales = cur.fetchall()
        
        if datos_mensuales:
            # Crear DataFrame
            df_mensual = pd.DataFrame(datos_mensuales, 
                                    columns=["Mes", "Cantidad", "Monto Total", "Ingreso Real", 
                                           "Deuda Pendiente", "Total Efectivo", "Total Digital", "Promedio"])
            
            # Formatear la fecha para mejor visualización
            df_mensual["Mes"] = pd.to_datetime(df_mensual["Mes"]).dt.strftime('%B %Y')
            
            # Crear columnas para la visualización
            col1, col2 = st.columns([2,1])
            
            with col1:
                # Formatear las columnas numéricas para la tabla
                df_display = df_mensual.copy()
                columnas_moneda = ["Monto Total", "Ingreso Real", "Deuda Pendiente", 
                                 "Total Efectivo", "Total Digital", "Promedio"]
                for col in columnas_moneda:
                    df_display[col] = df_display[col].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(
                    df_display,
                    column_config={
                        "Mes": st.column_config.TextColumn("📅 Mes"),
                        "Cantidad": st.column_config.NumberColumn("📊 Ventas"),
                        "Monto Total": st.column_config.TextColumn("💰 Total"),
                        "Ingreso Real": st.column_config.TextColumn("💵 Ingreso"),
                        "Deuda Pendiente": st.column_config.TextColumn("📝 Deuda"),
                        "Total Efectivo": st.column_config.TextColumn("💵 Efectivo"),
                        "Total Digital": st.column_config.TextColumn("💳 Digital"),
                        "Promedio": st.column_config.TextColumn("📈 Promedio")
                    },
                    hide_index=True,
                    width=800
                )
            
            with col2:
                st.markdown("#### 📊 Análisis del Mes")
                # Obtener datos del mes actual
                mes_actual = df_mensual.iloc[0]
                
                # Obtener los valores de efectivo y digital
                efectivo_actual = float(mes_actual['Total Efectivo'])
                digital_actual = float(mes_actual['Total Digital'])
                
                # Calcular porcentajes de efectivo y digital
                total_medios = efectivo_actual + digital_actual
                if total_medios > 0:
                    porc_efectivo = (efectivo_actual / total_medios) * 100
                    porc_digital = (digital_actual / total_medios) * 100
                    
                    # Mostrar solo los porcentajes
                    st.metric("💵 % Efectivo", f"{porc_efectivo:.1f}%")
                    st.metric("💳 % Digital", f"{porc_digital:.1f}%")
        else:
            st.info("No hay datos mensuales para mostrar.")

    elif vista == "📝 Registro de Operaciones":
        st.title("📝 Registro de Ventas y Egresos")
        # Mostrar el formulario de registro aquí
        conn = get_connection()
        cur = conn.cursor()

        # Estilo personalizado para el botón y formulario
        st.markdown("""
            <style>
            .stButton>button {
                background-color: #F0FFF0;
                color: #2E8B57;
                padding: 10px 24px;
                border-radius: 5px;
                border: none;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                transition: all 0.3s ease;
                font-weight: 500;
            }
            .stButton>button:hover {
                background-color: #E0EEE0;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }
            .stButton>button:active {
                background-color: #D1EED1;
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            }
            /* Quitar borde del formulario */
            .stForm {
                border: none !important;
                padding: 0 !important;
            }
            div[data-testid="stForm"] {
                border: none !important;
                padding: 0 !important;
            }
            </style>
        """, unsafe_allow_html=True)

        # -------- REGISTRO DE VENTAS --------
        st.subheader("Registrar venta")

        # Inicializar variables en session_state si no existen
        if 'form_submitted' not in st.session_state:
            st.session_state.form_submitted = False

        if 'monto_compra' not in st.session_state:
            st.session_state.monto_compra = 0.0
        if 'dinero_entregado' not in st.session_state:
            st.session_state.dinero_entregado = 0.0
        if 'vuelto_calculado' not in st.session_state:
            st.session_state.vuelto_calculado = 0.0

        # Variables para el cálculo del vuelto fuera del formulario
        col1, col2 = st.columns(2)
        with col1:
            monto_compra = st.number_input("Monto de la compra", 
                                         min_value=0.0, 
                                         step=100.0, 
                                         key="monto_compra_key", 
                                         format="%.2f",
                                         value=0.0 if st.session_state.form_submitted else st.session_state.get('monto_compra', 0.0),
                                         on_change=calcular_vuelto)
        with col2:
            metodo_pago = st.selectbox("Método de pago", 
                                     ["Efectivo", "Mercado Pago", "Cuenta DNI", "Fiado"], 
                                     key="metodo_fuera",
                                     index=0 if st.session_state.form_submitted else None)

        # Variable para almacenar el vuelto calculado
        vuelto_calculado = 0.0
        dinero_entregado = 0.0
        cliente_fiado = None
        telefono_fiado = None

        # Mostrar campo de dinero entregado si es efectivo
        if metodo_pago == "Efectivo":
            dinero_entregado = st.number_input("Dinero entregado por el cliente", 
                                             min_value=0.0, 
                                             step=100.0, 
                                             key="dinero_entregado_key",
                                             format="%.2f",
                                             value=0.0 if st.session_state.form_submitted else st.session_state.get('dinero_entregado', 0.0),
                                             on_change=calcular_vuelto)
            
            # Mostrar el vuelto calculado
            if st.session_state.vuelto_calculado != 0:
                if st.session_state.vuelto_calculado >= 0:
                    st.info(f"💵 Vuelto a entregar: ${st.session_state.vuelto_calculado:,.2f}")
                else:
                    st.warning(f"⚠️ Falta dinero por cobrar: ${abs(st.session_state.vuelto_calculado):,.2f}")
        elif metodo_pago == "Fiado":
            col1, col2 = st.columns(2)
            with col1:
                cliente_fiado = st.text_input("Nombre del cliente",
                                            value="" if st.session_state.form_submitted else st.session_state.get('cliente_fiado', ""))
            with col2:
                telefono_fiado = st.text_input("Teléfono (opcional)",
                                             value="" if st.session_state.form_submitted else st.session_state.get('telefono_fiado', ""))

        # Crear un formulario para la venta
        with st.form("formulario_venta", clear_on_submit=True):
            submitted = st.form_submit_button("Registrar Venta")
            
            if submitted:
                if monto_compra <= 0:
                    st.error("❌ El monto debe ser mayor a 0")
                elif metodo_pago == "Efectivo" and dinero_entregado < monto_compra:
                    st.error("❌ El dinero entregado debe ser mayor o igual al monto de la compra")
                elif metodo_pago == "Fiado" and not cliente_fiado:
                    st.error("❌ Debe ingresar el nombre del cliente para ventas fiadas")
                else:
                    # Preparar valores según el método de pago
                    if metodo_pago == "Efectivo":
                        ingreso = monto_compra
                        entregado = dinero_entregado
                        vuelto = vuelto_calculado
                        deuda = 0.0
                    elif metodo_pago in ["Mercado Pago", "Cuenta DNI"]:
                        ingreso = monto_compra
                        entregado = monto_compra
                        vuelto = 0.0
                        deuda = 0.0
                    else:  # Fiado
                        ingreso = 0.0
                        entregado = 0.0
                        vuelto = 0.0
                        deuda = monto_compra

                    # Registrar la venta
                    if registrar_venta(
                        st.session_state["sucursal"], 
                        monto_compra, 
                        metodo_pago, 
                        entregado, 
                        vuelto, 
                        ingreso, 
                        deuda,
                        cliente_fiado,
                        telefono_fiado
                    ):
                        st.success("✅ Venta registrada correctamente")
                        # Marcar el formulario como enviado para limpiar los campos
                        st.session_state.form_submitted = True
                        # Limpiar los valores almacenados
                        st.session_state.monto_compra = 0.0
                        st.session_state.dinero_entregado = 0.0
                        st.session_state.cliente_fiado = ""
                        st.session_state.telefono_fiado = ""
                        time.sleep(0.5)
                        st.rerun()

        # Después del formulario de ventas
        st.markdown("---")  # Línea divisoria

        # -------- REGISTRO DE EGRESOS --------
        st.subheader("➖ Registrar Egreso")

        # Inicializar variables para egresos en session_state
        if 'egreso_submitted' not in st.session_state:
            st.session_state.egreso_submitted = False

        with st.form("form_egreso", clear_on_submit=True):
            motivo = st.selectbox("Motivo del egreso", 
                                 ["Proveedor", "Sueldos", "Reparaciones", "Otros"] if st.session_state["rol"] == "dueño" else ["Proveedor", "Reparaciones", "Otros"],
                                 key="motivo_egreso")
            
            # Campos específicos para sueldos (solo visible para el dueño)
            if motivo == "Sueldos" and st.session_state["rol"] == "dueño":
                st.write("📋 Detalle de sueldos")
                
                # Obtener empleados activos de la sucursal y su último pago
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    WITH UltimoPago AS (
                        SELECT 
                            e.detalle,
                            MAX(e.fecha) as ultimo_pago
                        FROM egresos e
                        WHERE e.motivo = 'Sueldos'
                        GROUP BY e.detalle
                    )
                    SELECT 
                        emp.id, 
                        emp.nombre, 
                        emp.sueldo_base,
                        up.ultimo_pago
                    FROM empleados emp
                    LEFT JOIN UltimoPago up ON up.detalle = CONCAT('Sueldo de ', emp.nombre)
                    WHERE emp.sucursal = %s AND emp.activo = TRUE
                    ORDER BY emp.nombre
                """, (st.session_state["sucursal"],))
                empleados_db = cur.fetchall()
                conn.close()
                
                if not empleados_db:
                    st.warning("⚠️ No hay empleados registrados en esta sucursal")
                    if st.button("➕ Agregar empleado"):
                        st.info("Función en desarrollo")
                else:
                    # Crear DataFrame con los empleados
                    df_empleados = pd.DataFrame(empleados_db, columns=["ID", "Nombre", "Sueldo Base", "Último Pago"])
                    
                    # Agregar columna de checkbox para seleccionar empleados a pagar
                    df_empleados["Pagar"] = False
                    
                    # Mostrar la tabla con checkboxes editables
                    df_empleados_editado = st.data_editor(
                        df_empleados,
                        column_config={
                            "ID": st.column_config.NumberColumn("ID", disabled=True),
                            "Nombre": st.column_config.TextColumn("Nombre", disabled=True),
                            "Sueldo Base": st.column_config.NumberColumn(
                                "Sueldo Base",
                                help="Monto base del sueldo",
                                min_value=0,
                                max_value=1000000,
                                step=1000,
                                format="$%d"
                            ),
                            "Último Pago": st.column_config.DatetimeColumn(
                                "Último Pago",
                                help="Fecha del último pago realizado",
                                format="DD/MM/YYYY HH:mm",
                                disabled=True
                            ),
                            "Pagar": st.column_config.CheckboxColumn(
                                "Pagar",
                                help="Seleccionar para pagar"
                            )
                        },
                        hide_index=True,
                        key="tabla_empleados"
                    )
                    
                    # Calcular total a pagar de los empleados seleccionados
                    empleados_a_pagar = df_empleados_editado[df_empleados_editado["Pagar"]]
                    monto_total = empleados_a_pagar["Sueldo Base"].sum()
                    
                    if monto_total > 0:
                        st.info(f"💰 Total a pagar: ${monto_total:,.2f}")
                        
                        # Campo de observación
                        observacion = st.text_area(
                            "Observaciones (opcional)", 
                            height=100,
                            value="" if st.session_state.egreso_submitted else st.session_state.get('observacion', ""),
                            key="obs_sueldos"
                        )
                        
                        # Botón para confirmar el pago
                        if st.button("💸 Confirmar Pago de Sueldos"):
                            fecha_pago = datetime.now()
                            conn = get_connection()
                            cur = conn.cursor()
                            try:
                                for _, empleado in empleados_a_pagar.iterrows():
                                    detalle = f"Sueldo de {empleado['Nombre']}"
                                    cur.execute("""
                                        INSERT INTO egresos (sucursal, motivo, monto, observacion, fecha, detalle)
                                        VALUES (%s, %s, %s, %s, %s, %s)
                                    """, (st.session_state["sucursal"], "Sueldos", empleado["Sueldo Base"], 
                                         observacion, fecha_pago, detalle))
                                
                                conn.commit()
                                st.success(f"✅ Se han pagado {len(empleados_a_pagar)} sueldos por un total de ${monto_total:,.2f}")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al registrar los pagos: {str(e)}")
                                conn.rollback()
                            finally:
                                conn.close()
            else:
                monto_total = st.number_input("Monto del egreso", 
                                            min_value=0.0, 
                                            step=100.0, 
                                            format="%.2f",
                                            value=0.0 if st.session_state.egreso_submitted else st.session_state.get('monto_egreso', 0.0))
            
            # Campo de observación
            observacion = st.text_area("Observaciones (opcional)", 
                                      height=100,
                                      value="" if st.session_state.egreso_submitted else st.session_state.get('observacion', ""))

            submitted = st.form_submit_button("Registrar Egreso")
            
            if submitted:
                if motivo == "Sueldos" and not empleados_a_pagar.empty:
                    st.error("❌ Debe pagar todos los sueldos antes de registrar el egreso")
                elif motivo != "Sueldos" and monto_total <= 0:
                    st.error("❌ El monto debe ser mayor a 0")
                else:
                    conn = get_connection()
                    cur = conn.cursor()
                    try:
                        if motivo == "Sueldos":
                            # Registrar cada sueldo como un egreso individual
                            for _, empleado in empleados_a_pagar.iterrows():
                                detalle = f"Sueldo de {empleado['Nombre']}"
                                cur.execute("""
                                    INSERT INTO egresos (sucursal, motivo, monto, observacion, fecha, detalle)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (st.session_state["sucursal"], motivo, empleado["Sueldo Base"], observacion, datetime.now(), detalle))
                        else:
                            # Registrar egreso normal
                            cur.execute("""
                                INSERT INTO egresos (sucursal, motivo, monto, observacion, fecha)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (st.session_state["sucursal"], motivo, monto_total, observacion, datetime.now()))
                        
                        conn.commit()
                        st.success(f"✅ Egreso de ${monto_total:,.2f} registrado correctamente")
                        
                        # Limpiar los campos
                        st.session_state.egreso_submitted = True
                        st.session_state.monto_egreso = 0.0
                        st.session_state.observacion = ""
                        
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar el egreso: {str(e)}")
                        conn.rollback()
                    finally:
                        conn.close()

    elif vista == "💰 Cierre de caja":
        st.title("💰 Cierre de Caja por Sucursal")
        # Establecer conexión al inicio de la vista
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            # Selector de fecha
            col_fecha, col_espacio = st.columns([1, 3])
            with col_fecha:
                fecha_seleccionada = st.date_input(
                    "Seleccionar fecha",
                    value=datetime.now().date(),
                    max_value=datetime.now().date()
                )
            
            # Consulta para obtener totales del día
            cur.execute("""
                WITH Totales AS (
                    SELECT 
                        CAST(SUM(CASE WHEN metodo_pago = 'Efectivo' THEN ingreso ELSE 0 END) AS FLOAT) as efectivo,
                        CAST(SUM(CASE WHEN metodo_pago IN ('Mercado Pago', 'Cuenta DNI') THEN ingreso ELSE 0 END) AS FLOAT) as digital,
                        CAST(SUM(CASE WHEN metodo_pago = 'Fiado' THEN monto ELSE 0 END) AS FLOAT) as fiado
                    FROM ventas 
                    WHERE DATE(fecha) = %s
                    AND sucursal = %s
                    AND metodo_pago != 'Cierre'
                ),
                TotalEgresos AS (
                    SELECT CAST(SUM(monto) AS FLOAT) as egresos
                    FROM egresos 
                    WHERE DATE(fecha) = %s
                    AND sucursal = %s
                ),
                CierreCaja AS (
                    SELECT 
                        monto as monto_cierre,
                        ingreso as diferencia
                    FROM ventas
                    WHERE DATE(fecha) = %s
                    AND sucursal = %s
                    AND metodo_pago = 'Cierre'
                )
                SELECT 
                    COALESCE(efectivo, 0) as efectivo,
                    COALESCE(digital, 0) as digital,
                    COALESCE(fiado, 0) as fiado,
                    COALESCE(egresos, 0) as egresos,
                    COALESCE(monto_cierre, 0) as monto_cierre,
                    COALESCE(diferencia, 0) as diferencia
                FROM Totales, TotalEgresos 
                LEFT JOIN CierreCaja ON true;
            """, (fecha_seleccionada, st.session_state["sucursal"], 
                 fecha_seleccionada, st.session_state["sucursal"],
                 fecha_seleccionada, st.session_state["sucursal"]))
            
            totales = cur.fetchone()
            if totales:
                efectivo, digital, fiado, egresos, monto_cierre, diferencia = totales
                
                # Mostrar resumen del día
                st.subheader("📊 Resumen del Día")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("💵 Ventas en Efectivo", f"${efectivo:,.2f}")
                    st.metric("💳 Ventas Digitales", f"${digital:,.2f}")
                    st.metric("📝 Ventas Fiadas", f"${fiado:,.2f}")
                    st.metric("➖ Egresos", f"${egresos:,.2f}")
                    
                    # Calcular saldo teórico en caja
                    saldo_teorico = efectivo - egresos
                    st.metric("💰 Saldo Teórico en Caja", f"${saldo_teorico:,.2f}")
                
                with col2:
                    # Verificar si ya existe un cierre
                    if monto_cierre > 0:
                        st.subheader("📋 Cierre Registrado")
                        st.metric("💰 Monto Contado", f"${monto_cierre:,.2f}")
                        if diferencia > 0:
                            st.info(f"📈 Sobrante en caja: ${diferencia:,.2f}")
                        elif diferencia < 0:
                            st.warning(f"📉 Faltante en caja: ${abs(diferencia):,.2f}")
                    else:
                        st.subheader("✍️ Registrar Cierre")
                        with st.form("form_cierre"):
                            monto_contado = st.number_input("Monto contado en efectivo", 
                                                          min_value=0.0, 
                                                          step=100.0,
                                                          format="%.2f")
                            
                            observaciones = st.text_area("Observaciones", height=100)
                            
                            submitted = st.form_submit_button("Registrar Cierre")
                            
                            if submitted:
                                # Calcular diferencia
                                diferencia = monto_contado - saldo_teorico
                                
                                # Registrar el cierre como una venta especial
                                cur.execute("""
                                    INSERT INTO ventas 
                                    (sucursal, monto, metodo_pago, ingreso, deuda, fecha)
                                    VALUES (%s, %s, 'Cierre', %s, 0, %s)
                                """, (
                                    st.session_state["sucursal"],
                                    monto_contado,
                                    diferencia,
                                    fecha_seleccionada
                                ))
                                
                                conn.commit()
                                st.success("✅ Cierre registrado correctamente")
                                
                                if abs(diferencia) > 0:
                                    if diferencia > 0:
                                        st.info(f"📈 Sobrante en caja: ${diferencia:,.2f}")
                                    else:
                                        st.warning(f"📉 Faltante en caja: ${abs(diferencia):,.2f}")
                                
                                time.sleep(1)
                                st.rerun()
            else:
                st.info("No hay movimientos registrados para la fecha seleccionada")
            
        finally:
            # Cerrar la conexión al finalizar
            cur.close()
            conn.close()

else:
    # Interfaz para cajeros
    st.title("📝 Registro de Ventas y Egresos")
    conn = get_connection()
    cur = conn.cursor()

    # Estilo personalizado para el botón y formulario
    st.markdown("""
        <style>
        .stButton>button {
            background-color: #F0FFF0;
            color: #2E8B57;
            padding: 10px 24px;
            border-radius: 5px;
            border: none;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            font-weight: 500;
        }
        .stButton>button:hover {
            background-color: #E0EEE0;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .stButton>button:active {
            background-color: #D1EED1;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        /* Quitar borde del formulario */
        .stForm {
            border: none !important;
            padding: 0 !important;
        }
        div[data-testid="stForm"] {
            border: none !important;
            padding: 0 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # -------- REGISTRO DE VENTAS --------
    st.subheader("Registrar venta")

    # Inicializar variables en session_state si no existen
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False

    if 'monto_compra' not in st.session_state:
        st.session_state.monto_compra = 0.0
    if 'dinero_entregado' not in st.session_state:
        st.session_state.dinero_entregado = 0.0
    if 'vuelto_calculado' not in st.session_state:
        st.session_state.vuelto_calculado = 0.0

    # Variables para el cálculo del vuelto fuera del formulario
    col1, col2 = st.columns(2)
    with col1:
        monto_compra = st.number_input("Monto de la compra", 
                                     min_value=0.0, 
                                     step=100.0, 
                                     key="monto_compra_key", 
                                     format="%.2f",
                                     value=0.0 if st.session_state.form_submitted else st.session_state.get('monto_compra', 0.0),
                                     on_change=calcular_vuelto)
    with col2:
        metodo_pago = st.selectbox("Método de pago", 
                                 ["Efectivo", "Mercado Pago", "Cuenta DNI", "Fiado"], 
                                 key="metodo_fuera",
                                 index=0 if st.session_state.form_submitted else None)

    # Variable para almacenar el vuelto calculado
    vuelto_calculado = 0.0
    dinero_entregado = 0.0
    cliente_fiado = None
    telefono_fiado = None

    # Mostrar campo de dinero entregado si es efectivo
    if metodo_pago == "Efectivo":
        dinero_entregado = st.number_input("Dinero entregado por el cliente", 
                                         min_value=0.0, 
                                         step=100.0, 
                                         key="dinero_entregado_key",
                                         format="%.2f",
                                         value=0.0 if st.session_state.form_submitted else st.session_state.get('dinero_entregado', 0.0),
                                         on_change=calcular_vuelto)
        
        # Mostrar el vuelto calculado
        if st.session_state.vuelto_calculado != 0:
            if st.session_state.vuelto_calculado >= 0:
                st.info(f"💵 Vuelto a entregar: ${st.session_state.vuelto_calculado:,.2f}")
            else:
                st.warning(f"⚠️ Falta dinero por cobrar: ${abs(st.session_state.vuelto_calculado):,.2f}")
    elif metodo_pago == "Fiado":
        col1, col2 = st.columns(2)
        with col1:
            cliente_fiado = st.text_input("Nombre del cliente",
                                        value="" if st.session_state.form_submitted else st.session_state.get('cliente_fiado', ""))
        with col2:
            telefono_fiado = st.text_input("Teléfono (opcional)",
                                         value="" if st.session_state.form_submitted else st.session_state.get('telefono_fiado', ""))

    # Crear un formulario para la venta
    with st.form("formulario_venta", clear_on_submit=True):
        submitted = st.form_submit_button("Registrar Venta")
        
        if submitted:
            if monto_compra <= 0:
                st.error("❌ El monto debe ser mayor a 0")
            elif metodo_pago == "Efectivo" and dinero_entregado < monto_compra:
                st.error("❌ El dinero entregado debe ser mayor o igual al monto de la compra")
            elif metodo_pago == "Fiado" and not cliente_fiado:
                st.error("❌ Debe ingresar el nombre del cliente para ventas fiadas")
            else:
                # Preparar valores según el método de pago
                if metodo_pago == "Efectivo":
                    ingreso = monto_compra
                    entregado = dinero_entregado
                    vuelto = vuelto_calculado
                    deuda = 0.0
                elif metodo_pago in ["Mercado Pago", "Cuenta DNI"]:
                    ingreso = monto_compra
                    entregado = monto_compra
                    vuelto = 0.0
                    deuda = 0.0
                else:  # Fiado
                    ingreso = 0.0
                    entregado = 0.0
                    vuelto = 0.0
                    deuda = monto_compra

                # Registrar la venta
                if registrar_venta(
                    st.session_state["sucursal"], 
                    monto_compra, 
                    metodo_pago, 
                    entregado, 
                    vuelto, 
                    ingreso, 
                    deuda,
                    cliente_fiado,
                    telefono_fiado
                ):
                    st.success("✅ Venta registrada correctamente")
                    # Marcar el formulario como enviado para limpiar los campos
                    st.session_state.form_submitted = True
                    # Limpiar los valores almacenados
                    st.session_state.monto_compra = 0.0
                    st.session_state.dinero_entregado = 0.0
                    st.session_state.cliente_fiado = ""
                    st.session_state.telefono_fiado = ""
                    time.sleep(0.5)
                    st.rerun()

    # Después del formulario de ventas
    st.markdown("---")  # Línea divisoria

    # -------- REGISTRO DE EGRESOS --------
    st.subheader("➖ Registrar Egreso")

    # Inicializar variables para egresos en session_state
    if 'egreso_submitted' not in st.session_state:
        st.session_state.egreso_submitted = False

    with st.form("form_egreso", clear_on_submit=True):
        motivo = st.selectbox("Motivo del egreso", 
                             ["Proveedor", "Sueldos", "Reparaciones", "Otros"] if st.session_state["rol"] == "dueño" else ["Proveedor", "Reparaciones", "Otros"],
                             key="motivo_egreso")
        
        # Campos específicos para sueldos (solo visible para el dueño)
        if motivo == "Sueldos" and st.session_state["rol"] == "dueño":
            st.write("📋 Detalle de sueldos")
            
            # Obtener empleados activos de la sucursal y su último pago
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                WITH UltimoPago AS (
                    SELECT 
                        e.detalle,
                        MAX(e.fecha) as ultimo_pago
                    FROM egresos e
                    WHERE e.motivo = 'Sueldos'
                    GROUP BY e.detalle
                )
                SELECT 
                    emp.id, 
                    emp.nombre, 
                    emp.sueldo_base,
                    up.ultimo_pago
                FROM empleados emp
                LEFT JOIN UltimoPago up ON up.detalle = CONCAT('Sueldo de ', emp.nombre)
                WHERE emp.sucursal = %s AND emp.activo = TRUE
                ORDER BY emp.nombre
            """, (st.session_state["sucursal"],))
            empleados_db = cur.fetchall()
            conn.close()
            
            if not empleados_db:
                st.warning("⚠️ No hay empleados registrados en esta sucursal")
                if st.button("➕ Agregar empleado"):
                    st.info("Función en desarrollo")
            else:
                # Crear DataFrame con los empleados
                df_empleados = pd.DataFrame(empleados_db, columns=["ID", "Nombre", "Sueldo Base", "Último Pago"])
                
                # Agregar columna de checkbox para seleccionar empleados a pagar
                df_empleados["Pagar"] = False
                
                # Mostrar la tabla con checkboxes editables
                df_empleados_editado = st.data_editor(
                    df_empleados,
                    column_config={
                        "ID": st.column_config.NumberColumn("ID", disabled=True),
                        "Nombre": st.column_config.TextColumn("Nombre", disabled=True),
                        "Sueldo Base": st.column_config.NumberColumn(
                            "Sueldo Base",
                            help="Monto base del sueldo",
                            min_value=0,
                            max_value=1000000,
                            step=1000,
                            format="$%d"
                        ),
                        "Último Pago": st.column_config.DatetimeColumn(
                            "Último Pago",
                            help="Fecha del último pago realizado",
                            format="DD/MM/YYYY HH:mm",
                            disabled=True
                        ),
                        "Pagar": st.column_config.CheckboxColumn(
                            "Pagar",
                            help="Seleccionar para pagar"
                        )
                    },
                    hide_index=True,
                    key="tabla_empleados"
                )
                
                # Calcular total a pagar de los empleados seleccionados
                empleados_a_pagar = df_empleados_editado[df_empleados_editado["Pagar"]]
                monto_total = empleados_a_pagar["Sueldo Base"].sum()
                
                if monto_total > 0:
                    st.info(f"💰 Total a pagar: ${monto_total:,.2f}")
                    
                    # Campo de observación
                    observacion = st.text_area(
                        "Observaciones (opcional)", 
                        height=100,
                        value="" if st.session_state.egreso_submitted else st.session_state.get('observacion', ""),
                        key="obs_sueldos"
                    )
                    
                    # Botón para confirmar el pago
                    if st.button("💸 Confirmar Pago de Sueldos"):
                        fecha_pago = datetime.now()
                        conn = get_connection()
                        cur = conn.cursor()
                        try:
                            for _, empleado in empleados_a_pagar.iterrows():
                                detalle = f"Sueldo de {empleado['Nombre']}"
                                cur.execute("""
                                    INSERT INTO egresos (sucursal, motivo, monto, observacion, fecha, detalle)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (st.session_state["sucursal"], "Sueldos", empleado["Sueldo Base"], 
                                     observacion, fecha_pago, detalle))
                                
                            conn.commit()
                            st.success(f"✅ Se han pagado {len(empleados_a_pagar)} sueldos por un total de ${monto_total:,.2f}")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al registrar los pagos: {str(e)}")
                            conn.rollback()
                        finally:
                            conn.close()
        else:
            monto_total = st.number_input("Monto del egreso", 
                                        min_value=0.0, 
                                        step=100.0, 
                                        format="%.2f",
                                        value=0.0 if st.session_state.egreso_submitted else st.session_state.get('monto_egreso', 0.0))
        
        # Campo de observación
        observacion = st.text_area("Observaciones (opcional)", 
                                  height=100,
                                  value="" if st.session_state.egreso_submitted else st.session_state.get('observacion', ""))

        submitted = st.form_submit_button("Registrar Egreso")
        
        if submitted:
            if motivo == "Sueldos" and not empleados_a_pagar.empty:
                st.error("❌ Debe pagar todos los sueldos antes de registrar el egreso")
            elif motivo != "Sueldos" and monto_total <= 0:
                st.error("❌ El monto debe ser mayor a 0")
            else:
                conn = get_connection()
                cur = conn.cursor()
                try:
                    if motivo == "Sueldos":
                        # Registrar cada sueldo como un egreso individual
                        for _, empleado in empleados_a_pagar.iterrows():
                            detalle = f"Sueldo de {empleado['Nombre']}"
                            cur.execute("""
                                INSERT INTO egresos (sucursal, motivo, monto, observacion, fecha, detalle)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (st.session_state["sucursal"], motivo, empleado["Sueldo Base"], observacion, datetime.now(), detalle))
                    else:
                        # Registrar egreso normal
                        cur.execute("""
                            INSERT INTO egresos (sucursal, motivo, monto, observacion, fecha)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (st.session_state["sucursal"], motivo, monto_total, observacion, datetime.now()))
                    
                    conn.commit()
                    st.success(f"✅ Egreso de ${monto_total:,.2f} registrado correctamente")
                    
                    # Limpiar los campos
                    st.session_state.egreso_submitted = True
                    st.session_state.monto_egreso = 0.0
                    st.session_state.observacion = ""
                    
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar el egreso: {str(e)}")
                    conn.rollback()
                finally:
                    conn.close()

conn.close()
