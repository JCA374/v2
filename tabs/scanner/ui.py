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
    """Display scan results with improved ranking and watchlist integration."""
    # Skip if no results
    if st.session_state.get('scan_results') is None or st.session_state.get('scan_results').empty:
        if not st.session_state.get('scanner_running', False):
            st.info(
                "Click 'Run Scanner' to search for stocks matching your criteria.")
        return

    df_res = st.session_state.scan_results
    st.subheader(f"📈 Scan Results ({len(df_res)} stocks ranked)")

    # Initialize session state for top_n slider
    if 'scan_top_n' not in st.session_state:
        st.session_state.scan_top_n = min(20, len(df_res))

    # Callback to update top_n without forcing reload
    def update_top_n():
        st.session_state.scan_top_n = st.session_state.top_n_slider

    # Filtering options in an expander
    with st.expander("🔍 Filter & Sort Results", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            min_score = st.slider("Minimum Score", 0, 100, 0,
                                  help="Filter stocks by minimum comprehensive score")

        with col2:
            signals = st.multiselect(
                "Signals",
                ["KÖP", "HÅLL", "SÄLJ"],
                default=["KÖP", "HÅLL", "SÄLJ"],
                help="Filter by trading signals"
            )

        with col3:
            top_n = st.slider("Display Top N",
                              1, len(df_res),
                              st.session_state.scan_top_n,
                              key="top_n_slider",
                              on_change=update_top_n,
                              help="Number of top-ranked stocks to display")

    # Apply filters
    filtered_df = df_res[
        (df_res["Score"] >= min_score) &
        (df_res["Signal"].isin(signals))
    ].head(top_n)

    if filtered_df.empty:
        st.warning("No stocks match the current filters")
        return

    # Display watchlist integration UI if watchlist_manager provided
    if watchlist_manager:
        render_watchlist_integration(filtered_df, watchlist_manager)

    # Display main results table
    display_main_results_table(filtered_df)

    # Display top performers section
    display_top_performers(filtered_df.head(5), watchlist_manager)

    # Display failed tickers if any
    display_failed_analyses()


def render_watchlist_integration(filtered_df, watchlist_manager):
    """Render watchlist integration controls"""
    st.subheader("📝 Add to Watchlist")

    # Setup session state for watchlist interaction
    if 'watchlist_selected' not in st.session_state:
        st.session_state.watchlist_selected = 0
    if 'watchlist_picks' not in st.session_state:
        st.session_state.watchlist_picks = []

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
            added_count = 0

            for t in stock_picks:
                if watchlist_manager.add_stock_to_watchlist(wl_index, t):
                    added_count += 1

            # Show success message without reloading page
            if added_count > 0:
                if added_count == 1:
                    success_message.success(
                        f"Added {stock_picks[0]} to {names[wl_index]}")
                else:
                    success_message.success(
                        f"Added {added_count} stocks to {names[wl_index]}")
            else:
                success_message.error("Failed to add stocks to watchlist")

            # Clear picks from session state
            st.session_state.watchlist_picks = []
            st.session_state.picked_stocks = []

    wlists = watchlist_manager.get_all_watchlists()
    names = [w['name'] for w in wlists]

    if not wlists:
        st.warning(
            "No watchlists available. Create one first in the Watchlist tab.")
        return

    col1, col2, col3 = st.columns([2, 3, 1])

    with col1:
        # Use keys to link to session state
        sel = st.selectbox("Target Watchlist",
                           range(len(names)),
                           format_func=lambda i: names[i],
                           key="selected_wl_index",
                           on_change=update_selected_watchlist)

    with col2:
        # Show top stocks for easy selection
        top_options = [f"{row['Ticker']} (Rank #{row['Rank']}, Score: {row['Score']:.1f})"
                       for _, row in filtered_df.head(10).iterrows()]

        picks = st.multiselect("Select stocks to add:",
                               top_options,
                               key="picked_stocks",
                               on_change=update_picked_stocks,
                               help="Select from top 10 ranked stocks")

    with col3:
        # Use a callback to avoid page reload
        add_btn = st.button("Add to Watchlist",
                            on_click=add_to_watchlist,
                            disabled=(len(picks) == 0),
                            type="primary")


def display_main_results_table(filtered_df):
    """Display the main results table with proper formatting"""
    st.subheader("📊 Ranked Results")

    # Select columns to display
    display_columns = [
        "Rank", "Ticker", "Name", "Score", "Signal", "Price",
        "Above MA40", "Above MA4", "RSI > 50", "Profitable", "P/E"
    ]

    # Ensure all columns exist
    available_columns = [
        col for col in display_columns if col in filtered_df.columns]

    # Format the results before display
    display_df = filtered_df[available_columns].copy()

    # Style the dataframe
    def highlight_signals(val):
        if val == "KÖP" or val == "BUY":
            return "background-color: #d4edda; color: #155724;"
        elif val == "SÄLJ" or val == "SELL":
            return "background-color: #f8d7da; color: #721c24;"
        return ""

    def highlight_yes_no(val):
        if val == "Yes" or val == "✓":
            return "background-color: #d4edda;"
        elif val == "No" or val == "✗":
            return "background-color: #f8d7da;"
        return ""

    # Apply styling
    styled_df = display_df.style

    if "Signal" in display_df.columns:
        styled_df = styled_df.applymap(highlight_signals, subset=["Signal"])

    # Apply yes/no highlighting to relevant columns
    yes_no_columns = ["Above MA40", "Above MA4", "RSI > 50", "Profitable"]
    available_yes_no = [
        col for col in yes_no_columns if col in display_df.columns]
    if available_yes_no:
        styled_df = styled_df.applymap(
            highlight_yes_no, subset=available_yes_no)

    # Display with column configuration
    st.dataframe(
        styled_df,
        column_config={
            "Rank": st.column_config.NumberColumn("Rank", width="small"),
            "Score": st.column_config.ProgressColumn(
                "Score",
                min_value=0,
                max_value=100,
                format="%.1f"
            ),
            "Signal": st.column_config.TextColumn("Signal", width="small"),
            "Price": st.column_config.NumberColumn("Price", format="%.2f"),
        },
        use_container_width=True,
        hide_index=True
    )


def display_top_performers(top_df, watchlist_manager):
    """Display top performers section with quick add buttons"""
    if top_df.empty:
        return

    st.subheader("🏆 Top 5 Performers")

    for _, stock in top_df.iterrows():
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 3, 1, 1])

            with col1:
                st.metric("Rank", f"#{stock['Rank']}")

            with col2:
                st.write(f"**{stock['Ticker']}** - {stock['Name']}")
                st.caption(
                    f"Signal: {stock['Signal']} | P/E: {stock.get('P/E', 'N/A')}")

            with col3:
                st.metric("Score", f"{stock['Score']:.1f}")

            with col4:
                if st.button(f"Add {stock['Ticker']}", key=f"quick_add_{stock['Ticker']}"):
                    if watchlist_manager:
                        if watchlist_manager.add_stock(stock['Ticker']):
                            st.success(f"Added {stock['Ticker']}!")
                        else:
                            st.error("Failed to add")
                    else:
                        st.error("Watchlist manager not available")


