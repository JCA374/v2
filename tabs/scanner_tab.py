# tabs/scanner_tab.py
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from itertools import islice


def render_scanner_tab():
    """Render the stock scanner tab for finding stocks that match technical criteria"""
    st.header("📋 Stock Scanner & Watchlist Builder")

    # Access shared objects from session state
    watchlist_manager = st.session_state.watchlist_manager
    strategy = st.session_state.strategy

    # 1) Gather all tickers from your watchlists
    watchlists = watchlist_manager.get_all_watchlists()
    tickers = sorted({t for wl in watchlists for t in wl["stocks"]})
    if not tickers:
        st.info(
            "Din watchlist är tom. Lägg till aktier för att kunna använda scannern.")
        return

    # 2) Scanner settings
    with st.expander("⚙️ Scanner Inställningar", expanded=False):
        period = st.selectbox("Historikperiod", ["3mo", "6mo", "1y"], index=0)
        interval = st.selectbox("Interval", ["1d", "1h"], index=0)
        # Smart criteria
        rsi_min = st.number_input(
            "RSI ≥", min_value=0, max_value=100, value=30)
        rsi_max = st.number_input(
            "RSI ≤", min_value=0, max_value=100, value=70)
        vol_mul = st.number_input("Volym ≥ X × genomsnitt(20d)", min_value=0.1,
                                  max_value=10.0, value=1.1, step=0.1)
        days_cross = st.slider(
            "EMA50/200 korsning inom senaste N dagar", 1, 20, 5)

    # 3) Fetch & cache bulk data in chunks
    with st.spinner("Hämtar prisdata..."):
        bulk = fetch_bulk_data(tickers, period, interval)

    # 4) Run the screen
    with st.spinner("Analyserar aktier..."):
        results = screen_stocks(
            bulk, rsi_min, rsi_max, vol_mul, days_cross
        )

    st.subheader(f"📈 {len(results)} Aktier som uppfyller köpkriterierna")
    if results.empty:
        st.write("Inga aktier matchar dina kriterier.")
        return

    # 5) Show table & let user pick to add to watchlist or deep-dive
    table = st.dataframe(
        results,
        column_config={
            "RSI(14)": st.column_config.ProgressColumn(
                "RSI(14)",
                help="Relative Strength Index (14 perioder)",
                min_value=0,
                max_value=100,
                format="%.1f"
            ),
            "Vol Ratio": st.column_config.ProgressColumn(
                "Vol Ratio",
                help="Dagens volym jämfört med 20-dagars genomsnitt",
                min_value=0,
                max_value=3,
                format="%.2f"
            )
        },
        use_container_width=True,
        hide_index=True
    )

    # Pickers
    to_add = st.multiselect(
        "Välj aktier att lägga till i en watchlist:",
        options=results["Ticker"].tolist()
    )

    # Select destination watchlist
    watchlist_names = [wl["name"] for wl in watchlists]
    watchlist_indices = list(range(len(watchlists)))

    dest_index = st.selectbox(
        "Destination Watchlist",
        options=watchlist_indices,
        format_func=lambda i: watchlist_names[i],
        index=watchlist_manager.get_active_watchlist_index()
    )

    if to_add and st.button("➕ Lägg till i Watchlist"):
        added_count = 0
        for ticker in to_add:
            if watchlist_manager.add_stock_to_watchlist(dest_index, ticker):
                added_count += 1

        if added_count > 0:
            st.success(
                f"Lade till {added_count} aktier till \"{watchlist_names[dest_index]}\"")
        else:
            st.warning(
                "Inga nya aktier lades till. De kanske redan finns i watchlisten.")

    st.markdown("— eller —")

    if to_add and st.button("🔍 Analysera valda aktier"):
        # Store the selected tickers in session state for analysis
        st.session_state.batch_analysis_tickers = to_add
        st.session_state.analyze_selected = True

        # Redirect to the watchlist tab for batch analysis
        st.success(
            f"Valda {len(to_add)} aktier. Går till batch-analysfliken...")
        st.session_state['current_tab'] = "Watchlist & Batch Analysis"
        st.rerun()


