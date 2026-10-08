import folium
from folium.plugins import MarkerCluster
import geopandas as gpd
from modules.stats_utils import clean_name

def create_enhanced_map(selected_lake=None):
    """Create an interactive Folium map with lakes and river nodes"""
    try:
        map_center = [28.0, 84.0]
        zoom_start = 7
        target_lat, target_lon = None, None

        # Load layers
        lakes_gdf = load_lakes_shapefile()
        river_gdf = load_river_nodes_shapefile()
        
        # Try to find and center on selected lake
        if selected_lake and lakes_gdf is not None:
            target_lat, target_lon = find_lake_coordinates(lakes_gdf, selected_lake)
            if target_lat and target_lon:
                map_center = [target_lat, target_lon]
                zoom_start = 10

        # Create base map
        m = folium.Map(location=map_center, zoom_start=zoom_start, tiles=None, control_scale=True)
        
        # Add tile layers
        add_tile_layers(m)
        
        # Add Nepal boundary
        add_nepal_boundary(m)
        
        # Add lakes layer
        add_lakes_layer(m, lakes_gdf, selected_lake)
        
        # Add river nodes layer
        add_river_nodes_layer(m, river_gdf)
        
        # Fly to selected lake if found
        if target_lat and target_lon:
            add_fly_to_script(m, target_lat, target_lon)
            
        # Layer Control
        folium.LayerControl(collapsed=False).add_to(m)
        return m
        
    except Exception as e:
        import streamlit as st
        st.error(f"Error creating map: {str(e)}")
        return None

def load_lakes_shapefile():
    """Load lakes shapefile with standardized column names"""
    try:
        lakes_gdf = gpd.read_file("Shapefiles/SWOT_Lakes.shp")
        if isinstance(lakes_gdf, gpd.GeoSeries):
            lakes_gdf = gpd.GeoDataFrame({"geometry": lakes_gdf})

        possible_names = ['lake_name', 'Lake_Name', 'LAKE_NAME', 'name', 'Name', 'NAME', 'GNIS_NAME', 'gnis_name']
        lake_name_col = next((col for col in possible_names if col in lakes_gdf.columns), None)
        if lake_name_col:
            lakes_gdf = lakes_gdf.rename(columns={lake_name_col: 'lake_name'})
        else:
            for col in lakes_gdf.columns:
                if lakes_gdf[col].dtype == 'object' and col != 'geometry':
                    lakes_gdf = lakes_gdf.rename(columns={col: 'lake_name'})
                    break
            else:
                lakes_gdf['lake_name'] = "Lake " + lakes_gdf.index.astype(str)
                
        return lakes_gdf
    except Exception as e:
        import streamlit as st
        st.warning(f"Could not load lakes shapefile: {str(e)}")
        return None

def load_river_nodes_shapefile():
    """Load river nodes shapefile and standardize name column"""
    try:
        river_gdf = gpd.read_file("Shapefiles/River_Nodes.shp")
        if isinstance(river_gdf, gpd.GeoSeries):
            river_gdf = gpd.GeoDataFrame({"geometry": river_gdf})

        possible_names = ['node_name', 'Name', 'NAME', 'name', 'GNIS_NAME', 'river_name']
        name_col = next((col for col in possible_names if col in river_gdf.columns), None)
        if name_col:
            river_gdf = river_gdf.rename(columns={name_col: 'node_name'})
        else:
            river_gdf['node_name'] = "Node " + river_gdf.index.astype(str)

        return river_gdf
    except Exception as e:
        import streamlit as st
        st.warning(f"Could not load river nodes shapefile: {str(e)}")
        return None

def find_lake_coordinates(lakes_gdf, selected_lake):
    """Find coordinates for a selected lake using name matching"""
    selected_clean = clean_name(selected_lake)
    best_match = None
    best_score = 0
    
    for idx, row in lakes_gdf.iterrows():
        lake_name = row['lake_name']
        lake_clean = clean_name(lake_name)
        
        if selected_clean == lake_clean:
            best_match = row
            break
        elif selected_clean in lake_clean:
            score = len(selected_clean) / len(lake_clean) * 90
            if score > best_score:
                best_match = row
                best_score = score
        elif lake_clean in selected_clean:
            score = len(lake_clean) / len(selected_clean) * 80
            if score > best_score:
                best_match = row
                best_score = score
        elif (len(selected_clean) > 3 and len(lake_clean) > 3 and 
              selected_clean[:4] == lake_clean[:4]):
            score = 70
            if score > best_score:
                best_match = row
                best_score = score

    if best_match is not None:
        geom = best_match.geometry.centroid
        return geom.y, geom.x
    
    return None, None

def add_tile_layers(m):
    """Add various tile layers to the map"""
    folium.TileLayer(tiles='OpenStreetMap', name='OpenStreetMap', attr='OSM').add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri World Imagery'
    ).add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri World Topo'
    ).add_to(m)

def add_nepal_boundary(m):
    """Add Nepal boundary layer to the map"""
    nepal_layer = folium.FeatureGroup(name='Nepal Boundary', show=True)
    try:
        nepal_gdf = gpd.read_file("Shapefiles/Nepal Outer Boundary.shp")
        if isinstance(nepal_gdf, gpd.GeoSeries):
            nepal_gdf = gpd.GeoDataFrame({"geometry": nepal_gdf})
        nepal_gdf['geometry'] = nepal_gdf['geometry'].simplify(0.01)
        
        def style_nepal(feature):
            return {'fillColor': '#8B0000', 'color': '#8B0000', 'weight': 3, 'fillOpacity': 0.2}
            
        folium.GeoJson(
            nepal_gdf,
            style_function=style_nepal,
            name='Nepal Boundary'
        ).add_to(nepal_layer)
        nepal_layer.add_to(m)
    except Exception as e:
        import streamlit as st
        st.warning(f"Could not load Nepal boundary: {str(e)}")

