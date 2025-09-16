import streamlit as st
import pandas as pd
import pydeck as pdk
import hashlib
import glob
import matplotlib.pyplot as plt

st.set_page_config(page_title="Dashboard Maestro RTM", layout="wide")
st.title("📍 Dashboard Maestro RTM")

# Carga de datos

df = pd.concat([pd.read_csv(f) for f in glob.glob("data/salidas_por_centro/*.csv")], ignore_index=True)

# Sidebar: filtros
st.sidebar.header("Filtros")
uo = st.sidebar.selectbox("Unidad Operativa", options=df['CENTRO'].dropna().unique())

figuras_disponibles = df['Descripción Tipo'].dropna().unique()
figura = st.sidebar.selectbox("Figura Comercial", options=sorted(figuras_disponibles))
colorear_por = st.sidebar.selectbox("Colorear puntos por", ["Ninguno", "Ruta ZPV", "Descripción Tipo"])
estilo_mapa = st.sidebar.selectbox("Estilo de mapa base", ["OpenStreetMap", "MapTiler"])
pitch_value = st.sidebar.slider("Inclinación del mapa (pitch)", min_value=0, max_value=60, value=0)

# Filtrado de datos
df_filtrado = df[(df['CENTRO'] == uo) & (df['Descripción Tipo'] == figura)]
rutas_disponibles = df_filtrado['Ruta ZPV'].dropna().unique()
rutas_disponibles = ["Todas"] + sorted(rutas_disponibles.tolist())

ruta = st.sidebar.selectbox("Ruta", options=sorted(rutas_disponibles))

if ruta != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Ruta ZPV'] == ruta]
    df_filtrado = df[(df['Ruta ZPV'] == ruta)]

df_filtrado = df_filtrado.dropna(subset=["latitud", "longitud"])

if df_filtrado.empty:
    st.warning("⚠️ No hay clientes para los filtros seleccionados.")
    st.stop()

st.markdown(f"**Clientes encontrados:** {len(df_filtrado):,}")

# Función de color
def string_to_color(s):
    h = int(hashlib.md5(str(s).encode()).hexdigest(), 16)
    return [h % 255, (h >> 8) % 255, (h >> 16) % 255, 200]

# Asignar colores
if colorear_por == "Ruta ZPV":
    df_filtrado["color"] = df_filtrado["Ruta ZPV"].apply(string_to_color)
elif colorear_por == "Descripción Tipo":
    df_filtrado["color"] = df_filtrado["Descripción Tipo"].apply(string_to_color)
else:
    df_filtrado["color"] = [[255, 0, 0, 200]] * len(df_filtrado)

# Tooltip
tooltip = {
    "html": """
        <b>Cliente:</b> {ID_SAP}<br>
        <b>Nombre:</b> {CLIENTE}<br>
        <b>Ruta:</b> {Ruta ZPV}<br>
        <b>Figura:</b> {Descripción Tipo}<br>
        <b>GEC:</b> {GEC_RTM}<br>
        <b>Canal:</b> {GRUPO_RM1}
    """,
    "style": {
        "backgroundColor": "rgba(0, 0, 0, 0.7)",
        "color": "white",
        "fontSize": "12px"
    }
}

# Vista inicial del mapa
view = pdk.ViewState(
    latitude=df_filtrado['latitud'].mean(),
    longitude=df_filtrado['longitud'].mean(),
    zoom=9,
    pitch=pitch_value,
)

# Capa de puntos
puntos_layer = pdk.Layer(
    "ScatterplotLayer",
    data=df_filtrado,
    get_position='[longitud, latitud]',
    get_radius=1,
    radius_scale=6,
    radius_min_pixels=2,
    radius_max_pixels=40,
    get_fill_color='color',
    pickable=True
)

# Estilo del mapa
if estilo_mapa == "OpenStreetMap":
    map_style = None
    base_map = {
        "type": "raster",
        "tileSize": 256,
        "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"]
    }
elif estilo_mapa == "MapTiler":
    map_style = f"https://api.maptiler.com/maps/streets/style.json?key=wPVtmjKe1dltbddMou9m"
    base_map = {
        "type": "raster",
        "tileSize": 256,
        "tiles": [
            "https://api.maptiler.com/maps/streets/256/{z}/{x}/{y}.png?key=wPVtmjKe1dltbddMou9m"
        ],
        "attribution": "© OpenStreetMap contributors © MapTiler"
    }

deck = pdk.Deck(
    map_style=map_style,
    initial_view_state=view,
    layers=[puntos_layer],
    tooltip=tooltip
)
deck.base_map = base_map

# Mostrar mapa
st.subheader("🗺️ Clientes punteados en el mapa")
st.pydeck_chart(deck)

# Crear dos columnas para mostrar radar y tabla lado a lado
col1, col2 = st.columns([2, 3])  # puedes ajustar proporciones

with col1:
    st.subheader("🕸️ Promedio de visitas por día")

    import plotly.graph_objects as go

    # Nombres de días y columnas
    columnas_dias = ['ZPV_L', 'ZPV_M', 'ZPV_R', 'ZPV_J', 'ZPV_V', 'ZPV_S']
    nombres_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

    # Calcular promedios por día
    promedios = df_filtrado[columnas_dias].sum() / df_filtrado['Ruta ZPV'].nunique()
    valores = promedios.values.tolist()

    # Cerrar el ciclo en el gráfico (repetir el primer valor al final)
    valores.append(valores[0])
    nombres_dias_cerrado = nombres_dias + [nombres_dias[0]]

    # Texto de los valores a mostrar sobre cada punto
    valores_texto = [f"{v:.1f}" for v in valores]

    # Crear gráfico radar
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=valores,
        theta=nombres_dias_cerrado,
        fill='toself',
        name='Promedio visitas',
        line=dict(color='royalblue', width=3),
        marker=dict(size=6, color='royalblue'),
        text=valores_texto,
        textposition="middle center",
        mode='lines+markers+text',
        hovertemplate='%{theta}: %{r:.1f}<extra></extra>'
    ))

    fig.update_layout(
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(visible=True, showticklabels=False, showgrid=True),
            angularaxis=dict(
                tickfont=dict(size=13, color='white'),
                showline=True,
                linewidth=1,
                showgrid=True
            )
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        height=500,
        margin=dict(l=30, r=30, t=30, b=30)
    )

    st.plotly_chart(fig, use_container_width=True)

with col2:
    # Detección de rutas fuera de parámetro por promedio
    st.subheader("🚨 Rutas fuera de parámetro")

    # Calcular visitas por ruta
    df_visitas = df_filtrado.groupby('Ruta ZPV')[columnas_dias].sum()

    # Calcular promedio de visitas por día por ruta
    df_visitas['Promedio Diario'] = df_visitas[columnas_dias].mean(axis=1).round(0)

    # Filtrar rutas fuera de parámetro por promedio
    fuera_parametro = df_visitas[(df_visitas['Promedio Diario'] > 58) | (df_visitas['Promedio Diario'] < 48)]

    # Mostrar resultados
    st.write(f"Rutas fuera de parámetro encontradas: **{len(fuera_parametro)}**")
    st.dataframe(fuera_parametro.reset_index())

# Lista de clientes
st.subheader("📋 Lista de Clientes")
st.dataframe(df_filtrado[["ID_SAP", "CLIENTE", "Ruta ZPV", "Descripción Tipo", "latitud", "longitud"]])