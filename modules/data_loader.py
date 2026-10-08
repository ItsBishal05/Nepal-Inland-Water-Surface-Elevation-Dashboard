import pandas as pd
import folium
import streamlit as st
import requests
from datetime import datetime
from io import StringIO
from pathlib import Path

# ---------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------
LAKE_CSV_PATH  = r"D:\MSWRE\SWOT\Dashboard\Datas\NP_Lake_Datasets.csv"
RIVER_CSV_PATH = r"D:\MSWRE\SWOT\Dashboard\Datas\NP_River_Nodes_Datasets.csv"

BASE_DIR = Path(__file__).resolve().parent.parent
SHAPEFILE_DIR = BASE_DIR / "Shapefiles"


# =====================================================================
# DATA LOADING
# =====================================================================

@st.cache_data
def load_data():
    """
    Load LAKE data from CSV file.
    Uses Streamlit's cache to avoid reloading on every rerun.
    """
    try:
        df = pd.read_csv(LAKE_CSV_PATH)

        df = df[['lake_id', 'lake_name', 'wse_avg', 'p_lon', 'p_lat', 'area_avg']].copy()

        df.rename(columns={
            'p_lon': 'longitude',
            'p_lat': 'latitude',
            'area_avg': 'area'
        }, inplace=True)

        df = df.dropna(subset=['latitude', 'longitude', 'wse_avg'])
        df = df.drop_duplicates(subset=['lake_id'], keep='first')
        df = df.drop_duplicates(subset=['lake_name'], keep='first')

        df['wse_avg']   = df['wse_avg'].round(2)
        df['area']      = df['area'].round(2)
        df['latitude']  = df['latitude'].round(6)
        df['longitude'] = df['longitude'].round(6)

        df = df.reset_index(drop=True)
        return df

    except FileNotFoundError:
        st.error(f"Lake CSV file not found at: {LAKE_CSV_PATH}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading lake data: {str(e)}")
        return pd.DataFrame()


@st.cache_data
def load_river_data():
    """
    Load RIVER NODE data from CSV file.
    Note: does NOT dedupe by river_name — a single river legitimately
    has many nodes; each node is a distinct row and marker.
    """
    try:
        df = pd.read_csv(RIVER_CSV_PATH)

        # Keep only the columns we need
        df = df[['node_id', 'river_name', 'wse', 'width', 'p_lon', 'p_lat']].copy()

        # Rename to match the standard schema used across the dashboard
        df.rename(columns={
            'p_lon': 'longitude',
            'p_lat': 'latitude'
            # node_id     → node_id     (kept as-is)
            # river_name  → river_name  (kept as-is)
            # wse         → wse         (kept as-is)
            # width       → width       (kept as-is)
        }, inplace=True)

        # Clean
        df = df.dropna(subset=['latitude', 'longitude', 'wse'])

        # Dedupe by NODE — not by name. Rivers have many nodes per name.
        df = df.drop_duplicates(subset=['node_id'], keep='first')

        # Round for display
        df['wse']       = df['wse'].round(2)
        df['width']     = df['width'].round(2)
        

        # Ensure node_id is string (kept consistent for API calls)
        df['node_id'] = df['node_id'].astype(str)

        df = df.reset_index(drop=True)
        return df

    except FileNotFoundError:
        st.error(f"River CSV file not found at: {RIVER_CSV_PATH}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading river data: {str(e)}")
        return pd.DataFrame()


# =====================================================================
# MAP CREATION
# =====================================================================

def create_feature_map(mode, df_lakes=None, df_rivers=None, selected_name=None):
    """
    Build the Folium map for the current feature mode.

    mode: 'lake' or 'river'
    Only the markers for the active mode are drawn — never both at once.
    Tile layers + Nepal boundary are shared.
    """
    # Pick the dataframe for the active mode
    if mode == 'lake':
        df = df_lakes
        empty_center = [28.3949, 84.1240]
    else:
        df = df_rivers
        empty_center = [28.3949, 84.1240]

    if df is None or df.empty:
        return folium.Map(location=empty_center, zoom_start=7)

    # Center of the visible markers
    center_lat = df['latitude'].mean()
    center_lon = df['longitude'].mean()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=7,
        tiles=None,
        control_scale=True
    )

    # Shared visual layers
    add_tile_layers(m)
    add_nepal_boundary(m)
    add_nepal_rivers(m) 

    # Mode-specific markers
    if mode == 'lake':
        add_lake_markers(m, df, selected_name)
    else:
        add_river_markers(m, df, selected_name)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


