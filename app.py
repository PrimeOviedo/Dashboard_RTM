import streamlit as st
import pandas as pd
import pydeck as pdk
import hashlib
import glob
import streamlit.components.v1 as components
import plotly.graph_objects as go
import matplotlib.colors as mcolors

st.set_page_config(page_title="Dashboard Maestro RTM", layout="wide")
st.title("📍 Dashboard Maestro RTM")

# ===================== CARGA DE DATOS OPTIMIZADA =====================
@st.cache_data(show_spinner="Cargando datos...")
def load_data():
    df = pd.concat(
        [pd.read_csv(f, low_memory=False, dtype=str) for f in glob.glob("data/salidas_por_centro/*.csv")],
       ignore_index=True
    )

    #df = pd.read_parquet("data/clientes.parquet")

    df = df[df['ESTATUS'] == 'A']
    df.rename(columns={"Latitud Final": "latitud", "Longitud Final": "longitud"}, inplace=True)

    df_volumen = pd.concat(
        [pd.read_parquet(f) for f in glob.glob("data/volumen_por_centro/*.parquet")],
        ignore_index=True
    )

    #df_volumen = pd.read_parquet("data/volumen.parquet")
    df_volumen.rename(columns={"Latitud Final": "latitud", "Longitud Final": "longitud"}, inplace=True)

    # Conversiones tempranas
    for col in ["Mes", "Año"]:
        df_volumen[col] = pd.to_numeric(df_volumen[col], errors="coerce").astype("Int64")

    # Convertir categóricas clave
    cat_cols = ["CENTRO", "Descripción Tipo", "RUTA", "GRUPO_RM1", "EsquemaReparto",
                "MÉTODO_VENTA", "RITMO", "SECTOR", "FV", "GEC_RTM", "TPV"]
    for c in cat_cols:
        if c in df.columns:
            df[c] = df[c].astype("string")

    return df, df_volumen

df, df_volumen = load_data()

# ===================== FUNCIONES DE FILTRO OPTIMIZADAS =====================
def multiselect_all(label, options, key, default_all=True):
    options = [str(o) for o in options]

    # Claves únicas por filtro
    all_key = f"{key}_all"
    multi_key = f"{key}_multi"

    # Inicialización
    if all_key not in st.session_state:
        st.session_state[all_key] = default_all
    if multi_key not in st.session_state:
        st.session_state[multi_key] = options if default_all else []

    # Checkbox de "Seleccionar todo"
    select_all = st.checkbox(f"Seleccionar todo: {label}", value=st.session_state[all_key], key=all_key)

    # Lógica de sincronización
    if select_all:
        st.session_state[multi_key] = options
    elif set(st.session_state[multi_key]) == set(options):
        # Si se desmarca pero antes estaban todos → vaciar
        st.session_state[multi_key] = []

    # Multiselect que refleja siempre el estado actual
    selected = st.multiselect(label, options=options, default=st.session_state[multi_key], key=multi_key)

    # Si el usuario quita manualmente alguna opción, desmarcar "Seleccionar todo"
    if set(selected) != set(options) and st.session_state[all_key]:
        st.session_state[all_key] = False

    return selected

