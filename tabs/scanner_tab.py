import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
import time
from datetime import datetime, timedelta
import random
import json
import investpy

# Constants
CACHE_TTL = 7200  # 2 hour cache (increased from 1 hour)
RATE_LIMIT_WAIT = 30  # Wait time in seconds when rate limited
MAX_RETRIES = 3  # Maximum number of retries for API failures
BATCH_SIZE = 25  # Number of tickers to process at once
UPDATE_INTERVAL = 100  # Update UI after every 100 stocks processed
SWEDEN_BACKUP_CSV = "valid_swedish_company_data.csv"  # Backup CSV file for Swedish stocks if API fails

# Cache data fetched from yfinance with a longer TTL
@st.cache_data(ttl=CACHE_TTL)
def fetch_bulk_data(tickers, period, interval):
    """Fetch data for multiple tickers with retry logic."""
    result = {}
    total_tickers = len(tickers)
    
    # Process in smaller batches to avoid rate limits
    for batch_start in range(0, total_tickers, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_tickers)
        batch = tickers[batch_start:batch_end]
        
        # Extract just the ticker symbols
        batch_symbols = [t[1] if isinstance(t, (list, tuple)) else t for t in batch]
        
        # Try to fetch data with retries
        for retry in range(MAX_RETRIES):
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
                        orig = ticker_info[0] if isinstance(ticker_info, (list, tuple)) else ticker_info
                        sym = batch_symbols[i]
                        
                        if sym in data.columns.levels[0]:
                            df_sym = data[sym].copy()
                            if not df_sym.empty:
                                result[orig] = df_sym
                else:
                    if len(batch_symbols) == 1 and not data.empty:
                        orig = batch[0][0] if isinstance(batch[0], (list, tuple)) else batch[0]
                        result[orig] = data.copy()
                
                # Success! Break the retry loop
                break
                
            except Exception as e:
                error_msg = str(e).lower()
                
                if retry < MAX_RETRIES - 1:
                    # If it's a rate limit issue, wait longer
                    if "rate" in error_msg or "limit" in error_msg:
                        wait_time = RATE_LIMIT_WAIT * (retry + 1)
                        st.warning(f"Rate limit hit. Waiting {wait_time}s before retry {retry+1}/{MAX_RETRIES}")
                        time.sleep(wait_time)
                    else:
                        # For other errors, wait a bit less
                        time.sleep(5 * (retry + 1))
                else:
                    st.error(f"Failed to fetch data after {MAX_RETRIES} retries: {e}")
        
        # Add a small random delay between batches to avoid rate limiting
        time.sleep(random.uniform(1.0, 3.0))
    
    return result

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
    df['MACD'] = df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # Check for EMA crossovers
    df['EMA_Cross'] = ((df['EMA50'] > df['EMA200']) & (df['EMA50'].shift(1) <= df['EMA200'].shift(1))).astype(int)
    
    return df

