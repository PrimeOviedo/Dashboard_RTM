import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
import hashlib
import glob
import streamlit.components.v1 as components

# Este debe ir siempre al inicio
st.set_page_config(page_title="Dashboard Maestro RTM", layout="wide")
st.title("📍 Dashboard Maestro RTM")

# Carga de datos robusta
df = pd.concat(
    [pd.read_csv(f, low_memory=False, dtype=str) for f in glob.glob("data/salidas_por_centro/*.csv")],
    ignore_index=True
)

df.rename(columns={"Latitud Final": "latitud", "Longitud Final": "longitud"}, inplace=True)

# ───── Filtros dependientes en Sidebar ───────────────────────


def multiselect_all(label, options, key, default_all=True):
    options = [str(o) for o in options]  # asegurar strings
    select_all = st.checkbox(f"Seleccionar todo: {label}", value=default_all, key=f"all_{key}")
    if select_all:
        return st.multiselect(label, options=options, default=options, key=key)
    else:
        return st.multiselect(label, options=options, key=key)

with st.sidebar.expander("Filtros principales", expanded=False):
    # 1) Unidad Operativa
    uo_opts = sorted(df['CENTRO'].dropna().unique().tolist())
    uo_sel = st.multiselect("Unidad Operativa", options=uo_opts, default=uo_opts[:1])

    # Subconjunto por UO (si no selecciona nada → DataFrame vacío)
    if uo_sel:
        df_uo = df[df['CENTRO'].isin(uo_sel)].copy()
    else:
        df_uo = df.iloc[0:0].copy()

    # 2) Figura Comercial
    figura_opts = sorted(df_uo['Descripción Tipo'].dropna().astype(str).unique().tolist())
    fig_sel = multiselect_all("Figura Comercial", figura_opts, key="figuras", default_all=True)
    df_fig = df_uo[df_uo['Descripción Tipo'].astype(str).isin(fig_sel)] if fig_sel else df_uo.iloc[0:0]

    # 3) Ruta
    ruta_opts = sorted(df_fig['RUTA'].dropna().astype(str).unique().tolist())
    ruta_sel = multiselect_all("RUTA", ruta_opts, key="rutas", default_all=True)
    df_ruta = df_fig[df_fig['RUTA'].astype(str).isin(ruta_sel)] if ruta_sel else df_fig.iloc[0:0]

    # 4) Grupo RM1
    grupo_rm1_opts = sorted(df_ruta['GRUPO_RM1'].dropna().astype(str).unique().tolist())
    grupo_rm1_sel = multiselect_all("Grupo RM1", grupo_rm1_opts, key="grm1", default_all=True)
    df_filtrado = df_ruta[df_ruta['GRUPO_RM1'].astype(str).isin(grupo_rm1_sel)] if grupo_rm1_sel else df_ruta.iloc[0:0]

with st.sidebar.expander("Parámetros", expanded=False):
    # 1) Metodo de venta
    mtdo_opts = sorted(df_filtrado['MÉTODO_VENTA'].dropna().astype(str).unique().tolist())
    mtdo_sel = multiselect_all("Método de Venta", mtdo_opts, key="metodo", default_all=True)
    df_filtrado = df_filtrado[df_filtrado['MÉTODO_VENTA'].astype(str).isin(mtdo_sel)] if mtdo_sel else df_filtrado.iloc[0:0]

    # 2) Ritmo
    rit_opts = sorted(df_filtrado['RITMO'].dropna().astype(str).unique().tolist())
    rit_sel = multiselect_all("Ritmo", rit_opts, key="ritmo", default_all=True)
    df_filtrado = df_filtrado[
    df_filtrado['RITMO'].astype(str).isin(rit_sel)] if rit_sel else df_filtrado.iloc[0:0]

with st.sidebar.expander("Configuración de mapa", expanded=False):
    # Configuración de mapa
    estilo_mapa = st.selectbox("Estilo de mapa base", ["OpenStreetMap", "MapTiler"])
    pitch_value = st.slider("Inclinación del mapa (pitch)", min_value=0, max_value=60, value=0)
    colorear_por = st.selectbox("Colorear puntos por", ["Ninguno", "RUTA", "Descripción Tipo", "GEC_RTM", "GRUPO_RM1"])

# Seguridad: coordenadas
df_filtrado["latitud"] = pd.to_numeric(df_filtrado["latitud"], errors="coerce")
df_filtrado["longitud"] = pd.to_numeric(df_filtrado["longitud"], errors="coerce")
df_filtrado = df_filtrado.dropna(subset=["latitud", "longitud"])

