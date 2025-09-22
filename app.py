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

    # Valores preseleccionados
    default_figuras = ["Preventa Comercial", "Preventa Comercial On Premise"]

    # Verificar que existan en las opciones
    default_figuras = [f for f in default_figuras if f in figura_opts]

    fig_sel = st.multiselect(
        "Figura Comercial",
        options=figura_opts,
        default=default_figuras,  # 👈 solo estos dos por defecto
        key="figuras"
    )

    df_fig = df_uo[df_uo['Descripción Tipo'].astype(str).isin(fig_sel)] if fig_sel else df_uo.iloc[0:0]

    # 3) Ruta
    ruta_opts = sorted(df_fig['RUTA'].dropna().astype(str).unique().tolist())
    ruta_sel = multiselect_all("RUTA", ruta_opts, key="rutas", default_all=True)
    df_ruta = df_fig[df_fig['RUTA'].astype(str).isin(ruta_sel)] if ruta_sel else df_fig.iloc[0:0]

    # 4) Grupo RM1
    grupo_rm1_opts = sorted(df_ruta['GRUPO_RM1'].dropna().astype(str).unique().tolist())
    grupo_rm1_sel = multiselect_all("Grupo RM1", grupo_rm1_opts, key="grm1", default_all=True)
    df_grm1 = df_ruta[df_ruta['GRUPO_RM1'].astype(str).isin(grupo_rm1_sel)] if grupo_rm1_sel else df_ruta.iloc[0:0]

    # 5) Ruta
    esquema_rep_opts = sorted(df_grm1['EsquemaReparto'].dropna().astype(str).unique().tolist())
    esquema_rep_sel = multiselect_all("Esquema Reparto", esquema_rep_opts, key="esrep", default_all=True)
    df_filtrado = df_grm1[df_grm1['EsquemaReparto'].astype(str).isin(esquema_rep_sel)] if esquema_rep_sel else df_grm1.iloc[0:0]

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
    st.success(f"🔎 Registros encontrados: **{len(df_filtrado['ID_SAP'].unique()):,}**")


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
    # --- Evitar clientes duplicados en el mapa ---
    df_puntos = (
        df_filtrado
        .sort_values("ID_SAP")  # opcional: mantener orden
        .drop_duplicates(subset=["ID_SAP"])  # 👈 quedarnos solo con un registro por cliente
        .copy()
    )

    # Asegurar que lat/lon son numéricos y válidos
    df_puntos["latitud"] = pd.to_numeric(df_puntos["latitud"], errors="coerce")
    df_puntos["longitud"] = pd.to_numeric(df_puntos["longitud"], errors="coerce")
    df_puntos = df_puntos.dropna(subset=["latitud", "longitud"])

    view = pdk.ViewState(latitude=df_filtrado['latitud'].mean(skipna=True),
                         longitude=df_filtrado['longitud'].mean(skipna=True),
                         zoom=9, pitch=pitch_value)
    puntos_layer = pdk.Layer("ScatterplotLayer",
                             data=df_puntos,
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
    def rgba_to_css(rgba_list):
        r, g, b, a = rgba_list
        return f"rgba({r},{g},{b},{a / 255:.2f})"


    if colorear_por != "Ninguno":
        if "color_map_field" not in st.session_state or st.session_state["color_map_field"] != colorear_por:
            st.session_state["color_map_field"] = colorear_por
            categorias_globales = sorted(df[colorear_por].dropna().astype(str).unique())
            st.session_state["color_map"] = {c: rgba_to_css(string_to_color(c)) for c in categorias_globales}

        color_map = st.session_state["color_map"]
        counts = df_puntos[colorear_por].dropna().astype(str).value_counts()

        st.markdown(f"### 🎨 Leyenda de colores — *Color por:* `{colorear_por}`")

        legend_html = """
        <style>
        .leyenda-wrap {
            max-height: 180px; overflow-y: auto;
            padding: 10px 12px; border-radius: 10px;
            background: rgba(0,0,0,0.6);   /* Fondo oscuro más sólido */
            border: 1px solid rgba(255,255,255,0.15);
            color: #fff;                   /* Forzar texto blanco */
            font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, sans-serif;
        }
        .leyenda { display:flex; flex-wrap:wrap; gap:10px; }
        .item {
            display:flex; align-items:center; gap:8px;
            padding:4px 8px;
            background: rgba(255,255,255,0.05);
            border:1px solid rgba(255,255,255,0.15);
            border-radius:6px;
            font-size:14px;
            font-weight:500;               /* un poco más gruesa */
            color: #fff;                   /* texto siempre blanco */
        }
        .color-box {
            width:14px; height:14px; border-radius:3px;
            border:1px solid rgba(255,255,255,0.4);
            flex: 0 0 auto;
        }
        .small {
            opacity:.85;
            font-size:12px;
            margin-left:4px;
            color: #ddd;                   /* contraste suave */
        }
        </style>
        <div class='leyenda-wrap'><div class='leyenda'>
        """

        for categoria, cnt in counts.items():
            color = color_map.get(str(categoria), "rgba(200,200,200,0.80)")
            legend_html += f"""
            <div class='item'>
                <div class='color-box' style='background-color:{color};'></div>
                <span>{categoria}<span class='small'>({cnt:,})</span></span>
            </div>
            """

        legend_html += "</div></div>"

        components.html(legend_html, height=150, scrolling=True)
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

    # --- Sunburst con colores por nivel (CENTRO / MÉTODO / RITMO / FS) ---
    # 1) Pesos por nivel (suma de hojas)
    peso_centro = (
        df_sunburst.groupby(["CENTRO"], as_index=False)["peso"].sum()
        .rename(columns={"peso": "value"})
    )
    peso_metodo = (
        df_sunburst.groupby(["CENTRO", "MÉTODO_VENTA"], as_index=False)["peso"].sum()
        .rename(columns={"peso": "value"})
    )
    peso_ritmo = (
        df_sunburst.groupby(["CENTRO", "MÉTODO_VENTA", "RITMO"], as_index=False)["peso"].sum()
        .rename(columns={"peso": "value"})
    )
    peso_leaf = (
        df_sunburst.groupby(["CENTRO", "MÉTODO_VENTA", "RITMO", "FS_label"], as_index=False)["peso"].sum()
        .rename(columns={"peso": "value"})
    )

    # 2) Clientes reales por nivel (desde df_treemap)
    cli_centro = (
        df_treemap.groupby(["CENTRO"], as_index=False)["ID_SAP"].nunique()
        .rename(columns={"ID_SAP": "clientes"})
    )
    cli_metodo = (
        df_treemap.groupby(["CENTRO", "MÉTODO_VENTA"], as_index=False)["ID_SAP"].nunique()
        .rename(columns={"ID_SAP": "clientes"})
    )
    cli_ritmo = (
        df_treemap.groupby(["CENTRO", "MÉTODO_VENTA", "RITMO"], as_index=False)["ID_SAP"].nunique()
        .rename(columns={"ID_SAP": "clientes"})
    )
    cli_leaf = df_sunburst[["CENTRO", "MÉTODO_VENTA", "RITMO", "FS_label", "clientes"]].copy()

    # 3) Armar nodos (ids, labels, parents, valores y clientes) por nivel
    lvl0 = peso_centro.merge(cli_centro, on=["CENTRO"])  # CENTRO
    lvl0["id"] = "CENTRO|" + lvl0["CENTRO"].astype(str)
    lvl0["label"] = lvl0["CENTRO"].astype(str)
    lvl0["parent"] = ""
    lvl0["level"] = "CENTRO"

    lvl1 = peso_metodo.merge(cli_metodo, on=["CENTRO", "MÉTODO_VENTA"])  # MÉTODO
    lvl1["id"] = "MET|" + lvl1["CENTRO"].astype(str) + "|" + lvl1["MÉTODO_VENTA"].astype(str)
    lvl1["label"] = lvl1["MÉTODO_VENTA"].astype(str)
    lvl1["parent"] = "CENTRO|" + lvl1["CENTRO"].astype(str)
    lvl1["level"] = "METODO"

    lvl2 = peso_ritmo.merge(cli_ritmo, on=["CENTRO", "MÉTODO_VENTA", "RITMO"])  # RITMO
    lvl2["id"] = (
        "RIT|" + lvl2["CENTRO"].astype(str) + "|" + lvl2["MÉTODO_VENTA"].astype(str) + "|" + lvl2["RITMO"].astype(str)
    )
    lvl2["label"] = "Ritmo " + lvl2["RITMO"].astype(str)
    lvl2["parent"] = "MET|" + lvl2["CENTRO"].astype(str) + "|" + lvl2["MÉTODO_VENTA"].astype(str)
    lvl2["level"] = "RITMO"

    lvl3 = peso_leaf.merge(cli_leaf, on=["CENTRO", "MÉTODO_VENTA", "RITMO", "FS_label"])  # FS
    lvl3["id"] = (
        "FS|" + lvl3["CENTRO"].astype(str) + "|" + lvl3["MÉTODO_VENTA"].astype(str) + "|" + lvl3["RITMO"].astype(str) + "|" + lvl3["FS_label"].astype(str)
    )
    lvl3["label"] = lvl3["FS_label"].astype(str)
    lvl3["parent"] = "RIT|" + lvl3["CENTRO"].astype(str) + "|" + lvl3["MÉTODO_VENTA"].astype(str) + "|" + lvl3["RITMO"].astype(str)
    lvl3["level"] = "FS"

    nodes = pd.concat(
        [
            lvl0[["id", "label", "parent", "value", "clientes", "level"]],
            lvl1[["id", "label", "parent", "value", "clientes", "level"]],
            lvl2[["id", "label", "parent", "value", "clientes", "level"]],
            lvl3[["id", "label", "parent", "value", "clientes", "level"]],
        ],
        ignore_index=True,
    )

    # 4) Colores por nivel
    colores_metodo = {
        '(?)': '#282a2e',
        '1DA': '#37b741',
        '2DA': '#cfb53a',
        '3DA': '#ff0000',
        '4DA': '#ff0000',
        '5DA': '#ff0000',
        '6DA': '#ff0000',
        '7DA': '#ff0000',
        '8DA': '#ff0000',
        '9DA': '#ff0000',
        'NO DATA': '#ff0000',
        '-': '#ff0000',
    }
    colores_ritmo = {
        'Ritmo 1.0': '#37b741',
        'Ritmo 2.0': '#cfb53a',
        'Ritmo 3.0': '#ff0000',
        'Ritmo 4.0': '#cfb53a',
        'Ritmo 5.0': '#ff0000',
        'Ritmo 6.0': '#ff0000',
        'Ritmo NO DATA': '#aaaaaa',
    }
    colores_fs = {
        'FS 1': '#37b741', 'FS 2': '#37b741', 'FS 3': '#37b741',
        'FS 4': '#cfb53a', 'FS 5': '#cfb53a', 'FS 6': '#cfb53a',
    }

    def pick_color(row):
        if row['level'] == 'METODO':
            return colores_metodo.get(row['label'], '#999999')
        if row['level'] == 'RITMO':
            return colores_ritmo.get(row['label'], '#999999')
        if row['level'] == 'FS':
            return colores_fs.get(row['label'], '#cccccc')
        # CENTRO
        return '#444444'

    nodes['color'] = nodes.apply(pick_color, axis=1)

    # 5) Gráfico Sunburst con GO
    import plotly.graph_objects as go
    fig = go.Figure(go.Sunburst(
        ids=nodes['id'],
        labels=nodes['label'],
        parents=nodes['parent'],
        values=nodes['value'],
        branchvalues='total',
        marker=dict(colors=nodes['color']),
        customdata=nodes[['clientes']].to_numpy(),
        hovertemplate=(
            '<b>%{label}</b><br>'
            'Clientes reales: %{customdata[0]:,}<br>'
            '<extra></extra>'
        ),
        maxdepth=4,
    ))

    fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), width=500, height=500)
    st.plotly_chart(fig, use_container_width=True)

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

    parametros_tipo_ruta = {
        "Preventa Comercial": {"min": 48, "max": 58},
        "Farmer Comercial": {"min": 27, "max": 35},
        "Asesor Mayorista": {"min": 10, "max": 12},
        "Preventa Especializada TDC": {"min": 22, "max": 38},
        "EDI": {"min": 0, "max": 99},
        "IVR": {"min": 0, "max": 99},
        "Autoservicios": {"min": 0, "max": 99},
        "Juntos+ Tradicional (Portal)": {"min": 0, "max": 999},
        "Juntos+ Tradicional": {"min": 0, "max": 999},
        "Juntos+ Moderno": {"min": 0, "max": 999},
        "Juntos+ Mayoristas": {"min": 0, "max": 999},
        "CokeNet Moderno": {"min": 0, "max": 999},
        "Telventa": {"min": 0, "max": 999}
    }

    # Agrupar por RUTA y Descripción Tipo, mantener ambas columnas
    df_visitas = (
        df_filtrado
        .groupby(['RUTA', 'Descripción Tipo'])[columnas_dias]
        .sum(numeric_only=True)
        .reset_index()
    )
    # Calcular Promedio Diario
    df_visitas['Promedio'] = df_visitas[columnas_dias].mean(axis=1).round(0).astype(int)

    # Determinar si está en rango según parámetros dinámicos
    def en_rango(row):
        params = parametros_tipo_ruta.get(row["Descripción Tipo"], {"min": 48, "max": 58})
        return params["min"] <= row["Promedio"] <= params["max"]
    df_visitas["En Rango"] = df_visitas.apply(en_rango, axis=1)

    en_parametro = df_visitas[df_visitas["En Rango"]].copy()
    fuera_parametro = df_visitas[~df_visitas["En Rango"]].copy()

    st.subheader(f"🗺️ Total de rutas: **{len(df_visitas)}**")
    st.write(f"Rutas en parámetro encontradas: **{len(en_parametro)}**")

    def styled(df_in):
        def style_row(row):
            style = {}
            tipo = row["Descripción Tipo"]
            val = row["Promedio"]
            params = parametros_tipo_ruta.get(tipo, {"min": 48, "max": 58})
            color = 'background-color: rgb(69,255,85,0.7); color: black;'
            if val < params["min"]:
                color = 'background-color: rgb(255,222,69,0.8); color: black;'
            elif val > params["max"]:
                color = 'background-color: rgb(255,69,69,0.8); color: white;'
            for col in columnas_dias + ["Promedio"]:
                style[col] = color
            return pd.Series(style)
        return (
            df_in.style
            .apply(style_row, axis=1)
            .set_properties(**{'text-align': 'center'})
            .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
            .hide(axis="index")
        )


    # Mostrar tabla de rutas en parámetro
    height_en = 445 if fuera_parametro.empty else 245
    st.dataframe(
        styled(en_parametro.drop(columns=["En Rango"])),
        width='stretch',
        height=height_en
    )

    # Mostrar tabla de rutas fuera de parámetro solo si existen
    if not fuera_parametro.empty:
        st.write(f"Rutas fuera de parámetro encontradas: **{len(fuera_parametro)}**")
        st.dataframe(
            styled(fuera_parametro.drop(columns=["En Rango"])),
            width='stretch',
            height=245
        )

# Lista de clientes
st.subheader("📋 Lista de Clientes")
st.dataframe(df_filtrado[["ID_SAP", "CLIENTE", "TPV", "RUTA", "Descripción Tipo", "latitud", "longitud"]])