# tabs/scanner_tab.py
import streamlit as st
from .scanner.ui import build_settings_ui, display_results
from .scanner.data import load_ticker_list
from .scanner.state import reset_scanner_state, initialize_scanner_state
from .scanner.analysis import perform_scan


def render_scanner_tab():
    """Renders the stock scanner tab with a cleaner, modular structure."""
    # Initialize state if needed
    initialize_scanner_state()

    st.header("Stock Scanner")
    col1, col2 = st.columns([1, 3])

    with col1:
        # Create all UI elements and get user inputs
        settings = build_settings_ui()

    with col2:
        # Handle button actions
        if settings["clear_btn"]:
            reset_scanner_state()
            st.success("Results cleared successfully!")

        if settings["stop_btn"]:
            st.session_state.scanner_running = False
            st.warning(
                "⚠️ STOPPING SCANNER... Please wait for current batch to complete.")
            if 'status_message' in st.session_state:
                st.session_state.status_message = "Scanner stopping - Please wait..."

        # Handle scan button - only if not already running
        if settings["scan_btn"]:
            # Get tickers based on the universe selection
            tickers = load_ticker_list(
                universe=settings["universe"],
                custom_tickers=settings["custom"],
                scan_all=settings["scan_all_stocks"]
            )

            if tickers:
                perform_scan(
                    tickers,
                    period=settings["period"],
                    interval=settings["interval"],
                    rsi_range=(settings["rsi_min"], settings["rsi_max"]),
                    vol_multiplier=settings["vol_mul"],
                    lookback=settings["lookback"],
                    batch_size=settings["batch_size"],
                    continuous_scan=settings["continuous_scan"]
                )

        # Handle retry button
        if settings["retry_btn"]:
            from .scanner.data import load_retry_tickers
            retry_tickers = load_retry_tickers()
            if retry_tickers:
                retry_tickers = [[t, t] for t in retry_tickers]
                perform_scan(
                    retry_tickers,
                    period=settings["period"],
                    interval=settings["interval"],
                    rsi_range=(settings["rsi_min"], settings["rsi_max"]),
                    vol_multiplier=settings["vol_mul"],
                    lookback=settings["lookback"],
                    batch_size=settings["batch_size"],
                    continuous_scan=settings["continuous_scan"]
                )
            else:
                st.info("No failed tickers to retry")

        # Display results
        display_results(watchlist_manager=st.session_state.watchlist_manager)
