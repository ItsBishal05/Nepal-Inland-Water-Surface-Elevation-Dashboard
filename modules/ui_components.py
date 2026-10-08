import streamlit as st


def setup_page():
    """Setup page configuration and styling"""

    # Hide sidebar and adjust layout for top navigation
    st.markdown("""
        <style>
        /* Hide sidebar completely */
        [data-testid="stSidebar"] {
            display: none;
        }

        /* Make main content full width */
        .main .block-container {
            padding-top: 1rem;
            padding-left: 2rem;
            padding-right: 2rem;
            max-width: 100%;
        }

        /* Ensure top nav is visible and styled properly */
        .nav-container {
            margin-top: 0;
            margin-bottom: 20px;
        }

        /* Shrink success/warning alerts */
        div[data-testid="stAlert"] p {
            font-size: 0.85rem !important;
        }

        /* Style the feature-type radio as a segmented control */
        div[role="radiogroup"] {
            display: inline-flex !important;
            gap: 8px !important;
            background-color: #f0f2f6;
            padding: 6px;
            border-radius: 10px;
            margin-bottom: 12px;
        }
        div[role="radiogroup"] > label {
            background-color: transparent;
            padding: 6px 14px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s ease;
            margin: 0 !important;
        }
        div[role="radiogroup"] > label:hover {
            background-color: #e0e2e6;
        }
        /* Hide the radio circle itself — the label becomes the pill */
        div[role="radiogroup"] > label > div:first-child {
            display: none !important;
        }
        </style>
    """, unsafe_allow_html=True)


def render_navigation():
    """Render top navigation bar with side-by-side items"""

    # Custom CSS for top navigation
    st.markdown("""
        <style>
        /* Top navigation bar styles */
        .nav-container {
            background-color: #f0f2f6;
            padding: 10px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            gap: 20px;
            align-items: center;
            flex-wrap: wrap;
        }
        .nav-item {
            padding: 8px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 500;
            color: #333;
            text-decoration: none;
            transition: background-color 0.3s;
        }
        .nav-item:hover {
            background-color: #e0e2e6;
        }
        .nav-item.active {
            background-color: #0066cc;
            color: white;
        }
        .nav-item.active:hover {
            background-color: #0052a3;
        }

        /* Button styling override */
        .stButton button {
            width: 100%;
            border: none;
            padding: 10px 20px;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        .stButton button[kind="primary"] {
            background-color: #0066cc !important;
            color: white !important;
        }
        .stButton button[kind="secondary"] {
            background-color: #f0f2f6 !important;
            color: #333 !important;
        }
        .stButton button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        </style>
    """, unsafe_allow_html=True)

    # Define navigation items
    nav_items = ['Dashboard', 'How to Use', 'About SWOT', 'Contact Us']

    # Create columns for each nav item (side by side)
    cols = st.columns(len(nav_items))

    for idx, item in enumerate(nav_items):
        with cols[idx]:
            # Check if this item is currently active
            is_active = st.session_state.page == item

            # Create button with appropriate styling
            if st.button(
                item,
                key=f"nav_{item}",
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                st.session_state.page = item
                st.rerun()

    # Footer
    st.caption("Nepal's Inland Water Surface Elevation Dashboard v1.0")