# ————————————— Helpers ———————————————

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_bulk_data(tickers, period, interval, chunk_size=50):
    """
    Download stock data in batches and return dict[ticker]→DataFrame.
    
    Parameters:
    - tickers: List of stock tickers
    - period: Time period to download (e.g., '1y', '6mo')
    - interval: Data interval (e.g., '1d', '1h')
    - chunk_size: Number of tickers to download in each batch
    
    Returns:
    - Dictionary mapping tickers to their historical data DataFrames
    """
    out = {}
    it = iter(tickers)
    for chunk in iter(lambda: list(islice(it, chunk_size)), []):
        df = yf.download(
            tickers=chunk,
            period=period,
            interval=interval,
            group_by='ticker',
            progress=False,
        )
        # yf returns a MultiIndex if >1 ticker, else plain df
        if isinstance(df.columns, pd.MultiIndex):
            for t in chunk:
                if t in df.columns.levels[0]:
                    out[t] = df[t].dropna()
        else:
            # single-ticker fallback
            out[chunk[0]] = df.dropna()
    return out


def screen_stocks(bulk, rsi_min, rsi_max, vol_mul, days_cross):
    """
    Return DataFrame of tickers meeting basic buy rules.
    
    Parameters:
    - bulk: Dictionary of ticker to DataFrame with historical data
    - rsi_min: Minimum RSI value to consider
    - rsi_max: Maximum RSI value to consider
    - vol_mul: Volume multiplier compared to 20-day average
    - days_cross: Number of days to look back for EMA cross
    
    Returns:
    - DataFrame with tickers meeting criteria
    """
    rows = []
    for ticker, df in bulk.items():
        if len(df) < 50:
            continue  # not enough data

        # Indicators
        df = df.copy()
        df['EMA50'] = df['Close'].ewm(span=50).mean()
        df['EMA200'] = df['Close'].ewm(span=200).mean()
        df['RSI'] = compute_rsi(df['Close'], 14)
        df['VolAvg20'] = df['Volume'].rolling(20).mean()

        # Check for EMA cross in last N days
        try:
            last_n_days = min(days_cross, len(df)-1)
            ema_cross = (
                (df['EMA50'].iloc[-1] > df['EMA200'].iloc[-1]) and
                any(df['EMA50'].iloc[-i-1] <= df['EMA200'].iloc[-i-1]
                    for i in range(1, last_n_days+1))
            )
        except:
            ema_cross = False

        # Calculate MACD
        macd = df['Close'].ewm(span=12).mean() - \
            df['Close'].ewm(span=26).mean()
        macd_hist = macd - macd.ewm(span=9).mean()
        try:
            macd_ok = macd_hist.iloc[-1] > 0
        except:
            macd_ok = False

        # Check conditions
        try:
            rsi_value = df['RSI'].iloc[-1]
            rsi_ok = rsi_min <= rsi_value <= rsi_max
        except:
            rsi_ok = False

        try:
            vol_ratio = df['Volume'].iloc[-1] / df['VolAvg20'].iloc[-1]
            vol_ok = vol_ratio >= vol_mul
        except:
            vol_ok = False

        if ema_cross and macd_ok and rsi_ok and vol_ok:
            rows.append({
                "Ticker": ticker,
                "Pris": round(df['Close'].iloc[-1], 2),
                "EMA50": round(df['EMA50'].iloc[-1], 2),
                "EMA200": round(df['EMA200'].iloc[-1], 2),
                "RSI(14)": round(df['RSI'].iloc[-1], 2),
                "Volym(1d)": int(df['Volume'].iloc[-1]),
                "GenomsnittVol(20d)": int(df['VolAvg20'].iloc[-1]),
                "Vol Ratio": round(df['Volume'].iloc[-1] / df['VolAvg20'].iloc[-1], 2)
            })

    return pd.DataFrame(rows)


def compute_rsi(series, length):
    """
    Compute the Relative Strength Index (RSI) for a price series
    
    Parameters:
    - series: Price series (typically Close prices)
    - length: RSI period (typically 14)
    
    Returns:
    - Series containing RSI values
    """
    # Handle potential errors
    try:
        # Get price changes
        delta = series.diff()

        # Separate gains (up) and losses (down)
        gain = delta.copy()
        gain[gain < 0] = 0.0

        loss = -delta.copy()
        loss[loss < 0] = 0.0

        # Calculate average gain and loss
        avg_gain = gain.rolling(window=length).mean()
        avg_loss = loss.rolling(window=length).mean()

        # Calculate RS with error handling for division by zero
        rs = pd.Series(np.zeros(len(avg_gain)), index=avg_gain.index)
        for i in range(len(avg_gain)):
            if avg_loss.iloc[i] > 0:
                rs.iloc[i] = avg_gain.iloc[i] / avg_loss.iloc[i]

        # Calculate RSI
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except Exception as e:
        print(f"Error computing RSI: {e}")
        # Return a series of NaN with the same index as the input
        return pd.Series(np.nan, index=series.index)
