import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
from datetime import datetime

# Utility functions to load tickers from CSV files


@st.cache_data(ttl=3600)
def load_csv_tickers(file_name):
    possible_paths = [
        file_name,
        f"csv/{file_name}",
        f"../csv/{file_name}",
        f"../../csv/{file_name}",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name),
        os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "..", file_name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "csv", file_name)
    ]
    for path in possible_paths:
        try:
            if os.path.exists(path):
                df = pd.read_csv(path)
                if 'YahooTicker' in df.columns:
                    st.success(f"Loaded CSV: {path}")
                    return df[['Tickersymbol', 'YahooTicker']].values.tolist()
                elif 'Tickersymbol' in df.columns:
                    st.success(f"Loaded CSV: {path}")
                    return [[t, t] for t in df['Tickersymbol'].tolist()]
        except Exception:
            continue
    st.error(f"CSV '{file_name}' not found.")
    return []

# Calculate technical indicators


def calculate_indicators(df):
    df = df.copy()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    delta = df['Close'].diff()
    gain, loss = delta.copy(), -delta.copy()
    gain[gain < 0] = 0
    loss[loss < 0] = 0
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['VolAvg20'] = df['Volume'].rolling(20).mean()
    df['MACD'] = df['Close'].ewm(span=12, adjust=False).mean(
    ) - df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['EMA_Cross'] = ((df['EMA50'] > df['EMA200']) & (
        df['EMA50'].shift(1) <= df['EMA200'].shift(1))).astype(int)
    return df

# Fetch data in batches


@st.cache_data(ttl=3600)
def fetch_bulk_data(tickers, period, interval):
    result = {}
    chunk_size = 25
    total = len(tickers)
    for i in range(0, total, chunk_size):
        chunk = tickers[i:i+chunk_size]
        syms = [t[1] for t in chunk]
        try:
            data = yf.download(
                tickers=syms, period=period, interval=interval,
                group_by='ticker', auto_adjust=True, progress=False
            )
            if isinstance(data.columns, pd.MultiIndex):
                for orig, sym in chunk:
                    if sym in data.columns.levels[0]:
                        df_sym = data[sym].copy()
                        if not df_sym.empty:
                            result[orig] = df_sym
            else:
                if syms and not data.empty:
                    result[chunk[0][0]] = data.copy()
        except Exception:
            continue
    return result

# Main render function


def render_scanner_tab():
    """
    Renders stock scanner. Preserves results in session_state to avoid data loss on widget changes.
    """
    if 'scan_results' not in st.session_state:
        st.session_state.scan_results = None

    watchlist_manager = st.session_state.watchlist_manager
    st.header("Stock Scanner")
    col1, col2 = st.columns([1, 3])

    # UI mappings
    period_map = {"3 months": "3mo", "6 months": "6mo", "1 year": "1y"}
    interval_map = {"Daily": "1d", "Weekly": "1wk"}

    with col1:
        st.subheader("Scanner Settings")
        universe = st.selectbox(
            "Universe", ["Small Cap", "Mid Cap", "Large Cap"], index=1)
        csv_file = {"Small Cap": "updated_small.csv",
                    "Mid Cap": "updated_mid.csv", "Large Cap": "updated_large.csv"}[universe]

        history = st.selectbox("History", list(period_map.keys()), index=0)
        period = period_map[history]

        interval_label = st.selectbox(
            "Interval", list(interval_map.keys()), index=0)
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

        scan_btn = st.button("🔍 Run Scanner")
        clear_btn = st.button("🗑️ Clear Results")

    # Clear stored results
    if clear_btn:
        st.session_state.scan_results = None

    # Run or load results
    if scan_btn or st.session_state.scan_results is None:
        if scan_btn:
            tickers = load_csv_tickers(csv_file)
            if custom:
                tickers += [[t.strip(), t.strip()]
                            for t in custom.split(',') if t.strip()]
            if not tickers:
                st.warning("No tickers loaded.")
            else:
                data = fetch_bulk_data(tickers, period, interval)
                results = []
                for orig, _ in tickers:
                    df = data.get(orig)
                    if df is None or len(df) < 21:
                        continue
                    ind = calculate_indicators(df)
                    latest = ind.iloc[-1]
                    # scores
                    ema = int(latest['EMA_Cross'])
                    center = (rsi_min+rsi_max)/2
                    rsi_score = max(
                        0, 1-abs(latest['RSI']-center)/max((rsi_max-rsi_min)/2, 1))
                    vol_ratio = latest['Volume'] / \
                        latest['VolAvg20'] if latest['VolAvg20'] > 0 else 0
                    vol_score = min(vol_ratio/vol_mul, 1)
                    macd_diff = ind['MACD'].iloc[-1] - \
                        ind['MACD_Signal'].iloc[-1]
                    macd = int(macd_diff > 0)
                    score = round(ema*0.4+rsi_score*0.3 +
                                  vol_score*0.2+macd*0.1, 2)
                    results.append({'Ticker': orig, 'Price': round(latest['Close'], 2), 'RSI(14)': round(latest['RSI'], 2), 'Vol Ratio': round(
                        vol_ratio, 2), 'EMA Cross': 'Yes' if ema else 'No', 'MACD Diff': round(macd_diff, 2), 'Score': score})
                st.session_state.scan_results = pd.DataFrame(results).sort_values(
                    'Score', ascending=False).reset_index(drop=True)
    # Display stored results
    df_res = st.session_state.scan_results
    if df_res is not None and not df_res.empty:
        st.subheader("Results")
        top_n = st.slider("Display Top N", 1, len(
            df_res), min(20, len(df_res)))
        df_disp = df_res.head(top_n)
        wlists = watchlist_manager.get_all_watchlists()
        names = [w['name'] for w in wlists]
        sel = st.selectbox("Watchlist", range(len(names)),
                           format_func=lambda i: names[i])
        picks = st.multiselect("Select to add:", df_disp['Ticker'].tolist())
        if st.button("Add to Watchlist") and picks:
            for t in picks:
                watchlist_manager.add_stock_to_watchlist(sel, t)
                st.success(f"Added {t} to {names[sel]}")
        st.dataframe(df_disp, use_container_width=True)
