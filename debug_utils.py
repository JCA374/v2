import streamlit as st
import json
import base64
import time
from datetime import datetime
import sys
import platform
import os


def add_debug_section(watchlist_manager):
    """Add a debug section to the app to help troubleshoot cookie issues"""

    with st.expander("Debug Tools", expanded=False):
        st.write("## Cookie and Watchlist Debugging")

        # System information
        st.write("### System Information")
        system_info = {
            "Python Version": sys.version,
            "Platform": platform.platform(),
            "Streamlit Version": st.__version__,
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.json(system_info)

        # Cookie tools
        st.write("### Cookie Tools")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Test Cookie Storage"):
                test_result = test_cookie_storage()
                if test_result:
                    st.success("Cookie storage test succeeded!")
                else:
                    st.error("Cookie storage test failed!")

        with col2:
            if st.button("Force Save Watchlists"):
                result = watchlist_manager._save_to_cookies()
                if result:
                    st.success("Watchlists forcefully saved to cookies")
                else:
                    st.error("Failed to save watchlists to cookies")

        with col3:
            if st.button("Clear All Cookies"):
                watchlist_manager.cookie_manager.clear_cookie()
                if 'watchlists' in st.session_state:
                    del st.session_state['watchlists']
                if 'active_watchlist_index' in st.session_state:
                    del st.session_state['active_watchlist_index']
                st.success("All cookies and session data cleared")
                st.warning("Please refresh the page to see changes")

        # Enable debug mode for cookie manager
        enable_debug = st.checkbox("Enable Debug Logging", value=False)
        if enable_debug:
            watchlist_manager.cookie_manager.debug_mode = True

        # Display current watchlist state
        if st.button("Show Current Watchlist State"):
            watchlist_manager.debug_watchlists()

        # Manual cookie management
        st.write("### Manual Cookie Management")

        # Export current watchlists to JSON
        if 'watchlists' in st.session_state:
            data = {
                "watchlists": st.session_state.watchlists,
                "active_index": st.session_state.get('active_watchlist_index', 0),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            json_data = json.dumps(data, indent=2)
            st.download_button(
                "Download Watchlists as JSON",
                json_data,
                "watchlists_backup.json",
                "application/json"
            )

        # Import from JSON file
        st.write("#### Import Watchlists from JSON")
        uploaded_file = st.file_uploader("Upload JSON file", type=['json'])
        if uploaded_file is not None:
            try:
                import_data = json.loads(uploaded_file.getvalue().decode())
                if "watchlists" in import_data:
                    st.session_state.watchlists = import_data["watchlists"]
                    st.session_state.active_watchlist_index = import_data.get(
                        "active_index", 0)
                    watchlist_manager._save_to_cookies()
                    st.success(
                        f"Imported {len(import_data['watchlists'])} watchlists from file")
                    st.warning("Please refresh the page to see changes")
                else:
                    st.error("Invalid JSON format - missing 'watchlists' key")
            except Exception as e:
                st.error(f"Error importing JSON: {str(e)}")


def test_cookie_storage():
    """Test if cookie storage is working properly"""
    # Create a unique test value
    test_value = f"test_{int(time.time())}"
    test_data = {"test": test_value}

    # Create a test cookie manager
    from cookie_manager import CookieManager
    test_manager = CookieManager(cookie_name="test_cookie")

    # Try to save the test data
    save_result = test_manager.save_cookie(test_data)
    if not save_result:
        st.write("Failed to save test cookie")
        return False

    # Add a small delay to let the browser process
    time.sleep(0.5)

    # Try to load the data back
    loaded_data = test_manager.load_cookie()
    if loaded_data and loaded_data.get("test") == test_value:
        # Clean up after test
        test_manager.clear_cookie()
        return True
    else:
        st.write(f"Expected: {test_value}")
        st.write(f"Got: {loaded_data}")
        return False
