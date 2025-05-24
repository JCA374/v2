# tabs/scanner_tab.py
"""
Stock Scanner Tab - Redesigned with comprehensive ranking and simplified watchlist management.
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
from .scanner.data import load_ticker_list, load_retry_tickers
from .scanner.state import reset_scanner_state, initialize_scanner_state
from .scanner.analysis import perform_scan
from .scanner.ui import build_settings_ui, display_results, render_scan_summary

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('scanner_tab')


class StockScorer:
    """
    Comprehensive stock scoring system that combines multiple factors
    """

    def __init__(self, strategy):
        self.strategy = strategy

    def calculate_comprehensive_score(self, analysis_result):
        """
        Calculate a comprehensive score from 0-100 based on multiple factors
        """
        if "error" in analysis_result:
            return 0

        score = 0

        # Technical Score (40% weight)
        tech_score = analysis_result.get('tech_score', 0)
        score += (tech_score / 100) * 40

        # Fundamental Score (30% weight)
        fund_score = self._calculate_fundamental_score(analysis_result)
        score += (fund_score / 100) * 30

        # Momentum Score (20% weight)
        momentum_score = self._calculate_momentum_score(analysis_result)
        score += (momentum_score / 100) * 20

        # Quality Score (10% weight)
        quality_score = self._calculate_quality_score(analysis_result)
        score += (quality_score / 100) * 10

        return min(100, max(0, score))

    def _calculate_fundamental_score(self, analysis):
        """Calculate fundamental score based on financial metrics"""
        score = 0

        # Profitability (40 points)
        if analysis.get('is_profitable', False):
            score += 20

        pe_ratio = analysis.get('pe_ratio')
        if pe_ratio and pd.notna(pe_ratio):
            if 5 <= pe_ratio <= 25:  # Reasonable P/E
                score += 20
            elif pe_ratio < 5 and pe_ratio > 0:
                score += 10  # Very cheap but risky

        # Growth (30 points)
        revenue_growth = analysis.get('revenue_growth', 0)
        if revenue_growth and pd.notna(revenue_growth):
            if revenue_growth > 0.1:  # 10%+ growth
                score += 15
            elif revenue_growth > 0.05:  # 5%+ growth
                score += 10

        profit_margin = analysis.get('profit_margin', 0)
        if profit_margin and pd.notna(profit_margin):
            if profit_margin > 0.15:  # 15%+ margin
                score += 15
            elif profit_margin > 0.05:  # 5%+ margin
                score += 10

        # Earnings trend (30 points)
        earnings_trend = analysis.get('earnings_trend', '')
        if 'ökande' in earnings_trend.lower():  # Increasing
            score += 30
        elif 'nyligen ökande' in earnings_trend.lower():  # Recently increasing
            score += 20

        return min(100, score)

    def _calculate_momentum_score(self, analysis):
        """Calculate momentum score based on price action"""
        score = 0

        # Price vs moving averages (50 points)
        if analysis.get('above_ma40', False):
            score += 25
        if analysis.get('above_ma4', False):
            score += 25

        # RSI momentum (25 points)
        if analysis.get('rsi_above_50', False):
            score += 25

        # Price patterns (25 points)
        if analysis.get('higher_lows', False):
            score += 10
        if analysis.get('near_52w_high', False):
            score += 10
        if analysis.get('breakout', False):
            score += 5

        return min(100, score)

    def _calculate_quality_score(self, analysis):
        """Calculate quality score based on business quality indicators"""
        score = 50  # Base score

        # Data source quality
        data_source = analysis.get('data_source', 'unknown')
        if data_source in ['yahoo', 'alphavantage']:
            score += 20

        # Fundamental data availability
        if analysis.get('pe_ratio') is not None and pd.notna(analysis.get('pe_ratio')):
            score += 15
        if analysis.get('revenue_growth') is not None and pd.notna(analysis.get('revenue_growth')):
            score += 15

        return min(100, score)


class StockScanner:
    """
    Stock scanner with comprehensive ranking and easy watchlist management
    """

    def __init__(self):
        self.strategy = st.session_state.get('strategy')
        self.watchlist_manager = st.session_state.get('watchlist_manager')
        self.scorer = StockScorer(self.strategy) if self.strategy else None

    def scan_and_rank_stocks(self, tickers, progress_callback=None):
        """
        Scan stocks and rank them comprehensively
        """
        if not self.strategy or not self.scorer:
            st.error("Strategy not initialized")
            return []

        results = []
        failed_analyses = []

        for i, ticker in enumerate(tickers):
            if progress_callback:
                progress = i / len(tickers)
                progress_callback(
                    progress, f"Analyzing {ticker}... ({i+1}/{len(tickers)})")

            # Get analysis from strategy
            analysis = self.strategy.analyze_stock(ticker)

            if "error" in analysis:
                failed_analyses.append({
                    "ticker": ticker,
                    "error": analysis["error"],
                    "error_message": analysis.get("error_message", "Unknown error")
                })
                continue

            # Calculate comprehensive score
            comprehensive_score = self.scorer.calculate_comprehensive_score(
                analysis)

            # Create result
            result = {
                "Rank": 0,  # Will be set after sorting
                "Ticker": analysis["ticker"],
                "Name": analysis.get("name", ticker),
                "Price": round(analysis.get("price", 0), 2),
                "Score": round(comprehensive_score, 1),
                "Tech Score": analysis.get("tech_score", 0),
                "Signal": analysis.get("signal", "HÅLL"),
                "Above MA40": "✓" if analysis.get("above_ma40", False) else "✗",
                "Above MA4": "✓" if analysis.get("above_ma4", False) else "✗",
                "RSI > 50": "✓" if analysis.get("rsi_above_50", False) else "✗",
                "Near 52w High": "✓" if analysis.get("near_52w_high", False) else "✗",
                "Profitable": "✓" if analysis.get("is_profitable", False) else "✗",
                "P/E": round(analysis.get("pe_ratio", 0), 1) if analysis.get("pe_ratio") and pd.notna(analysis.get("pe_ratio")) else "N/A",
                "Data Source": analysis.get("data_source", "unknown").title(),
                "_analysis": analysis  # Keep full analysis for detailed view
            }

            results.append(result)

        # Sort by comprehensive score and assign ranks
        results.sort(key=lambda x: x["Score"], reverse=True)
        for i, result in enumerate(results):
            result["Rank"] = i + 1

        # Store failed analyses
        st.session_state.failed_analyses = failed_analyses

        return results


def load_tickers_from_csv(filename, limit_stocks=False):
    """
    Load ticker symbols from CSV file
    """
    try:
        # Try different possible paths
        possible_paths = [
            f"csv/{filename}",
            filename,
            f"../{filename}",
            f"../csv/{filename}"
        ]

        df = None
        for path in possible_paths:
            try:
                df = pd.read_csv(path)
                break
            except FileNotFoundError:
                continue

        if df is None:
            st.error(f"Could not find file: {filename}")
            return []

        if 'YahooTicker' in df.columns:
            tickers = df['YahooTicker'].tolist()
        elif 'Tickersymbol' in df.columns:
            tickers = df['Tickersymbol'].tolist()
        else:
            # Use first column as tickers
            tickers = df.iloc[:, 0].tolist()

        # Remove any NaN values
        tickers = [str(t) for t in tickers if pd.notna(t)]

        if limit_stocks:
            tickers = tickers[:20]

        return tickers

    except Exception as e:
        st.error(f"Error loading {filename}: {str(e)}")
        return []


def add_to_watchlist(ticker, watchlist_index=None):
    """
    Add ticker to specified watchlist or active watchlist
    """
    watchlist_manager = st.session_state.get('watchlist_manager')
    if not watchlist_manager:
        return False

    if watchlist_index is not None:
        return watchlist_manager.add_stock_to_watchlist(watchlist_index, ticker)
    else:
        return watchlist_manager.add_stock(ticker)


def render_scanner_controls():
    """
    Render scanner control panel
    """
    st.subheader("🎯 Scanner Settings")

    # Stock universe selection
    universe_options = [
        "updated_small.csv",
        "updated_mid.csv",
        "updated_large.csv",
        "valid_swedish_company_data.csv"
    ]

    selected_universe = st.selectbox(
        "Stock Universe",
        universe_options,
        index=1,  # Default to mid
        help="Choose which set of stocks to scan"
    )

    # Scan options
    st.subheader("⚙️ Options")

    limit_stocks = st.checkbox(
        "Limit to first 20 stocks (for testing)", value=False)

    batch_size = st.slider("Batch Size", 10, 50, 25,
                           help="Number of stocks to process at once")

    # Scan button
    scan_clicked = st.button(
        "🚀 Start Scan", type="primary", use_container_width=True)

    return {
        'scan_clicked': scan_clicked,
        'universe': selected_universe,
        'limit_stocks': limit_stocks,
        'batch_size': batch_size
    }


def render_watchlist_quick_add():
    """
    Render quick watchlist add interface
    """
    if 'scan_results' not in st.session_state or not st.session_state.scan_results:
        return

    st.subheader("📝 Quick Add to Watchlist")

    watchlist_manager = st.session_state.get('watchlist_manager')
    if not watchlist_manager:
        st.error("Watchlist manager not available")
        return

    watchlists = watchlist_manager.get_all_watchlists()
    watchlist_names = [w["name"] for w in watchlists]

    if not watchlists:
        st.warning("No watchlists available. Create one first.")
        return

    # Select watchlist
    target_watchlist = st.selectbox(
        "Target Watchlist",
        range(len(watchlist_names)),
        format_func=lambda i: watchlist_names[i]
    )

    # Multi-select stocks (top 20 by score)
    top_stocks = sorted(st.session_state.scan_results,
                        key=lambda x: x['Score'], reverse=True)[:20]
    stock_options = [f"{r['Ticker']} (Score: {r['Score']:.1f}, Signal: {r['Signal']})"
                     for r in top_stocks]

    selected_stocks = st.multiselect(
        "Select Stocks to Add",
        stock_options
    )

    if selected_stocks and st.button("Add Selected to Watchlist"):
        added_count = 0
        for stock_option in selected_stocks:
            ticker = stock_option.split(" ")[0]  # Extract ticker
            if add_to_watchlist(ticker, target_watchlist):
                added_count += 1

        if added_count > 0:
            st.success(
                f"Added {added_count} stocks to {watchlist_names[target_watchlist]}")
        else:
            st.error("Failed to add stocks to watchlist")


def render_scanner_results():
    """
    Render scanner results with ranking
    """
    if 'scan_results' not in st.session_state or not st.session_state.scan_results:
        st.info("👈 Use the controls to start a scan")
        return

    results = st.session_state.scan_results
    df = pd.DataFrame(results)

    st.subheader(f"📈 Scan Results ({len(results)} stocks)")

    # Filtering options
    with st.expander("🔍 Filter Results", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            min_score = st.slider("Minimum Score", 0, 100, 0)

        with col2:
            signals = st.multiselect(
                "Signals",
                ["KÖP", "HÅLL", "SÄLJ"],
                default=["KÖP", "HÅLL", "SÄLJ"]
            )

        with col3:
            top_n = st.slider("Show Top N", 10, len(
                results), min(50, len(results)))

    # Apply filters
    filtered_df = df[
        (df["Score"] >= min_score) &
        (df["Signal"].isin(signals))
    ].head(top_n)

    if filtered_df.empty:
        st.warning("No stocks match the current filters")
        return

    # Display results table
    display_columns = [
        "Rank", "Ticker", "Name", "Score", "Signal", "Price",
        "Above MA40", "Above MA4", "RSI > 50", "Profitable", "P/E"
    ]

    st.dataframe(
        filtered_df[display_columns],
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

    # Top performers highlight
    st.subheader("🏆 Top 5 Performers")
    top_5 = filtered_df.head(5)

    for _, stock in top_5.iterrows():
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 2, 1, 1])

            with col1:
                st.metric("Rank", f"#{stock['Rank']}")

            with col2:
                st.write(f"**{stock['Ticker']}** - {stock['Name']}")
                st.caption(f"Signal: {stock['Signal']} | P/E: {stock['P/E']}")

            with col3:
                st.metric("Score", f"{stock['Score']:.1f}")

            with col4:
                if st.button(f"Add {stock['Ticker']}", key=f"add_{stock['Ticker']}"):
                    if add_to_watchlist(stock['Ticker']):
                        st.success(f"Added {stock['Ticker']}!")
                    else:
                        st.error("Failed to add")

    # Show failed analyses if any
    if 'failed_analyses' in st.session_state and st.session_state.failed_analyses:
        with st.expander(f"⚠️ Failed Analyses ({len(st.session_state.failed_analyses)})", expanded=False):
            for fail in st.session_state.failed_analyses:
                st.error(
                    f"**{fail['ticker']}**: {fail.get('error_message', fail['error'])}")


def start_scan(universe_file, limit_stocks, batch_size):
    """
    Start the scanning process
    """
    # Initialize scanner
    scanner = StockScanner()

    # Load tickers from CSV
    tickers = load_tickers_from_csv(universe_file, limit_stocks)

    if not tickers:
        st.error("No tickers found to scan")
        return

    st.info(f"Found {len(tickers)} tickers to scan")

    # Show progress
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(progress, message):
        progress_bar.progress(progress)
        status_text.text(message)

    # Run scan
    try:
        results = scanner.scan_and_rank_stocks(tickers, update_progress)

        # Store results
        st.session_state.scan_results = results

        # Clear progress
        progress_bar.empty()
        status_text.empty()

        if results:
            st.success(f"✅ Scan complete! Analyzed {len(results)} stocks.")
        else:
            st.warning("Scan completed but no valid results were found.")

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Error during scan: {str(e)}")


def render_scanner_tab():
    """
    Main function to render the scanner tab - simplified to use existing modular structure
    """
    st.header("📊 Stock Scanner")
    st.markdown("*Comprehensive stock ranking with easy watchlist management*")

    # Initialize state if needed
    initialize_scanner_state()

    # Check if required components are available
    if 'strategy' not in st.session_state:
        st.error("Strategy not initialized. Please check the main app setup.")
        return

    if 'watchlist_manager' not in st.session_state:
        st.error(
            "Watchlist manager not initialized. Please check the main app setup.")
        return

    col1, col2 = st.columns([1, 3])

    with col1:
        # Call build_settings_ui and ensure we get a dictionary back
        settings = build_settings_ui()

        # Ensure settings is not None and has default values
        if settings is None:
            settings = {
                "universe": "updated_mid.csv",
                "period": "1y",
                "interval": "1wk",
                "custom": "",
                "rsi_min": 30,
                "rsi_max": 70,
                "vol_mul": 1.5,
                "lookback": 30,
                "scan_all_stocks": True,
                "batch_size": 25,
                "continuous_scan": True,
                "clear_btn": False,
                "scan_btn": False,
                "retry_btn": False,
                "stop_btn": False
            }

        # Add scan control buttons
        st.subheader("🎯 Scan Controls")

        col_a, col_b = st.columns(2)
        with col_a:
            scan_btn = st.button("🚀 Start Scan", type="primary",
                                 disabled=st.session_state.get('scanner_running', False))
            clear_btn = st.button("🗑️ Clear Results",
                                  disabled=st.session_state.get('scanner_running', False))

        with col_b:
            retry_btn = st.button("🔄 Retry Failed",
                                  disabled=st.session_state.get('scanner_running', False))
            stop_btn = st.button("⛔ Stop Scanner", type="secondary",
                                 disabled=not st.session_state.get('scanner_running', False))

        # Additional scan options
        st.subheader("⚙️ Options")
        limit_stocks = st.checkbox(
            "Limit to first 20 stocks (for testing)", value=False)
        batch_size = st.slider("Batch Size", 10, 50, 25,
                               help="Number of stocks to process at once")

    with col2:
        # Handle button actions
        if clear_btn:
            reset_scanner_state()
            st.success("Results cleared successfully!")

        if stop_btn:
            st.session_state.scanner_running = False
            st.warning(
                "⚠️ STOPPING SCANNER... Please wait for current batch to complete.")

        # Handle scan button - only if not already running
        if scan_btn:
            # Get tickers based on the universe selection
            universe = st.session_state.get(
                'scanner_universe', 'updated_mid.csv')
            tickers = load_ticker_list(
                universe=universe,
                custom_tickers="",  # Could add custom tickers input
                scan_all=not limit_stocks
            )

            if tickers:
                st.info(f"Starting scan of {len(tickers)} stocks...")
                perform_scan(
                    tickers,
                    period="1y",
                    interval="1wk",
                    rsi_range=(30, 70),
                    vol_multiplier=1.5,
                    lookback=30,
                    batch_size=batch_size,
                    continuous_scan=True
                )

        # Handle retry button
        if retry_btn:
            retry_tickers = load_retry_tickers()
            if retry_tickers:
                retry_tickers = [[t, t] for t in retry_tickers]
                st.info(f"Retrying {len(retry_tickers)} failed stocks...")
                perform_scan(
                    retry_tickers,
                    period="1y",
                    interval="1wk",
                    rsi_range=(30, 70),
                    vol_multiplier=1.5,
                    lookback=30,
                    batch_size=batch_size,
                    continuous_scan=True
                )
            else:
                st.info("No failed tickers to retry")

        # Display scan summary if we have results
        if 'scan_results' in st.session_state and not st.session_state.scan_results.empty:
            render_scan_summary()

        # Display results
        display_results(
            watchlist_manager=st.session_state.get('watchlist_manager'))


# Remove duplicate classes since they're now in the analysis module
# Keep the old classes for backward compatibility if needed
class StockScorer:
    """Backward compatibility - use the one in analysis.py instead"""
    pass


class StockScanner:
    """Backward compatibility - use the one in analysis.py instead"""
    pass