def load_csv_tickers(file_name):
    """Safely load ticker data from CSV files with appropriate error handling."""
    possible_paths = [
        file_name,
        f"csv/{file_name}",
        f"../csv/{file_name}",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "csv", file_name)
    ]
    
    for path in possible_paths:
        try:
            if os.path.exists(path):
                # Debug the file content
                st.write(f"▶️ Loading CSV from: {path}")
                
                # Read the CSV file with different encodings and error handling
                try:
                    # Try UTF-8 first
                    df = pd.read_csv(path, encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        # Try Latin-1 encoding
                        df = pd.read_csv(path, encoding='latin-1')
                    except Exception as e2:
                        st.warning(f"Failed to read CSV with latin-1 encoding: {e2}")
                        # Try with error handling
                        df = pd.read_csv(path, encoding='utf-8', on_bad_lines='skip')
                
                # Debug the dataframe
                st.write(f"▶️ CSV columns: {list(df.columns)}")
                st.write(f"▶️ CSV row count: {len(df)}")
                
                # Handle different CSV formats
                if 'YahooTicker' in df.columns and 'Tickersymbol' in df.columns:
                    tickers = df[['Tickersymbol', 'YahooTicker']].values.tolist()
                    st.write(f"▶️ Found both Tickersymbol and YahooTicker columns. Loaded {len(tickers)} tickers.")
                    return tickers
                elif 'Tickersymbol' in df.columns:
                    tickers = [[t, t] for t in df['Tickersymbol'].tolist()]
                    st.write(f"▶️ Found only Tickersymbol column. Loaded {len(tickers)} tickers.")
                    return tickers
                elif 'YahooTicker' in df.columns:
                    tickers = [[t, t] for t in df['YahooTicker'].tolist()]
                    st.write(f"▶️ Found only YahooTicker column. Loaded {len(tickers)} tickers.")
                    return tickers
                else:
                    # If no recognized columns, try to use the first column
                    first_col = df.columns[0]
                    tickers = [[t, t] for t in df[first_col].tolist()]
                    st.write(f"▶️ Using first column '{first_col}'. Loaded {len(tickers)} tickers.")
                    return tickers
        except Exception as e:
            st.warning(f"Error loading {path}: {e}")
            continue
    
    st.error(f"Could not load CSV file: {file_name}")
    return []

def save_failed_tickers(tickers, reason="API Error"):
    """Save failed tickers to a file for later retry."""
    retry_file = "scanner_retry_tickers.json"
    
    # Try to load existing retry data
    retry_data = []
    if os.path.exists(retry_file):
        try:
            with open(retry_file, 'r') as f:
                retry_data = json.load(f)
        except:
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
        st.error(f"Failed to save retry data: {e}")

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
                    timestamp = datetime.strptime(item["timestamp"], "%Y-%m-%d %H:%M:%S")
                    if timestamp < cutoff_time:
                        retry_tickers.append(item["ticker"])
                except:
                    # Skip malformed entries
                    pass
            
            return retry_tickers
        except Exception as e:
            st.warning(f"Error loading retry tickers: {e}")
    
    return []

def clear_completed_retries(completed_tickers):
    """Remove successfully completed tickers from the retry file."""
    retry_file = "scanner_retry_tickers.json"
    
    if os.path.exists(retry_file) and completed_tickers:
        try:
            with open(retry_file, 'r') as f:
                retry_data = json.load(f)
            
            # Keep only tickers that weren't completed
            updated_data = [item for item in retry_data if item["ticker"] not in completed_tickers]
            
            with open(retry_file, 'w') as f:
                json.dump(updated_data, f, indent=2)
        except Exception as e:
            st.warning(f"Error updating retry file: {e}")

def render_scanner_tab():
    """
    Renders stock scanner tab. Preserves results in session_state to avoid data loss on widget changes.
    """
    if 'scan_results' not in st.session_state:
        st.session_state.scan_results = None
    
    if 'scanner_running' not in st.session_state:
        st.session_state.scanner_running = False
    
    if 'failed_tickers' not in st.session_state:
        st.session_state.failed_tickers = []
        
    # Save a reference to the watchlist manager for later
    watchlist_manager = st.session_state.watchlist_manager
    
    st.header("Stock Scanner")
    col1, col2 = st.columns([1, 3])

    # UI mappings
    period_map = {"3 months": "3mo", "6 months": "6mo", "1 year": "1y"}
    interval_map = {"Daily": "1d", "Weekly": "1wk"}

    # Initialize session state for scanner settings to avoid tab switching
    if 'scanner_universe' not in st.session_state:
        st.session_state.scanner_universe = "Mid Cap"
        
    # Define callback to update session state without causing rerun
    def update_universe():
        st.session_state.scanner_universe = st.session_state.universe_selectbox
        
    with col1:
        st.subheader("Scanner Settings")
        universe_options = ["Small Cap", "Mid Cap", "Large Cap", "Swedish Stocks", "Failed Tickers"]
        # Use key parameter to link to session state
        universe = st.selectbox("Stock Universe", universe_options, 
                              index=universe_options.index(st.session_state.scanner_universe),
                              key="universe_selectbox",
                              on_change=update_universe)
        
        # Map the selection to CSV files
        csv_file = {
            "Small Cap": "updated_small.csv", 
            "Mid Cap": "updated_mid.csv", 
            "Large Cap": "updated_large.csv",
            "Swedish Stocks": None,  # Handled differently using investpy API
            "Failed Tickers": None   # Special case, loaded differently
        }[universe]

        history = st.selectbox("History", list(period_map.keys()), index=0)
        period = period_map[history]

        interval_label = st.selectbox("Interval", list(interval_map.keys()), index=0)
        interval = interval_map[interval_label]

        st.subheader("Technical Filters")
        preset = st.selectbox(
            "Preset", ["Conservative", "Balanced", "Aggressive", "Custom"], index=1)
        
        presets = {
            "Conservative": {"rsi": (40, 60), "vol_mul": 2.0, "lookback": 20},
            "Balanced":   {"rsi": (30, 70), "vol_mul": 1.5, "lookback": 30},
            "Aggressive": {"rsi": (20, 80), "vol_mul": 1.2, "lookback": 40}
        }
        
        if preset != "Custom":
            rsi_min, rsi_max = presets[preset]["rsi"]
            vol_mul = presets[preset]["vol_mul"]
            lookback = presets[preset]["lookback"]
            st.markdown(
                f"**{preset}**: RSI {rsi_min}-{rsi_max}, Vol×{vol_mul}, EMA lookback {lookback}d")
        else:
            rsi_min, rsi_max = st.slider("RSI Range", 0, 100, (30, 70))
            vol_mul = st.slider(
                "Volume Multiplier (×20d avg)", 0.1, 5.0, 1.5, step=0.1)
            lookback = st.slider("EMA Crossover Lookback (days)", 5, 60, 30)

        st.subheader("Custom Tickers")
        custom = st.text_input("Extra tickers (comma-separated)")
        
        # Add batch size option
        batch_process = st.slider("Process Batch Size", 5, 100, 100, step=5,
                               help="Number of stocks to process at once. Lower for fewer API errors.")
        
        # Add continuous scan option
        continuous_scan = st.checkbox("Continuous Scanning", 
                                    value=True,
                                    help="Continue scanning in small batches to avoid API limits")
                                    
        # Add option to scan all stocks
        scan_all_stocks = st.checkbox("Scan All Stocks", 
                                    value=True,
                                    help="Scan all stocks in the selected CSV file")
        
        scan_btn = st.button("🔍 Run Scanner", disabled=st.session_state.scanner_running)
        retry_btn = st.button("🔄 Retry Failed", disabled=st.session_state.scanner_running)
        stop_btn = st.button("⏹️ Stop Scanner", disabled=not st.session_state.scanner_running)
        clear_btn = st.button("🗑️ Clear Results")

    # Set up the main result area
    with col2:
        # Handle clear button - avoid using st.experimental_rerun() to prevent tab switching
        if clear_btn:
            # Clear the state without forcing a rerun
            st.session_state.scan_results = None
            st.session_state.failed_tickers = []
            st.session_state.scanner_running = False
            # Show success message instead of rerunning
            st.success("Results cleared successfully!")
            
        # Handle stop button
        if stop_btn:
            st.session_state.scanner_running = False
            st.success("Scanner stopped")
            
        # Handle loading and processing tickers
        def perform_scan(ticker_list):
            st.session_state.scanner_running = True
            
            # Initialize progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.empty()
            
            all_results = []
            failed_tickers = []
            completed_retries = []
            
            # Split into batches for processing
            total_tickers = len(ticker_list)
            batch_count = (total_tickers + batch_process - 1) // batch_process
            
            try:
                for batch_idx in range(batch_count):
                    # Check if scanner was stopped
                    if not st.session_state.scanner_running:
                        status_text.warning("Scanner stopped by user")
                        break
                        
                    # Get the current batch
                    start_idx = batch_idx * batch_process
                    end_idx = min(start_idx + batch_process, total_tickers)
                    current_batch = ticker_list[start_idx:end_idx]
                    
                    # Update progress
                    progress = (batch_idx * batch_process) / total_tickers
                    progress_bar.progress(progress)
                    status_text.text(f"Processing batch {batch_idx+1}/{batch_count} ({start_idx+1}-{end_idx} of {total_tickers})")
                    
                    # Fetch data for the batch
                    batch_data = fetch_bulk_data(current_batch, period, interval)
                    
                    # Process each ticker
                    batch_results = []
                    for ticker_info in current_batch:
                        try:
                            orig = ticker_info[0] if isinstance(ticker_info, (list, tuple)) else ticker_info
                            df = batch_data.get(orig)
                            
                            if df is None or len(df) < 21:
                                failed_tickers.append(orig)
                                continue
                                
                            # Calculate indicators
                            ind = calculate_indicators(df)
                            if ind is None:
                                failed_tickers.append(orig)
                                continue
                                
                            # Extract the latest data point
                            latest = ind.iloc[-1]
                            
                            # Calculate scores
                            ema_cross = int(latest['EMA_Cross'])
                            rsi_val = latest['RSI']
                            center = (rsi_min + rsi_max) / 2
                            rsi_score = max(0, 1 - abs(rsi_val - center) / max((rsi_max - rsi_min) / 2, 1))
                            vol_ratio = latest['VolRatio'] if 'VolRatio' in latest else (latest['Volume'] / latest['VolAvg20'] if 'VolAvg20' in latest and latest['VolAvg20'] > 0 else 0)
                            vol_score = min(vol_ratio / vol_mul, 1)
                            macd_diff = latest['MACD'] - latest['MACD_Signal'] if 'MACD' in latest and 'MACD_Signal' in latest else 0
                            macd = int(macd_diff > 0)
                            score = round(ema_cross * 0.4 + rsi_score * 0.3 + vol_score * 0.2 + macd * 0.1, 2)
                            
                            # Add to results
                            result = {
                                'Ticker': orig, 
                                'Price': round(latest['Close'], 2), 
                                'RSI(14)': round(rsi_val, 2), 
                                'Vol Ratio': round(vol_ratio, 2), 
                                'EMA Cross': 'Yes' if ema_cross else 'No', 
                                'MACD Diff': round(macd_diff, 2),
                                'Score': score
                            }
                            batch_results.append(result)
                            
                            # If this was a retry, mark it as completed
                            if universe == "Failed Tickers":
                                completed_retries.append(orig)
                            
                        except Exception as e:
                            st.warning(f"Error processing {orig}: {e}")
                            failed_tickers.append(orig)
                    
                    # Add batch results to overall results
                    all_results.extend(batch_results)
                    
                    # Update the displayed results after each UPDATE_INTERVAL stocks
                    processed_count = (batch_idx + 1) * batch_process
                    if all_results and (processed_count % UPDATE_INTERVAL <= batch_process) or batch_idx == batch_count - 1:
                        df_results = pd.DataFrame(all_results).sort_values('Score', ascending=False)
                        with results_container.container():
                            st.dataframe(df_results)
                            st.text(f"Processed {min(processed_count, total_tickers)} of {total_tickers} stocks. Found {len(all_results)} matches.")
                    
                    # Wait between batches if continuous scanning
                    if continuous_scan and batch_idx < batch_count - 1:
                        wait_time = 5  # Increased wait time to 5 seconds to avoid API limits
                        for i in range(wait_time, 0, -1):
                            status_text.text(f"Waiting {i}s before next batch...")
                            time.sleep(1)
                
                # Final progress update
                if st.session_state.scanner_running:
                    progress_bar.progress(1.0)
                    status_text.text(f"Completed scanning {total_tickers} tickers. Found {len(all_results)} matches.")
                
                # Save results to session state
                if all_results:
                    results_df = pd.DataFrame(all_results).sort_values('Score', ascending=False)
                    st.session_state.scan_results = results_df
                
                # Save failed tickers for retry
                if failed_tickers:
                    st.session_state.failed_tickers = failed_tickers
                    save_failed_tickers(failed_tickers)
                    status_text.warning(f"{len(failed_tickers)} tickers failed and saved for retry")
                
                # Update retry file by removing successful retries
                if completed_retries:
                    clear_completed_retries(completed_retries)
                
            except Exception as e:
                st.error(f"Error during scanning: {e}")
            finally:
                st.session_state.scanner_running = False
        
        # Handle button clicks for scanning
        if scan_btn:
            # Get tickers based on selected universe
            if universe == "Failed Tickers":
                tickers = load_retry_tickers()
                if not tickers:
                    st.info("No failed tickers to retry")
                    st.session_state.scanner_running = False
                else:
                    tickers = [[t, t] for t in tickers]
            elif universe == "Swedish Stocks":
                # First try fetching Swedish stocks using investpy API
                tickers = []
                try:
                    with st.spinner("Fetching Swedish stocks from investpy API..."):
                        stocks_df = investpy.get_stocks(country="Sweden")
                        stocks_df['YahooTicker'] = stocks_df['symbol'].str.upper() + '.ST'
                        tickers = [[t, t] for t in stocks_df['YahooTicker'].tolist()]
                    
                    st.success(f"Successfully fetched {len(tickers)} Swedish stocks from investpy API")
                except Exception as e:
                    st.warning(f"Error fetching Swedish stocks from investpy API: {e}")
                    st.info("Falling back to valid_swedish_company_data.csv file...")
                    
                    # Fallback to valid_swedish_company_data.csv
                    st.write(f"▶️ Looking for backup file: {SWEDEN_BACKUP_CSV}")
                    # Try all possible paths for the backup file
                    possible_paths = [
                        SWEDEN_BACKUP_CSV,
                        f"csv/{SWEDEN_BACKUP_CSV}",
                        f"../csv/{SWEDEN_BACKUP_CSV}",
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "csv", SWEDEN_BACKUP_CSV),
                        # Add absolute path for WSL environments
                        f"/mnt/c/Users/JonasCarlsson/OneDrive - Lemontree Enterprise Solutions AB/AI/AI Aktier/Teknisk analys Jockes/v2/csv/{SWEDEN_BACKUP_CSV}"
                    ]
                    
                    for path in possible_paths:
                        exists = os.path.exists(path)
                        st.write(f"▶️ Checking path: {path} - Exists: {exists}")
                        if exists:
                            try:
                                # Try multiple encodings to ensure the file loads correctly
                                try:
                                    df = pd.read_csv(path, encoding='utf-8')
                                except:
                                    try:
                                        df = pd.read_csv(path, encoding='latin-1')
                                    except:
                                        df = pd.read_csv(path, encoding='utf-8', on_bad_lines='skip')
                                
                                st.write(f"▶️ Backup CSV columns: {list(df.columns)}")
                                st.write(f"▶️ Backup CSV rows: {len(df)}")
                                
                                # Determine which columns to use for tickers
                                if 'YahooTicker' in df.columns:
                                    tickers = [[t, t] for t in df['YahooTicker'].tolist() if pd.notna(t) and str(t).strip() != '']
                                elif 'Tickersymbol' in df.columns:
                                    tickers = [[t, t] for t in df['Tickersymbol'].tolist() if pd.notna(t) and str(t).strip() != '']
                                
                                st.success(f"Successfully loaded {len(tickers)} Swedish stocks from backup file")
                                break
                            except Exception as e_csv:
                                st.error(f"Error loading backup file {path}: {e_csv}")
                
                # Display ticker information
                if tickers:
                    st.write(f"▶️ Total Swedish stocks: {len(tickers)}")
                    st.write("▶️ First 5 tickers:", tickers[:5])
                    if len(tickers) > 10:
                        st.write("▶️ Last 5 tickers:", tickers[-5:])
                else:
                    st.error("Failed to fetch Swedish stocks from both API and backup file.")
            else:
                tickers = load_csv_tickers(csv_file)
                st.write("▶️ CSV file path:", csv_file, "| Exists?", os.path.exists(csv_file))
                st.write("▶️ Loaded tickers count:", len(tickers))
                # Show first 5 tickers and last 5 tickers to verify full loading
                st.write("▶️ First 5 tickers:", tickers[:5])
                if len(tickers) > 10:
                    st.write("▶️ Last 5 tickers:", tickers[-5:])
            
            # Use all tickers if scan_all_stocks is enabled
            if 'scan_all_stocks' in locals() and scan_all_stocks:
                st.write(f"▶️ Scanning ALL tickers in the CSV file: {len(tickers)}")
            else:
                # Limit to first 19 tickers if not scanning all
                orig_count = len(tickers)
                tickers = tickers[:19]
                st.write(f"▶️ Limited to first 19 tickers for testing (out of {orig_count})")
                
            # Add custom tickers if provided
            if custom:
                custom_tickers = [[t.strip(), t.strip()] for t in custom.split(',') if t.strip()]
                tickers.extend(custom_tickers)
                
            if not tickers:
                st.warning("No tickers to scan.")
                st.session_state.scanner_running = False
            else:
                perform_scan(tickers)
                
        elif retry_btn:
            # Load and retry failed tickers
            retry_tickers = load_retry_tickers()
            if retry_tickers:
                retry_tickers = [[t, t] for t in retry_tickers]
                perform_scan(retry_tickers)
            else:
                st.info("No failed tickers to retry")
        
        # Display scan results if available
        df_res = st.session_state.scan_results
        if df_res is not None and not df_res.empty:
            st.subheader("Results")
            top_n = st.slider("Display Top N", 1, len(df_res), min(20, len(df_res)))
            df_disp = df_res.head(top_n)
            
            # Allow adding to watchlist
            if 'watchlist_manager' in st.session_state:
                wlists = watchlist_manager.get_all_watchlists()
                names = [w['name'] for w in wlists]
                sel = st.selectbox("Watchlist", range(len(names)),
                                format_func=lambda i: names[i])
                picks = st.multiselect("Select to add:", df_disp['Ticker'].tolist())
                if st.button("Add to Watchlist") and picks:
                    for t in picks:
                        watchlist_manager.add_stock_to_watchlist(sel, t)
                        st.success(f"Added {t} to {names[sel]}")
            
            # Display the dataframe
            st.dataframe(df_disp, use_container_width=True)
            
            # Display failed tickers if any
            if hasattr(st.session_state, 'failed_tickers') and st.session_state.failed_tickers:
                with st.expander(f"Failed Tickers ({len(st.session_state.failed_tickers)})"):
                    st.write(", ".join(st.session_state.failed_tickers))
        
        elif not st.session_state.scanner_running:
            st.info("Click 'Run Scanner' to search for stocks matching your criteria.")