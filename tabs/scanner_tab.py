import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
import time
from datetime import datetime, timedelta
import random
import json
import csv
from strategy import ValueMomentumStrategy  # ← new

# Try to import investpy, but don't fail if it's not available
try:
    import investpy
    INVESTPY_AVAILABLE = True
except ImportError:
    INVESTPY_AVAILABLE = False
    st.warning("investpy module not available. Swedish stocks will be loaded from CSV only.")

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
    
    # Instantiate your strategy (so we can use its tech+fund scoring)
    strategy = ValueMomentumStrategy()
    
    st.header("Stock Scanner")
    col1, col2 = st.columns([1, 3])

    # UI mappings
    period_map = {"3 months": "3mo", "6 months": "6mo", "1 year": "1y"}
    interval_map = {"Daily": "1d", "Weekly": "1wk"}

    # Initialize session state for scanner settings with all needed fields
    if 'scanner_universe' not in st.session_state:
        st.session_state.scanner_universe = "Mid Cap"
    if 'universe_selectbox' not in st.session_state:
        st.session_state.universe_selectbox = st.session_state.scanner_universe
    if 'prevent_tab_change' not in st.session_state:
        st.session_state.prevent_tab_change = True
        
    # Define callback to update session state without causing rerun
    def update_universe():
        # Only set scanner_universe if we're not in initial state
        if not st.session_state.prevent_tab_change:
            st.session_state.scanner_universe = st.session_state.universe_selectbox
        else:
            # After first use, allow normal behavior
            st.session_state.prevent_tab_change = False
            
    with col1:
        st.subheader("Scanner Settings")
        universe_options = ["Small Cap", "Mid Cap", "Large Cap", "Swedish Stocks", "Failed Tickers"]
        
        # Get current selected universe (defaulting to Mid Cap)
        current_universe = st.session_state.scanner_universe
        current_index = universe_options.index(current_universe) if current_universe in universe_options else 1
        
        # Use key parameter to link to session state
        universe = st.selectbox("Stock Universe", 
                              options=universe_options, 
                              index=current_index,
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
            stop_message = st.empty()
            stop_message.warning("⚠️ STOPPING SCANNER... Please wait for current batch to complete.")
            # Force a status update
            if 'status_message' in st.session_state:
                st.session_state.status_message = "Scanner stopping - Please wait..."
            
        # Handle loading and processing tickers
        def perform_scan(ticker_list):
            st.session_state.scanner_running = True
            
            # Initialize progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.empty()
            
            try:
                # Instead of manual scoring, hand the entire ticker list off to your strategy
                symbols = [t[0] if isinstance(t, (list, tuple)) else t for t in ticker_list]
                
                # Display initial status
                status_text.text(f"Starting analysis of {len(symbols)} stocks...")
                
                # Use the ValueMomentumStrategy to analyze all tickers
                analyses = strategy.batch_analyze(symbols,
                    progress_callback=lambda p, msg: (progress_bar.progress(p), status_text.text(msg)))
                
                # Build DataFrame from the returned analyses
                all_results = []
                failed = []
                
                for a in analyses:
                    if a.get("error"):
                        failed.append(a["ticker"])
                        continue
                    all_results.append({
                        "Ticker":     a["ticker"],
                        "Price":      a["price"],
                        "Tech Score": a["tech_score"],
                        "Fund OK":    "Yes" if a["fundamental_check"] else "No",
                        "Signal":     a["signal"]
                    })
                
                # Sort by the strategy's Tech Score
                if all_results:
                    df_results = pd.DataFrame(all_results).sort_values("Tech Score", ascending=False)
                    st.session_state.scan_results = df_results
                
                # Track failed tickers for retry
                if failed:
                    st.session_state.failed_tickers = failed
                    save_failed_tickers(failed)
                
                # Final status update without displaying the table (the outer code will handle that)
                status_text.text(f"Completed. {len(all_results)} results, {len(failed)} failed.")
                
                # Record successful retries if we were retrying failed tickers
                if universe == "Failed Tickers" and all_results:
                    completed_retries = [a["ticker"] for a in analyses if not a.get("error")]
                    if completed_retries:
                        clear_completed_retries(completed_retries)
                
            except Exception as e:
                st.error(f"Error during scanning: {e}")
                import traceback
                st.error(traceback.format_exc())
            finally:
                # Always set scanner to finished state
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
                # Directly use valid_swedish_company_data.csv without trying investpy
                tickers = []
                
                # Try using investpy if available (but most deployments won't have it)
                if INVESTPY_AVAILABLE:
                    try:
                        with st.spinner("Fetching Swedish stocks from investpy API..."):
                            stocks_df = investpy.get_stocks(country="Sweden")
                            stocks_df['YahooTicker'] = stocks_df['symbol'].str.upper() + '.ST'
                            tickers = [[t, t] for t in stocks_df['YahooTicker'].tolist()]
                            st.success(f"Successfully fetched {len(tickers)} Swedish stocks from investpy API")
                            # If we got tickers, no need to load from CSV
                            if tickers:
                                return tickers
                    except Exception as e:
                        st.warning(f"Could not use investpy: {e}. Falling back to CSV file.")
                
                # Define paths to look for the CSV file
                possible_paths = [
                    f"csv/{SWEDEN_BACKUP_CSV}",  # Relative path for deployment
                    SWEDEN_BACKUP_CSV,           # Direct path
                    f"../csv/{SWEDEN_BACKUP_CSV}",
                    SWEDEN_BACKUP_CSV,
                    f"csv/{SWEDEN_BACKUP_CSV}",
                    f"../csv/{SWEDEN_BACKUP_CSV}",
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "csv", SWEDEN_BACKUP_CSV)
                ]
                
                # Try each path until we find the file
                for path in possible_paths:
                    exists = os.path.exists(path)
                    st.write(f"▶️ Checking path: {path} - Exists: {exists}")
                    
                    if exists:
                        try:
                            # Try to load with UTF-8 encoding first, then fallback to latin-1
                            # Try a direct approach with the csv module to handle quotes properly
                            ticker_list = []
                            
                            # First try with pandas for convenience
                            try:
                                df = pd.read_csv(path, encoding='utf-8')
                                has_yahoo_ticker = 'YahooTicker' in df.columns
                                
                                if not has_yahoo_ticker:
                                    # Try a more manual approach with the csv module
                                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                                        reader = csv.reader(f)
                                        headers = next(reader)
                                        yahoo_idx = headers.index('YahooTicker') if 'YahooTicker' in headers else 0
                                        
                                        for row in reader:
                                            if row and len(row) > yahoo_idx:
                                                ticker = row[yahoo_idx].strip()
                                                if ticker and not ticker.startswith('#'):
                                                    if ',' in ticker:
                                                        ticker = ticker.split(',')[0]
                                                    ticker_list.append(ticker)
                                    
                                    # Create a DataFrame if csv approach worked
                                    if ticker_list:
                                        df = pd.DataFrame({'YahooTicker': ticker_list})
                            
                            except UnicodeDecodeError:
                                # Try with latin-1 encoding
                                df = pd.read_csv(path, encoding='latin-1')
                            
                            st.write(f"▶️ CSV columns: {list(df.columns)}")
                            st.write(f"▶️ CSV row count: {len(df)}")
                            
                            # Process tickers - handling quoted entries with commas
                            if 'YahooTicker' in df.columns:
                                # Clean and process tickers
                                processed_tickers = []
                                for t in df['YahooTicker']:
                                    if pd.isna(t) or str(t).strip() == '':
                                        continue
                                        
                                    ticker = str(t)
                                    # Handle quoted entries with commas
                                    if '"' in ticker:
                                        # Extract the first part before comma
                                        ticker = ticker.replace('"', '').split(',')[0]
                                    
                                    processed_tickers.append(ticker)
                                
                                tickers = [[t, t] for t in processed_tickers]
                                st.success(f"Successfully loaded {len(tickers)} Swedish stocks")
                                break
                        except Exception as e:
                            st.error(f"Error loading CSV from {path}: {e}")
                
                # Display ticker information
                if tickers:
                    st.write(f"▶️ Total Swedish stocks: {len(tickers)}")
                    st.write("▶️ First 5 tickers:", tickers[:5])
                    if len(tickers) > 10:
                        st.write("▶️ Last 5 tickers:", tickers[-5:])
                else:
                    st.error("Failed to load Swedish stocks from valid_swedish_company_data.csv")
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
                
            # Callback functions to update state without page reload
            def update_selected_watchlist():
                st.session_state.watchlist_selected = st.session_state.selected_wl_index
                
            def update_picked_stocks():
                st.session_state.watchlist_picks = st.session_state.picked_stocks
                
            def add_to_watchlist():
                # Use values stored in session state
                wl_index = st.session_state.watchlist_selected
                stock_picks = st.session_state.watchlist_picks
                
                if stock_picks and 'watchlist_manager' in st.session_state:
                    wlists = watchlist_manager.get_all_watchlists()
                    names = [w['name'] for w in wlists]
                    
                    success_message = st.empty()
                    for t in stock_picks:
                        watchlist_manager.add_stock_to_watchlist(wl_index, t)
                    
                    # Show success message without reloading page
                    if len(stock_picks) == 1:
                        success_message.success(f"Added {stock_picks[0]} to {names[wl_index]}")
                    else:
                        success_message.success(f"Added {len(stock_picks)} stocks to {names[wl_index]}")
                    
                    # Clear picks from session state
                    st.session_state.watchlist_picks = []
                    # This will reset the multiselect without reloading
                    st.session_state.picked_stocks = []
            
            # Allow adding to watchlist
            if 'watchlist_manager' in st.session_state:
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
            
            # Display the dataframe
            st.dataframe(df_disp, use_container_width=True)
            
            # Display failed tickers if any
            if hasattr(st.session_state, 'failed_tickers') and st.session_state.failed_tickers:
                with st.expander(f"Failed Tickers ({len(st.session_state.failed_tickers)})"):
                    st.write(", ".join(st.session_state.failed_tickers))
        
        elif not st.session_state.scanner_running:
            st.info("Click 'Run Scanner' to search for stocks matching your criteria.")