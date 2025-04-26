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

    # Check URL parameters for shared watchlist
    handle_url_params()

    # Define tabs - easily extensible
    tabs = {
        "Watchlist & Batch Analysis": render_watchlist_tab,
        "Enskild Aktieanalys": render_analysis_tab,
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

    # Manual backup/restore functionality in sidebar for localStorage fallback
    st.sidebar.markdown("---")

    # Test localStorage and show status
    if st.sidebar.button("Test Storage"):
        st.session_state.watchlist_manager.cookie_manager.test_localstorage()

    # Add manual backup/restore to sidebar (always available)
    with st.sidebar.expander("Backup/Restore Watchlists", expanded=True):
        st.write("If automatic storage isn't working, use these options:")

        # Export current watchlists to JSON file
        if 'watchlists' in st.session_state:
            data = {
                "watchlists": st.session_state.watchlists,
                "active_index": st.session_state.get('active_watchlist_index', 0),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            json_data = json.dumps(data, indent=2)
            st.download_button(
                "Download Backup",
                json_data,
                "watchlists_backup.json",
                "application/json"
            )

        # Import from JSON file
        st.write("Restore from backup:")
        uploaded_file = st.file_uploader("Upload Backup File", type=['json'])
        if uploaded_file is not None:
            try:
                import_data = json.loads(uploaded_file.getvalue().decode())
                if "watchlists" in import_data:
                    st.session_state.watchlists = import_data["watchlists"]
                    st.session_state.active_watchlist_index = import_data.get(
                        "active_index", 0)
                    # Try to save to cookies as well
                    st.session_state.watchlist_manager._save_to_cookies()
                    st.success(
                        f"Restored {len(import_data['watchlists'])} watchlists!")
                    st.button("Reload App", on_click=lambda: st.rerun())
                else:
                    st.error("Invalid backup file")
            except Exception as e:
                st.error(f"Error importing backup: {str(e)}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Utvecklad med Python och Streamlit**")


if __name__ == "__main__":
    create_streamlit_app()
