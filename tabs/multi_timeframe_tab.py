# tabs/multi_timeframe_tab.py
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

# Define configuration for different timeframes
TIMEFRAME_CONFIG = {
    "long": {
        "period": "5y",
        "interval": "1wk",
        "title": "Long-Term Weekly Chart",
        "indicators": {"sma": [50, 200], "ema": [50, 200], "rsi": 14}
    },
    "medium": {
        "period": "1y",
        "interval": "1d",
        "title": "Medium-Term Daily Chart",
        "indicators": {"sma": [20, 50, 200], "ema": [20, 50, 200], "rsi": 14}
    },
    "short": {
        "period": "1mo",
        "interval": "60m",
        "title": "Short-Term Hourly Chart",
        "indicators": {"sma": [20, 50], "ema": [9, 20], "rsi": 14}
    }
}


def render_multi_timeframe_tab():
    """Render the multi-timeframe technical analysis tab"""
    st.header("Multi-Timeframe Technical Analysis")

    # Initialize settings in session state if not present
    if 'mta_settings' not in st.session_state:
        st.session_state.mta_settings = {
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "ma_short": 20,
            "ma_medium": 50,
            "ma_long": 200,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9
        }

    # Access shared objects from session state
    watchlist_manager = st.session_state.get('watchlist_manager')

    col1, col2 = st.columns([1, 3])

    with col1:
        st.subheader("Select Stock")

        # Get unique tickers from all watchlists
        unique_tickers = []
        if watchlist_manager:
            all_watchlists = watchlist_manager.get_all_watchlists()
            for watchlist in all_watchlists:
                unique_tickers.extend(watchlist.get("stocks", []))
            unique_tickers = sorted(set(unique_tickers))

        # Allow manual ticker input
        manual_ticker = st.text_input(
            "Enter ticker symbol:", placeholder="e.g., AAPL").strip().upper()

        # Or select from watchlist
        watchlist_ticker = st.selectbox(
            "Or select from watchlist:", [""] + unique_tickers)

        # Use either manual input or selection
        ticker = manual_ticker or watchlist_ticker

        # Settings expander
        with st.expander("Analysis Settings"):
            s = st.session_state.mta_settings
            s["rsi_oversold"] = st.slider(
                "RSI Oversold Threshold", 10, 40, s["rsi_oversold"])
            s["rsi_overbought"] = st.slider(
                "RSI Overbought Threshold", 60, 90, s["rsi_overbought"])
            s["ma_short"] = st.slider("Short MA Period", 5, 50, s["ma_short"])
            s["ma_medium"] = st.slider(
                "Medium MA Period", 20, 100, s["ma_medium"])
            s["ma_long"] = st.slider("Long MA Period", 100, 300, s["ma_long"])

            # Reset button
            if st.button("Reset to Defaults"):
                st.session_state.mta_settings = {
                    "rsi_oversold": 30,
                    "rsi_overbought": 70,
                    "ma_short": 20,
                    "ma_medium": 50,
                    "ma_long": 200,
                    "macd_fast": 12,
                    "macd_slow": 26,
                    "macd_signal": 9
                }
                st.rerun()

        # Analyze button
        analyze_btn = st.button("Analyze", disabled=not ticker)

    with col2:
        if not ticker:
            st.info("Please enter or select a ticker symbol to analyze.")
            return

        if not analyze_btn and 'current_mta_ticker' not in st.session_state:
            st.info("Click 'Analyze' to perform multi-timeframe analysis.")
            return

        # Store the current ticker and analysis data in session state
        if 'mta_data' not in st.session_state:
            st.session_state.mta_data = {}

        # Clear data if we're analyzing a new ticker
        if analyze_btn or st.session_state.get('current_mta_ticker') != ticker:
            st.session_state.mta_data = {}
            st.session_state.current_mta_ticker = ticker

        # Create tabs for different timeframes
        long_tab, medium_tab, short_tab = st.tabs(
            ["Long-Term", "Medium-Term", "Short-Term"])

        # Long-term analysis tab
        with long_tab:
            st.subheader(TIMEFRAME_CONFIG["long"]["title"])

            # Check if we already have data for this timeframe
            if "long" not in st.session_state.mta_data:
                with st.spinner(f"Loading long-term data for {ticker}..."):
                    try:
                        df_long = fetch_and_analyze_data(ticker, "long")
                        st.session_state.mta_data["long"] = df_long
                    except Exception as e:
                        st.error(f"Error loading long-term data: {str(e)}")
                        st.session_state.mta_data["long"] = None

            # Display analysis for this timeframe
            if st.session_state.mta_data.get("long") is not None:
                display_long_term_analysis(
                    ticker, st.session_state.mta_data["long"])
            else:
                st.warning(f"Could not load long-term data for {ticker}.")

        # Medium-term analysis tab
        with medium_tab:
            st.subheader(TIMEFRAME_CONFIG["medium"]["title"])

            if "medium" not in st.session_state.mta_data:
                with st.spinner(f"Loading medium-term data for {ticker}..."):
                    try:
                        df_medium = fetch_and_analyze_data(ticker, "medium")
                        st.session_state.mta_data["medium"] = df_medium
                    except Exception as e:
                        st.error(f"Error loading medium-term data: {str(e)}")
                        st.session_state.mta_data["medium"] = None

            if st.session_state.mta_data.get("medium") is not None:
                display_medium_term_analysis(
                    ticker, st.session_state.mta_data["medium"])
            else:
                st.warning(f"Could not load medium-term data for {ticker}.")

        # Short-term analysis tab
        with short_tab:
            st.subheader(TIMEFRAME_CONFIG["short"]["title"])

            if "short" not in st.session_state.mta_data:
                with st.spinner(f"Loading short-term data for {ticker}..."):
                    try:
                        df_short = fetch_and_analyze_data(ticker, "short")
                        st.session_state.mta_data["short"] = df_short
                    except Exception as e:
                        st.error(f"Error loading short-term data: {str(e)}")
                        st.session_state.mta_data["short"] = None

            if st.session_state.mta_data.get("short") is not None:
                display_short_term_analysis(
                    ticker, st.session_state.mta_data["short"])
            else:
                st.warning(f"Could not load short-term data for {ticker}.")