# ---------------------------------------------------------------------
# MARKER HELPERS — LAKES
# ---------------------------------------------------------------------

def add_lake_markers(m, df, selected_name=None):
    """Original lake marker style — 📍 emoji, tooltip = lake_name."""
    for _, row in df.iterrows():
        popup_html = f"""
            <div style="width:150px;padding:0px;">
                <h6>{row['lake_name']}</h6>
            </div>
        """
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=row['lake_name'],
            icon=folium.DivIcon(
                html="""
                    <div style="
                        font-size: 20px;
                        line-height: 14px;
                        color: #0066cc;
                        text-align: center;
                        transform: translate(-50%, -50%);
                    ">📍</div>
                """,
                icon_size=(14, 14),
                icon_anchor=(7, 7),
            )
        ).add_to(m)


# ---------------------------------------------------------------------
# MARKER HELPERS — RIVERS
# ---------------------------------------------------------------------

def add_river_markers(m, df, selected_name=None):
    """
    River markers — small blue dots, tooltip = 'River Name (Node <id>)'.
    Popup is kept minimal — full details live in the right-side panel.
    """
    for _, row in df.iterrows():
        tooltip_text = f"{row['river_name']} (Node {row['node_id']})"

        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=folium.Popup(tooltip_text, max_width=300),
            tooltip=tooltip_text,
            icon=folium.DivIcon(
                html="""
                    <div style="
                        font-size: 6px;
                        line-height: 12px;
                        color: #1a5276;
                        text-align: center;
                        transform: translate(-50%, -50%);
                    ">🔵</div>
                """,
                icon_size=(14, 14),
                icon_anchor=(7, 7),
            )
        ).add_to(m)


# ---------------------------------------------------------------------
# SHARED LAYERS
# ---------------------------------------------------------------------

def add_tile_layers(m):
    """Satellite default + optional OSM / Topo / Labels."""
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community',
        name='🛰️ Satellite',
        overlay=False, control=True, show=False
    ).add_to(m)

    folium.TileLayer(
        tiles='OpenStreetMap',
        attr='&copy; OpenStreetMap contributors',
        name='🗺️ OpenStreetMap',
        overlay=False, control=True, show=True
    ).add_to(m)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles &copy; Esri',
        name='⛰️ Topographic',
        overlay=False, control=True, show=False
    ).add_to(m)


def add_nepal_boundary(m):
    """Nepal outline overlay. Silently skipped if shapefile missing."""
    try:
        import geopandas as gpd
        shp = SHAPEFILE_DIR / "Nepal Outer Boundary.shp"
        if not shp.exists():
            return

        nepal_gdf = gpd.read_file(shp)
        if isinstance(nepal_gdf, gpd.GeoSeries):
            nepal_gdf = gpd.GeoDataFrame({"geometry": nepal_gdf})
        nepal_gdf['geometry'] = nepal_gdf['geometry'].simplify(0.01)

        nepal_layer = folium.FeatureGroup(name='🇳🇵 Nepal Boundary', show=True)

        def style_nepal(feature):
            return {
                'fillColor': '#8B0000',
                'color': '#8B0000',
                'weight': 2,
                'fillOpacity': 0.05,
            }

        folium.GeoJson(
            nepal_gdf,
            style_function=style_nepal,
            name='Nepal Boundary'
        ).add_to(nepal_layer)

        nepal_layer.add_to(m)
    except Exception:
        pass

def add_nepal_rivers(m):
    """
    Nepal rivers overlay from a shapefile.
    Off by default — user can toggle it via Layer Control.
    Silently skipped if the shapefile is missing.
    """
    try:
        import geopandas as gpd
        shp = SHAPEFILE_DIR / "SWOT_Rivers_Reaches_V17b.shp"  
        if not shp.exists():
            return

        rivers_gdf = gpd.read_file(shp)

        # Simplify geometry for faster rendering
        rivers_gdf['geometry'] = rivers_gdf['geometry'].simplify(0.005)

        rivers_layer = folium.FeatureGroup(name='🏞️ Nepal Rivers', show=False)

        def style_rivers(feature):
            return {
                'color': '#1f78b4',     # river blue
                'weight': 1.5,
                'opacity': 0.75,
                'fill': False,
            }

        folium.GeoJson(
            rivers_gdf,
            style_function=style_rivers,
            name='Nepal Rivers'
        ).add_to(rivers_layer)

        rivers_layer.add_to(m)
    except Exception:
        pass

