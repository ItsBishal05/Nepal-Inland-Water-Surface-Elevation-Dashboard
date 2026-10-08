import streamlit as st
from modules.ui_components import setup_page, render_navigation
from modules.data_loader import load_data, load_river_data
from modules.pages import render_dashboard, render_how_to_use, render_about_swot, render_contact_us

# FORCE LIGHT THEME - This will override everything
st.markdown("""
    <style>
    /* COMPLETE Streamlit theme override */
    .stApp {
        background-color: white !important;
        color: black !important;
    }
    
    /* Main content */
    .main .block-container {
        background-color: white !important;
        color: black !important;
    }
    
    /* Sidebar - hidden but if visible */
    .css-1d391kg, .css-1lcbmhc, [data-testid="stSidebar"] {
        background-color: #f0f2f6 !important;
        display: none !important;
    }
    
    /* All text elements */
    .stMarkdown, h1, h2, h3, h4, h5, h6, p, div, span, label {
        color: black !important;
    }
    
    /* Widgets */
    .stTextInput, .stSelectbox, .stTextArea, .stNumberInput {
        background-color: white !important;
        color: black !important;
    }
    
    /* Buttons */
    .stButton button {
        background-color: white !important;
        color: black !important;
        border: 1px solid #ccc !important;
    }
    
    /* Dataframes */
    .stDataFrame, .dataframe {
        background-color: white !important;
        color: black !important;
    }
    
    /* Metrics */
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"], [data-testid="stMetricDelta"] {
        color: black !important;
    }
    
    /* Plotly charts */
    .js-plotly-plot .plotly, .modebar {
        background-color: white !important;
    }
    
    /* Folium map */
    .folium-map {
        background-color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Then your normal page config
st.set_page_config(
    page_title="Nepal's Inland Water Surface Elevation Dashboard",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------------------
# Initialize session state
# ---------------------------------------------------------------------
if 'page' not in st.session_state:
    st.session_state.page = 'Dashboard'

# Data sources
if 'df_lakes' not in st.session_state:
    st.session_state.df_lakes = None
if 'df_rivers' not in st.session_state:
    st.session_state.df_rivers = None

# Feature mode: 'lake' or 'river'
if 'feature_type' not in st.session_state:
    st.session_state.feature_type = 'lake'

# Currently selected feature (name + API id)
if 'selected_feature_name' not in st.session_state:
    st.session_state.selected_feature_name = None
if 'selected_feature_id' not in st.session_state:
    st.session_state.selected_feature_id = None

# Time-series cache
if 'timeseries_data' not in st.session_state:
    st.session_state.timeseries_data = None
if 'timeseries_error' not in st.session_state:
    st.session_state.timeseries_error = None
if 'fetched_feature_id' not in st.session_state:
    st.session_state.fetched_feature_id = None



def main():
    # Setup page configuration and styling
    setup_page()

    # Visible page title — placed ABOVE the navigation bar
    st.markdown(
        "<h1 style='text-align: center; margin-bottom: 0.5rem;'>"
        "Nepal's Inland Water Surface Elevation Dashboard"
        "</h1>",
        unsafe_allow_html=True
    )

    # Render top navigation bar (instead of sidebar)
    render_navigation()

    # Load lake data if not already loaded
    if st.session_state.df_lakes is None:
        with st.spinner("Loading lake data..."):
            st.session_state.df_lakes = load_data()

    # Load river data if not already loaded
    if st.session_state.df_rivers is None:
        with st.spinner("Loading river data..."):
            st.session_state.df_rivers = load_river_data()

    # Render the current page
    if st.session_state.page == 'Dashboard':
        render_dashboard()
    elif st.session_state.page == 'How to Use':
        render_how_to_use()
    elif st.session_state.page == 'About SWOT':
        render_about_swot()
    elif st.session_state.page == 'Contact Us':
        render_contact_us()


if __name__ == "__main__":
    main()