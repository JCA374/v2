import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# Utility functions to fetch ticker lists


@st.cache_data(ttl=86400)
def get_us_tickers():
    """
    Fetches the list of NASDAQ/Nyse tickers from NasdaqTrader FTP.
    """
    url = 'ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt'
    try:
        df = pd.read_csv(url, sep='|')
        # Filter out test issues and empty symbols
        df = df[df['Test Issue'] == 'N']
        tickers = df['Symbol'].dropna().tolist()
        return tickers
    except Exception as e:
        st.error(f"Error fetching US tickers: {e}")
        return []


@st.cache_data(ttl=86400)
def get_se_tickers():
    """
    Returns a static list of Swedish tickers (.ST suffix).
    Extend this list or load from a file if needed.
    """
    # Basic OMX Stockholm large-cap list; extend as needed
    return [
        "ALIV-SDB.ST", "ASSA-B.ST", "ATCO-A.ST", "ATCO-B.ST", "AXFO.ST",
        "BOL.ST", "ELUX-B.ST", "ERIC-B.ST", "ESSITY-B.ST", "EVO.ST",
        "GETI-B.ST", "HEXA-B.ST", "HM-B.ST", "INVE-B.ST", "KINV-B.ST",
        "NDA-SE.ST", "SAND.ST", "SCA-B.ST", "SEB-A.ST", "SHB-A.ST",
        "SINCH.ST", "SKA-B.ST", "SKF-B.ST", "SWED-A.ST", "SWMA.ST",
        "TEL2-B.ST", "TELIA.ST", "VOLV-B.ST"
    ]


@st.cache_data(ttl=86400)
def get_all_tickers():
    """
    Combine US and Swedish tickers into a single list.
    """
    us = get_us_tickers()
    se = get_se_tickers()
    return list(set(us + se))


@st.cache_data(ttl=86400)
def get_se_tickers():
    """
    Fetches *all* Swedish equity tickers from Nasdaq OMX Stockholm via their CSV API,
    and appends the “.ST” suffix needed by yfinance.
    """
    url = (
        "https://www.nasdaqomxnordic.com/shares/"
        "microsite/AllShares.csv"
        "?Instrument=Equity&Exchange=STO&Currency=SEK"
    )
    # The CSV is semicolon-delimited and includes columns like 'Trading Code'
    df = pd.read_csv(url, sep=';')
    # Filter out any non-active or non-equity instruments if needed:
    df = df[df['Instrument Category'] == 'Equity']
    # Append the “.ST” suffix so yfinance can resolve them
    tickers = (df['Trading Code'].str.strip() + ".ST").tolist()
    return tickers



# Screening functions (unchanged)


def calculate_indicators(df):
    df = df.copy()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    delta = df['Close'].diff()
    gain = delta.copy()
    gain[gain < 0] = 0
    loss = -delta.copy()
    loss[loss > 0] = 0
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df['VolAvg20'] = df['Volume'].rolling(window=20).mean()
    return df


def passes_criteria(df, rsi_min, rsi_max, vol_mul):
    if df.empty or 'RSI' not in df or 'Volume' not in df or 'VolAvg20' not in df:
        return False
    latest_rsi = df['RSI'].iloc[-1]
    latest_vol = df['Volume'].iloc[-1]
    latest_volavg = df['VolAvg20'].iloc[-1]
    if pd.isna(latest_rsi) or latest_rsi < rsi_min or latest_rsi > rsi_max:
        return False
    if pd.isna(latest_volavg) or latest_vol < latest_volavg * vol_mul:
        return False
    return True


def fetch_bulk_data(tickers, period, interval):
    result = {}
    try:
        data = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            group_by='ticker',
            auto_adjust=True,
            progress=False
        )
        if isinstance(data.columns, pd.MultiIndex):
            for t in tickers:
                if t in data.columns.levels[0]:
                    df = data[t].copy()
                    if not df.empty:
                        result[t] = df
        else:
            if len(tickers) == 1 and not data.empty:
                result[tickers[0]] = data.copy()
    except Exception as e:
        st.error(f"Bulk download error: {e}")
    return result

# Main render


def render_scanner_tab():
    st.header("📋 Stock Scanner: All US & SE Stocks")

    # Scanner settings
    period = st.selectbox("Historical period", ["3mo", "6mo", "1y"], index=0)
    interval = st.selectbox("Data interval", ["1d", "1h"], index=0)
    rsi_min = st.number_input("RSI ≥", 0, 100, 30)
    rsi_max = st.number_input("RSI ≤", 0, 100, 70)
    vol_mul = st.number_input("Volume ≥ X×20d avg", 0.1, 10.0, 1.5, 0.1)

    custom = st.text_input("Custom tickers (comma-separated)")
    custom_list = [t.strip() for t in custom.split(',')] if custom else []

    if st.button("🔍 Run Scanner on All Stocks"):
        tickers = get_all_tickers() + custom_list
        tickers = list(set(tickers))
        st.subheader(f"⏳ Scanning {len(tickers)} stocks...")
        progress = st.progress(0)
        rows = []
        total = len(tickers)
        for i, t in enumerate(tickers):
            try:
                data = yf.download(
                    t, period=period, interval=interval, progress=False)
                if len(data) < 50:
                    continue
                df = calculate_indicators(data)
                if passes_criteria(df, rsi_min, rsi_max, vol_mul):
                    rows.append({
                        'Ticker': t,
                        'Price': round(df['Close'].iloc[-1], 2),
                        'RSI(14)': round(df['RSI'].iloc[-1], 2),
                        'Vol Ratio': round(df['Volume'].iloc[-1]/df['VolAvg20'].iloc[-1], 2)
                    })
            except Exception:
                continue
            if i % 50 == 0:
                progress.progress(i/total)
        progress.empty()
        if rows:
            df_res = pd.DataFrame(rows).sort_values('RSI(14)')
            st.dataframe(df_res, use_container_width=True)
        else:
            st.warning("No stocks matched the simplified criteria.")
