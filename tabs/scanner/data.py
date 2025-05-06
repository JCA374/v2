# tabs/scanner/data.py
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
import time
import json
import random
from datetime import datetime, timedelta
import csv

# Constants
CACHE_TTL = 7200  # 2 hour cache (increased from 1 hour)
RATE_LIMIT_WAIT = 30  # Wait time in seconds when rate limited
MAX_RETRIES = 3  # Maximum number of retries for API failures
DEFAULT_BATCH_SIZE = 25  # Default batch size if not provided
UPDATE_INTERVAL = 100  # Update UI after every 100 stocks processed
# Backup CSV file for Swedish stocks
SWEDEN_BACKUP_CSV = "valid_swedish_company_data.csv"

# Cache data fetched from yfinance with a longer TTL


@st.cache_data(ttl=CACHE_TTL)
def fetch_bulk_data(tickers, period, interval, batch_size=None):
    """Fetch data for multiple tickers with retry logic."""
    result = {}
    total_tickers = len(tickers)

    # Use provided batch_size or default
    batch_size = batch_size or DEFAULT_BATCH_SIZE

    # Process in batches to avoid rate limits
    for batch_start in range(0, total_tickers, batch_size):
        # Check if scanner has been stopped
        if not st.session_state.get('scanner_running', True):
            st.warning("Scanner stopped by user. Partial results returned.")
            break

        batch_end = min(batch_start + batch_size, total_tickers)
        batch = tickers[batch_start:batch_end]

        # Extract just the ticker symbols
        batch_symbols = [t[1] if isinstance(
            t, (list, tuple)) else t for t in batch]

        # Try to fetch data with retries
        for retry in range(MAX_RETRIES):
            # Check for stop condition even during retries
            if not st.session_state.get('scanner_running', True):
                break

            try:
                data = yf.download(
                    tickers=batch_symbols,
                    period=period,
                    interval=interval,
                    group_by='ticker',
                    auto_adjust=True,
                    progress=False
                )

                # Process the results
                if isinstance(data.columns, pd.MultiIndex):
                    for i, ticker_info in enumerate(batch):
                        orig = ticker_info[0] if isinstance(
                            ticker_info, (list, tuple)) else ticker_info
                        sym = batch_symbols[i]

                        if sym in data.columns.levels[0]:
                            df_sym = data[sym].copy()
                            if not df_sym.empty:
                                result[orig] = df_sym
                else:
                    if len(batch_symbols) == 1 and not data.empty:
                        orig = batch[0][0] if isinstance(
                            batch[0], (list, tuple)) else batch[0]
                        result[orig] = data.copy()

                # Success! Break the retry loop
                break

            except Exception as e:
                error_msg = str(e).lower()

                if retry < MAX_RETRIES - 1:
                    # If it's a rate limit issue, wait longer
                    if "rate" in error_msg or "limit" in error_msg:
                        wait_time = RATE_LIMIT_WAIT * (retry + 1)
                        # Update status but don't block with st.warning
                        st.session_state.status_message = f"Rate limit hit. Waiting {wait_time}s before retry {retry+1}/{MAX_RETRIES}"
                        time.sleep(wait_time)
                    else:
                        # For other errors, wait a bit less
                        time.sleep(5 * (retry + 1))
                else:
                    # Log failures but keep going
                    failed_tickers = [t[0] if isinstance(
                        t, (list, tuple)) else t for t in batch]
                    save_failed_tickers(
                        failed_tickers, reason=f"API Error: {error_msg}")
                    if 'failed_tickers' in st.session_state:
                        st.session_state.failed_tickers.extend(failed_tickers)

        # Add a small random delay between batches to avoid rate limiting
        if st.session_state.get('scanner_running', True):
            time.sleep(random.uniform(1.0, 3.0))

    return result


