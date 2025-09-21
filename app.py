from operator import index

import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import hashlib
import glob
import streamlit.components.v1 as components



# Este debe ir siempre al inicio
st.set_page_config(page_title="Dashboard Maestro RTM", layout="wide")

# Título de la página
st.title("📍 Dashboard Maestro RTM")

# Carga de datos

df = pd.concat([pd.read_csv(f) for f in glob.glob("data/salidas_por_centro/*.csv")], ignore_index=True)

# ───── Filtros dependientes en Sidebar (con multiselect) ───────────────────────
st.sidebar.header("Filtros")

def multiselect_all(label, options, key, default_all=True):
    """
    Multiselect con checkbox 'Seleccionar todo'.
    - options: lista (ordenada) de opciones disponibles
    - default_all: si True, por defecto marca todo
    Devuelve: lista de seleccionados (list[str])
    """
    options = [str(o) for o in options]  # asegurar strings
    select_all = st.sidebar.checkbox(f"Seleccionar todo: {label}", value=default_all, key=f"all_{key}")
    if select_all:
        return st.sidebar.multiselect(label, options=options, default=options, key=key)
    else:
        return st.sidebar.multiselect(label, options=options, key=key)

# 1) Unidad Operativa (dejamos selectbox simple, como tenías)
uo_opts = sorted(df['CENTRO'].dropna().unique().tolist())
uo = st.sidebar.selectbox("Unidad Operativa", options=uo_opts)

# Subconjunto por UO
df_uo = df[df['CENTRO'] == uo].copy()

# 2) Figura Comercial (multiselect)
figura_opts = sorted(df_uo['Descripción Tipo'].dropna().astype(str).unique().tolist())
fig_sel = multiselect_all("Figura Comercial", figura_opts, key="figuras", default_all=True)

# Si el usuario no elige nada, devolvemos vacío explícitamente
if len(fig_sel) == 0:
    df_fig = df_uo.iloc[0:0].copy()
else:
    df_fig = df_uo[df_uo['Descripción Tipo'].astype(str).isin(fig_sel)].copy()

# 3) Ruta ZPV (multiselect dependiente de Figuras)
ruta_opts = sorted(df_fig['Ruta ZPV'].dropna().astype(str).unique().tolist())
ruta_sel = multiselect_all("Ruta ZPV", ruta_opts, key="rutas", default_all=True)

if len(ruta_sel) == 0:
    df_ruta = df_fig.iloc[0:0].copy()
else:
    df_ruta = df_fig[df_fig['Ruta ZPV'].astype(str).isin(ruta_sel)].copy()

# 4) Grupo RM1 (multiselect dependiente de Rutas)
grupo_rm1_opts = sorted(df_ruta['GRUPO_RM1'].dropna().astype(str).unique().tolist())
grupo_rm1_sel = multiselect_all("Grupo RM1", grupo_rm1_opts, key="grm1", default_all=True)

if len(grupo_rm1_sel) == 0:
    df_filtrado = df_ruta.iloc[0:0].copy()
else:
    df_filtrado = df_ruta[df_ruta['GRUPO_RM1'].astype(str).isin(grupo_rm1_sel)].copy()

# Seguridad: eliminar filas sin coordenadas
df_filtrado = df_filtrado.dropna(subset=["latitud", "longitud"])

st.subheader(f"Indicadores para la UO: `{uo}`")

# Validación final
if df_filtrado.empty:
    st.warning("⚠️ No hay registros para los filtros seleccionados.")
    st.stop()
else:
    st.success(f"🔎 Registros encontrados: **{len(df_filtrado):,}**")

estilo_mapa = st.sidebar.selectbox("Estilo de mapa base", ["OpenStreetMap", "MapTiler"])
pitch_value = st.sidebar.slider("Inclinación del mapa (pitch)", min_value=0, max_value=60, value=0)

colorear_por = st.sidebar.selectbox("Colorear puntos por", ["Ninguno", "Ruta ZPV", "Descripción Tipo", "GEC_RTM", "GRUPO_RM1"])

# Función de color
def string_to_color(s):
    h = int(hashlib.md5(str(s).encode()).hexdigest(), 16)
    return [h % 255, (h >> 8) % 255, (h >> 16) % 255, 200]

# Asignar colores
if colorear_por == "Ruta ZPV":
    df_filtrado["color"] = df_filtrado["Ruta ZPV"].apply(string_to_color)
elif colorear_por == "Descripción Tipo":
    df_filtrado["color"] = df_filtrado["Descripción Tipo"].apply(string_to_color)