# ===================== FILTROS =====================
with st.sidebar.expander("Filtros principales", expanded=False).form(key="filtros_form"):
    st.markdown("### 🎛️ Filtros principales")

    # Botón
    aplicar = st.form_submit_button("✅ Aplicar filtros")

    # 1) Unidad Operativa
    uo_opts = sorted(df['CENTRO'].dropna().unique().tolist())
    uo_sel = st.multiselect("Unidad Operativa", options=uo_opts, default=uo_opts[:1])

    if uo_sel:
        df_uo = df[df['CENTRO'].isin(uo_sel)]
        df_vol_uo = df_volumen[df_volumen['CENTRO'].isin(uo_sel)]
    else:
        df_uo = df.iloc[0:0]
        df_vol_uo = df_volumen.iloc[0:0]

    # 2) Figura Comercial
    figura_opts = sorted(df_uo['Descripción Tipo'].dropna().unique().tolist())
    fig_sel = multiselect_all("Figura Comercial", figura_opts, key="figuras", default_all=True)
    df_fig = df_uo[df_uo['Descripción Tipo'].isin(fig_sel)] if fig_sel else df_uo.iloc[0:0]
    df_vol_fig = df_vol_uo[df_vol_uo['Descripción Tipo'].isin(fig_sel)] if fig_sel else df_vol_uo.iloc[0:0]

    # 3) Ruta
    ruta_opts = sorted(df_fig['RUTA'].dropna().unique().tolist())
    ruta_sel = multiselect_all("RUTA", ruta_opts, key="rutas", default_all=True)
    df_ruta = df_fig[df_fig['RUTA'].isin(ruta_sel)] if ruta_sel else df_fig.iloc[0:0]
    df_vol_ruta = df_vol_fig[df_vol_fig['RUTA_MANDANTE'].isin(ruta_sel)] if ruta_sel else df_vol_fig.iloc[0:0]

    # 4) Grupo RM1
    grupo_rm1_opts = sorted(df_ruta['GRUPO_RM1'].dropna().unique().tolist())
    grupo_rm1_sel = multiselect_all("Grupo RM1", grupo_rm1_opts, key="grm1", default_all=True)
    df_grm1 = df_ruta[df_ruta['GRUPO_RM1'].isin(grupo_rm1_sel)] if grupo_rm1_sel else df_ruta.iloc[0:0]
    df_vol_grm1 = df_vol_ruta[df_vol_ruta['GRUPO_RM1'].isin(grupo_rm1_sel)] if grupo_rm1_sel else df_vol_ruta.iloc[0:0]

    # 5) Esquema Reparto
    esquema_rep_opts = sorted(df_grm1['EsquemaReparto'].dropna().unique().tolist())
    esquema_rep_sel = multiselect_all("Esquema Reparto", esquema_rep_opts, key="esrep", default_all=True)
    df_filtrado = df_grm1[df_grm1['EsquemaReparto'].isin(esquema_rep_sel)] if esquema_rep_sel else df_grm1.iloc[0:0]
    df_vol_filtrado = df_vol_grm1[df_vol_grm1['EsquemaReparto'].isin(esquema_rep_sel)] if esquema_rep_sel else df_vol_grm1.iloc[0:0]

# 👇 Solo aplicamos si presionan el botón
# 👇 Si no se ha aplicado, usar defaults para mostrar algo inicial
if aplicar:
    uo_seleccionadas = uo_sel
    figuras_seleccionadas = fig_sel
    rutas_seleccionadas = ruta_sel
    grupos_rm1_seleccionados = grupo_rm1_sel
    esquemas_seleccionados = esquema_rep_sel
else:
    # Defaults iniciales (puedes ajustarlos a lo que prefieras)
    uo_seleccionadas = uo_opts[:1]  # primera UO
    figuras_seleccionadas = figura_opts  # todas
    rutas_seleccionadas = ruta_opts     # todas
    grupos_rm1_seleccionados = grupo_rm1_opts  # todas
    esquemas_seleccionados = esquema_rep_opts  # todas

with st.sidebar.expander("Parámetros", expanded=False):
    # Método de Venta
    mtdo_opts = sorted(df_filtrado['MÉTODO_VENTA'].dropna().unique().tolist())
    mtdo_sel = multiselect_all("Método de Venta", mtdo_opts, key="metodo", default_all=True)
    if mtdo_sel: df_filtrado = df_filtrado[df_filtrado['MÉTODO_VENTA'].isin(mtdo_sel)]

    # Ritmo
    rit_opts = sorted(df_filtrado['RITMO'].dropna().unique().tolist())
    rit_sel = multiselect_all("Ritmo", rit_opts, key="ritmo", default_all=True)
    if rit_sel: df_filtrado = df_filtrado[df_filtrado['RITMO'].isin(rit_sel)]


    # Sector
    sec_opts = sorted(df_filtrado['SECTOR'].dropna().unique().tolist())
    sec_sel = multiselect_all("Sector", sec_opts, key="sector", default_all=True)
    if sec_sel: df_filtrado = df_filtrado[df_filtrado['SECTOR'].isin(sec_sel)]

    # Día de visita (optimizado con contains)
    dias_validos = ["L", "M", "R", "J", "V", "S"]
    dias_sel = st.multiselect("Día de visita", options=dias_validos, default=dias_validos, key="dias_visita")
    if dias_sel:
        regex = "|".join(dias_sel)
        df_filtrado = df_filtrado[df_filtrado["FV"].str.contains(regex, na=False)]
    else:
        df_filtrado = df_filtrado.iloc[0:0]


