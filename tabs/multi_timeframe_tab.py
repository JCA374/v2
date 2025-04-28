# tabs/multi_timeframe_tab.py
import streamlit as st # Make sure streamlit is imported if not already
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import traceback

# Define configuration for different timeframes
TIMEFRAME_CONFIG = {
    "long": {"period": "5y", "interval": "1wk", "title": "Long-Term Weekly Chart",
             "indicators": {"sma": [50, 200], "ema": [50, 200], "rsi_period": 14}},
    "medium": {"period": "1y", "interval": "1d", "title": "Medium-Term Daily Chart",
               "indicators": {"sma": [20, 50, 200], "ema": [20, 50, 200], "rsi_period": 14}},
    "short": {"period": "1mo", "interval": "60m", "title": "Short-Term Hourly Chart",
              "indicators": {"sma": [20, 50], "ema": [9, 20], "rsi_period": 14}}
}

# Default settings (consider making MA periods dynamic based on timeframe if needed)
DEFAULT_SETTINGS = {"rsi_oversold": 30, "rsi_overbought": 70,
                    "ma_short": 20, "ma_medium": 50, "ma_long": 200,
                    # Add MACD defaults if you want them configurable
                    "macd_fast": 12, "macd_slow": 26, "macd_signal": 9}


def render_multi_timeframe_tab():
    st.header("Multi-Timeframe Technical Analysis")
    if 'mta_settings' not in st.session_state:
        st.session_state.mta_settings = DEFAULT_SETTINGS.copy()

    # Access session state items safely
    # Assuming this might be used later
    strategy = st.session_state.get("strategy")
    watchlist_manager = st.session_state.get("watchlist_manager")

    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader("Select Stock")
        unique_tickers = []
        if watchlist_manager:
            try:
                all_watchlists = watchlist_manager.get_all_watchlists()
                unique_tickers = sorted(
                    {t for wl in all_watchlists for t in wl.get(
                        "stocks", [])}  # Safer access
                )
            except Exception as e:
                st.warning(f"Could not load watchlists: {e}")

        manual = st.text_input("Enter ticker symbol:",
                               placeholder="e.g., AAPL").strip().upper()
        select_options = [""] + unique_tickers
        select = st.selectbox("Or select from watchlist:", select_options)
        ticker = manual or select

        with st.expander("Analysis Settings"):
            s = st.session_state.mta_settings
            s["rsi_oversold"] = st.slider(
                "RSI Oversold Threshold", 10, 40, s["rsi_oversold"])
            s["rsi_overbought"] = st.slider(
                "RSI Overbought Threshold", 60, 90, s["rsi_overbought"])
            # Note: These MA sliders currently don't directly affect the fixed MAs (50/200 etc)
            # used in the analysis logic unless TIMEFRAME_CONFIG is updated dynamically.
            s["ma_short"] = st.slider("Short MA Period", 5, 50, s["ma_short"])
            s["ma_medium"] = st.slider(
                "Medium MA Period", 20, 100, s["ma_medium"])
            s["ma_long"] = st.slider("Long MA Period", 100, 300, s["ma_long"])

            # Optional: Add sliders for MACD if desired
            # s["macd_fast"] = st.slider("MACD Fast EMA", 5, 20, s["macd_fast"])
            # s["macd_slow"] = st.slider("MACD Slow EMA", 20, 50, s["macd_slow"])
            # s["macd_signal"] = st.slider("MACD Signal EMA", 5, 15, s["macd_signal"])

            if st.button("Reset to Defaults"):
                st.session_state.mta_settings = DEFAULT_SETTINGS.copy()
                st.rerun()

        analyze_clicked = st.button(
            "Analyze", key="analyze_mta", disabled=not ticker)

    with col2:
        if not ticker:
            st.info("Please enter or select a ticker symbol.")
            return
        if not analyze_clicked:
            st.info("Click 'Analyze' to load data.")
            return

        # Store fetched data in session state to avoid re-fetching when switching tabs
        if 'mta_data' not in st.session_state:
            st.session_state.mta_data = {}
        if 'current_mta_ticker' not in st.session_state:
            st.session_state.current_mta_ticker = None

        # If ticker changed or analyze clicked, clear old data and fetch new
        if st.session_state.current_mta_ticker != ticker or analyze_clicked:
            st.session_state.mta_data = {}  # Clear cache for other timeframes
            st.session_state.current_mta_ticker = ticker

        tabs = st.tabs(["Long-Term", "Medium-Term", "Short-Term"])
        for tab, key in zip(tabs, ["long", "medium", "short"]):
            with tab:
                title = TIMEFRAME_CONFIG[key]["title"]
                st.subheader(title)

                # Check cache before fetching
                df = st.session_state.mta_data.get(key)

                if df is None:  # Not in cache, fetch it
                    with st.spinner(f"Loading {key}-term data for {ticker}..."):
                        try:
                            df = _get_analyzed_data(
                                ticker, key, st.session_state.mta_settings)
                            # Store in cache
                            st.session_state.mta_data[key] = df
                        except Exception as e:
                            st.error(
                                f"An error occurred while fetching/analyzing data: {e}")
                            st.exception(e)  # Show traceback if needed
                            df = None  # Ensure df is None on error
                            # Cache the failure
                            st.session_state.mta_data[key] = None

                # Display data or error
                if df is None:
                    st.error(
                        f"Could not load or process {key}-term data for {ticker}.")
                elif df.empty:
                    st.warning(f"No {key}-term data returned for {ticker}.")
                else:
                    # Pass settings to analysis functions
                    settings = st.session_state.mta_settings
                    if key == "long":
                        _long_term_analysis(df, ticker, settings)
                    elif key == "medium":
                        _medium_term_analysis(df, ticker, settings)
                    elif key == "short":
                        _short_term_analysis(df, ticker, settings)


