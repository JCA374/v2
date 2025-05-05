# tabs/scanner/__init__.py
"""
Scanner package to manage stock scanning functionality.
This module makes key functions available directly from the scanner package.
"""
# Make functions from other modules available directly from scanner package
from .ui import build_settings_ui, display_results
from .data import load_ticker_list, load_retry_tickers
from .analysis import perform_scan
from .state import reset_scanner_state, initialize_scanner_state

# tabs/scanner/analysis.py
import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime
from .data import fetch_bulk_data, clear_completed_retries, save_failed_tickers


def calculate_indicators(df):
    """Calculate technical indicators for a dataframe."""
    if df is None or len(df) < 21:
        return None

    df = df.copy()

    # Calculate EMA indicators
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()

    # Calculate RSI
    delta = df['Close'].diff()
    gain, loss = delta.copy(), -delta.copy()
    gain[gain < 0] = 0
    loss[loss < 0] = 0
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))

    # Volume metrics
    df['VolAvg20'] = df['Volume'].rolling(20).mean()
    df['VolRatio'] = df['Volume'] / df['VolAvg20']

    # MACD
    df['MACD'] = df['Close'].ewm(span=12, adjust=False).mean(
    ) - df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # Check for EMA crossovers
    df['EMA_Cross'] = ((df['EMA50'] > df['EMA200']) & (
        df['EMA50'].shift(1) <= df['EMA200'].shift(1))).astype(int)

    return df


def perform_scan(tickers, period, interval, rsi_range=(30, 70), vol_multiplier=1.5,
                 lookback=30, batch_size=25, continuous_scan=True):
    """
    Perform technical analysis scan on a list of tickers.
    
    Args:
        tickers: List of tickers to scan
        period: Historical data period (e.g., "1y", "6mo")
        interval: Data interval (e.g., "1d", "1wk")
        rsi_range: Tuple of (min, max) RSI values to filter
        vol_multiplier: Volume multiplier threshold
        lookback: Days to look back for EMA crossovers
        batch_size: Number of tickers to process at once
        continuous_scan: Whether to add delays between batches to avoid rate limits
    """
    # Set scanner running flag
    st.session_state.scanner_running = True

    # Initialize progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.empty()

    try:
        # Get total ticker count
        total_tickers = len(tickers)

        # Initialize status display
        status_text.text(f"Starting analysis of {total_tickers} stocks...")

        # Fetch data for all tickers (this respects the batch_size parameter)
        status_text.text(f"Fetching historical data...")
        data = fetch_bulk_data(tickers, period, interval, batch_size)

        # Check if we were stopped during data fetch
        if not st.session_state.get('scanner_running', True):
            status_text.warning("Scanner stopped during data fetch.")
            return

        # Process results
        status_text.text(
            f"Processing technical indicators for {len(data)} stocks...")

        # Initialize results
        all_results = []
        failed = []

        # Track tickers for updating progress
        processed_count = 0

        # Get the ValueMomentumStrategy from session state
        strategy = st.session_state.strategy

        # Process each ticker
        for ticker, df in data.items():
            # Check if we were stopped
            if not st.session_state.get('scanner_running', True):
                status_text.warning("Scanner stopped during analysis.")
                break

            try:
                # Calculate technical indicators
                df_with_indicators = calculate_indicators(df)

                if df_with_indicators is None:
                    # Not enough data for analysis
                    failed.append(ticker)
                    continue

                # Get the last row for current values
                last_row = df_with_indicators.iloc[-1]

                # Check if it meets our filter criteria
                rsi_min, rsi_max = rsi_range
                rsi_value = last_row.get('RSI', 0)
                vol_ratio = last_row.get('VolRatio', 0)

                # Check for recent EMA crossover (within lookback period)
                recent_crossover = False
                if 'EMA_Cross' in df_with_indicators.columns:
                    crossovers = df_with_indicators.tail(
                        lookback)['EMA_Cross'].sum()
                    recent_crossover = crossovers > 0

                # Create technical score based on filter criteria
                tech_score = 0

                # RSI in range adds up to 40 points
                if pd.notna(rsi_value):
                    if rsi_min <= rsi_value <= rsi_max:
                        tech_score += 40
                    elif rsi_value < rsi_min:
                        # Below range but close
                        proximity = rsi_value / rsi_min
                        tech_score += int(proximity * 20)
                    elif rsi_value > rsi_max:
                        # Above range but close
                        overflow = 100 - rsi_value
                        proximity = overflow / (100 - rsi_max)
                        tech_score += int(proximity * 20)

                # Volume above threshold adds up to 30 points
                if pd.notna(vol_ratio) and vol_ratio >= vol_multiplier:
                    vol_score = min(
                        30, int(30 * (vol_ratio / (vol_multiplier * 2))))
                    tech_score += vol_score

                # Recent EMA crossover adds 30 points
                if recent_crossover:
                    tech_score += 30

                # Determine signal based on tech_score
                signal = "NEUTRAL"
                if tech_score >= 70:
                    signal = "BUY"
                elif tech_score <= 30:
                    signal = "SELL"

                # Determine if price is above key MAs
                above_ema50 = "No"
                above_ema200 = "No"

                if 'EMA50' in df_with_indicators.columns and 'Close' in df_with_indicators.columns:
                    ema50 = last_row.get('EMA50', 0)
                    if pd.notna(ema50) and last_row['Close'] > ema50:
                        above_ema50 = "Yes"

                if 'EMA200' in df_with_indicators.columns and 'Close' in df_with_indicators.columns:
                    ema200 = last_row.get('EMA200', 0)
                    if pd.notna(ema200) and last_row['Close'] > ema200:
                        above_ema200 = "Yes"

                # Add to results
                all_results.append({
                    "Ticker": ticker,
                    "Price": round(last_row['Close'], 2) if 'Close' in last_row else 0,
                    "RSI(14)": round(rsi_value, 1) if pd.notna(rsi_value) else "N/A",
                    "Vol Ratio": round(vol_ratio, 1) if pd.notna(vol_ratio) else "N/A",
                    "EMA Cross": "Yes" if recent_crossover else "No",
                    "Above EMA50": above_ema50,
                    "Above EMA200": above_ema200,
                    "MACD Diff": round(last_row.get('MACD_Hist', 0), 3) if 'MACD_Hist' in last_row else "N/A",
                    "Score": tech_score,
                    "Signal": signal
                })

            except Exception as e:
                failed.append(ticker)
                if 'failed_tickers' not in st.session_state:
                    st.session_state.failed_tickers = []
                st.session_state.failed_tickers.append(ticker)
                save_failed_tickers([ticker], reason=str(e))

            # Update progress
            processed_count += 1
            progress = processed_count / len(data)
            progress_bar.progress(progress)

            # Update status text periodically
            if processed_count % 10 == 0 or processed_count == len(data):
                status_text.text(
                    f"Processed {processed_count}/{len(data)} stocks ({progress:.0%})")

            # If continuous scan is enabled, add a small delay between tickers
            if continuous_scan:
                time.sleep(0.1)  # 100ms delay

        # Sort results by Score (descending)
        if all_results:
            df_results = pd.DataFrame(all_results).sort_values(
                "Score", ascending=False)
            st.session_state.scan_results = df_results

        # Process failed tickers
        if failed:
            st.session_state.failed_tickers = failed

        # Record successful retries if we were retrying failed tickers
        if all_results:
            completed_tickers = [r["Ticker"] for r in all_results]
            clear_completed_retries(completed_tickers)

        # Final status update
        status_text.text(
            f"Completed. {len(all_results)} results, {len(failed)} failed.")

    except Exception as e:
        st.error(f"Error during scanning: {e}")
        import traceback
        st.error(traceback.format_exc())
    finally:
        # Always set scanner to finished state
        st.session_state.scanner_running = False


