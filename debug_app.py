import streamlit as st
import os
import sys

st.set_page_config(page_title="Debug App", layout="wide")

st.title("Debug Information")

st.write("## System Info")
st.write(f"Python version: {sys.version}")
st.write(f"Working directory: {os.getcwd()}")

st.write("## Import Test")
try:
    from storage.watchlist_manager import MultiWatchlistManager
    st.success("✅ Successfully imported MultiWatchlistManager")
except Exception as e:
    st.error(f"❌ Failed to import MultiWatchlistManager: {str(e)}")
    st.code(f"{type(e).__name__}: {str(e)}")

try:
    from storage.db_storage import DatabaseStorage
    st.success("✅ Successfully imported DatabaseStorage")
except Exception as e:
    st.error(f"❌ Failed to import DatabaseStorage: {str(e)}")
    st.code(f"{type(e).__name__}: {str(e)}")

try:
    from tabs.storage_settings_tab import render_storage_settings_tab
    st.success("✅ Successfully imported storage_settings_tab")
except Exception as e:
    st.error(f"❌ Failed to import storage_settings_tab: {str(e)}")
    st.code(f"{type(e).__name__}: {str(e)}")

st.write("## Directory Listing")
try:
    st.write("### Main directory:")
    st.write(os.listdir("."))

    if os.path.exists("storage"):
        st.write("### Storage directory:")
        st.write(os.listdir("storage"))
    else:
        st.error("❌ Storage directory not found")

    if os.path.exists("tabs"):
        st.write("### Tabs directory:")
        st.write(os.listdir("tabs"))
    else:
        st.error("❌ Tabs directory not found")
except Exception as e:
    st.error(f"Error listing directories: {str(e)}")

st.write("## Database Test")
try:
    # Only try to create DB if imports worked
    if 'DatabaseStorage' in locals():
        home_dir = os.path.expanduser("~")
        test_dir = os.path.join(home_dir, ".streamlit_test")
        test_file = os.path.join(test_dir, "test_db.db")

        st.write(f"Attempting to create test directory: {test_dir}")
        os.makedirs(test_dir, exist_ok=True)
        st.success(f"✅ Created directory")

        st.write(f"Attempting to create test database: {test_file}")
        db = DatabaseStorage(test_file)
        st.success(f"✅ Created test database")

        # Test saving something
        watchlists = [
            {"id": "test", "name": "Test Watchlist", "stocks": ["AAPL"]}]
        db.save_watchlists(watchlists, 0)
        st.success("✅ Saved test data to database")
except Exception as e:
    st.error(f"❌ Database test failed: {str(e)}")
    import traceback
    st.code(traceback.format_exc())

if st.button("Try importing all tabs"):
    try:
        from tabs.watchlist_tab import render_watchlist_tab
        from tabs.analysis_tab import render_analysis_tab
        from tabs.scanner_tab import render_scanner_tab
        from tabs.multi_timeframe_tab import render_multi_timeframe_tab
        st.success("✅ Successfully imported all tabs")
    except Exception as e:
        st.error(f"❌ Failed to import tabs: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
