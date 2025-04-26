# tabs/debug_tab.py
import streamlit as st
import json
from datetime import datetime
import sys
import platform
import os
from debug_utils import add_debug_section


def render_debug_tab():
    """Render the debug tab for watchlist and cookie troubleshooting"""
    st.header("Debug och Felsökning")

    # Access shared objects from session state
    watchlist_manager = st.session_state.watchlist_manager

    # Enable debugging mode for the watchlist and cookie managers
    debug_mode = st.checkbox("Aktivera debug läge", value=False)
    if debug_mode:
        watchlist_manager.debug_mode = True
        watchlist_manager.cookie_manager.debug_mode = True
    else:
        watchlist_manager.debug_mode = False
        watchlist_manager.cookie_manager.debug_mode = False

    # System information
    with st.expander("Systeminformation", expanded=True):
        system_info = {
            "Python Version": sys.version,
            "Platform": platform.platform(),
            "Streamlit Version": st.__version__,
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Session State Keys": list(st.session_state.keys())
        }
        st.json(system_info)

    # Current watchlist state
    with st.expander("Watchlist Status", expanded=True):
        watchlist_manager.debug_watchlists()

    # Cookie management tools
    with st.expander("Cookie-hantering", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Testa Cookie Storage"):
                # Add test code for cookie storage
                from debug_utils import test_cookie_storage
                result = test_cookie_storage()
                if result:
                    st.success("Cookie storage test lyckades!")
                else:
                    st.error("Cookie storage test misslyckades!")

        with col2:
            if st.button("Tvinga Spara Watchlists"):
                result = watchlist_manager._save_to_cookies()
                if result:
                    st.success("Watchlists sparades till cookies")
                else:
                    st.error("Kunde inte spara watchlists till cookies")

        with col3:
            if st.button("Rensa Alla Cookies"):
                # Clear cookies
                watchlist_manager.cookie_manager.clear_cookie()
                if 'watchlists' in st.session_state:
                    del st.session_state['watchlists']
                if 'active_watchlist_index' in st.session_state:
                    del st.session_state['active_watchlist_index']
                st.success("Alla cookies och sessionsdata rensade")
                st.warning("Vänligen ladda om sidan för att se ändringar")

    # Manual cookie data handling
    with st.expander("Manuell Data-hantering", expanded=True):
        # Export current watchlists to JSON
        if 'watchlists' in st.session_state:
            data = {
                "watchlists": st.session_state.watchlists,
                "active_index": st.session_state.get('active_watchlist_index', 0),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            json_data = json.dumps(data, indent=2)
            st.download_button(
                "Ladda ner Watchlists som JSON",
                json_data,
                "watchlists_backup.json",
                "application/json"
            )

        # Import from JSON file
        st.write("#### Importera Watchlists från JSON")
        uploaded_file = st.file_uploader("Ladda upp JSON-fil", type=['json'])
        if uploaded_file is not None:
            try:
                import_data = json.loads(uploaded_file.getvalue().decode())
                if "watchlists" in import_data:
                    st.session_state.watchlists = import_data["watchlists"]
                    st.session_state.active_watchlist_index = import_data.get(
                        "active_index", 0)
                    watchlist_manager._save_to_cookies()
                    st.success(
                        f"Importerade {len(import_data['watchlists'])} watchlists från fil")
                    st.warning("Vänligen ladda om sidan för att se ändringar")
                else:
                    st.error("Ogiltig JSON-format - saknar 'watchlists' nyckel")
            except Exception as e:
                st.error(f"Fel vid import av JSON: {str(e)}")

    # Test creating a new watchlist directly in session state
    with st.expander("Test: Skapa Ny Watchlist Direkt", expanded=False):
        test_name = st.text_input("Namn på test-watchlist", "Test Watchlist")
        if st.button("Skapa Test-Watchlist"):
            if 'watchlists' not in st.session_state:
                st.session_state.watchlists = []

            new_watchlist = {
                "id": "test-" + datetime.now().strftime("%Y%m%d%H%M%S"),
                "name": test_name,
                "stocks": ["AAPL", "MSFT", "GOOG"]
            }

            st.session_state.watchlists.append(new_watchlist)
            st.success(f"Skapade test-watchlist med ID {new_watchlist['id']}")
            if not hasattr(watchlist_manager, "_save_to_cookies"):
                st.error("watchlist_manager saknar _save_to_cookies-metoden!")
            else:
                result = watchlist_manager._save_to_cookies()
                if result:
                    st.success("Sparade till cookies")
                else:
                    st.error("Kunde inte spara till cookies")

    # Add a logout button that will clear all data and reload the page
    st.markdown("---")
    if st.button("Starta om applikationen (rensa all data)", type="primary"):
        # Clear all session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        # Clear cookies
        if 'watchlist_manager' in st.session_state:
            st.session_state.watchlist_manager.cookie_manager.clear_cookie()

        # Use JavaScript to reload the page
        js = """
        <script>
        setTimeout(function() {
            window.location.href = window.location.pathname;
        }, 1000);
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)
        st.success("Rensar data och startar om...")