@st.cache_data(ttl=3600)
def fetch_and_analyze_data(ticker, timeframe):
    """Fetch and analyze data for the given ticker and timeframe"""
    config = TIMEFRAME_CONFIG[timeframe]

    # Add a small delay to avoid rate limiting when fetching multiple timeframes
    time.sleep(0.5)

    # Fetch data from Yahoo Finance
    try:
        df = yf.download(
            ticker,
            period=config["period"],
            interval=config["interval"],
            progress=False
        )

        if df.empty:
            return None

        # Calculate technical indicators
        # SMA
        for period in config["indicators"]["sma"]:
            df[f'SMA{period}'] = df['Close'].rolling(window=period).mean()

        # EMA
        for period in config["indicators"]["ema"]:
            df[f'EMA{period}'] = df['Close'].ewm(
                span=period, adjust=False).mean()

        # RSI
        rsi_period = config["indicators"]["rsi"]
        delta = df['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=rsi_period).mean()
        avg_loss = loss.rolling(window=rsi_period).mean()

        # Handle first rsi_period observations
        for i in range(1, rsi_period):
            avg_gain.iloc[i] = gain.iloc[1:i+1].mean()
            avg_loss.iloc[i] = loss.iloc[1:i+1].mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        df['RSI'] = 100 - (100 / (1 + rs))

        # MACD
        macd_fast = st.session_state.mta_settings["macd_fast"]
        macd_slow = st.session_state.mta_settings["macd_slow"]
        macd_signal = st.session_state.mta_settings["macd_signal"]

        df['MACD'] = df['Close'].ewm(span=macd_fast, adjust=False).mean() - \
            df['Close'].ewm(span=macd_slow, adjust=False).mean()
        df['MACD_Signal'] = df['MACD'].ewm(
            span=macd_signal, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']

        # Identify buy/sell signals
        # Simple example: EMA crossover
        df['signal'] = 0
        df.loc[(df[f'EMA{config["indicators"]["ema"][0]}'] > df[f'EMA{config["indicators"]["ema"][1]}']) &
               (df[f'EMA{config["indicators"]["ema"][0]}'].shift(1) <=
                df[f'EMA{config["indicators"]["ema"][1]}'].shift(1)),
               'signal'] = 1  # Buy signal

        df.loc[(df[f'EMA{config["indicators"]["ema"][0]}'] < df[f'EMA{config["indicators"]["ema"][1]}']) &
               (df[f'EMA{config["indicators"]["ema"][0]}'].shift(1) >=
                df[f'EMA{config["indicators"]["ema"][1]}'].shift(1)),
               'signal'] = -1  # Sell signal

        return df
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
        return None


def plot_chart(df, ticker, timeframe):
    """Create an interactive Plotly chart for the given dataframe"""
    config = TIMEFRAME_CONFIG[timeframe]

    # Create figure
    fig = go.Figure()

    # Add candlestick trace
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name=ticker,
        increasing_line_color='green',
        decreasing_line_color='red'
    ))

    # Add SMA lines
    for period in config["indicators"]["sma"]:
        if f'SMA{period}' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df[f'SMA{period}'],
                mode='lines',
                name=f'SMA {period}',
                line=dict(width=1, dash='dash')
            ))

    # Add EMA lines
    for period in config["indicators"]["ema"]:
        if f'EMA{period}' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df[f'EMA{period}'],
                mode='lines',
                name=f'EMA {period}',
                line=dict(width=1)
            ))

    # Add buy signals
    buy_signals = df[df['signal'] == 1]
    if not buy_signals.empty:
        fig.add_trace(go.Scatter(
            x=buy_signals.index,
            y=buy_signals['Close'],
            mode='markers',
            name='Buy Signal',
            marker=dict(
                symbol='triangle-up',
                size=15,
                color='green',
                line=dict(width=1, color='darkgreen')
            )
        ))

    # Add sell signals
    sell_signals = df[df['signal'] == -1]
    if not sell_signals.empty:
        fig.add_trace(go.Scatter(
            x=sell_signals.index,
            y=sell_signals['Close'],
            mode='markers',
            name='Sell Signal',
            marker=dict(
                symbol='triangle-down',
                size=15,
                color='red',
                line=dict(width=1, color='darkred')
            )
        ))

    # Update layout
    fig.update_layout(
        title=f"{config['title']} - {ticker}",
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        height=600,
        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=50, t=80, b=50),
        hovermode="x unified"
    )

    # Add custom buttons for common time ranges
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=3, label="3M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(step="all")
            ])
        )
    )

    return fig