# Cache data fetched from yfinance

# Cache data fetched from yfinance

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def _fetch_data(symbol: str, period: str, interval: str) -> pd.DataFrame | None:
    """Fetches data using yfinance, handling potential tuple columns."""
    try:
        # Fetch data - keep auto_adjust=False as it often gives cleaner raw data
        df = yf.download(symbol, period=period, interval=interval, auto_adjust=False,
                         progress=False, actions=False)  # Explicitly disable actions columns

        if df is None or df.empty:
            st.warning(
                f"No data returned by yfinance for {symbol} ({period}, {interval})")
            return None

        # --- Robust Column Identification and Selection ---
        # Define required columns in lowercase for case-insensitive matching
        required_cols_lower = ['open', 'high', 'low', 'close', 'volume']
        # Mapping from standardized capitalized name to the original column identifier found
        column_mapping = {}

        for col in df.columns:
            # Keep the original (could be string or tuple)
            original_col_identifier = col
            col_name_to_check = None

            if isinstance(col, tuple) and col:
                # If it's a tuple, take the first element as the potential name
                # Convert to string just in case it's not, and then lowercase
                col_name_to_check = str(col[0]).lower()
            elif isinstance(col, str):
                # If it's a string, lowercase it
                col_name_to_check = col.lower()
            else:
                # Skip unexpected column types
                continue

            # If this column matches one of our required columns
            if col_name_to_check in required_cols_lower:
                # Standardize the name (e.g., 'open' -> 'Open')
                standard_name = col_name_to_check.capitalize()
                # Store the mapping: Standard Name -> Original Identifier
                # Avoid overwriting if multiple columns somehow map (e.g., 'Adj Close' vs 'Close')
                # Prioritize direct matches if possible, but usually OHLCV are unique.
                if standard_name not in column_mapping:
                    column_mapping[standard_name] = original_col_identifier

        # Check if all required columns were found and mapped
        required_cols_cap = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(c in column_mapping for c in required_cols_cap):
            st.error(
                f"Data for {symbol} missing required OHLCV columns. Found mappings: {list(column_mapping.keys())}")
            # Optionally print df.columns here for debugging:
            # st.warning(f"Original columns for {symbol}: {df.columns}")
            return None

        # Select only the required columns using their original identifiers
        df_selected = df[[column_mapping[std_name]
                          for std_name in required_cols_cap]]

        # Rename the columns of the *selected* DataFrame to the standard names
        df_selected.columns = required_cols_cap

        # Now work with the cleaned df_selected
        df = df_selected
        # --- End of Robust Column Handling ---

        # Final checks on the cleaned data
        if df['Close'].isnull().all():
            st.error(
                f"Cleaned data for {symbol} contains only null 'Close' prices.")
            return None

        # Ensure index is datetime (yf usually does this, but good practice)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        return df.copy()  # Return a copy

    except Exception as e:
        st.error(f"Error during data fetch or processing for {symbol}: {e}")
        # st.exception(e) # Uncomment for detailed traceback in the Streamlit app
        return None