elif colorear_por == "GEC_RTM":
    df_filtrado["color"] = df_filtrado["GEC_RTM"].apply(string_to_color)
elif colorear_por == "GRUPO_RM1":
    df_filtrado["color"] = df_filtrado["GRUPO_RM1"].apply(string_to_color)
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

# Crear dos columnas para mostrar radar y tabla lado a lado
col1_1, col1_2 = st.columns([4, 3])  # puedes ajustar proporciones

with col1_1:
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

    # ========== LEYENDA (render HTML real con components.html) ==========
    def rgba_to_css(rgba_list):
        """Convierte [R,G,B,A 0..255] a 'rgba(r,g,b,a)' con a en 0..1 para CSS."""
        r, g, b, a = rgba_list
        return f"rgba({r},{g},{b},{a/255:.2f})"

    if colorear_por != "Ninguno" and colorear_por in df_filtrado.columns:
        # Mapa de colores estable para que no cambie entre filtros
        if "color_map_field" not in st.session_state or st.session_state["color_map_field"] != colorear_por:
            st.session_state["color_map_field"] = colorear_por
            categorias_globales = sorted(df[colorear_por].dropna().astype(str).unique())
            st.session_state["color_map"] = {c: rgba_to_css(string_to_color(c)) for c in categorias_globales}

        color_map = st.session_state["color_map"]

        # Conteos en el subconjunto filtrado
        counts = (
            df_filtrado[colorear_por]
            .dropna()
            .astype(str)
            .value_counts()
        )

        # Título usando markdown (solo el título)
        st.markdown(f"### 🎨 Leyenda de colores — *Color por:* `{colorear_por}`")

        # HTML+CSS para la leyenda — se renderiza como HTML real con components.html
        legend_html = """
        <html>
        <head>
          <style>
            :root {
              /* Intenta heredar tipografías del tema de Streamlit: */
              --font: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Helvetica Neue, Arial, sans-serif;
            }
            body {
              margin: 0;
              padding: 0;
              font-family: var(--font), sans-serif !important;
              color: inherit;
              background: transparent;
              color: #fff;
            }
            .leyenda-wrap{
              max-height: 180px; overflow-y: auto;
              padding: 10px 12px; border-radius: 10px;
              background: rgba(255,255,255,0.03);
              border: 1px solid rgba(255,255,255,0.08);
            }
            .leyenda{ display:flex; flex-wrap:wrap; gap:10px; }
            .item{
              display:flex; align-items:center; gap:8px;
              padding:4px 8px; background: rgba(255,255,255,0.04);
              border:1px solid rgba(255,255,255,0.08); border-radius:6px;
              font-size:13px; color: inherit;
              font-family: var(--font), sans-serif !important;
              white-space: nowrap;
            }
            .color-box{
              width:14px; height:14px; border-radius:3px;
              border:1px solid rgba(255,255,255,0.4);
              flex: 0 0 auto;
            }
            .small{ opacity:.8; font-size:12px; margin-left:4px; }
          </style>
        </head>
        <body>
          <div class="leyenda-wrap">
            <div class="leyenda">
        """

        for categoria, cnt in counts.items():
            color = color_map.get(str(categoria), "rgba(200,200,200,0.80)")
            legend_html += f"""
              <div class="item">
                <div class="color-box" style="background-color:{color};"></div>
                <span>{categoria}<span class="small">({cnt:,})</span></span>
              </div>
            """

        legend_html += """
            </div>
          </div>
        </body>
        </html>
        """

        # Render como HTML real (no st.markdown ni st.code)
        components.html(legend_html, height=100, scrolling=True)

    else:
        st.info("Selecciona un campo en **Colorear puntos por** para ver la leyenda.")