with st.sidebar.expander("Configuración de mapa", expanded=False):
    # Configuración de mapa
    estilo_mapa = st.selectbox("Estilo de mapa base", ["OpenStreetMap", "MapTiler"])
    pitch_value = st.slider("Inclinación del mapa (pitch)", min_value=0, max_value=60, value=0)
    colorear_por = st.selectbox("Colorear puntos por", ["Ninguno", "RUTA", "Descripción Tipo", "SECTOR", "GEC_RTM", "GRUPO_RM1"])

# Seguridad: eliminar filas sin coordenadas
if df_filtrado.empty or "latitud" not in df_filtrado.columns or "longitud" not in df_filtrado.columns:
    st.warning("⚠️ No hay registros para los filtros seleccionados.")
    st.stop()

df_filtrado = df_filtrado.dropna(subset=["latitud", "longitud"])
df_filtrado["latitud"] = pd.to_numeric(df_filtrado["latitud"], errors="coerce")
df_filtrado["longitud"] = pd.to_numeric(df_filtrado["longitud"], errors="coerce")

st.subheader(f"Indicadores para la UO: `{uo_sel}`")
if df_filtrado.empty:
    st.warning("⚠️ No hay registros para los filtros seleccionados.")
    st.stop()
else:
    st.success(f"🔎 Registros encontrados: **{len(df_filtrado['ID_SAP'].unique()):,}**")

def string_to_color(s):
    h = int(hashlib.md5(str(s).encode()).hexdigest(), 16)
    return [h % 255, (h >> 8) % 255, (h >> 16) % 255, 200]

 #============= Variables para gráficos =============↴

columnas_dias = ['L','M','R','J','V','S']
nombres_dias = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado']
df_filtrado[columnas_dias] = df_filtrado[columnas_dias].apply(pd.to_numeric, errors="coerce")
rutas_unicas = df_filtrado['RUTA'].nunique()
promedios = df_filtrado[columnas_dias].sum(numeric_only=True) / max(rutas_unicas, 1)
valores = promedios.values.tolist()
valores.append(valores[0])
nombres_dias_cerrado = nombres_dias + [nombres_dias[0]]
valores_texto = [f"{v:.1f}" for v in valores]

# ============= Variables para gráficos =============

 #============= Rutas en Parámetros =============↴
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

# ============= Rutas en Parámetros =============

# Asignar colores
if colorear_por == "SECTOR":
    colores_sector = {
        "Sector A": [227, 0, 0],     # Rojo
        "Sector B": [0, 113, 255],     # Azul
        "Sector AB": [135, 0, 255],  # Morado
    }
    df_filtrado["color"] = df_filtrado["SECTOR"].apply(
        lambda x: colores_sector.get(x, [200, 200, 200, 200])  # usa gris si no está en el diccionario
    )
elif colorear_por != "Ninguno":
    df_filtrado["color"] = df_filtrado[colorear_por].apply(string_to_color)
else:
    df_filtrado["color"] = [[255, 0, 0, 200]] * len(df_filtrado)

tooltip = {
    "html": """
        <b>Cliente:</b> {ID_SAP}<br>
        <b>Nombre:</b> {CLIENTE}<br>
        <b>Ruta:</b> {RUTA}<br>
        <b>FV:</b> {FV}<br>
        <b>Figura:</b> {Descripción Tipo}<br>
        <b>GEC:</b> {GEC_RTM}<br>
        <b>Canal:</b> {GRUPO_RM1}
    """,
    "style": {"backgroundColor": "rgba(0,0,0,0.7)", "color": "white", "fontSize": "12px"}
}

st.subheader("📊 Indicadores clave")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Clientes únicos", f"{df_filtrado['ID_SAP'].nunique():,}")

with col2:
    st.metric("Total rutas", f"{df_filtrado['RUTA'].nunique():,}")

with col3:
    pct_en_rango = (len(en_parametro) / max(len(df_visitas), 1)) * 100
    st.metric("Rutas en rango (%)", f"{pct_en_rango:.1f}%")