# =====================================================================
# TIME-SERIES API
# =====================================================================

def fetch_timeseries(feature_type, feature_id):
    """
    Generic Hydrocron time-series fetch.

    feature_type: "PriorLake" (lakes) or "Node" (rivers)
    feature_id:   lake_id or node_id
    """
    start_time = "2023-01-01T00:00:00Z"
    end_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    base_url = "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries"

    if feature_type == "PriorLake":
        # Lake fields
        fields = ("lake_id,lake_name,time_str,wse,area_total,"
                  "quality_f,collection_shortname,crid,PLD_version,range_start_time")
        params = {
            "feature": feature_type,
            "feature_id": feature_id,
            "start_time": start_time,
            "end_time": end_time,
            "fields": fields,
            "output": "csv"
        }
        quality_col = "quality_f"
        area_col = "area_total"
    else:
        # River node fields
        fields = ("node_id,reach_id,river_name,time_str,wse,width,"
                  "lat,lon,node_q,sword_version")
        params = {
            "feature": feature_type,
            "feature_id": feature_id,
            "start_time": start_time,
            "end_time": end_time,
            "fields": fields,
            "output": "csv"
        }
        quality_col = "node_q"
        area_col = "width"

    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        if 'results' not in data or 'csv' not in data['results']:
            st.warning(f"No valid results in API response for {feature_type} ID: {feature_id}")
            return pd.DataFrame()

        df = pd.read_csv(StringIO(data['results']['csv']))

        if df.empty:
            st.warning(f"Empty dataset returned for {feature_type} ID: {feature_id}")
            return pd.DataFrame()

        # Clean time and WSE
        df['time_str'] = df['time_str'].replace('no_data', pd.NA)
        df['wse'] = pd.to_numeric(df['wse'], errors='coerce')
        df = df.dropna(subset=['time_str', 'wse'])

        if df.empty:
            st.warning(f"No valid WSE observations for {feature_type} ID: {feature_id}")
            return pd.DataFrame()

        # Numeric quality column
        if quality_col in df.columns:
            df[quality_col] = pd.to_numeric(df[quality_col], errors='coerce')
            # Keep only quality 0 (Good) and 1 (Suspect)
            df = df[df[quality_col].isin([0, 1])]

            if df.empty:
                st.warning(f"No data with quality 0 or 1 for {feature_type} ID: {feature_id}")
                return pd.DataFrame()

            # Normalize to a common column name for the plot/dashboard
            df['quality_label'] = df[quality_col].map({0: 'Good', 1: 'Suspect', 2: 'Bad'})
        else:
            df['quality_label'] = 'Good'

        # Coerce the area/width column to numeric too (used in some views)
        if area_col in df.columns:
            df[area_col] = pd.to_numeric(df[area_col], errors='coerce')

        df['time_str'] = pd.to_datetime(df['time_str'])
        df = df.sort_values('time_str')

        return df

    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from Hydrocron API: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"An error occurred while processing the data: {e}")
        return pd.DataFrame()


def fetch_lake_timeseries(lake_id):
    """Convenience wrapper for lakes."""
    return fetch_timeseries("PriorLake", lake_id)


def fetch_river_timeseries(node_id):
    """Convenience wrapper for river nodes."""
    return fetch_timeseries("Node", node_id)


def test_api_connection():
    """Test if the Hydrocron API is accessible with a known working lake ID."""
    test_lake_id = "6350036102"
    try:
        response = requests.get(
            "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries",
            params={
                "feature": "PriorLake",
                "feature_id": test_lake_id,
                "start_time": "2024-07-20T00:00:00Z",
                "end_time": "2024-07-26T00:00:00Z",
                "fields": "lake_id,time_str,wse",
                "output": "csv"
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if 'results' in data and 'csv' in data['results']:
                return True, "API is accessible and returning data"
            else:
                return False, "API returned unexpected response format"
        else:
            return False, f"API returned status {response.status_code}"
    except Exception as e:
        return False, f"API connection failed: {str(e)}"


# For backward compatibility with old code
LAKE_DATA = {}