def plot_indicator_chart(df, indicator, ticker, timeframe):
    """Create a separate chart for indicators like RSI"""
    config = TIMEFRAME_CONFIG[timeframe]

    fig = go.Figure()

    if indicator == 'RSI':
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['RSI'],
            mode='lines',
            name='RSI',
            line=dict(color='purple', width=1)
        ))

        # Add overbought and oversold lines
        fig.add_shape(
            type="line",
            x0=df.index[0],
            y0=st.session_state.mta_settings["rsi_oversold"],
            x1=df.index[-1],
            y1=st.session_state.mta_settings["rsi_oversold"],
            line=dict(color="green", width=1, dash="dash"),
        )

        fig.add_shape(
            type="line",
            x0=df.index[0],
            y0=st.session_state.mta_settings["rsi_overbought"],
            x1=df.index[-1],
            y1=st.session_state.mta_settings["rsi_overbought"],
            line=dict(color="red", width=1, dash="dash"),
        )

        # Add middle line
        fig.add_shape(
            type="line",
            x0=df.index[0],
            y0=50,
            x1=df.index[-1],
            y1=50,
            line=dict(color="black", width=1, dash="dash"),
        )

        fig.update_layout(
            title=f"RSI ({config['indicators']['rsi']}) - {ticker}",
            xaxis_title="Date",
            yaxis_title="RSI",
            yaxis=dict(range=[0, 100]),
            height=300,
            margin=dict(l=50, r=50, t=80, b=50),
            hovermode="x unified"
        )

    elif indicator == 'MACD':
        # MACD line
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['MACD'],
            mode='lines',
            name='MACD',
            line=dict(color='blue', width=1)
        ))

        # Signal line
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['MACD_Signal'],
            mode='lines',
            name='Signal',
            line=dict(color='red', width=1)
        ))

        # Histogram
        colors = ['green' if val >=
                  0 else 'red' for val in df['MACD_Histogram']]
        fig.add_trace(go.Bar(
            x=df.index,
            y=df['MACD_Histogram'],
            name='Histogram',
            marker_color=colors
        ))

        fig.update_layout(
            title=f"MACD - {ticker}",
            xaxis_title="Date",
            yaxis_title="MACD",
            height=300,
            margin=dict(l=50, r=50, t=80, b=50),
            hovermode="x unified"
        )

    return fig