def save_failed_tickers(tickers, reason="API Error"):
    """Save failed tickers to a file for later retry."""
    retry_file = "scanner_retry_tickers.json"

    # Try to load existing retry data
    retry_data = []
    if os.path.exists(retry_file):
        try:
            with open(retry_file, 'r') as f:
                retry_data = json.load(f)
        except Exception:
            pass

    # Add new failed tickers with timestamp
    for ticker in tickers:
        retry_data.append({
            "ticker": ticker,
            "reason": reason,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    # Save updated retry data
    try:
        with open(retry_file, 'w') as f:
            json.dump(retry_data, f, indent=2)
    except Exception as e:
        st.session_state.status_message = f"Failed to save retry data: {e}"


def load_retry_tickers():
    """Load tickers that previously failed and should be retried."""
    retry_file = "scanner_retry_tickers.json"

    if os.path.exists(retry_file):
        try:
            with open(retry_file, 'r') as f:
                retry_data = json.load(f)

            # Filter to get only those older than 15 minutes (to avoid immediate retries)
            cutoff_time = datetime.now() - timedelta(minutes=15)
            retry_tickers = []

            for item in retry_data:
                try:
                    timestamp = datetime.strptime(
                        item["timestamp"], "%Y-%m-%d %H:%M:%S")
                    if timestamp < cutoff_time:
                        retry_tickers.append(item["ticker"])
                except:
                    # Skip malformed entries
                    pass

            return retry_tickers
        except Exception as e:
            st.session_state.status_message = f"Error loading retry tickers: {e}"

    return []


def load_csv_tickers(file_name):
    """Safely load ticker data from CSV files with appropriate error handling."""
    possible_paths = [
        file_name,
        f"csv/{file_name}",
        f"../csv/{file_name}",
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "csv", file_name)
    ]

    for path in possible_paths:
        try:
            if os.path.exists(path):
                try:
                    # Try UTF-8 first
                    df = pd.read_csv(path, encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        # Try Latin-1 encoding
                        df = pd.read_csv(path, encoding='latin-1')
                    except Exception:
                        # Try with error handling
                        df = pd.read_csv(
                            path, encoding='utf-8', on_bad_lines='skip')

                # Handle different CSV formats
                if 'YahooTicker' in df.columns and 'Tickersymbol' in df.columns:
                    tickers = df[['Tickersymbol', 'YahooTicker']
                                 ].values.tolist()
                    return tickers
                elif 'Tickersymbol' in df.columns:
                    tickers = [[t, t] for t in df['Tickersymbol'].tolist()]
                    return tickers
                elif 'YahooTicker' in df.columns:
                    tickers = [[t, t] for t in df['YahooTicker'].tolist()]
                    return tickers
                else:
                    # If no recognized columns, try to use the first column
                    first_col = df.columns[0]
                    tickers = [[t, t] for t in df[first_col].tolist()]
                    return tickers
        except Exception:
            continue

    st.error(f"Could not load CSV file: {file_name}")
    return []


def load_ticker_list(universe="updated_mid.csv", custom_tickers="", scan_all=True):
    """Load the appropriate ticker list based on selected universe."""
    # Get tickers based on selected universe
    if universe == "Failed Tickers":
        tickers = load_retry_tickers()
        if not tickers:
            st.info("No failed tickers to retry")
            return []
        else:
            tickers = [[t, t] for t in tickers]
    else:
        # Load directly from CSV file
        tickers = load_csv_tickers(universe)

        if not tickers:
            st.error(f"Failed to load {universe}")
            return []

    # Limit or use all tickers based on scan_all flag
    if not scan_all and len(tickers) > 20:
        # Limit to first 20 tickers if not scanning all (for testing)
        orig_count = len(tickers)
        tickers = tickers[:20]
        st.info(
            f"Limited to first 20 tickers for testing (out of {orig_count})")

    # Add custom tickers if provided
    if custom_tickers:
        custom_tickers = [[t.strip(), t.strip()]
                          for t in custom_tickers.split(',') if t.strip()]
        tickers.extend(custom_tickers)

    return tickers


def clear_completed_retries(completed_tickers):
    """Remove successfully completed tickers from the retry file."""
    retry_file = "scanner_retry_tickers.json"

    if os.path.exists(retry_file) and completed_tickers:
        try:
            with open(retry_file, 'r') as f:
                retry_data = json.load(f)

            # Keep only tickers that weren't completed
            updated_data = [
                item for item in retry_data if item["ticker"] not in completed_tickers]

            with open(retry_file, 'w') as f:
                json.dump(updated_data, f, indent=2)
        except Exception as e:
            st.session_state.status_message = f"Error updating retry file: {e}"