def display_failed_analyses():
    """Display failed analyses if any"""
    if hasattr(st.session_state, 'failed_tickers') and st.session_state.failed_tickers:
        with st.expander(f"⚠️ Failed Analyses ({len(st.session_state.failed_tickers)})", expanded=False):
            st.write("The following tickers could not be analyzed:")
            failed_text = ", ".join(st.session_state.failed_tickers)
            st.code(failed_text)

            if st.button("Retry Failed Tickers"):
                # Clear failed tickers and suggest retry
                st.session_state.failed_tickers = []
                st.info(
                    "Use the 'Failed Tickers' option in the universe selector to retry these.")

    # Also show failed analyses from the enhanced analysis
    if hasattr(st.session_state, 'failed_analyses') and st.session_state.failed_analyses:
        with st.expander(f"❌ Analysis Errors ({len(st.session_state.failed_analyses)})", expanded=False):
            for fail in st.session_state.failed_analyses:
                st.error(
                    f"**{fail['ticker']}**: {fail.get('error_message', fail.get('error', 'Unknown error'))}")


def render_scan_summary():
    """Render a summary of scan results"""
    if 'scan_results' not in st.session_state or st.session_state.scan_results.empty:
        return

    df = st.session_state.scan_results

    # Calculate summary stats
    total_stocks = len(df)
    buy_signals = len(df[df['Signal'] == 'KÖP'])
    avg_score = df['Score'].mean()
    top_score = df['Score'].max()

    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Analyzed", total_stocks)

    with col2:
        st.metric("Buy Signals", buy_signals)

    with col3:
        st.metric("Avg Score", f"{avg_score:.1f}")

    with col4:
        st.metric("Top Score", f"{top_score:.1f}")

    # Show distribution of signals
    if total_stocks > 0:
        signal_counts = df['Signal'].value_counts()
        st.write("**Signal Distribution:**")

        signal_cols = st.columns(len(signal_counts))
        for i, (signal, count) in enumerate(signal_counts.items()):
            with signal_cols[i]:
                percentage = (count / total_stocks) * 100
                st.metric(signal, f"{count} ({percentage:.1f}%)")