def display_long_term_analysis(ticker, df):
    """Display long-term analysis charts and metrics"""
    if df is None or df.empty:
        st.warning(f"No long-term data available for {ticker}")
        return

    # Display main price chart
    st.plotly_chart(plot_chart(df, ticker, "long"), use_container_width=True)

    # Display indicator charts
    indicator_tabs = st.tabs(["RSI", "MACD"])

    with indicator_tabs[0]:
        st.plotly_chart(plot_indicator_chart(
            df, "RSI", ticker, "long"), use_container_width=True)

    with indicator_tabs[1]:
        st.plotly_chart(plot_indicator_chart(
            df, "MACD", ticker, "long"), use_container_width=True)

    # Display key metrics and analysis
    st.subheader("Long-Term Trend Analysis")

    # Get latest data point
    latest = df.iloc[-1]

    # Determine trend based on EMA relationship
    trend = "Neutral"
    color = "gray"

    if "EMA50" in df.columns and "EMA200" in df.columns:
        if latest["EMA50"] > latest["EMA200"]:
            trend = "Bullish"
            color = "green"
        elif latest["EMA50"] < latest["EMA200"]:
            trend = "Bearish"
            color = "red"

    # Display trend information
    st.markdown(
        f"**Primary Trend:** <span style='color:{color};font-weight:bold'>{trend}</span>", unsafe_allow_html=True)

    # Calculate 52-week metrics
    if len(df) >= 52:
        high_52w = df['High'].rolling(window=52).max().iloc[-1]
        low_52w = df['Low'].rolling(window=52).min().iloc[-1]
        current = latest['Close']

        st.write(f"**52-Week Range:** {low_52w:.2f} - {high_52w:.2f}")
        if high_52w > low_52w:  # Avoid division by zero
            position = (current - low_52w) / (high_52w - low_52w) * 100
            st.write(f"**Position in Range:** {position:.1f}%")

    # Display recent signals
    recent_buy_signals = df[df['signal'] ==
                            1].iloc[-12:] if len(df) > 0 else pd.DataFrame()
    recent_sell_signals = df[df['signal'] == -
                             1].iloc[-12:] if len(df) > 0 else pd.DataFrame()

    if not recent_buy_signals.empty:
        st.write("**Recent Buy Signals:**")
        for idx, _ in recent_buy_signals.iterrows():
            st.write(f"- {idx.strftime('%Y-%m-%d')}")

    if not recent_sell_signals.empty:
        st.write("**Recent Sell Signals:**")
        for idx, _ in recent_sell_signals.iterrows():
            st.write(f"- {idx.strftime('%Y-%m-%d')}")

    # Offer interpretation
    st.subheader("Long-Term Outlook")

    # Simplified interpretation based on trend and recent signals
    if trend == "Bullish":
        st.success("The long-term trend appears positive with price above major moving averages. Consider buying on pullbacks or holding existing positions.")
    elif trend == "Bearish":
        st.error("The long-term trend appears negative with price below major moving averages. Consider reducing exposure or looking for shorting opportunities.")
    else:
        st.info("The long-term trend is currently neutral. Wait for a clearer signal before making major position changes.")


