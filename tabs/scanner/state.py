# tabs/scanner/state.py
import streamlit as st


def initialize_scanner_state():
    """Initialize all required session state variables for the scanner."""
    if 'scan_results' not in st.session_state:
        st.session_state.scan_results = None

    if 'scanner_running' not in st.session_state:
        st.session_state.scanner_running = False

    if 'failed_tickers' not in st.session_state:
        st.session_state.failed_tickers = []

    if 'scanner_universe' not in st.session_state:
        st.session_state.scanner_universe = "Mid Cap"

    if 'universe_selectbox' not in st.session_state:
        st.session_state.universe_selectbox = st.session_state.scanner_universe

    if 'prevent_tab_change' not in st.session_state:
        st.session_state.prevent_tab_change = True

    if 'batch_size' not in st.session_state:
        st.session_state.batch_size = 25  # Default batch size

    if 'status_message' not in st.session_state:
        st.session_state.status_message = ""


def reset_scanner_state():
    """Clear all scanner-related state for a fresh start."""
    st.session_state.scanner_running = False
    st.session_state.scan_results = None
    st.session_state.failed_tickers = []
    st.session_state.status_message = ""
