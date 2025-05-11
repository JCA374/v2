# app.py
import streamlit as st
from strategy import ValueMomentumStrategy
from storage.watchlist_manager import MultiWatchlistManager
from storage.supabase_stock_db import SupabaseStockDB  # Import Supabase storage
from helpers import create_results_table, get_index_constituents
from datetime import datetime
import json
import os
import shutil  # Added to fix the disk_usage error
import uuid  # Added for generating unique IDs

# Import tabs
from tabs.watchlist_tab import render_watchlist_tab
from tabs.analysis_tab import render_analysis_tab
from tabs.scanner_tab import render_scanner_tab
from tabs.multi_timeframe_tab import render_multi_timeframe_tab
# Import the new storage settings tab
from tabs.storage_settings_tab import render_storage_settings_tab

# Import file storage
from storage.file_storage import FileStorage


def create_streamlit_app():
    st.set_page_config(
        page_title="Värde & Momentum Aktiestrategi",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    hide_streamlit_style = """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
        """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    st.title("Värde & Momentum Aktiestrategi")

    # Initialize Supabase database connection if it doesn't exist
    if 'supabase_db' not in st.session_state:
        st.session_state.supabase_db = SupabaseStockDB()
        # Enable debug mode initially to diagnose issues
        st.session_state.supabase_db.debug_mode = True

    # Initialize shared state objects if they don't exist
    if 'strategy' not in st.session_state:
        st.session_state.strategy = ValueMomentumStrategy()

    # Initialize watchlist manager
    if 'watchlist_manager' not in st.session_state:
        st.session_state.watchlist_manager = MultiWatchlistManager()
        # Enable debug mode initially to diagnose issues
        st.session_state.watchlist_manager.debug_mode = True

    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = []

    # Initialize file storage for backup/restore
    if 'file_storage' not in st.session_state:
        st.session_state.file_storage = FileStorage()

    # Check URL parameters for shared watchlist
    handle_url_params()

    # Define tabs - easily extensible
    tabs = {
        "Watchlist & Batch Analysis": render_watchlist_tab,
        "Enskild Aktieanalys": render_analysis_tab,
        "Stock Scanner": render_scanner_tab,
        "Multi-Timeframe Analysis": render_multi_timeframe_tab,
        "Storage Settings": render_storage_settings_tab,
    }

    # Get current tab from query params (this is more reliable than session state)
    current_tab_index = handle_tab_state()

    # Create the tabs
    tab_names = list(tabs.keys())
    streamlit_tabs = st.tabs(tab_names)

    # Render the tab content
    for i, (name, render_function) in enumerate(tabs.items()):
        with streamlit_tabs[i]:
            # When this tab is active, update the URL parameter
            if i == current_tab_index:
                st.query_params["tab"] = str(i)

            # Store the current tab in session state (for components that need it)
            st.session_state['current_tab'] = name

            # Render the tab content
            render_function()

    # Render sidebar
    render_sidebar()


def handle_url_params():
    """Handle URL parameters like shared watchlist links"""
    query_params = st.query_params
    if "shared_watchlist" in query_params:
        encoded_data = query_params["shared_watchlist"][0]
        imported_index = st.session_state.watchlist_manager.import_from_share_link(
            encoded_data)
        if imported_index is not None:
            st.session_state.watchlist_manager.set_active_watchlist(
                imported_index)
            st.success("Importerad watchlist från delad länk!")
            # Clear the parameter after import to avoid reimporting on refresh
            st.query_params.clear()


def render_storage_status():
    """
    Render the storage status section in the Streamlit sidebar.
    Shows information about the current Supabase database connection.
    """
    import streamlit as st

    st.sidebar.header("Storage Status")

    try:
        # Display Supabase connection status
        if 'supabase_db' in st.session_state and st.session_state.supabase_db.supabase:
            st.sidebar.success("✅ Connected to Supabase")
            
            # Show basic connection info
            supabase_url = st.secrets.get("supabase_url", "")
            display_url = supabase_url.replace("https://", "").replace("http://", "").rstrip("/")
            st.sidebar.info(f"Database: {display_url}")
            
            # Try to get some stats from the database
            try:
                # Get number of stocks with price data
                price_response = st.session_state.supabase_db.supabase.table("stock_prices").select("ticker").execute()
                if price_response.data:
                    unique_tickers = len(set(row['ticker'] for row in price_response.data))
                    st.sidebar.metric("Stocks with Price Data", unique_tickers)
            except Exception as e:
                st.sidebar.warning(f"Could not retrieve stats: {e}")
        else:
            st.sidebar.warning("⚠️ Not connected to Supabase database")
            st.sidebar.info("Check your secrets.toml file configuration")

    except Exception as e:
        st.sidebar.error(f"Error rendering storage status: {e}")


def render_sidebar():
    """Render the sidebar content"""
    # Sidebar for stock analysis input in the second tab
    if st.session_state.get('current_tab') == 'Enskild Aktieanalys':
        st.sidebar.header("Aktiesök")
        ticker = st.sidebar.text_input(
            "Aktiesymbol (t.ex. AAPL, ERIC-B.ST)", "AAPL")

        if st.sidebar.button("Analysera"):
            st.session_state['analyze_ticker'] = ticker
            st.rerun()

    # Add storage status - ONLY if watchlist_manager is initialized
    if 'watchlist_manager' in st.session_state:
        render_storage_status()

    # Add database status indicator in sidebar
    if 'supabase_db' in st.session_state and 'watchlist_manager' in st.session_state:
        db_info = st.session_state.watchlist_manager.get_database_info()
        with st.sidebar.expander("Database Status", expanded=False):
            st.info(f"Database: {db_info.get('path', 'Unknown')}")
            st.write(f"Type: {db_info.get('size_formatted', 'Cloud DB')}")
            st.write(f"Watchlists: {db_info.get('watchlist_count', 0)}")
            st.write(f"Total stocks: {db_info.get('stock_count', 0)}")

            if st.button("Open Storage Settings", key="open_storage_settings"):
                # Set the current tab to Storage Settings
                tab_index = list(["Watchlist & Batch Analysis", "Enskild Aktieanalys",
                                  "Stock Scanner", "Multi-Timeframe Analysis",
                                  "Storage Settings"]).index("Storage Settings")
                st.session_state['current_tab'] = "Storage Settings"
                st.rerun()

    # Quick backup option in sidebar
    with st.sidebar.expander("Quick Backup", expanded=False):
        if 'watchlists' in st.session_state and 'watchlist_manager' in st.session_state:
            # Generate backup JSON for download
            data = {
                "watchlists": st.session_state.watchlists,
                "active_index": st.session_state.active_watchlist_index,
                "export_date": datetime.now().isoformat()
            }
            json_data = json.dumps(data, indent=2)

            st.download_button(
                "Download Backup File",
                json_data,
                file_name=f"watchlists_backup_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )

            st.info("For more options, go to the Storage Settings tab")

        # Upload option
        uploaded_file = st.file_uploader(
            "Restore from backup",
            type=["json"],
            key="sidebar_uploader",
            help="Upload a backup file to restore your watchlists"
        )

        if uploaded_file is not None:
            try:
                data = json.loads(uploaded_file.getvalue().decode())
                if "watchlists" in data:
                    # Update session state
                    st.session_state.watchlists = data["watchlists"]
                    st.session_state.active_watchlist_index = data.get(
                        "active_index", 0)
                    # Save to database
                    st.session_state.watchlist_manager._save_to_storage()
                    st.success("Watchlists restored successfully!")
                    st.button("Reload App", on_click=lambda: st.rerun())
                else:
                    st.error("Invalid backup file format")
            except Exception as e:
                st.error(f"Error restoring backup: {str(e)}")


def handle_tab_state():
    """
    Handles tab state persistence using query parameters and session state for backup.
    This is more reliable with Streamlit's rendering model.
    """
    # Get the tabs defined in the app
    tab_names = ["Watchlist & Batch Analysis", "Enskild Aktieanalys",
                 "Stock Scanner", "Multi-Timeframe Analysis",
                 "Storage Settings"]

    # Define tab index for Stock Scanner
    SCANNER_TAB_INDEX = 2

    # Initialize session state for tab tracking if not exists
    if 'current_tab_index' not in st.session_state:
        st.session_state.current_tab_index = 0

    # Add a flag to protect against tab switching during initial widget interaction
    if 'widget_interaction_started' not in st.session_state:
        st.session_state.widget_interaction_started = False

    # Check if a tab is specified in the URL query parameters
    query_params = st.query_params
    tab_param = query_params.get("tab", [None])[0]

    # Special handling to prevent unintended tab switches
    if 'prevent_tab_change' in st.session_state and st.session_state.prevent_tab_change:
        # If we're in the scanner tab and this is our first widget interaction,
        # force us to stay in the scanner tab
        if st.session_state.current_tab_index == SCANNER_TAB_INDEX:
            tab_index = SCANNER_TAB_INDEX
            st.session_state.widget_interaction_started = True
            return tab_index

    # Normal processing for tab state
    if tab_param is not None:
        try:
            tab_index = int(tab_param)
        except:
            # Use session state as fallback if query param is invalid
            tab_index = st.session_state.current_tab_index
    else:
        # Use session state if no query param
        tab_index = st.session_state.current_tab_index

    # Make sure the tab index is valid
    if tab_index < 0 or tab_index >= len(tab_names):
        tab_index = 0

    # Store current tab index in session state for persistence
    st.session_state.current_tab_index = tab_index

    # Update the query parameter for the current tab only if it has changed
    if str(tab_index) != tab_param:
        st.query_params["tab"] = str(tab_index)

    # Return the current tab index to use when creating tabs
    return tab_index


if __name__ == "__main__":
    create_streamlit_app()