def display_medium_term_analysis(ticker, df):
    """Display medium-term analysis charts and metrics"""
    if df is None or df.empty:
        st.warning(f"No medium-term data available for {ticker}")
        return

    # Display main price chart
    st.plotly_chart(plot_chart(df, ticker, "medium"), use_container_width=True)

    # Display indicator charts
    indicator_tabs = st.tabs(["RSI", "MACD"])

    with indicator_tabs[0]:
        st.plotly_chart(plot_indicator_chart(
            df, "RSI", ticker, "medium"), use_container_width=True)

    with indicator_tabs[1]:
        st.plotly_chart(plot_indicator_chart(
            df, "MACD", ticker, "medium"), use_container_width=True)

    # Display key metrics
    st.subheader("Medium-Term Technical Indicators")

    if df.empty:
        st.warning("Insufficient data for medium-term analysis")
        return

    latest = df.iloc[-1]

    # Create metrics display
    col1, col2, col3 = st.columns(3)

    with col1:
        # RSI status
        if 'RSI' in df.columns:
            rsi_value = latest['RSI']
            if pd.notna(rsi_value):
                rsi_status = "Overbought" if rsi_value > st.session_state.mta_settings["rsi_overbought"] else \
                             "Oversold" if rsi_value < st.session_state.mta_settings[
                                 "rsi_oversold"] else "Neutral"

                # Get delta from previous day
                delta = latest['RSI'] - \
                    df.iloc[-2]['RSI'] if len(df) > 1 else None
                delta_text = f"{delta:.1f}" if delta is not None else None

                st.metric("RSI", f"{rsi_value:.1f}", delta_text)
                st.write(f"Status: **{rsi_status}**")

    with col2:
        # MACD status
        if all(x in df.columns for x in ['MACD', 'MACD_Signal']):
            macd = latest['MACD']
            signal = latest['MACD_Signal']
            histogram = latest['MACD_Histogram']

            if pd.notna(macd) and pd.notna(signal):
                macd_status = "Bullish" if macd > signal else "Bearish"

                # Get delta from previous day
                delta = histogram - \
                    df['MACD_Histogram'].iloc[-2] if len(df) > 1 else None
                delta_text = f"{delta:.3f}" if delta is not None else None

                st.metric("MACD Histogram", f"{histogram:.3f}", delta_text)
                st.write(f"Signal: **{macd_status}**")

    with col3:
        # Moving Average relationship
        if 'EMA50' in df.columns and 'EMA200' in df.columns:
            ema50 = latest['EMA50']
            ema200 = latest['EMA200']

            if pd.notna(ema50) and pd.notna(ema200):
                ma_status = "Above 200 EMA" if latest['Close'] > ema200 else "Below 200 EMA"
                ma_relationship = "Golden Cross" if ema50 > ema200 and df['EMA50'].iloc[-20:].min() < df['EMA200'].iloc[-20:].max() else \
                    "Death Cross" if ema50 < ema200 and df['EMA50'].iloc[-20:].max() > df['EMA200'].iloc[-20:].min() else \
                    "Bullish" if ema50 > ema200 else "Bearish"

                # Percentage from EMA200
                pct_from_200 = (latest['Close'] / ema200 - 1) * 100

                st.metric("Price vs 200 EMA", f"{pct_from_200:.2f}%")
                st.write(f"Trend: **{ma_relationship}**")

    # Recent signals section
    st.subheader("Recent Signals")

    recent_days = min(20, len(df))
    recent_df = df.iloc[-recent_days:]

    buy_signals = recent_df[recent_df['signal'] == 1]
    sell_signals = recent_df[recent_df['signal'] == -1]

    if not buy_signals.empty:
        st.success(
            f"EMA Crossover Buy Signal detected on {buy_signals.index[-1].strftime('%Y-%m-%d')}")

    if not sell_signals.empty:
        st.error(
            f"EMA Crossover Sell Signal detected on {sell_signals.index[-1].strftime('%Y-%m-%d')}")

    if buy_signals.empty and sell_signals.empty:
        st.info("No EMA crossover signals detected in the last 20 trading days.")

    # Combine indicators for an overall recommendation
    st.subheader("Medium-Term Recommendation")

    # Simple scoring system
    score = 0
    reasons = []

    # EMA relationship
    if 'EMA50' in df.columns and 'EMA200' in df.columns:
        if latest['EMA50'] > latest['EMA200']:
            score += 2
            reasons.append("EMA50 > EMA200 (Bullish)")
        else:
            score -= 2
            reasons.append("EMA50 < EMA200 (Bearish)")

    # RSI
    if 'RSI' in df.columns:
        if latest['RSI'] > 60:
            score += 1
            reasons.append(f"RSI at {latest['RSI']:.1f} (Bullish momentum)")
        elif latest['RSI'] < 40:
            score -= 1
            reasons.append(f"RSI at {latest['RSI']:.1f} (Bearish momentum)")

    # MACD
    if 'MACD' in df.columns and 'MACD_Signal' in df.columns:
        if latest['MACD'] > latest['MACD_Signal']:
            score += 1
            reasons.append("MACD > Signal (Bullish)")
        else:
            score -= 1
            reasons.append("MACD < Signal (Bearish)")

    # Recent signals carry extra weight
    if not buy_signals.empty and (datetime.now() - buy_signals.index[-1]).days < 10:
        score += 2
        reasons.append("Recent Buy Signal")

    if not sell_signals.empty and (datetime.now() - sell_signals.index[-1]).days < 10:
        score -= 2
        reasons.append("Recent Sell Signal")

    # Price vs 200 EMA
    if 'EMA200' in df.columns:
        if latest['Close'] > latest['EMA200']:
            score += 1
            reasons.append("Price > 200 EMA (Bullish)")
        else:
            score -= 1
            reasons.append("Price < 200 EMA (Bearish)")

    # Overall recommendation
    st.write("**Factors considered:**", ", ".join(reasons))

    if score >= 3:
        st.success(
            "**Strong Bullish:** Multiple indicators suggest a positive medium-term trend. Consider buying or adding to positions.")
    elif score >= 1:
        st.info("**Moderately Bullish:** Some positive signals present. Look for additional confirmation before entering long positions.")
    elif score <= -3:
        st.error("**Strong Bearish:** Multiple indicators suggest a negative medium-term trend. Consider reducing exposure or establishing short positions.")
    elif score <= -1:
        st.warning(
            "**Moderately Bearish:** Some negative signals present. Be cautious with new long positions.")
    else:
        st.info("**Neutral:** Mixed or conflicting signals. Wait for clearer direction before taking significant action.")