st.subheader(f"Indicadores para la UO: `{uo_sel}`")
if df_filtrado.empty:
    st.warning("⚠️ No hay registros para los filtros seleccionados.")
    st.stop()
else:
    st.success(f"🔎 Registros encontrados: **{len(df_filtrado):,}**")


def string_to_color(s):
    h = int(hashlib.md5(str(s).encode()).hexdigest(), 16)
    return [h % 255, (h >> 8) % 255, (h >> 16) % 255, 200]

# Asignar colores
if colorear_por != "Ninguno":
    df_filtrado["color"] = df_filtrado[colorear_por].apply(string_to_color)
else:
    df_filtrado["color"] = [[255, 0, 0, 200]] * len(df_filtrado)

tooltip = {
    "html": """
        <b>Cliente:</b> {ID_SAP}<br>
        <b>Nombre:</b> {CLIENTE}<br>
        <b>Ruta:</b> {RUTA}<br>
        <b>Figura:</b> {Descripción Tipo}<br>
        <b>GEC:</b> {GEC_RTM}<br>
        <b>Canal:</b> {GRUPO_RM1}
    """,
    "style": {"backgroundColor": "rgba(0,0,0,0.7)", "color": "white", "fontSize": "12px"}
}

# Columna izquierda: mapa
col1_1, col1_2 = st.columns([4, 3])
with col1_1:
    view = pdk.ViewState(latitude=df_filtrado['latitud'].mean(skipna=True),
                         longitude=df_filtrado['longitud'].mean(skipna=True),
                         zoom=9, pitch=pitch_value)
    puntos_layer = pdk.Layer("ScatterplotLayer",
                             data=df_filtrado,
                             get_position='[longitud, latitud]',
                             get_radius=1,
                             radius_scale=6,
                             radius_min_pixels=2,
                             radius_max_pixels=40,
                             get_fill_color='color',
                             pickable=True)
    if estilo_mapa == "OpenStreetMap":
        map_style = None
        base_map = {"type": "raster", "tileSize": 256, "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"]}
    else:
        map_style = "https://api.maptiler.com/maps/streets/style.json?key=wPVtmjKe1dltbddMou9m"
        base_map = {"type": "raster",
                    "tileSize": 256,
                    "tiles": ["https://api.maptiler.com/maps/streets/256/{z}/{x}/{y}.png?key=wPVtmjKe1dltbddMou9m"],
                    "attribution": "© OpenStreetMap contributors © MapTiler"}
    deck = pdk.Deck(map_style=map_style, initial_view_state=view, layers=[puntos_layer], tooltip=tooltip)
    deck.base_map = base_map
    st.subheader("🗺️ Clientes punteados en el mapa")
    st.pydeck_chart(deck, use_container_width=True, height=600)

    # Leyenda de colores
    def rgba_to_css(rgba_list): r, g, b, a = rgba_list; return f"rgba({r},{g},{b},{a/255:.2f})"
    if colorear_por != "Ninguno":
        if "color_map_field" not in st.session_state or st.session_state["color_map_field"] != colorear_por:
            st.session_state["color_map_field"] = colorear_por
            categorias_globales = sorted(df[colorear_por].dropna().astype(str).unique())
            st.session_state["color_map"] = {c: rgba_to_css(string_to_color(c)) for c in categorias_globales}
        color_map = st.session_state["color_map"]
        counts = df_filtrado[colorear_por].dropna().astype(str).value_counts()
        st.markdown(f"### 🎨 Leyenda de colores — *Color por:* `{colorear_por}`")
        legend_html = "<div class='leyenda-wrap'><div class='leyenda'>"
        for categoria, cnt in counts.items():
            color = color_map.get(str(categoria), "rgba(200,200,200,0.80)")
            legend_html += f"<div class='item'><div class='color-box' style='background-color:{color};'></div><span>{categoria} <span class='small'>({cnt:,})</span></span></div>"
        legend_html += "</div></div>"
        components.html(legend_html, height=120, scrolling=True)
    else:
        st.info("Selecciona un campo en **Colorear puntos por** para ver la leyenda.")

