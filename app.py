# app.py
import streamlit as st
from strategy import ValueMomentumStrategy
from storage.watchlist_manager import MultiWatchlistManager
from helpers import create_results_table, get_index_constituents
from datetime import datetime
import json

# Import tabs
from tabs.watchlist_tab import render_watchlist_tab
from tabs.analysis_tab import render_analysis_tab
from tabs.scanner_tab import render_scanner_tab
from tabs.multi_timeframe_tab import render_multi_timeframe_tab

# Import file storage
from storage.file_storage import FileStorage


def create_streamlit_app():
    st.set_page_config(
        page_title="Värde & Momentum Aktiestrategi",
        page_icon="📈",
        layout="wide"
    )

    st.title("Värde & Momentum Aktiestrategi")

    # Initialize shared state objects if they don't exist
    if 'strategy' not in st.session_state:
        st.session_state.strategy = ValueMomentumStrategy()

    if 'watchlist_manager' not in st.session_state:
        st.session_state.watchlist_manager = MultiWatchlistManager()
        # Enable debug mode initially to diagnose issues
        st.session_state.watchlist_manager.debug_mode = True
        st.session_state.watchlist_manager.cookie_manager.debug_mode = True

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
    }

    # Create the tabs
    tab_names = list(tabs.keys())
    streamlit_tabs = st.tabs(tab_names)

    # Store the current tab in session state
    if 'current_tab' not in st.session_state:
        st.session_state['current_tab'] = tab_names[0]

    # Render each tab's content
    for i, (name, render_function) in enumerate(tabs.items()):
        with streamlit_tabs[i]:
            # When this tab is active, update the current tab in session state
            st.session_state['current_tab'] = name
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

    # Backup & Restore in sidebar
    with st.sidebar.expander("Backup & Restore", expanded=False):
        # Save current watchlists
        if 'watchlists' in st.session_state and 'file_storage' in st.session_state:
            st.session_state.file_storage.save_watchlists(
                st.session_state.watchlists,
                st.session_state.active_watchlist_index
            )

        # Load watchlists from file
        if 'file_storage' in st.session_state:
            loaded_data = st.session_state.file_storage.load_watchlists()
            if loaded_data:
                st.session_state.watchlists = loaded_data["watchlists"]
                st.session_state.active_watchlist_index = loaded_data["active_index"]
                st.success("Watchlists loaded successfully!")
                st.button("Refresh App", on_click=lambda: st.rerun())

    # Strategy information in the sidebar (shown on all tabs)
    with st.sidebar.expander("Om Värde & Momentum-strategin"):
        st.write("""
        **Värde & Momentum-strategin** kombinerar fundamentala och tekniska kriterier för aktier:
        
        **Fundamentala kriterier:**
        * Bolaget ska tjäna pengar
        * Bolaget ska öka omsättning och vinst, eller öka omsättning med stabil vinstmarginal
        * Bolaget ska handlas till ett rimligt P/E-tal jämfört med sig själv
        
        **Tekniska kriterier:**
        * Bolaget ska sätta högre bottnar
        * Bolaget ska handlas över MA40 (veckovis) och gärna MA4 för extra momentum
        * Bolaget ska ha ett RSI över 50
        * Starkt om bolaget bryter upp ur en konsolideringsfas
        * Starkt om bolaget handlas till sin högsta 52-veckorsnivå
        
        Strategin följer principen "Rid vinnarna och sälj förlorarna". Vid brott under MA40, sälj direkt eller bevaka hårt. Ta förluster tidigt.
        """)

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Utvecklad med Python och Streamlit**")


def render_storage_status():
    """Render storage status and backup/restore functionality"""
    manager = st.session_state.watchlist_manager

    # Show storage status
    if hasattr(manager, 'storage_status') and manager.storage_status:
        status = manager.storage_status

        if status == "saved":
            st.sidebar.success("✅ Watchlists saved to browser storage")
        elif status == "loaded":
            st.sidebar.success("✅ Watchlists loaded from browser storage")
        elif status == "save_failed":
            st.sidebar.error(
                "❌ Failed to save watchlists - using manual backup recommended")
        elif status == "initialized":
            st.sidebar.info(
                "ℹ️ New watchlist created - will be saved to browser storage")

    # Add a button to test storage
    if st.sidebar.button("Test Browser Storage"):
        manager.cookie_manager.test_localstorage()

    # Manual backup/restore functionality
    with st.sidebar.expander("Storage Options", expanded=False):
        st.write("If automatic storage isn't working, use these options:")

        # Export current watchlists to JSON file
        if 'watchlists' in st.session_state:
            # Use the new export_all_watchlists method if available
            if hasattr(manager, 'export_all_watchlists'):
                json_data = manager.export_all_watchlists()
            else:
                # Fallback to manual JSON creation
                from datetime import datetime
                import json
                data = {
                    "watchlists": st.session_state.watchlists,
                    "active_index": st.session_state.get('active_watchlist_index', 0),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                json_data = json.dumps(data, indent=2)

            # Provide download button
            st.download_button(
                "💾 Download Backup",
                json_data,
                "watchlists_backup.json",
                "application/json"
            )

        # Import from JSON file
        st.write("Restore from backup:")
        uploaded_file = st.file_uploader("Upload Backup File", type=[
                                         'json'], key="storage_uploader")
        if uploaded_file is not None:
            try:
                import json
                import_data = json.loads(uploaded_file.getvalue().decode())

                # Use the new import_all_watchlists method if available
                if hasattr(manager, 'import_all_watchlists'):
                    success = manager.import_all_watchlists(
                        uploaded_file.getvalue().decode())
                    if success:
                        st.success(
                            f"Restored {len(st.session_state.watchlists)} watchlists!")
                        if st.button("Reload App", key="storage_reload"):
                            st.rerun()
                else:
                    # Fallback to manual import
                    if "watchlists" in import_data:
                        st.session_state.watchlists = import_data["watchlists"]
                        st.session_state.active_watchlist_index = import_data.get(
                            "active_index", 0)
                        # Try to save to cookies as well
                        manager._save_to_cookies()
                        st.success(
                            f"Restored {len(import_data['watchlists'])} watchlists!")
                        if st.button("Reload App", key="storage_reload2"):
                            st.rerun()
                    else:
                        st.error("Invalid backup file")
            except Exception as e:
                st.error(f"Error importing backup: {str(e)}")


if __name__ == "__main__":
    create_streamlit_app()