def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculates RSI."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    # Use EMA for average gain/loss calculation
    avg_gain = gain.ewm(com=period - 1, min_periods=period,
                        adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period,
                        adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Handle potential division by zero if avg_loss is zero
    rsi = rsi.replace([np.inf, -np.inf], np.nan)
    rsi = rsi.fillna(100)  # If avg_loss is 0, RSI is 100

    return rsi


def _get_analyzed_data(symbol: str, tf: str, settings: dict) -> pd.DataFrame | None:
    """Fetches and analyzes data for a given timeframe."""
    cfg = TIMEFRAME_CONFIG[tf]
    df = _fetch_data(symbol, cfg["period"], cfg["interval"])

    if df is None or df.empty:
        return None  # Fetching failed or returned empty

    try:
        # Ensure 'Close' column exists after potential capitalization
        if 'Close' not in df.columns:
            st.error(
                f"Critical Error: 'Close' column not found in fetched data for {symbol}.")
            return None

        # --- Indicator Calculation ---
        close_price = df['Close']

        # SMAs
        for p in cfg["indicators"]["sma"]:
            df[f"SMA{p}"] = close_price.rolling(window=p, min_periods=p).mean()
        # EMAs
        for p in cfg["indicators"]["ema"]:
            df[f"EMA{p}"] = close_price.ewm(
                span=p, adjust=False, min_periods=p).mean()

        # RSI
        rsi_period = cfg["indicators"]["rsi_period"]
        df['RSI'] = _calculate_rsi(close_price, rsi_period)

        # MACD (using default/configurable periods)
        ema_fast = close_price.ewm(
            span=settings["macd_fast"], adjust=False).mean()
        ema_slow = close_price.ewm(
            span=settings["macd_slow"], adjust=False).mean()
        df['MACD'] = ema_fast - ema_slow
        df['MACD_Signal'] = df['MACD'].ewm(
            span=settings["macd_signal"], adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        # --- Signal Calculation (Vectorized EMA Crossover) ---
        df['buy_signal'] = False
        df['sell_signal'] = False

        # Use EMA50/EMA200 as the standard crossover signal example
        ema_short_col, ema_long_col = 'EMA50', 'EMA200'

        if ema_short_col in df.columns and ema_long_col in df.columns:
            ema_short = df[ema_short_col]
            ema_long = df[ema_long_col]

            # Shift to get previous values
            prev_ema_short = ema_short.shift(1)
            prev_ema_long = ema_long.shift(1)

            # Define crossover conditions
            buy_cond = (prev_ema_short <= prev_ema_long) & (
                ema_short > ema_long)
            sell_cond = (prev_ema_short >= prev_ema_long) & (
                ema_short < ema_long)

            # Apply signals (use .loc to avoid SettingWithCopyWarning)
            df.loc[buy_cond, 'buy_signal'] = True
            df.loc[sell_cond, 'sell_signal'] = True

        # --- Store signals in df.attrs for easy access in plotting ---
        # Ensure index is datetime for proper plotting/filtering later
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        buy_mask = df['buy_signal']
        sell_mask = df['sell_signal']

        # Store as lists of (Timestamp, ClosePrice) tuples
        df.attrs['buy_signals'] = list(
            zip(df.index[buy_mask], close_price[buy_mask])
        )
        df.attrs['sell_signals'] = list(
            zip(df.index[sell_mask], close_price[sell_mask])
        )

        return df.copy()  # Return a copy to avoid modifying cached object directly

    except Exception as e:
        st.error(
            f"Error during technical analysis calculation for {symbol} ({tf}): {e}")
        st.exception(e)  # Show traceback
        return None


def _plot_chart(df: pd.DataFrame, title: str, ticker: str) -> go.Figure:
    """Generates the Plotly chart."""
    fig = go.Figure()

    # Candlestick
    if all(col in df.columns for col in ['Open', 'High', 'Low', 'Close']):
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name='Price', increasing_line_color='green', decreasing_line_color='red'
        ))
    elif 'Close' in df.columns:  # Fallback to line if OHLC not available
        fig.add_trace(go.Scatter(
            x=df.index, y=df['Close'], name='Close Price', mode='lines'))

    # Moving Averages
    ma_colors = {'SMA': 'blue', 'EMA': 'orange'}
    for col in df.columns:
        if isinstance(col, str):
            prefix = None
            if col.startswith("SMA"):
                prefix = 'SMA'
            elif col.startswith("EMA"):
                prefix = 'EMA'

            if prefix and not df[col].isnull().all():
                fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col,
                                         mode='lines', line=dict(dash='dash', color=ma_colors.get(prefix))))

    # Buy/Sell Signals from df.attrs
    buys = df.attrs.get('buy_signals', [])
    sells = df.attrs.get('sell_signals', [])

    if buys:
        buy_dates, buy_prices = zip(*buys)
        fig.add_trace(go.Scatter(x=list(buy_dates), y=list(buy_prices), mode='markers',
                                 marker=dict(symbol='triangle-up', size=10, color='green'), name='Buy Signal'))  # Larger markers
    if sells:
        sell_dates, sell_prices = zip(*sells)
        fig.add_trace(go.Scatter(x=list(sell_dates), y=list(sell_prices), mode='markers',
                                 marker=dict(symbol='triangle-down', size=10, color='red'), name='Sell Signal'))  # Larger markers

    fig.update_layout(
        title=f"{title} — {ticker}",
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        height=500,  # Adjusted height slightly
        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=50, t=50, b=50)  # Add some margin
    )
    return fig


