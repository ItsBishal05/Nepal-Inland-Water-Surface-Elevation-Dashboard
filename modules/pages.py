import streamlit as st
import pandas as pd
import re
from pathlib import Path
from streamlit_folium import st_folium

from modules.data_loader import (
    create_feature_map,
    fetch_lake_timeseries,
    fetch_river_timeseries,
    test_api_connection,
)
from modules.wse_plots import create_wse_time_series_plot


# ---------------------------------------------------------------------
# Paths for assets (images etc.)
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATAS_DIR = BASE_DIR / "Datas"

def render_dashboard():
    """Render dashboard page."""

    # -----------------------------------------------------------------
    # API status check (once per session)
    # -----------------------------------------------------------------
    if 'api_tested' not in st.session_state:
        with st.spinner("Testing API connection..."):
            api_ok, api_message = test_api_connection()
            st.session_state.api_tested = True
            st.session_state.api_ok = api_ok
            st.session_state.api_message = api_message

    if st.session_state.api_ok:
        st.success("✅ API Connection: OK")
    else:
        st.warning(f"⚠️ API Connection: {st.session_state.api_message}")
        st.info("💡 Some features may not have data. Try different selections.")

    # -----------------------------------------------------------------
    # Feature-type selector: Lakes vs Rivers
    # -----------------------------------------------------------------
    mode_label = st.radio(
        "Feature type",
        options=["🏞️ Lakes", "🌊 Rivers"],
        index=0 if st.session_state.feature_type == 'lake' else 1,
        horizontal=True,
        label_visibility="collapsed",
        key="feature_mode_radio",
    )
    new_mode = 'lake' if "Lakes" in mode_label else 'river'

    # If the mode changed, reset the current selection
    if new_mode != st.session_state.feature_type:
        st.session_state.feature_type = new_mode
        st.session_state.selected_feature_name = None
        st.session_state.selected_feature_id = None
        st.session_state.timeseries_data = None
        st.session_state.timeseries_error = None
        st.session_state.fetched_feature_id = None
        st.rerun()

    # -----------------------------------------------------------------
    # Pick the right dataframe for the current mode
    # -----------------------------------------------------------------
    if new_mode == 'lake':
        df = st.session_state.df_lakes
        feature_display = "lake"
        empty_hint = "👈 Click a lake on the map to see its details and time-series data."
    else:
        df = st.session_state.df_rivers
        feature_display = "river node"
        empty_hint = "👈 Click a river node on the map to see its details and time-series data."

    if df is None or df.empty:
        st.warning(f"⚠️ No {feature_display} data available. Please check the data source.")
        return

    # -----------------------------------------------------------------
    # TOP SECTION: Map + right panel
    # -----------------------------------------------------------------
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🗺️ Interactive Map")

        m = create_feature_map(
            mode=new_mode,
            df_lakes=st.session_state.df_lakes,
            df_rivers=st.session_state.df_rivers,
            selected_name=st.session_state.selected_feature_name,
        )
        map_data = st_folium(m, height=550, width="100%", key=f"{new_mode}_map")

        # ----- Handle map click (ID-based; zoom/pan does NOT trigger) -----
        clicked = map_data.get('last_object_clicked') if map_data else None

        if clicked is not None:
            raw = (map_data.get('last_object_clicked_tooltip') or "").replace("[SELECTED] ", "").strip()

            # Resolve clicked marker -> feature_id WITHOUT mutating state yet
            clicked_id = None
            clicked_name = None

            if new_mode == 'lake':
                if raw in df['lake_name'].values:
                    clicked_name = raw
                    clicked_id = df[df['lake_name'] == clicked_name]['lake_id'].iloc[0]
            else:
                match = re.search(r"\(Node\s+(\d+)\)", raw)
                if match:
                    clicked_id = match.group(1)
                    row = df[df['node_id'] == clicked_id]
                    if not row.empty:
                        clicked_name = row['river_name'].iloc[0]

            # Only react when the selected feature actually changes.
            # Same ID (e.g. from a zoom/pan re-render) -> do nothing.
            if clicked_id is not None and str(clicked_id) != str(st.session_state.selected_feature_id):
                st.session_state.selected_feature_name = clicked_name
                st.session_state.selected_feature_id = clicked_id
                st.session_state.timeseries_data = None
                st.session_state.timeseries_error = None
                st.session_state.fetched_feature_id = None

    with col2:
        if st.session_state.selected_feature_name and st.session_state.selected_feature_id:
            name = st.session_state.selected_feature_name
            fid = st.session_state.selected_feature_id

            # ---------------- LAKE PANEL ----------------
            if new_mode == 'lake':
                row = df[df['lake_id'] == fid]
                if not row.empty:
                    lake_data = row.iloc[0]

                    st.subheader(f"🏞️ {name}")

                    st.markdown(f"""
                    <div style="background-color:#f0f2f6;padding:15px;border-radius:10px;">
                        <p><b>Lake ID:</b> {lake_data['lake_id']}</p>
                        <p><b>WSE Average:</b> <span style="color:#1a5276;font-weight:bold;">{lake_data['wse_avg']:.2f} m</span></p>
                        <p><b>Latitude:</b> {lake_data['latitude']:.6f}°N</p>
                        <p><b>Longitude:</b> {lake_data['longitude']:.6f}°E</p>
                    </div>
                    """, unsafe_allow_html=True)

            # ---------------- RIVER PANEL ----------------
            else:
                row = df[df['node_id'] == str(fid)]
                if not row.empty:
                    river_data = row.iloc[0]

                    st.subheader(f"🌊 {name}")

                    st.markdown(f"""
                    <div style="background-color:#f0f2f6;padding:15px;border-radius:10px;">
                        <p><b>Node ID:</b> {river_data['node_id']}</p>
                        <p><b>WSE:</b> <span style="color:#1a5276;font-weight:bold;">{river_data['wse']:.2f} m</span></p>
                        <p><b>Width:</b> {river_data['width']:.2f} m</p>
                        <p><b>Latitude:</b> {river_data['latitude']:.6f}°N</p>
                        <p><b>Longitude:</b> {river_data['longitude']:.6f}°E</p>
                    </div>
                    """, unsafe_allow_html=True)

            # ---------------- Fetch time-series (once per feature ID) ----------------
            current_id = str(st.session_state.selected_feature_id)
            fetched_for = st.session_state.get('fetched_feature_id')

            if st.session_state.get('timeseries_data') is None or fetched_for != current_id:
                with st.spinner(f"Fetching time-series data for {name}..."):
                    if new_mode == 'lake':
                        ts_df = fetch_lake_timeseries(current_id)
                    else:
                        ts_df = fetch_river_timeseries(current_id)

                    if ts_df is not None and not ts_df.empty:
                        st.session_state.timeseries_data = ts_df
                        st.session_state.timeseries_error = None
                    else:
                        st.session_state.timeseries_data = pd.DataFrame()
                        st.session_state.timeseries_error = "No data available"
                    st.session_state.fetched_feature_id = current_id
        else:
            st.info(empty_hint)

    # -----------------------------------------------------------------
    # BOTTOM SECTION: Time-Series Data
    # -----------------------------------------------------------------
    st.markdown("---")

    if st.session_state.selected_feature_name and st.session_state.selected_feature_id:
        name = st.session_state.selected_feature_name
        fid = st.session_state.selected_feature_id

        st.subheader("📈 Time-Series Data")

        if new_mode == 'lake':
            st.markdown(f"**Lake Name:** {name}")
            st.markdown(f"**Lake ID:** {fid}")
        else:
            st.markdown(f"**River Name:** {name}")
            st.markdown(f"**Node ID:** {fid}")

        # Refresh button
        if st.button("🔄 Refresh Time-Series Data", key="fetch_ts"):
            st.session_state.timeseries_data = None
            st.session_state.timeseries_error = None
            st.session_state.fetched_feature_id = None
            st.rerun()

        ts_df = st.session_state.get('timeseries_data')

        if ts_df is not None and not ts_df.empty:
            # ---- Captions ----
            quality_counts = ts_df['quality_label'].value_counts()
            quality_summary = ", ".join([f"{k}: {v}" for k, v in quality_counts.items()])
            st.caption(f"📊 Data Points: {len(ts_df)}")
            st.caption(f"📊 Quality Summary: {quality_summary}")

            # ---- Prepare plot df ----
            plot_df = ts_df.rename(columns={
                'time_str': 'Date',
                'wse': 'WSE',
            }).copy()
            plot_df['Date'] = pd.to_datetime(plot_df['Date'])

            plot_title = name

            result = create_wse_time_series_plot(plot_df, plot_title)

            if result is not None:
                fig, wse_non, trend_wse = result
                st.plotly_chart(fig, use_container_width=True)

                # ---- Summary stats card ----
                if wse_non is not None and not wse_non.empty:
                    min_wse = wse_non["WSE"].min()
                    max_wse = wse_non["WSE"].max()
                    mean_wse = wse_non["WSE"].mean()
                    n_points = len(wse_non)

                    slope_yr_txt = "—"
                    r2_txt = "—"
                    p_txt = "—"
                    sig_txt = ""

                    if trend_wse is not None:
                        try:
                            slope_per_year = trend_wse.slope * 365.25
                            slope_yr_txt = f"{slope_per_year:+.3f} m/year"
                            r2_txt = f"{trend_wse.rvalue ** 2:.3f}"
                            p_txt = f"{trend_wse.pvalue:.4f}"

                            p = trend_wse.pvalue
                            if p < 0.001:
                                sig_txt = " ***"
                            elif p < 0.01:
                                sig_txt = " **"
                            elif p < 0.05:
                                sig_txt = " *"
                        except AttributeError:
                            pass

                    st.markdown(f"""
                    <div style="
                        background-color:#f0f2f6;
                        padding:14px 18px;
                        border-radius:10px;
                        margin-top:8px;
                        display:flex;
                        flex-wrap:wrap;
                        gap:24px;
                        font-size:0.9rem;
                    ">
                        <div><b>Min WSE:</b> {min_wse:.2f} m</div>
                        <div><b>Max WSE:</b> {max_wse:.2f} m</div>
                        <div><b>Mean WSE:</b> {mean_wse:.2f} m</div>
                        <div><b>Points:</b> {n_points}</div>
                        <div><b>Trend:</b> {slope_yr_txt}</div>
                        <div><b>R²:</b> {r2_txt}</div>
                        <div><b>p-value:</b> {p_txt}{sig_txt}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("📉 Not enough data to plot.")

            # ---- Data table ----
            with st.expander("📋 View Time-Series Data Table"):
                show_cols = ['time_str', 'wse', 'quality_label']
                if new_mode == 'lake' and 'area_total' in ts_df.columns:
                    show_cols.append('area_total')
                if new_mode == 'river' and 'width' in ts_df.columns:
                    show_cols.append('width')
                show_cols = [c for c in show_cols if c in ts_df.columns]

                st.dataframe(
                    ts_df[show_cols],
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.info(f"💡 No time-series data available for this {feature_display} in the SWOT database.")
            st.info("""
            **Possible reasons:**
            - The feature may not have been observed by SWOT
            - The feature ID might be incorrect
            - No data with quality 0 or 1 available
            - Try selecting a different feature
            """)
    else:
        st.info(f"👈 Click a {feature_display} on the map to view its time-series data.")

        
# =====================================================================
# OTHER PAGES
# =====================================================================

def render_how_to_use():
    """Render How to Use page."""
    st.title("📖 How to Use")

    st.markdown("""
### 🧭 Navigation

Use the top navigation bar to switch between:

- **Dashboard** — main map and data visualization
- **How to Use** — this guide
- **About SWOT** — background on the SWOT mission
- **About This Project** — team, acknowledgments, and contact

---

### 🎛️ Feature Type Selector

Under Dashboard Section, use the **🏞️ Lakes / 🌊 Rivers** toggle to switch between feature types:

- Only markers for the selected type are shown on the map at any time.
- Switching types **clears the current selection** — you'll need to pick a new marker.

---

### 🚀 Quick Start

1. Choose a feature type — click **🏞️ Lakes** or **🌊 Rivers** below the API status line.
2. Click a marker on the map to select that feature.
3. View the details in the right-side panel and the WSE time-series plot below.
4. Download the data (CSV) or the interactive plot (HTML) if needed.

---

### 🗺️ Dashboard Layout

The dashboard is organized into two main areas:

**Top section — Map & feature info**
- **Left:** Interactive satellite/street map with markers for the selected feature type
- **Right:** Information panel for the currently selected feature (ID, WSE, coordinates)

**Bottom section — Time-series**
- **Trend plot:** WSE over time, with outliers and a fitted trend line
- **Summary stats:** Min / Max / Mean WSE, data point count, trend slope, R², p-value
- **Data table:** All raw observations in a scrollable table (CSV export option is available inside this table view at the bottom of the dashboard)

---

### 📈 Understanding the Time-Series Plot

Each selected feature plots its Water Surface Elevation (WSE) over time:

- **Blue markers** — Good-quality observations (quality flag 0)
- **Orange markers** — Suspect observations (quality flag 1, use with caution)
- **Red ❌ markers** — Statistical outliers, detected via the IQR method
- **Navy dashed line** — Linear trend fitted through non-outlier points
- **Light-gray dashed line** — Mean WSE across non-outliers

**💾 Download Plot:** An option to download the interactive plot (HTML) is available at the top-right corner of the plot.

---

### 📊 Quality Indicators

Data is filtered to keep only usable observations:

| Flag | Label | Included in plot? |
|---|---|---|
| 0 | 🟦 Good | ✅ Yes |
| 1 | 🟧 Suspect | ✅ Yes |
| 2 | ❌ Bad | ❌ Automatically excluded |

---

### 📐 Trend Statistics

Beneath the plot, a summary card reports:

- **Min / Max / Mean WSE** — from non-outlier points only
- **Trend** — annualized rate of change (m/year); a positive value means the water surface is rising
- **R²** — how well the trend line fits the data (0 = no fit, 1 = perfect)
- **p-value** — statistical significance of the trend:
  - `***` → p < 0.001 (highly significant)
  - `**` → p < 0.01
  - `*` → p < 0.05 (significant)
  - *(no stars)* → not statistically significant

---

### 🔧 Troubleshooting

**No time-series data appears for a feature**
- Some lakes/rivers were not observed by SWOT during the covered period
- Try a different feature nearby
- Click **🔄 Refresh Time-Series Data** to retry the API call

**Markers don't respond to clicks**
- Make sure the feature type radio button matches what you're trying to click
- Zoom in slightly — markers can be close together in dense areas

**"API Connection" warning at the top**
- The Hydrocron API may be temporarily unavailable
- Try again in a few minutes

**Map is slow or unresponsive**
- Toggle off the **🏞️ Nepal Rivers** layer via the map's Layer Control
- Reduce the number of visible markers by zooming into a smaller area

---

### 📚 Data Sources

- **SWOT satellite data:** NASA / CNES — retrieved via the [Hydrocron API](https://podaac.github.io/hydrocron/user-guide/sword-versions/)
- **Prior lakes:** PLD ([Prior Lake Database](https://doi.org/10.1029/2023WR036896))
- **River nodes:** SWORD ([SWOT River Database](https://doi.org/10.5281/zenodo.15299138))
- **Basemaps:** Esri Satellite / OpenStreetMap / Topographic
""")


def render_about_swot():
    """Render About SWOT page."""
    st.title("🛰️ About the SWOT Mission")

    st.markdown("""
### 🌍 Mission Overview

SWOT (Surface Water and Ocean Topography) is a groundbreaking Earth-observation satellite mission launched on **December 16, 2022**. It is an international partnership jointly developed by **NASA**, **CNES** (France), **CSA** (Canada), and **UKSA** (UK). Unlike traditional satellite altimetry that measures along a single narrow track, SWOT provides the first-ever global, two-dimensional observations of Earth's surface water.

### 🎯 What SWOT Measures

SWOT is designed to measure key hydrological variables across the globe:

- Water Surface Elevation (WSE)
- Surface Water Extent (SWE)
- Water-surface slope
- And many other related characteristics of inland water surfaces

### 📡 Revolutionary Technology: The KaRIn Instrument

The core of the SWOT mission is the **Ka-band Radar Interferometer (KaRIn)**. Operating at 35.75 GHz, it uses two antennas separated by a 10-meter baseline to observe two wide swaths simultaneously.
""")

    # --- SWOT KaRIn image (standalone call, outside the markdown string) ---
    st.image(
        str(DATAS_DIR / "swot_karin_concept.jpg"),
        caption=(
            "Conceptual view of the SWOT mission — KaRIn swaths (yellow polygons) "
            "and Ku-band nadir altimeter (yellow line) (Biancamaria et al., 2016)."
        ),
        use_container_width=True,
    )

    st.markdown("""
- **Each swath:** ~50 km wide
- **Combined coverage:** ~120 km
- **Gap between swaths:** ~20 km

### 📊 Key Data Products

SWOT provides High-Rate (HR) products tailored for inland water applications:

- **L2_HR_PIXC:** Geolocated measurements of individual water pixels.
- **L2_HR_RiverSP:** Reach- and node-based river observations (organized via the SWORD database).
- **L2_HR_LakeSP:** Observations for lakes and reservoirs.
- **L2_HR_Raster:** Gridded water-surface and water-extent information.

### 🇳🇵 Importance & Applications for Nepal

Nepal's complex mountainous terrain and spatially limited hydrological observations make SWOT particularly valuable:

**Why SWOT matters for Nepal:**

- **Spatial Coverage:** Provides distributed water-surface information across remote and inaccessible regions.
- **Complementary Data:** Fills the gaps left by conventional point-based gauge measurements.
- **Resource Management:** Supports flood studies, discharge estimation, and broader hydrological analysis in data-scarce mountain environments.

**Applications for Nepal:**

- Monitor glacial lake changes in the Himalayas
- Support hydropower planning and reservoir operations
- Assess water availability for agriculture and irrigation
- Early warning for glacial lake outburst floods (GLOFs)

### ⚠️ Coverage & Important Considerations

- **Global Coverage:** SWOT observes more than ~90% of Earth's surface water in each 21-day science repeat cycle.
- **Revisit Frequency:** Observations are not continuous; exact availability for a specific river or lake depends on the satellite's orbital geometry.
- **Measurement Quality:** Data accuracy can be influenced by narrow river widths, dense vegetation, complex terrain, and water-surface conditions.
- **Validation:** For critical applications, SWOT data should be cross-checked with in-situ (ground-based) observations when available.

### 👥 Who Can Use This Data?

SWOT data is made openly accessible and provides immense value to a wide range of users:

- **Researchers & Academics:** For hydrological modelling, climate change studies, and academic research.
- **Water Resource Managers:** For monitoring reservoir levels, lake storage variations, and river dynamics.
- **Policymakers & Planners:** For informed decision-making regarding flood risk assessment and water resource allocation.
- **Students & Developers:** For building analytical tools, interactive dashboards, and educational projects.
- **Farmers & Agricultural Planners:** For understanding local water availability, planning irrigation, and adapting to seasonal water changes.
- **Humanitarian Agencies:** For disaster response, flood mapping, drought monitoring, and supporting vulnerable communities.
- **Curious Members of the Public:** For exploring local lakes and rivers, and staying informed about environmental changes.
""")


def render_contact_us():
    """Render About This Project / Contact page."""
    st.title("📬 About This Project")

    st.markdown("""
This web application is developed as part of a Master's thesis. This is the first version of the web app.<br>
This web app and its content were developed by **Bishal Dahal** under the supervision of:

- **Dr. Pawan Kumar Bhattarai**<br>&nbsp;&nbsp;&nbsp;&nbsp;Department of Civil Engineering, Institute of Engineering, Pulchowk Campus
- **Asst. Prof. Rocky Talchabhadel, PhD**<br>&nbsp;&nbsp;&nbsp;&nbsp;Department of Civil and Environmental Engineering, Jackson State University

*Note: Development is currently underway. We apologize for any inconvenience and appreciate your patience.*

### Acknowledgments

- NASA SWOT Mission for satellite data
- SWORD and PLD for prior lake and river database
- Hydrocron API for extracting the data

### For General Inquiries

**Bishal Dahal**<br>📧 Email: 080mswre006.bishal@pcampus.edu.np<br>💼 LinkedIn: [linkedin.com/in/bishaldahal1997](https://linkedin.com/in/bishaldahal1997)
""", unsafe_allow_html=True)