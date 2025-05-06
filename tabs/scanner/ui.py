# tabs/scanner/ui.py
import streamlit as st
import pandas as pd


def build_settings_ui():
    """
    Build the scanner settings UI and return all user inputs.
    
    Returns:
        dict: All UI settings and button states
    """
    # Initialize session state for Scanner universe
    if 'universe_selectbox' not in st.session_state:
        st.session_state.universe_selectbox = st.session_state.get(
            'scanner_universe', "updated_mid.csv")

    # CSV file options only - no more legacy name formats
    universe_options = ["updated_small.csv", "updated_mid.csv",
                        "updated_large.csv", "valid_swedish_company_data.csv", "Failed Tickers"]

    # Define callback to update session state without causing rerun
    def update_universe():
        # Only set scanner_universe if we're not in initial state
        if not st.session_state.get('prevent_tab_change', False):
            # Save the selected CSV file to session state
            st.session_state.scanner_universe = st.session_state.universe_selectbox
        else:
            # After first use, allow normal behavior
            st.session_state.prevent_tab_change = False

    # Get current selected universe (defaulting to updated_mid.csv)
    current_universe = st.session_state.get(
        'scanner_universe', "updated_mid.csv")

    # Set default to index 1 (updated_mid.csv) if not found
    current_index = universe_options.index(
        current_universe) if current_universe in universe_options else 1

    # UI section - Stock Universe
    st.subheader("Scanner Settings")
    # Format options to show clear CSV file names

    def format_universe_option(option):
        if option == "Failed Tickers":
            return option
        return f"CSV: {option}"

    universe = st.selectbox("Stock File",
                            options=universe_options,
                            index=current_index,
                            key="universe_selectbox",
                            on_change=update_universe,
                            format_func=format_universe_option,
                            help="Select a CSV file to scan or choose 'Failed Tickers' to retry previously failed scans.")

def display_results(watchlist_manager=None):
    """Display scan results and handle watchlist integration."""
    # Skip if no results
    if st.session_state.get('scan_results') is None or st.session_state.get('scan_results').empty:
        if not st.session_state.get('scanner_running', False):
            st.info(
                "Click 'Run Scanner' to search for stocks matching your criteria.")
        return

    df_res = st.session_state.scan_results
    st.subheader("Results")

    # Initialize session state for top_n slider
    if 'scan_top_n' not in st.session_state:
        st.session_state.scan_top_n = min(20, len(df_res))

    # Callback to update top_n without forcing reload
    def update_top_n():
        st.session_state.scan_top_n = st.session_state.top_n_slider

    # Use key and on_change to handle slider changes
    top_n = st.slider("Display Top N",
                      1, len(df_res),
                      st.session_state.scan_top_n,
                      key="top_n_slider",
                      on_change=update_top_n)

    df_disp = df_res.head(top_n)

    # Setup session state for watchlist interaction
    if 'watchlist_selected' not in st.session_state:
        st.session_state.watchlist_selected = 0
    if 'watchlist_picks' not in st.session_state:
        st.session_state.watchlist_picks = []

    # Display watchlist integration UI if watchlist_manager provided
    if watchlist_manager:
        # Callback functions to update state without page reload
        def update_selected_watchlist():
            st.session_state.watchlist_selected = st.session_state.selected_wl_index

        def update_picked_stocks():
            st.session_state.watchlist_picks = st.session_state.picked_stocks

        def add_to_watchlist():
            # Use values stored in session state
            wl_index = st.session_state.watchlist_selected
            stock_picks = st.session_state.watchlist_picks

            if stock_picks:
                wlists = watchlist_manager.get_all_watchlists()
                names = [w['name'] for w in wlists]

                success_message = st.empty()
                for t in stock_picks:
                    watchlist_manager.add_stock_to_watchlist(wl_index, t)

                # Show success message without reloading page
                if len(stock_picks) == 1:
                    success_message.success(
                        f"Added {stock_picks[0]} to {names[wl_index]}")
                else:
                    success_message.success(
                        f"Added {len(stock_picks)} stocks to {names[wl_index]}")

                # Clear picks from session state
                st.session_state.watchlist_picks = []
                # This will reset the multiselect without reloading
                st.session_state.picked_stocks = []

        wlists = watchlist_manager.get_all_watchlists()
        names = [w['name'] for w in wlists]

        # Use keys to link to session state
        sel = st.selectbox("Watchlist",
                           range(len(names)),
                           format_func=lambda i: names[i],
                           key="selected_wl_index",
                           on_change=update_selected_watchlist)

        picks = st.multiselect("Select to add:",
                               df_disp['Ticker'].tolist(),
                               key="picked_stocks",
                               on_change=update_picked_stocks)

        # Use a callback to avoid page reload
        add_btn = st.button("Add to Watchlist",
                            on_click=add_to_watchlist,
                            disabled=(len(picks) == 0))

    # Format results before display
    # Add styling to dataframe
    def highlight_signals(val):
        if val == "KÖP" or val == "BUY":
            return "background-color: #d4edda; color: #155724;"
        elif val == "SÄLJ" or val == "SELL":
            return "background-color: #f8d7da; color: #721c24;"
        return ""
    
    # Style fund check column
    def highlight_fund_ok(val):
        if val == "Yes":
            return "background-color: #d4edda;"
        elif val == "No":
            return "background-color: #f8d7da;"
            return ""
    
    # Format numeric columns - handling both "Tech Score" or "Score" column names
    score_col = None
    if "Tech Score" in df_disp.columns:
        score_col = "Tech Score"
    elif "Score" in df_disp.columns:
        score_col = "Score"
    
    # Create a copy to avoid modifying the original
    df_display = df_disp.copy()
    
    # Format the score column if it exists
    if score_col:
        try:
            df_display[score_col] = df_display[score_col].apply(
                lambda x: f"{int(x)}" if isinstance(x, (int, float)) and pd.notna(x) else "N/A")
        except Exception as e:
            st.warning(f"Could not format score column: {e}")
    
    # Set up styler with formatting
    styled_df = df_display.style
    
    # Apply signal highlighting if column exists
    if "Signal" in df_display.columns:
        styled_df = styled_df.applymap(highlight_signals, subset=["Signal"])
        
    # Apply fund check highlighting if column exists
    if "Fund OK" in df_display.columns:
        styled_df = styled_df.applymap(highlight_fund_ok, subset=["Fund OK"])
    
    # Display styled dataframe
    st.dataframe(styled_df, use_container_width=True)

    # Display failed tickers if any
    if hasattr(st.session_state, 'failed_tickers') and st.session_state.failed_tickers:
        with st.expander(f"Failed Tickers ({len(st.session_state.failed_tickers)})"):
            st.write(", ".join(st.session_state.failed_tickers))