# --- Analysis Functions (Now accept settings) ---

def _long_term_analysis(df: pd.DataFrame, ticker: str, settings: dict):
    st.plotly_chart(_plot_chart(df, TIMEFRAME_CONFIG["long"]["title"], ticker),
                    use_container_width=True)

    st.subheader("Long-Term Analysis")
    trend = "Neutral"
    color = "gray"

    # Trend based on SMA50 vs SMA200
    sma50_col, sma200_col = 'SMA50', 'SMA200'
    if sma50_col in df.columns and sma200_col in df.columns:
        sma50_last = df[sma50_col].iloc[-1]
        sma200_last = df[sma200_col].iloc[-1]
        if pd.notna(sma50_last) and pd.notna(sma200_last):
            if sma50_last > sma200_last:
                trend = "Bullish"
                color = "green"
            elif sma50_last < sma200_last:
                trend = "Bearish"
                color = "red"

    st.markdown(f"**Primary Trend (SMA50 vs SMA200):** <span style='color:{color}; font-weight:bold;'>{trend}</span>",
                unsafe_allow_html=True)

    # 52-week metrics (relative to current date on weekly chart)
    if df.shape[0] >= 52 and all(c in df.columns for c in ['High', 'Low', 'Close']):
        window_52 = df.iloc[-52:]  # Last 52 data points (weeks)
        high_52 = window_52['High'].max()
        low_52 = window_52['Low'].min()
        last_close = df['Close'].iloc[-1]

        if pd.notna(high_52) and pd.notna(low_52) and pd.notna(last_close):
            st.write(f"**52-Week Range:** {low_52:.2f} - {high_52:.2f}")
            st.write(f"**Last Close:** {last_close:.2f}")
            if high_52 != low_52:  # Avoid division by zero if range is flat
                position_in_range = (
                    (last_close - low_52) / (high_52 - low_52)) * 100
                st.write(
                    f"**Position in 52-Week Range:** {position_in_range:.1f}%")
        else:
            st.write("Could not calculate 52-week metrics (missing data).")

    # Recent Signals (e.g., last 12 weeks)
    recent_buys = [d for d, _ in df.attrs.get(
        'buy_signals', []) if d > df.index[-12]]
    recent_sells = [d for d, _ in df.attrs.get(
        'sell_signals', []) if d > df.index[-12]]

    if recent_buys:
        st.write("**Recent Buy Signals (Last 12wk):** ",
                 ", ".join(d.strftime("%Y-%m-%d") for d in sorted(recent_buys)))
    if recent_sells:
        st.write("**Recent Sell Signals (Last 12wk):** ",
                 ", ".join(d.strftime("%Y-%m-%d") for d in sorted(recent_sells)))

    st.subheader("Long-Term Recommendation")
    if trend == "Bullish":
        st.markdown("✅ **Outlook: Bullish.** The long-term trend appears positive based on moving averages. Consider looking for buying opportunities, potentially on pullbacks.")
    elif trend == "Bearish":
        st.markdown("❌ **Outlook: Bearish.** The long-term trend appears negative. Caution is advised. Consider reducing exposure or looking for shorting opportunities on rallies.")
    else:
        st.markdown("➖ **Outlook: Neutral.** The long-term moving averages are not showing a clear directional trend. It might be prudent to wait for a clearer signal before committing significant capital.")