with col1_2:
    st.markdown(f"### Datos de grupo de clientes")
    # ---- Gráfico Sunburst

    # Copiar dataframe y normalizar columnas clave
    df_treemap = df_filtrado.copy()

    # Normalizar valores nulos y convertir a string
    for col in ["CENTRO", "Método_venta ZPV", "Ritmo ZPV", "Fv ZPV"]:
        if col in df_treemap.columns:
            df_treemap[col] = df_treemap[col].fillna("Sin dato").astype(str)

    # Calcular frecuencia de visita (cuántos días a la semana)
    df_treemap['FS'] = df_treemap['Fv ZPV'].str.len()

    # Agrupar y contar clientes reales
    df_sunburst = (
        df_treemap
        .groupby(["CENTRO", "Método_venta ZPV", "Ritmo ZPV", "FS"])
        .agg(clientes=("ID_SAP", "nunique"))
        .reset_index()
    )

    # columna para geometría balanceada
    df_sunburst["peso"] = 1

    # Creamos etiquetas personalizadas uniendo nombre del nivel + valor
    df_sunburst["Ritmo_label"] = "Ritmo " + df_sunburst["Ritmo ZPV"].astype(str)
    df_sunburst["FS_label"] = "FS " + df_sunburst["FS"].astype(str)

    fig = px.sunburst(
        df_sunburst,
        path=["CENTRO", "Método_venta ZPV", "Ritmo_label", "FS_label"],
        values="peso",
        custom_data=["clientes"],
        color="Método_venta ZPV",
        color_discrete_map={
            '(?)': '#282a2e',
            '1DA': '#37b741',
            '2DA': '#cfb53a',
            '3DA': '#ff0000',
            'NO DATA': '#ff0000',
            '-': '#ff0000'
        },
        maxdepth=4
    )

    # Mostrar también clientes en hover
    fig.update_traces(
        hovertemplate="<b>%{label}</b><extra></extra>"
    )

    # Mostrar gráfico en Streamlit
    st.plotly_chart(fig, width="stretch")



# Crear dos columnas para mostrar radar y tabla lado a lado
col1, col2 = st.columns([3, 4])  # puedes ajustar proporciones

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
        line=dict(color='rgba(69, 255, 227, 0.7)', width=3),
        marker=dict(size=6, color='rgba(69, 255, 227, 0.7)'),
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
        margin=dict(l=40, r=40, t=40, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)

with col2:
    # Agrupar visitas por ruta
    df_visitas = df_filtrado.groupby('Ruta ZPV')[columnas_dias].sum()

    # Calcular promedio diario
    df_visitas['Promedio Diario'] = df_visitas[columnas_dias].mean(axis=1).round(0).astype(int)

    # Filtrar rutas fuera de parámetro
    fuera_parametro = df_visitas[(df_visitas['Promedio Diario'] > 58) | (df_visitas['Promedio Diario'] < 48)]
    en_parametro = df_visitas[(df_visitas['Promedio Diario'] >= 48) & (df_visitas['Promedio Diario'] <= 58)]

    st.subheader(f"🗺️ Total de rutas: **{len(fuera_parametro)+len(en_parametro)}**")
    st.write(f"Rutas en de parámetro encontradas: **{len(en_parametro)}**")


    # Función de color condicional
    def color_dias(val):
        if val < 48:
            return 'background-color: rgb(255, 222, 69, 0.8); color: black;'
        elif val > 58:
            return 'background-color: rgb(255, 69, 69, 0.8); color: white;'

        return 'background-color: rgb(69, 255, 85, 0.7); color: black;'

    if len(fuera_parametro) >0:

        # Aplicar estilo
        styled_df = (
            en_parametro
            .reset_index()
            .style
            .applymap(color_dias, subset=columnas_dias + ['Promedio Diario'])
            .set_properties(**{'text-align': 'center'})  # Centrar contenido
            .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
            .hide(axis="index")  # Ocultar índice
        )

        # Mostrar tabla con desplazamiento y estilo integrado
        st.dataframe(styled_df, use_container_width=True, height=200)

        st.write(f"Rutas fuera de parámetro encontradas: **{len(fuera_parametro)}**")

        # Aplicar estilo
        styled_df_2 = (
            fuera_parametro
            .reset_index()
            .style
            .applymap(color_dias, subset=columnas_dias + ['Promedio Diario'])
            .set_properties(**{'text-align': 'center'})  # Centrar contenido
            .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
            .hide(axis="index")  # Ocultar índice
        )
    else:
        # Aplicar estilo
        styled_df = (
            en_parametro
            .reset_index()
            .style
            .applymap(color_dias, subset=columnas_dias + ['Promedio Diario'])
            .set_properties(**{'text-align': 'center'})  # Centrar contenido
            .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
            .hide(axis="index")  # Ocultar índice
        )

        # Mostrar tabla con desplazamiento y estilo integrado
        st.dataframe(styled_df, use_container_width=True, height=500)

# Lista de clientes
st.subheader("📋 Lista de Clientes")
st.dataframe(df_filtrado[["ID_SAP", "CLIENTE", "Ruta ZPV", "Descripción Tipo", "latitud", "longitud"]])