# Columna derecha: Sunburst
with col1_2:
    st.markdown("### Datos de grupo de clientes")
    df_treemap = df_filtrado.copy()
    for col in ["CENTRO", "MÉTODO_VENTA", "RITMO", "FV"]:
        df_treemap[col] = df_treemap[col].fillna("Sin dato").astype(str)
    df_treemap['FS'] = df_treemap['FV'].str.len()
    df_sunburst = (df_treemap.groupby(["CENTRO", "MÉTODO_VENTA", "RITMO", "FS"])
                   .agg(clientes=("ID_SAP", "nunique")).reset_index())
    df_sunburst["peso"] = 1
    df_sunburst["Ritmo_label"] = "Ritmo " + df_sunburst["RITMO"].astype(str)
    df_sunburst["FS_label"] = "FS " + df_sunburst["FS"].astype(str)
    fig = px.sunburst(df_sunburst,
                      path=["CENTRO", "MÉTODO_VENTA", "Ritmo_label", "FS_label"],
                      values="peso", custom_data=["clientes"], color="MÉTODO_VENTA",
                      maxdepth=4,
                      color_discrete_map={'(?)':'#282a2e','1DA':'#37b741','2DA':'#cfb53a',
                                          '3DA':'#ff0000','NO DATA':'#ff0000','-':'#ff0000'})
    fig.update_traces(hovertemplate="<b>%{label}</b><br><extra></extra>")
    fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), width=400, height=400)  # 👈 aquí
    st.plotly_chart(fig, width="stretch")

# Radar y tabla
col1, col2 = st.columns([3, 4])
with col1:
    st.subheader("🕸️ Promedio de visitas por día")
    columnas_dias = ['L','M','R','J','V','S']
    nombres_dias = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado']
    df_filtrado[columnas_dias] = df_filtrado[columnas_dias].apply(pd.to_numeric, errors="coerce")
    rutas_unicas = df_filtrado['RUTA'].nunique()
    promedios = df_filtrado[columnas_dias].sum(numeric_only=True) / max(rutas_unicas, 1)
    valores = promedios.values.tolist()
    valores.append(valores[0])
    nombres_dias_cerrado = nombres_dias + [nombres_dias[0]]
    valores_texto = [f"{v:.1f}" for v in valores]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=valores, theta=nombres_dias_cerrado, fill='toself',
                                  name='Promedio visitas',
                                  line=dict(color='rgba(69,255,227,0.7)', width=3),
                                  marker=dict(size=6, color='rgba(69,255,227,0.7)'),
                                  text=valores_texto, textposition="middle center",
                                  mode='lines+markers+text',
                                  hovertemplate='%{theta}: %{r:.1f}<extra></extra>'))
    fig.update_layout(polar=dict(bgcolor='rgba(0,0,0,0)',
                                 radialaxis=dict(visible=True, showticklabels=False),
                                 angularaxis=dict(tickfont=dict(size=13,color='white'),
                                                  showline=True,linewidth=1,showgrid=True)),
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      showlegend=False, height=500, margin=dict(l=40,r=40,t=40,b=40))
    st.plotly_chart(fig, width='strech')

with col2:
    df_visitas = df_filtrado.groupby('RUTA')[columnas_dias].sum(numeric_only=True)
    df_visitas['Promedio Diario'] = df_visitas[columnas_dias].mean(axis=1).round(0).astype(int)
    fuera_parametro = df_visitas[(df_visitas['Promedio Diario'] > 58) | (df_visitas['Promedio Diario'] < 48)]
    en_parametro = df_visitas[(df_visitas['Promedio Diario'] >= 48) & (df_visitas['Promedio Diario'] <= 58)]
    st.subheader(f"🗺️ Total de rutas: **{len(fuera_parametro)+len(en_parametro)}**")
    st.write(f"Rutas en parámetro encontradas: **{len(en_parametro)}**")

    def color_dias(val):
        if val < 48: return 'background-color: rgb(255,222,69,0.8); color: black;'
        elif val > 58: return 'background-color: rgb(255,69,69,0.8); color: white;'
        return 'background-color: rgb(69,255,85,0.7); color: black;'

    def styled(df_in):
        return (df_in.reset_index().style
                .map(color_dias, subset=columnas_dias+['Promedio Diario'])
                .set_properties(**{'text-align':'center'})
                .set_table_styles([{'selector':'th','props':[('text-align','center')]}])
                .hide(axis="index"))

    st.dataframe(styled(en_parametro), width='stretch', height=200)
    if not fuera_parametro.empty:
        st.write(f"Rutas fuera de parámetro encontradas: **{len(fuera_parametro)}**")
        st.dataframe(styled(fuera_parametro), width='stretch', height=200)

# Lista de clientes
st.subheader("📋 Lista de Clientes")
st.dataframe(df_filtrado[["ID_SAP", "CLIENTE", "RUTA", "Descripción Tipo", "latitud", "longitud"]])