def _medium_term_analysis(df: pd.DataFrame, ticker: str, settings: dict):
    st.plotly_chart(_plot_chart(df, TIMEFRAME_CONFIG["medium"]["title"], ticker),
                    use_container_width=True)
    st.subheader("Medium-Term Analysis (Daily)")
    c1, c2, c3 = st.columns(3)

    # RSI
    with c1:
        if 'RSI' in df.columns:
            val = df['RSI'].iloc[-1]
            if pd.notna(val):
                rsi_ob = settings["rsi_overbought"]
                rsi_os = settings["rsi_oversold"]
                status = "Overbought" if val > rsi_ob else "Oversold" if val < rsi_os else "Neutral"
                delta = df['RSI'].iloc[-1] - df['RSI'].iloc[-2] if df.shape[0] > 1 and pd.notna(
                    df['RSI'].iloc[-2]) else None
                st.metric("RSI (14)", f"{val:.1f}", f"{status}", delta_color=(
                    "inverse" if status == "Overbought" else "normal" if status == "Oversold" else "off"))
            else:
                st.metric("RSI (14)", "N/A")

    # MACD
    with c2:
        if 'MACD' in df.columns and 'MACD_Signal' in df.columns and 'MACD_Hist' in df.columns:
            macd_val = df['MACD'].iloc[-1]
            signal_val = df['MACD_Signal'].iloc[-1]
            hist_val = df['MACD_Hist'].iloc[-1]
            if pd.notna(macd_val) and pd.notna(signal_val) and pd.notna(hist_val):
                status = "Above Signal" if macd_val > signal_val else "Below Signal"
                # Use hist_val for delta - shows change in MACD-Signal difference
                delta = df['MACD_Hist'].iloc[-1] - df['MACD_Hist'].iloc[-2] if df.shape[0] > 1 and pd.notna(
                    df['MACD_Hist'].iloc[-2]) else None
                st.metric("MACD Hist", f"{hist_val:.3f}", f"{status}", delta_color=(
                    "normal" if hist_val > 0 else "inverse"))
            else:
                st.metric("MACD Hist", "N/A")

    # Price vs EMA50
    with c3:
        if 'EMA50' in df.columns and 'Close' in df.columns:
            ema50_val = df['EMA50'].iloc[-1]
            price_val = df['Close'].iloc[-1]
            if pd.notna(ema50_val) and pd.notna(price_val):
                status = "Above EMA50" if price_val > ema50_val else "Below EMA50"
                delta_pct = ((price_val - ema50_val) / ema50_val) * \
                    100 if ema50_val != 0 else 0
                st.metric("Price vs EMA50", f"{status}", f"{delta_pct:.1f}%")
            else:
                st.metric("Price vs EMA50", "N/A")

    # Latest buy/sell signals (e.g., within last 20 trading days)
    st.subheader("Recent Signals")
    buys = df.attrs.get('buy_signals', [])
    sells = df.attrs.get('sell_signals', [])
    signal_found = False
    if buys and buys[-1][0] >= df.index[-20]:
        st.success(
            f"✅ EMA Crossover Buy Signal on: {buys[-1][0].strftime('%Y-%m-%d')}")
        signal_found = True
    if sells and sells[-1][0] >= df.index[-20]:
        st.error(
            f"❌ EMA Crossover Sell Signal on: {sells[-1][0].strftime('%Y-%m-%d')}")
        signal_found = True
    if not signal_found:
        st.info("No EMA Crossover signals within the last 20 periods.")

    # Recommendation based on confluence
    st.subheader("Medium-Term Recommendation")
    bullish_score = 0
    bearish_score = 0
    reasons = []

    # 1. Trend (EMA50 vs EMA200)
    if 'EMA50' in df.columns and 'EMA200' in df.columns:
        e50, e200 = df['EMA50'].iloc[-1], df['EMA200'].iloc[-1]
        if pd.notna(e50) and pd.notna(e200):
            if e50 > e200:
                bullish_score += 1
                reasons.append("EMA50 > EMA200 (Uptrend)")
            elif e50 < e200:
                bearish_score += 1
                reasons.append("EMA50 < EMA200 (Downtrend)")

    # 2. Momentum (RSI)
    if 'RSI' in df.columns:
        r = df['RSI'].iloc[-1]
        if pd.notna(r):
            if r > 55:  # Slightly above neutral
                bullish_score += 1
                reasons.append(f"RSI ({r:.1f}) > 55 (Bullish Momentum)")
            elif r < 45:  # Slightly below neutral
                bearish_score += 1
                reasons.append(f"RSI ({r:.1f}) < 45 (Bearish Momentum)")

    # 3. MACD
    if 'MACD' in df.columns and 'MACD_Signal' in df.columns:
        m, ms = df['MACD'].iloc[-1], df['MACD_Signal'].iloc[-1]
        if pd.notna(m) and pd.notna(ms):
            if m > ms:
                bullish_score += 1
                reasons.append("MACD > Signal Line")
            elif m < ms:
                bearish_score += 1
                reasons.append("MACD < Signal Line")

    # 4. Recent Crossover Signal (stronger weight?)
    if buys and buys[-1][0] >= df.index[-10]:  # Within last 10 days
        bullish_score += 1  # Add weight if desired
        reasons.append("Recent Buy Signal")
    if sells and sells[-1][0] >= df.index[-10]:  # Within last 10 days
        bearish_score += 1  # Add weight if desired
        reasons.append("Recent Sell Signal")

    st.write("Contributing Factors:", ", ".join(
        reasons) if reasons else "None")

    if bullish_score > bearish_score + 1:  # Need stronger confirmation
        st.markdown(
            "✅ **Recommendation: Bullish.** Multiple indicators suggest potential upside. Consider buying or holding.")
    elif bearish_score > bullish_score + 1:
        st.markdown(
            "❌ **Recommendation: Bearish.** Multiple indicators suggest potential downside. Consider selling or staying cautious.")
    else:
        st.markdown(
            "➖ **Recommendation: Mixed/Neutral.** Indicators are conflicting or neutral. Wait for clearer confirmation.")


