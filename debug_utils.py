import uuid
import streamlit as st
import json
import base64
import time
from datetime import datetime
import sys
import platform
import os



def add_debug_section(watchlist_manager):
    """Add a debug section to help troubleshoot cookie and storage issues"""

    with st.expander("Debug Tools", expanded=False):
        st.write("## Cookie and Watchlist Debugging")

        # System information
        st.write("### System Information")
        system_info = {
            "Python Version": sys.version,
            "Platform": platform.platform(),
            "Streamlit Version": st.__version__,
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Browser LocalStorage Available": "<Will be checked via JavaScript>"
        }
        st.json(system_info)

        # Add JavaScript to check localStorage availability
        st.markdown("""
        <script>
        try {
            localStorage.setItem('streamlit_test', 'test');
            localStorage.removeItem('streamlit_test');
            document.getElementById('storage-status').innerHTML = 'Available ✓';
        } catch (e) {
            document.getElementById('storage-status').innerHTML = 'Not Available ✗ - ' + e.message;
        }
        </script>
        <div id="storage-status"></div>
        """, unsafe_allow_html=True)

        # Current storage state
        st.write("### Current Storage State")

        # Session state information
        st.write(f"Session State Keys: {list(st.session_state.keys())}")
        if 'watchlists' in st.session_state:
            st.write(
                f"Number of watchlists in session: {len(st.session_state.watchlists)}")

        # Cookie information
        cookie_data = watchlist_manager.cookie_manager.load_cookie()
        if cookie_data:
            st.write(
                f"Cookie data found with {len(cookie_data.get('watchlists', []))} watchlists")
            st.write(
                f"Active watchlist index in cookie: {cookie_data.get('active_index', 'Not set')}")
            if 'timestamp' in cookie_data:
                st.write(f"Last updated: {cookie_data['timestamp']}")
        else:
            st.write("No cookie data found")

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
            watchlist_manager.debug_mode = True
            st.write("Debug mode enabled - check console for details")

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

        # Storage alternative
        st.write("### Alternative Storage Solution")
        st.write("""
        If cookies aren't working on your browser, you can use the manual export/import
        functionality to save and load your watchlists.
        
        1. Use the 'Download Watchlists as JSON' button above to save your data
        2. Keep this file safe
        3. When you need to restore your watchlists, use the 'Upload JSON file' option
        """)


def test_cookie_storage():
    """Test if cookie storage is working properly"""
    # Create a unique test value
    test_value = f"test_{uuid.uuid4()}"
    test_data = {"test": test_value, "timestamp": str(datetime.now())}

    # Create a test cookie manager
    from storage.cookie_manager import CookieManager
    test_manager = CookieManager(cookie_name="test_cookie")
    test_manager.debug_mode = True

    # Try to save the test data
    st.write("Saving test cookie...")
    save_result = test_manager.save_cookie(test_data)
    if not save_result:
        st.write("Failed to save test cookie")
        return False

    # Add a small delay to let the browser process
    time.sleep(0.5)
    st.write("Loading test cookie...")

    # Try to load the data back
    loaded_data = test_manager.load_cookie()
    if loaded_data and loaded_data.get("test") == test_value:
        # Clean up after test
        st.write("Test passed! Clearing test cookie...")
        test_manager.clear_cookie()
        return True
    else:
        st.write(f"Expected: {test_value}")
        st.write(f"Got: {loaded_data}")
        return False


def check_browser_storage_support():
    """Check if the browser supports localStorage"""
    result = st.empty()

    js = """
    <script>
    (function() {
        let storageSupported = false;
        let errorMessage = "";
        
        try {
            localStorage.setItem('test', 'test');
            localStorage.removeItem('test');
            storageSupported = true;
        } catch (e) {
            errorMessage = e.toString();
        }
        
        // Send result to Streamlit
        const data = {
            supported: storageSupported,
            error: errorMessage
        };
        
        // Find the input element
        const inputElement = window.parent.document.querySelector('input[aria-label="storage_check_result"]');
        if (inputElement) {
            inputElement.value = JSON.stringify(data);
            inputElement.dispatchEvent(new Event('input', { bubbles: true }));
        }
    })();
    </script>
    """
    st.markdown(js, unsafe_allow_html=True)

    # Create a hidden input to receive the result
    check_result = st.text_input(
        "storage_check_result",
        "",
        key="storage_check_result",
        label_visibility="hidden"
    )

    if check_result:
        try:
            data = json.loads(check_result)
            return data
        except:
            return {"supported": False, "error": "Failed to parse result"}

    return {"supported": None, "error": "Test pending"}