def display_short_term_analysis(ticker, df):
    """Display short-term analysis charts and metrics"""
    if df is None or df.empty:
        st.warning(f"No short-term data available for {ticker}")
        return

    # Display main price chart
    st.plotly_chart(plot_chart(df, ticker, "short"), use_container_width=True)

    # Display indicator charts
    indicator_tabs = st.tabs(["RSI", "MACD"])

    with indicator_tabs[0]:
        st.plotly_chart(plot_indicator_chart(
            df, "RSI", ticker, "short"), use_container_width=True)

    with indicator_tabs[1]:
        st.plotly_chart(plot_indicator_chart(
            df, "MACD", ticker, "short"), use_container_width=True)

    # Display key metrics for the short-term view
    st.subheader("Short-Term Trading Signals")

    if df.empty:
        st.warning("Insufficient data for short-term analysis")
        return

    # Get latest and recent data
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None

    # Create metrics display
    col1, col2, col3 = st.columns(3)

    with col1:
        # Latest price change
        if prev is not None:
            price_change = latest['Close'] - prev['Close']
            price_change_pct = (price_change / prev['Close']) * 100
            st.metric(
                "Last Price",
                f"{latest['Close']:.2f}",
                f"{price_change:.2f} ({price_change_pct:.2f}%)"
            )
        else:
            st.metric("Last Price", f"{latest['Close']:.2f}")

    with col2:
        # RSI status for short-term
        if 'RSI' in df.columns:
            rsi_value = latest['RSI']
            if pd.notna(rsi_value):
                rsi_status = "Overbought" if rsi_value > st.session_state.mta_settings["rsi_overbought"] else \
                             "Oversold" if rsi_value < st.session_state.mta_settings[
                                 "rsi_oversold"] else "Neutral"

                # Get delta from previous value
                delta = latest['RSI'] - \
                    prev['RSI'] if prev is not None else None
                delta_text = f"{delta:.1f}" if delta is not None else None

                st.metric("RSI", f"{rsi_value:.1f}", delta_text)
                st.write(f"Status: **{rsi_status}**")

    with col3:
        # Volume analysis
        if 'Volume' in df.columns:
            # Calculate average volume over last 5 periods
            avg_vol = df['Volume'].iloc[-6:-
                                        1].mean() if len(df) > 5 else df['Volume'].mean()
            vol_change = (latest['Volume'] / avg_vol -
                          1) * 100 if avg_vol > 0 else 0

            vol_status = "Above Average" if vol_change > 20 else \
                         "Below Average" if vol_change < -20 else "Normal"

            st.metric(
                "Volume", f"{int(latest['Volume']):,}", f"{vol_change:.1f}%")
            st.write(f"Level: **{vol_status}**")

    # Intraday patterns and signals
    st.subheader("Intraday Patterns")

    # Check for most recent signals
    # Last trading day (assuming hourly data)
    recent_periods = min(12, len(df))
    recent_df = df.iloc[-recent_periods:]

    buy_signals = recent_df[recent_df['signal'] == 1]
    sell_signals = recent_df[recent_df['signal'] == -1]

    # Price action patterns
    patterns = []

    # Check for intraday trends
    if len(recent_df) > 2:
        # Simple trend detection
        if recent_df['Close'].iloc[-1] > recent_df['Close'].iloc[0] and \
           recent_df['Close'].pct_change().mean() > 0:
            patterns.append(
                "Rising prices during the session (bullish intraday trend)")
        elif recent_df['Close'].iloc[-1] < recent_df['Close'].iloc[0] and \
                recent_df['Close'].pct_change().mean() < 0:
            patterns.append(
                "Falling prices during the session (bearish intraday trend)")

        # Check for climactic volume
        if recent_df['Volume'].iloc[-1] > recent_df['Volume'].iloc[:-1].mean() * 1.5:
            if recent_df['Close'].iloc[-1] > recent_df['Close'].iloc[-2]:
                patterns.append(
                    "High volume on rising prices (possible climactic buying)")
            else:
                patterns.append(
                    "High volume on falling prices (possible climactic selling)")

    # Display patterns
    if patterns:
        for pattern in patterns:
            st.info(f"**Pattern detected:** {pattern}")
    else:
        st.info("No significant intraday patterns detected")

    # Display recent signals
    if not buy_signals.empty:
        latest_buy = buy_signals.index[-1]
        st.success(
            f"EMA Crossover Buy Signal detected at {latest_buy.strftime('%Y-%m-%d %H:%M')}")

    if not sell_signals.empty:
        latest_sell = sell_signals.index[-1]
        st.error(
            f"EMA Crossover Sell Signal detected at {latest_sell.strftime('%Y-%m-%d %H:%M')}")

    if buy_signals.empty and sell_signals.empty:
        st.info("No EMA crossover signals detected in the recent session")

    # Short-term recommendation
    st.subheader("Short-Term Recommendation")

    # RSI conditions
    if 'RSI' in df.columns and pd.notna(latest['RSI']):
        if latest['RSI'] < st.session_state.mta_settings["rsi_oversold"]:
            st.success(
                f"**RSI Oversold ({latest['RSI']:.1f}):** The stock is potentially oversold in the short term, suggesting a possible bounce. Look for confirmation before entering long positions.")
        elif latest['RSI'] > st.session_state.mta_settings["rsi_overbought"]:
            st.warning(
                f"**RSI Overbought ({latest['RSI']:.1f}):** The stock is potentially overbought in the short term, suggesting caution for new long positions. Consider taking profits or tightening stop losses.")
        # Within last 4 hours
        elif not buy_signals.empty and (datetime.now() - buy_signals.index[-1]).seconds < 60*60*4:
            st.success(
                "**Recent Buy Signal:** A recent bullish crossover suggests potential short-term upside. Consider entering with tight stop losses.")
        # Within last 4 hours
        elif not sell_signals.empty and (datetime.now() - sell_signals.index[-1]).seconds < 60*60*4:
            st.warning("**Recent Sell Signal:** A recent bearish crossover suggests potential short-term weakness. Consider closing long positions or establishing short positions with appropriate risk management.")
        elif 'EMA9' in df.columns and 'EMA20' in df.columns:
            if latest['EMA9'] > latest['EMA20']:
                st.info("**Short-Term Bullish:** Fast EMA is above slow EMA, suggesting short-term momentum is bullish. Look for pullbacks as potential entry points.")
            else:
                st.info("**Short-Term Bearish:** Fast EMA is below slow EMA, suggesting short-term momentum is bearish. Wait for confirmation of trend change before entering long positions.")
        else:
            st.info("**Neutral:** No clear short-term signals. Consider waiting for more definitive price action before taking positions.")