def add_lakes_layer(m, lakes_gdf, selected_lake):
    """Add lakes as markers to the map"""
    if lakes_gdf is None:
        return
        
    lakes_layer = folium.FeatureGroup(name='Lakes', show=True)

    for idx, row in lakes_gdf.iterrows():
        lake_name = row['lake_name']
        centroid = row.geometry.centroid
        lat, lon = centroid.y, centroid.x

        is_selected = is_lake_selected(lake_name, selected_lake)
        marker = create_lake_marker(lat, lon, lake_name, is_selected)
        marker.add_to(lakes_layer)

        if is_selected:
            label = create_lake_label(lat, lon, lake_name)
            label.add_to(lakes_layer)

    lakes_layer.add_to(m)

def add_river_nodes_layer(m, river_gdf):
    """Add river nodes as markers to the map with min_node_id and min_river_name"""
    if river_gdf is None:
        return

    river_layer = folium.FeatureGroup(name='River Nodes', show=True)

    for _, row in river_gdf.iterrows():
        # Get node ID and river name; fallback if missing
        node_id = row.get('min_node_i', 'N/A')
        river_name = row.get('min_river_', 'Unnamed River')
        
        # Build label and popup
        tooltip_text = f"ID: {node_id} | {river_name}"
        popup_text = f"<b>River Node</b><br>ID: {node_id}<br>River: {river_name}"

        # Extract coordinates
        geom = row.geometry
        if geom.is_empty:
            continue
        if hasattr(geom, 'x') and hasattr(geom, 'y'):
            lon, lat = geom.x, geom.y
        else:
            centroid = geom.centroid
            lat, lon = centroid.y, centroid.x

        # Create marker
        icon = folium.DivIcon(
            html='''
            <div style="background-color: #228B22; 
                        border: 1px solid white; 
                        border-radius: 50%; 
                        width: 10px; 
                        height: 10px;">
            </div>
            ''',
            icon_size=(10, 10),
            icon_anchor=(5, 5)
        )

        folium.Marker(
            location=[lat, lon],
            popup=popup_text,
            tooltip=tooltip_text,
            icon=icon
        ).add_to(river_layer)

    river_layer.add_to(m)

def is_lake_selected(lake_name, selected_lake):
    """Check if a lake matches the selected lake"""
    if not selected_lake:
        return False
        
    lake_clean = clean_name(lake_name)
    selected_clean = clean_name(selected_lake)
    
    return (selected_clean == lake_clean or 
            selected_clean in lake_clean or 
            lake_clean in selected_clean or
            (len(selected_clean) > 3 and len(lake_clean) > 3 and 
             selected_clean[:4] == lake_clean[:4]))

def create_lake_marker(lat, lon, lake_name, is_selected):
    """Create a marker for a lake"""
    if is_selected:
        icon_html = '''
        <div style="display: inline-block;
                    background-color: rgba(30, 144, 255, 0.8);
                    border: 2px solid red;
                    border-radius: 50%;
                    width: 18px;
                    height: 18px;
                    text-align: center;">
        </div>
        '''
        icon_size = (18, 18)
        icon_anchor = (9, 9)
    else:
        icon_html = '''
        <div style="display: inline-block;
                    background-color: rgba(30, 144, 255, 0.6);
                    border: 1px solid white;
                    border-radius: 50%;
                    width: 12px;
                    height: 12px;
                    text-align: center;">
        </div>
        '''
        icon_size = (12, 12)
        icon_anchor = (6, 6)

    icon = folium.DivIcon(
        html=icon_html,
        icon_size=icon_size,
        icon_anchor=icon_anchor
    )

    popup_content = f"<b>{lake_name}</b><br><i>{'🔴 SELECTED' if is_selected else '🔵 Normal'}</i>"

    return folium.Marker(
        location=[lat, lon],
        popup=popup_content,
        tooltip=f"{'[SELECTED] ' if is_selected else ''}{lake_name}",
        icon=icon
    )

def create_lake_label(lat, lon, lake_name):
    """Create a label for the selected lake"""
    return folium.Marker(
        location=[lat + 0.01, lon],
        icon=folium.DivIcon(
            html=f'<div style="font-weight: bold; color: red; font-size: 12px; background: rgba(255,255,255,0.7); padding: 2px; border-radius: 3px;">{lake_name}</div>',
            icon_size=(150, 30),
            icon_anchor=(0, 0)
        )
    )

def add_fly_to_script(m, target_lat, target_lon):
    """Add script to fly to selected lake"""
    fly_to_js = f"""
    <script>
        function flyToSelected() {{
            var map = document.querySelector('.folium-map')._leaflet_map;
            if (map) {{
                map.flyTo([{target_lat}, {target_lon}], 10, {{
                    duration: 1.5,
                    easeLinearity: 0.25
                }});
            }}
        }}
        setTimeout(flyToSelected, 800);
    </script>
    """
    m.get_root().html.add_child(folium.Element(fly_to_js))