def _short_term_analysis(df: pd.DataFrame, ticker: str, settings: dict):
    st.plotly_chart(_plot_chart(df, TIMEFRAME_CONFIG["short"]["title"], ticker),
                    use_container_width=True)
    st.subheader("Short-Term Analysis (Hourly)")
    c1, c2, c3 = st.columns(3)

    # Last price move
    with c1:
        if 'Close' in df.columns and df.shape[0] > 1:
            # FIX: Use .iloc for both previous and last values
            p0, p1 = df['Close'].iloc[-2], df['Close'].iloc[-1]
            if pd.notna(p0) and pd.notna(p1):
                delta = p1 - p0
                delta_pct = (delta / p0) * 100 if p0 != 0 else 0
                st.metric("Last Price", f"{p1:.2f}",
                          f"{delta:+.2f} ({delta_pct:.2f}%)")
            elif pd.notna(p1):
                st.metric("Last Price", f"{p1:.2f}", "Prev N/A")
            else:
                st.metric("Last Price", "N/A")
        elif 'Close' in df.columns and df.shape[0] == 1:
            p1 = df['Close'].iloc[-1]
            st.metric("Last Price", f"{p1:.2f}", "Single Point")
        else:
            st.metric("Last Price", "N/A")

    # RSI
    with c2:
        if 'RSI' in df.columns:
            val = df['RSI'].iloc[-1]
            if pd.notna(val):
                rsi_ob = settings["rsi_overbought"]
                rsi_os = settings["rsi_oversold"]
                status = "Overbought" if val > rsi_ob else "Oversold" if val < rsi_os else "Neutral"
                delta = df['RSI'].iloc[-1] - df['RSI'].iloc[-2] if df.shape[0] > 1 and pd.notna(
                    df['RSI'].iloc[-2]) else None
                st.metric("RSI (14)", f"{val:.1f}", f"{status}", delta_color=(
                    "inverse" if status == "Overbought" else "normal" if status == "Oversold" else "off"))
            else:
                st.metric("RSI (14)", "N/A")

    # EMA9 vs EMA20
    with c3:
        if 'EMA9' in df.columns and 'EMA20' in df.columns:
            e9, e20 = df['EMA9'].iloc[-1], df['EMA20'].iloc[-1]
            if pd.notna(e9) and pd.notna(e20):
                status = "EMA9 > EMA20" if e9 > e20 else "EMA9 < EMA20" if e9 < e20 else "EMA9 = EMA20"
                delta_pct = ((e9 - e20) / e20) * 100 if e20 != 0 else 0
                st.metric("Fast EMAs", status, f"{delta_pct:.2f}% diff")
            else:
                st.metric("Fast EMAs", "N/A")

    # Short-term signals & recommendation
    st.subheader("Recent Signals (Hourly)")
    buys = df.attrs.get('buy_signals', [])
    sells = df.attrs.get('sell_signals', [])
    # Look back e.g., 24 hours (assuming 6-8 trading hours / day -> 24 periods approx)
    lookback_periods = 24
    recent_buy_signal = buys and buys[-1][0] >= df.index[-lookback_periods]
    recent_sell_signal = sells and sells[-1][0] >= df.index[-lookback_periods]
    signal_found = False

    if recent_buy_signal:
        st.success(
            f"✅ EMA Crossover Buy Signal: {buys[-1][0].strftime('%Y-%m-%d %H:%M')}")
        signal_found = True
    if recent_sell_signal:
        st.error(
            f"❌ EMA Crossover Sell Signal: {sells[-1][0].strftime('%Y-%m-%d %H:%M')}")
        signal_found = True
    if not signal_found:
        st.info(
            f"No EMA Crossover signals in the last {lookback_periods} periods.")

    st.subheader("Short-Term Recommendation")
    rsi_val = df['RSI'].iloc[-1] if 'RSI' in df.columns and pd.notna(
        df['RSI'].iloc[-1]) else None
    e9 = df['EMA9'].iloc[-1] if 'EMA9' in df.columns and pd.notna(
        df['EMA9'].iloc[-1]) else None
    e20 = df['EMA20'].iloc[-1] if 'EMA20' in df.columns and pd.notna(
        df['EMA20'].iloc[-1]) else None

    if rsi_val is not None:
        if rsi_val < settings["rsi_oversold"]:
            st.markdown(
                "💡 **Condition: Oversold.** Potential for a short-term bounce. Look for confirmation before entering long.")
        elif rsi_val > settings["rsi_overbought"]:
            st.markdown(
                "💡 **Condition: Overbought.** Potential for a pullback or consolidation. Consider taking profits on long positions or waiting for entry.")
        elif recent_buy_signal and (e9 is not None and e20 is not None and e9 > e20):
            st.markdown(
                "💡 **Signal: Recent Buy.** Momentum aligned with recent buy signal. May continue upward, but manage risk (e.g., trailing stop).")
        elif recent_sell_signal and (e9 is not None and e20 is not None and e9 < e20):
            st.markdown(
                "💡 **Signal: Recent Sell.** Momentum aligned with recent sell signal. May continue downward. Consider exiting long or potential short entry.")
        elif e9 is not None and e20 is not None and e9 > e20:
            st.markdown(
                "💡 **Trend: EMA9 > EMA20.** Short-term momentum is currently bullish, but RSI is neutral. Monitor for continuation or divergence.")
        elif e9 is not None and e20 is not None and e9 < e20:
            st.markdown(
                "💡 **Trend: EMA9 < EMA20.** Short-term momentum is currently bearish, but RSI is neutral. Monitor for continuation or divergence.")
        else:
            st.markdown(
                "💡 **Condition: Neutral.** RSI is neutral and no strong recent signals/trends. Wait for clearer short-term direction.")
    else:
        st.markdown("💡 Waiting for sufficient data for short-term analysis.")