def analyze_ticker_with_strategy(ticker, strategy=None):
    """
    Alternative approach: Use the ValueMomentumStrategy directly
    instead of reimplementing the technical analysis.
    
    Args:
        ticker: Ticker symbol to analyze
        strategy: ValueMomentumStrategy instance (or None to use session state)
    
    Returns:
        dict: Analysis results or None if failed
    """
    if strategy is None:
        # Get strategy from session state
        strategy = st.session_state.get('strategy')
        if not strategy:
            return None

    try:
        # Use the strategy to analyze the stock
        analysis = strategy.analyze_stock(ticker)

        if "error" in analysis:
            return None

        # Extract needed fields for scanner results
        result = {
            "Ticker": analysis["ticker"],
            "Price": round(analysis["price"], 2),
            "RSI(14)": round(analysis.get("rsi", 0), 1) if analysis.get("rsi") else "N/A",
            "Vol Ratio": "N/A",  # Not provided by the strategy
            "EMA Cross": "N/A",  # Not directly provided
            "Above EMA50": "Yes" if analysis.get("above_ma50", False) else "No",
            # MA40 is used as long-term MA
            "Above EMA200": "Yes" if analysis.get("above_ma40", False) else "No",
            "MACD Diff": "N/A",  # Not provided by the strategy
            "Score": analysis["tech_score"],
            "Signal": analysis["signal"],
            "Fund OK": "Yes" if analysis["fundamental_check"] else "No"
        }

        return result
    except Exception:
        return None