with col4:
    clientes_por_ruta = df_filtrado['ID_SAP'].nunique() / max(df_filtrado['RUTA'].nunique(), 1)
    st.metric("Promedio clientes x ruta", f"{clientes_por_ruta:.1f}")

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
                             get_radius=3,
                             radius_scale=6,
                             radius_min_pixels=1,
                             radius_max_pixels=10,
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
        r, g, b = rgba_list[:3]
        if len(rgba_list) == 4:
            a = rgba_list[3] / 255  # normalizar
        else:
            a = 1
        return f"rgba({r},{g},{b},{a:.2f})"


    if colorear_por == "SECTOR":
        # Diccionario fijo de colores
        colores_sector = {
            "Sector A": "rgba(227,0,0,0.8)",  # Rojo
            "Sector B": "rgba(0,113,255,0.8)",  # Azul
            "Sector AB": "rgba(128,0,128,0.8)",  # Morado
        }
        counts = df_puntos["SECTOR"].dropna().astype(str).value_counts()

        st.markdown("### 🎨 Leyenda de colores — *Color por:* `SECTOR`")

        legend_html = """
        <style>
        .leyenda-wrap {
            max-height: 180px; overflow-y: auto;
            padding: 10px 12px; border-radius: 10px;
            background: rgba(0,0,0,0.6);
            border: 1px solid rgba(255,255,255,0.15);
            color: #fff;
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
            font-weight:500;
            color: #fff;
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
            color: #ddd;
        }
        </style>
        <div class='leyenda-wrap'><div class='leyenda'>
        """

        for categoria, cnt in counts.items():
            color = colores_sector.get(categoria, "rgba(200,200,200,0.8)")
            legend_html += f"""
            <div class='item'>
                <div class='color-box' style='background-color:{color};'></div>
                <span>{categoria}<span class='small'>({cnt:,})</span></span>
            </div>
            """

        legend_html += "</div></div>"
        components.html(legend_html, height=150, scrolling=True)

    elif colorear_por != "Ninguno":
        # --- Caso dinámico ---
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
            background: rgba(0,0,0,0.6);
            border: 1px solid rgba(255,255,255,0.15);
            color: #fff;
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
            font-weight:500;
            color: #fff;
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
            color: #ddd;
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
    fig = go.Figure()
    # Remove text from the trace, use mode='lines+markers+text' and add textfont/textposition
    # Trace principal
    fig.add_trace(go.Scatterpolar(
        r=valores,
        theta=nombres_dias_cerrado,
        fill='toself',
        name='Promedio visitas',
        line=dict(color='rgba(69,255,227,0.7)', width=3),
        marker=dict(size=6, color='rgba(69,255,227,0.7)'),
        mode='lines+markers',
        hovertemplate='%{theta}: %{r:.1f}<extra></extra>'
    ))

    # Trace para labels dentro del círculo (un poquito más cortos en radio)
    r_labels = [v * 0.8 for v in valores]  # 👈 multiplica por 0.9 para acercarlos al centro
    fig.add_trace(go.Scatterpolar(
        r=r_labels,
        theta=nombres_dias_cerrado,
        mode="text",
        text=valores_texto,
        textfont=dict(size=16, color="white"),
        hoverinfo="skip"  # evita hover duplicado
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='rgba(255,0,0,0)',
            radialaxis=dict(visible=True, showticklabels=False),
            angularaxis=dict(
                tickfont=dict(size=20, color='white'),
                showline=True, linewidth=5, showgrid=True
            )
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        height=500,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    # Add annotations for each point with a colored background (black semi-transparent)
    import numpy as np
    # Calculate angles in radians for each theta
    num_points = len(nombres_dias_cerrado)
    angles = np.linspace(0, 2 * np.pi, num_points)
    # Place annotation for each day (skip the last to avoid duplicate at start/end)
    for i in range(len(nombres_dias)):
        angle = angles[i]
        radius = valores[i]
        # Polar to cartesian for annotation placement
        x = radius * np.cos(angle - np.pi/2)
        y = radius * np.sin(angle - np.pi/2)

    st.plotly_chart(fig, use_container_width=True, config={"responsive": True})

with col2:

    st.subheader(f"🗺️ Total de rutas: **{len(df_visitas)}**")
    st.write(f"Rutas en parámetro encontradas: **{len(en_parametro)}**")


    def styled(df_in):
        def style_row(row):
            style = {}
            tipo = row["Descripción Tipo"]
            params = parametros_tipo_ruta.get(tipo, {"min": 48, "max": 58})

            # Evaluar cada día
            for col in columnas_dias:
                val = row[col]
                color = 'background-color: rgb(69,255,85,0.7); color: black;'  # en rango
                if val < params["min"]:
                    color = 'background-color: rgb(255,222,69,0.8); color: black;'  # por debajo
                elif val > params["max"]:
                    color = 'background-color: rgb(255,69,69,0.8); color: white;'  # por arriba
                style[col] = color

            # Evaluar también el promedio
            val_prom = row["Promedio"]
            color_prom = 'background-color: rgb(69,255,85,0.7); color: black;'
            if val_prom < params["min"]:
                color_prom = 'background-color: rgb(255,222,69,0.8); color: black;'
            elif val_prom > params["max"]:
                color_prom = 'background-color: rgb(255,69,69,0.8); color: white;'
            style["Promedio"] = color_prom

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


# Sankey

import matplotlib.colors as mcolors

# ───────────────────────────────
# 🔹 Flujos
flows1 = df_filtrado.groupby(["Descripción Tipo","GRUPO_RM1"]).size().reset_index(name="value")
flows2 = df_filtrado.groupby(["GRUPO_RM1","GEC_RTM"]).size().reset_index(name="value")

# ───────────────────────────────
# 🔹 Colores distintos por nivel
figura_colors = ["#d62728"] * len(df_filtrado["Descripción Tipo"].unique())   # rojo para Figuras
rm1_colors    = ["#1f77b4"] * len(df_filtrado["GRUPO_RM1"].unique())          # azul para RM1
gec_colors    = ["#2ca02c"] * len(df_filtrado["GEC_RTM"].unique())            # verde para GEC

node_colors = figura_colors + rm1_colors + gec_colors

# Función HEX → RGBA
def hex_to_rgba(hex_color, alpha=0.5):
    rgb = mcolors.to_rgb(hex_color)
    return f"rgba({int(rgb[0]*255)}, {int(rgb[1]*255)}, {int(rgb[2]*255)}, {alpha})"

# ───────────────────────────────
# 🔹 Nodos únicos de todos los niveles
labels = (
    list(df_filtrado["Descripción Tipo"].unique())
    + list(df_filtrado["GRUPO_RM1"].unique())
    + list(df_filtrado["GEC_RTM"].unique())
)

# Mapear cada nodo a índice
node_map = {label: idx for idx, label in enumerate(labels)}

# Construir flujos
sources = flows1["Descripción Tipo"].map(node_map).tolist() + flows2["GRUPO_RM1"].map(node_map).tolist()
targets = flows1["GRUPO_RM1"].map(node_map).tolist() + flows2["GEC_RTM"].map(node_map).tolist()
values  = flows1["value"].tolist() + flows2["value"].tolist()

# Colores de links = heredan color de origen con transparencia
link_colors = [hex_to_rgba(node_colors[s], 0.5) for s in sources]

# ───────────────────────────────
# 🔹 Crear Sankey
fig = go.Figure(data=[go.Sankey(
    node=dict(
        pad=20,
        thickness=20,
        line=dict(color="black", width=0.5),
        label=labels,
        color=node_colors
    ),
    link=dict(
        source=sources,
        target=targets,
        value=values,
        color=link_colors
    )
)])

st.subheader("📊 Clientes por Canal Grupo RM1")

st.plotly_chart(fig, use_container_width=True)


# Lista de clientes
import plotly.express as px
st.dataframe(df_filtrado[["ID_SAP", "CLIENTE", "TPV", "RUTA", "Descripción Tipo", "latitud", "longitud"]])

# Radar y tabla
col1, col2 = st.columns([4, 3])

# Agrupar por Año y Mes, sumando CF, CFC y CU
tabla_volumen = (
    df_vol_filtrado
    .groupby(["CENTRO", "Año", "Mes"])[["CF", "CFC", "CU"]]
    .sum()
    .reset_index()
    .sort_values(["Año", "Mes"])
)

tabla_volumen["Mes"] = tabla_volumen["Mes"].astype(int)
tabla_volumen["Año"] = tabla_volumen["Año"].astype(int)

with col1:
    st.subheader("📊 Comparativo de Volumen CU")

    import plotly.graph_objects as go
    from datetime import datetime

    # 📌 Mes actual
    mes_actual = datetime.now().month

    # ✅ Agregar por Año+Mes (acumula todos los centros)
    tabla_comp = (
        tabla_volumen
        .loc[tabla_volumen["Mes"] <= mes_actual, ["Año", "Mes", "CU"]]
        .groupby(["Año", "Mes"], as_index=False)["CU"].sum()
        .sort_values(["Año", "Mes"])
    )

    # Colores por año
    color_line = {2025: "#dc0000", 2024: "#9aa0a6"}  # líneas
    color_mark = {2025: "rgba(220,0,0,0.9)", 2024: "rgba(154,160,166,0.9)"}  # marcadores

    fig = go.Figure()

    # 🔴⚪️ Agregar trazas por año con colores fijos
    for año in sorted(tabla_comp["Año"].unique()):
        df_año = tabla_comp[tabla_comp["Año"] == año].sort_values("Mes")

        fig.add_trace(go.Scatter(
            x=df_año["Mes"],
            y=df_año["CU"],
            mode="lines+markers",
            name=str(año),
            line=dict(
                color=color_line.get(año, "#3ba3ff"),
                width=4,
                shape="spline"
            ),
            marker=dict(
                size=10,
                color=color_mark.get(año, "rgba(59,163,255,0.9)"),
                line=dict(width=2, color="white")
            ),
            # ✅ Hover correcto (volumen total por mes) y formateado
            hovertemplate=f"Año {año}<br>Mes: %{{x:.0f}}<br>Volumen CU: %{{y:,.0f}}<extra></extra>"
        ))

    # Estilo
    fig.update_layout(
        plot_bgcolor="rgba(20,20,20,0.9)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        xaxis=dict(
            title="Mes",
            gridcolor="rgba(255,255,255,0.1)",
            linecolor="white",
            dtick=1
        ),
        yaxis=dict(
            title="Volumen CU",
            gridcolor="rgba(255,255,255,0.1)",
            linecolor="white",
            tickformat=","
        ),
        legend=dict(
            title="Año",
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(255,255,255,0.2)",
            borderwidth=1,
            font=dict(size=14)
        ),
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

with col2:
    # Chord diagram
    # Filtrar al mes actual

    tabla_volumen["Mes"] = tabla_volumen["Mes"].astype(int)
    tabla_volumen["Año"] = tabla_volumen["Año"].astype(int)

    anio_actual = datetime.now().year
    mes_actual = datetime.now().month

    df_mes_actual = df_vol_filtrado[
        (df_vol_filtrado["Año"] == 2025) &
        (df_vol_filtrado["Mes"] == 10)
        ]

    if df_mes_actual.empty:
        st.warning(f"⚠️ No hay datos para {anio_actual}-{mes_actual}")
    else:
        import plotly.express as px

        st.subheader("Desglose de volumen por TPV y GEC")

        # Agrupar por TPV y sumar volumen CU
        volumen_tpv = df_mes_actual.groupby(["TPV", "GEC_RTM"])["CU"].sum().reset_index()

        colores_tpv = {
            "ZPV": "rgba(0,185,0,0.6)",  # verde con transparencia
            "ZTK": "rgba(220,0,0,0.6)",  # rojo con transparencia
            "ZJV": "rgba(255,165,0,0.6)",  # amarillo con transparencia
            "SA": "rgba(91,91,91,0.6)"  # gris con transparencia
        }

        # Gráfico polar
        fig = px.bar_polar(
            volumen_tpv,
            r="CU",
            theta="GEC_RTM",
            color="TPV",
            template="plotly_dark",
            color_discrete_sequence=px.colors.qualitative.Set2
        )

        # Asignar colores fijos
        fig.update_traces(marker=dict(colorscale=None))  # asegura que no use escala continua
        fig.for_each_trace(
            lambda t: t.update(marker_color=colores_tpv.get(t.name, None))
        )

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    type="-",  # 👈 escala logarítmica
                    tickformat=",",
                    tickangle=45,
                    showticklabels=False,
                    showline=False,
                    linewidth=2,
                    showgrid=True,
                    gridcolor="rgba(255,255,255,0.2)",
                    gridwidth=0.5
                ),
                angularaxis=dict(
                    tickfont=dict(size=14, color="white")
                )
            ),
            showlegend=True
        )

        fig.update_traces(
            hovertemplate="<b>%{theta}</b><br>" +
                          "TPV: %{fullData.name}<br>" +
                          "Volumen: %{r:,.0f}<extra></extra>"
        )

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})