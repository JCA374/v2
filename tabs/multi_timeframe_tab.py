# tabs/multi_timeframe_tab.py
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pandas_ta as ta  # More efficient indicator library

# Define configuration for different timeframes
TIMEFRAME_CONFIG = {
    "long": {
        "period": "5y",
        "interval": "1wk",
        "title": "Long-Term Weekly Chart",
        "indicators": {
            "sma": [50, 200],
            "ema": [50, 200],
            "rsi": 14,
            "macd": {"fast": 12, "slow": 26, "signal": 9}
        },
        "signals": {
            "buy": [
                {"type": "ma_cross", "fast": "SMA50",
                    "slow": "SMA200", "direction": "above"},
                {"type": "rsi", "value": 50, "direction": "above", "weight": 0.5}
            ],
            "sell": [
                {"type": "ma_cross", "fast": "SMA50",
                    "slow": "SMA200", "direction": "below"},
                {"type": "rsi", "value": 50, "direction": "below", "weight": 0.5}
            ],
            "min_score": 1.0  # Minimum score to generate a signal
        }
    },
    "medium": {
        "period": "1y",
        "interval": "1d",
        "title": "Medium-Term Daily Chart",
        "indicators": {
            "sma": [20, 50, 200],
            "ema": [20, 50, 200],
            "rsi": 14,
            "macd": {"fast": 12, "slow": 26, "signal": 9},
            "bbands": {"length": 20, "std": 2}
        },
        "signals": {
            "buy": [
                {"type": "ma_cross", "fast": "EMA50",
                    "slow": "EMA200", "direction": "above"},
                {"type": "macd_cross", "direction": "above"},
                {"type": "rsi", "value": 30, "direction": "cross_above"}
            ],
            "sell": [
                {"type": "ma_cross", "fast": "EMA50",
                    "slow": "EMA200", "direction": "below"},
                {"type": "macd_cross", "direction": "below"},
                {"type": "rsi", "value": 70, "direction": "cross_below"}
            ],
            "min_score": 2.0  # Need at least 2 conditions for a signal
        }
    },
    "short": {
        "period": "1mo",
        "interval": "60m",
        "title": "Short-Term Hourly Chart",
        "indicators": {
            "sma": [20, 50],
            "ema": [9, 20],
            "rsi": 14,
            "bbands": {"length": 20, "std": 2}
        },
        "signals": {
            "buy": [
                {"type": "bbands_bounce", "direction": "lower"},
                {"type": "rsi", "value": 30, "direction": "cross_above"},
                {"type": "ma_cross", "fast": "EMA9",
                    "slow": "EMA20", "direction": "above"}
            ],
            "sell": [
                {"type": "bbands_bounce", "direction": "upper"},
                {"type": "rsi", "value": 70, "direction": "cross_below"},
                {"type": "ma_cross", "fast": "EMA9",
                    "slow": "EMA20", "direction": "below"}
            ],
            # Need at least 2 conditions (with weight) for a signal
            "min_score": 1.5
        }
    }
}

# Default settings - can be overridden by user
DEFAULT_SETTINGS = {
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "ma_short": 20,
    "ma_medium": 50,
    "ma_long": 200,
    "bb_length": 20,
    "bb_std": 2,
}


def render_multi_timeframe_tab():
    """Render the multi-timeframe technical analysis tab with ESG integration"""
    # Access shared objects from session state
    strategy = st.session_state.strategy
    watchlist_manager = st.session_state.watchlist_manager

    st.header("Multi-Timeframe Technical Analysis with ESG Integration")

    # Initialize settings in session state if not present
    if 'mta_settings' not in st.session_state:
        st.session_state.mta_settings = DEFAULT_SETTINGS.copy()

    # Layout with sidebar for settings
    col1, col2 = st.columns([1, 3])

    with col1:
        # Stock selection section
        st.subheader("Select Stock")

        # Get all stocks from all watchlists
        all_watchlists = watchlist_manager.get_all_watchlists()
        all_stocks = []

        for watchlist in all_watchlists:
            all_stocks.extend([(ticker, watchlist["name"])
                              for ticker in watchlist["stocks"]])

        # Deduplicate tickers
        unique_tickers = list(set([t[0] for t in all_stocks]))

        # Option to manually enter a ticker
        manual_ticker = st.text_input(
            "Enter ticker symbol:", placeholder="e.g., AAPL")

        # Select from watchlist tickers
        if all_stocks:
            selected_ticker = st.selectbox(
                "Or select from watchlist:",
                options=[""] + unique_tickers
            )
        else:
            selected_ticker = ""
            st.info(
                "Your watchlists are empty. Please add stocks to your watchlist first.")

        # Use either manual input or selection
        ticker = manual_ticker if manual_ticker else selected_ticker

        # Settings expander
        with st.expander("Analysis Settings", expanded=False):
            settings_tab1, settings_tab2 = st.tabs(
                ["Indicators", "Signal Rules"])

            with settings_tab1:
                st.session_state.mta_settings["rsi_oversold"] = st.slider(
                    "RSI Oversold Threshold", 10, 40,
                    st.session_state.mta_settings["rsi_oversold"])

                st.session_state.mta_settings["rsi_overbought"] = st.slider(
                    "RSI Overbought Threshold", 60, 90,
                    st.session_state.mta_settings["rsi_overbought"])

                st.session_state.mta_settings["ma_short"] = st.slider(
                    "Short MA Period", 5, 50,
                    st.session_state.mta_settings["ma_short"])

                st.session_state.mta_settings["ma_medium"] = st.slider(
                    "Medium MA Period", 20, 100,
                    st.session_state.mta_settings["ma_medium"])

                st.session_state.mta_settings["ma_long"] = st.slider(
                    "Long MA Period", 100, 300,
                    st.session_state.mta_settings["ma_long"])

            with settings_tab2:
                st.session_state.mta_settings["bb_length"] = st.slider(
                    "Bollinger Band Length", 10, 50,
                    st.session_state.mta_settings["bb_length"])

                st.session_state.mta_settings["bb_std"] = st.slider(
                    "Bollinger Band StdDev", 1.0, 3.0,
                    st.session_state.mta_settings["bb_std"], 0.1)

                # Reset to defaults button
                if st.button("Reset to Defaults"):
                    st.session_state.mta_settings = DEFAULT_SETTINGS.copy()
                    st.rerun()

        # Button to analyze
        analyze_clicked = st.button("Analyze", key="analyze_multi_timeframe")

        # Fetch and display ESG data if we have a ticker
        if ticker:
            with st.spinner("Fetching ESG data..."):
                esg_data = fetch_esg_data(ticker)

                st.subheader("ESG Information")
                if esg_data is not None:
                    display_esg_data(esg_data)
                else:
                    st.info("No ESG data available for this stock")
                    # Display placeholder with explanation
                    st.markdown("""
                    ℹ️ **ESG data unavailable**
                    
                    This could be because:
                    - The company is not covered by Yahoo Finance ESG ratings
                    - The company is too small or not publicly traded
                    - There was an error fetching the data
                    
                    Consider researching the company's sustainability practices directly.
                    """)

    with col2:
        if ticker and analyze_clicked:
            # Create 3 tabs for different timeframes
            tab_long, tab_med, tab_short = st.tabs(
                ["Long-Term", "Medium-Term", "Short-Term"])

            with tab_long:
                st.subheader("Long-Term Analysis (Weekly)")
                with st.spinner("Loading long-term data..."):
                    df_long = get_analyzed_data(ticker, "long")
                    if df_long is not None and not df_long.empty:
                        long_term_analysis(df_long, ticker)
                    else:
                        st.error(f"Could not load long-term data for {ticker}")

            with tab_med:
                st.subheader("Medium-Term Analysis (Daily)")
                with st.spinner("Loading medium-term data..."):
                    df_med = get_analyzed_data(ticker, "medium")
                    if df_med is not None and not df_med.empty:
                        medium_term_analysis(df_med, ticker)
                    else:
                        st.error(
                            f"Could not load medium-term data for {ticker}")

            with tab_short:
                st.subheader("Short-Term Analysis (Hourly)")
                with st.spinner("Loading short-term data..."):
                    df_short = get_analyzed_data(ticker, "short")
                    if df_short is not None and not df_short.empty:
                        short_term_analysis(df_short, ticker)
                    else:
                        st.error(
                            f"Could not load short-term data for {ticker}")
        elif ticker:
            st.info("Click 'Analyze' to see multi-timeframe analysis")
        else:
            st.info("Please select or enter a ticker symbol to begin analysis")


@st.cache_data(ttl=3600)
def get_analyzed_data(symbol, timeframe_key):
    """Load, process, and analyze data for a specific timeframe"""
    config = TIMEFRAME_CONFIG[timeframe_key]

    try:
        # Download data
        df = yf.download(
            symbol,
            period=config["period"],
            interval=config["interval"],
            progress=False
        )

        if df.empty:
            return None

        # Calculate indicators based on configuration
        # SMA indicators
        for period in config["indicators"].get("sma", []):
            col_name = f'SMA{period}'
            df[col_name] = ta.sma(df['Close'], length=period)

        # EMA indicators
        for period in config["indicators"].get("ema", []):
            col_name = f'EMA{period}'
            df[col_name] = ta.ema(df['Close'], length=period)

        # RSI
        if "rsi" in config["indicators"]:
            period = config["indicators"]["rsi"]
            df['RSI'] = ta.rsi(df['Close'], length=period)

        # MACD
        if "macd" in config["indicators"]:
            macd_config = config["indicators"]["macd"]
            macd_result = ta.macd(
                df['Close'],
                fast=macd_config["fast"],
                slow=macd_config["slow"],
                signal=macd_config["signal"]
            )
            df['MACD'] = macd_result['MACD_12_26_9']
            df['MACD_Signal'] = macd_result['MACDs_12_26_9']
            df['MACD_Hist'] = macd_result['MACDh_12_26_9']

        # Bollinger Bands
        if "bbands" in config["indicators"]:
            bb_config = config["indicators"]["bbands"]
            bbands = ta.bbands(
                df['Close'],
                length=bb_config["length"],
                std=bb_config["std"]
            )
            df['BB_Upper'] = bbands['BBU_20_2.0']
            df['BB_Middle'] = bbands['BBM_20_2.0']
            df['BB_Lower'] = bbands['BBL_20_2.0']

        # OBV (On-Balance Volume)
        df['OBV'] = ta.obv(df['Close'], df['Volume'])

        # Compute signals
        buy_signals, sell_signals = compute_signals(df, config["signals"])

        # Add signal markers to dataframe for easier access
        df['buy_signal'] = False
        df['sell_signal'] = False

        for date, _ in buy_signals:
            if date in df.index:
                df.loc[date, 'buy_signal'] = True

        for date, _ in sell_signals:
            if date in df.index:
                df.loc[date, 'sell_signal'] = True

        # Store signals separately for plotting
        df.attrs['buy_signals'] = buy_signals
        df.attrs['sell_signals'] = sell_signals

        return df

    except Exception as e:
        st.error(f"Error processing data: {str(e)}")
        return None


def compute_signals(df, signal_config):
    """Calculate buy/sell signals based on configured rules"""
    buy_signals = []
    sell_signals = []

    if len(df) < 2:
        return buy_signals, sell_signals

    # Process each row (except first) to check for signals
    for i in range(1, len(df)):
        buy_score = 0
        sell_score = 0

        # Evaluate buy rules
        for rule in signal_config["buy"]:
            rule_type = rule["type"]
            weight = rule.get("weight", 1.0)

            if rule_type == "ma_cross":
                # Moving average crossover
                fast_col = rule["fast"]
                slow_col = rule["slow"]
                direction = rule["direction"]

                if (fast_col in df.columns and slow_col in df.columns and
                    pd.notna(df[fast_col].iloc[i]) and pd.notna(df[slow_col].iloc[i]) and
                        pd.notna(df[fast_col].iloc[i-1]) and pd.notna(df[slow_col].iloc[i-1])):

                    if direction == "above" and (df[fast_col].iloc[i] > df[slow_col].iloc[i] and
                                                 df[fast_col].iloc[i-1] <= df[slow_col].iloc[i-1]):
                        buy_score += weight
                    elif direction == "below" and (df[fast_col].iloc[i] < df[slow_col].iloc[i] and
                                                   df[fast_col].iloc[i-1] >= df[slow_col].iloc[i-1]):
                        sell_score += weight

            elif rule_type == "macd_cross":
                # MACD line crosses signal line
                if ('MACD' in df.columns and 'MACD_Signal' in df.columns and
                    pd.notna(df['MACD'].iloc[i]) and pd.notna(df['MACD_Signal'].iloc[i]) and
                        pd.notna(df['MACD'].iloc[i-1]) and pd.notna(df['MACD_Signal'].iloc[i-1])):

                    direction = rule["direction"]
                    if direction == "above" and (df['MACD'].iloc[i] > df['MACD_Signal'].iloc[i] and
                                                 df['MACD'].iloc[i-1] <= df['MACD_Signal'].iloc[i-1]):
                        buy_score += weight
                    elif direction == "below" and (df['MACD'].iloc[i] < df['MACD_Signal'].iloc[i] and
                                                   df['MACD'].iloc[i-1] >= df['MACD_Signal'].iloc[i-1]):
                        sell_score += weight

            elif rule_type == "rsi":
                # RSI conditions
                if 'RSI' in df.columns and pd.notna(df['RSI'].iloc[i]) and pd.notna(df['RSI'].iloc[i-1]):
                    value = rule["value"]
                    direction = rule["direction"]

                    if direction == "above" and df['RSI'].iloc[i] > value:
                        buy_score += weight
                    elif direction == "below" and df['RSI'].iloc[i] < value:
                        sell_score += weight
                    elif direction == "cross_above" and (df['RSI'].iloc[i] > value and df['RSI'].iloc[i-1] <= value):
                        buy_score += weight
                    elif direction == "cross_below" and (df['RSI'].iloc[i] < value and df['RSI'].iloc[i-1] >= value):
                        sell_score += weight

            elif rule_type == "bbands_bounce":
                # Bollinger Bands bounce
                if all(col in df.columns for col in ['BB_Upper', 'BB_Middle', 'BB_Lower']):
                    direction = rule["direction"]

                    if direction == "lower" and (df['Low'].iloc[i] <= df['BB_Lower'].iloc[i] * 1.01 and
                                                 df['Close'].iloc[i] > df['Open'].iloc[i]):
                        buy_score += weight
                    elif direction == "upper" and (df['High'].iloc[i] >= df['BB_Upper'].iloc[i] * 0.99 and
                                                   df['Close'].iloc[i] < df['Open'].iloc[i]):
                        sell_score += weight

        # Check if we have enough score for a signal
        if buy_score >= signal_config["min_score"]:
            buy_signals.append((df.index[i], df['Close'].iloc[i]))

        if sell_score >= signal_config["min_score"]:
            sell_signals.append((df.index[i], df['Close'].iloc[i]))

    return buy_signals, sell_signals


def plot_chart(df, title, ticker):
    """Create an interactive Plotly chart with signals"""
    fig = go.Figure()

    # Get signals from dataframe attributes
    buy_signals = df.attrs.get('buy_signals', [])
    sell_signals = df.attrs.get('sell_signals', [])

    # Add candlestick trace
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price'
    ))

    # Add Moving Averages
    ma_columns = [col for col in df.columns if col.startswith(
        'SMA') or col.startswith('EMA')]

    for col in ma_columns:
        if col in df.columns and not df[col].isna().all():
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df[col],
                mode='lines',
                name=col
            ))

    # Add Bollinger Bands
    if all(col in df.columns for col in ['BB_Upper', 'BB_Middle', 'BB_Lower']):
        fig.add_trace(go.Scatter(
            x=df.index, y=df['BB_Upper'],
            mode='lines',
            line=dict(color='rgba(173, 204, 255, 0.7)'),
            name='BB Upper'
        ))
        fig.add_trace(go.Scatter(
            x=df.index, y=df['BB_Lower'],
            mode='lines',
            line=dict(color='rgba(173, 204, 255, 0.7)'),
            fill='tonexty',
            fillcolor='rgba(173, 204, 255, 0.2)',
            name='BB Lower'
        ))

    # Add buy signals as green up triangles
    if buy_signals:
        buy_x, buy_y = zip(*buy_signals) if buy_signals else ([], [])
        fig.add_trace(go.Scatter(
            x=buy_x, y=buy_y,
            mode='markers',
            marker=dict(symbol='triangle-up', size=12, color='green'),
            name='Buy Signal'
        ))

    # Add sell signals as red down triangles
    if sell_signals:
        sell_x, sell_y = zip(*sell_signals) if sell_signals else ([], [])
        fig.add_trace(go.Scatter(
            x=sell_x, y=sell_y,
            mode='markers',
            marker=dict(symbol='triangle-down', size=12, color='red'),
            name='Sell Signal'
        ))

    # Update layout
    fig.update_layout(
        title=f"{title} - {ticker}",
        xaxis_title="Date",
        yaxis_title="Price",
        height=600,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, xanchor="center", x=0.5)
    )

    return fig


def long_term_analysis(df, ticker):
    """Display long-term analysis (weekly data)"""
    # Plot chart
    fig = plot_chart(df, TIMEFRAME_CONFIG["long"]["title"], ticker)
    st.plotly_chart(fig, use_container_width=True)

    # Analysis text
    st.subheader("Long-Term Analysis")

    # Determine long-term trend
    trend = "Neutral"
    if 'SMA50' in df.columns and 'SMA200' in df.columns and not df['SMA50'].isna().all() and not df['SMA200'].isna().all():
        last_sma50 = df['SMA50'].iloc[-1]
        last_sma200 = df['SMA200'].iloc[-1]

        if pd.notna(last_sma50) and pd.notna(last_sma200):
            if last_sma50 > last_sma200:
                trend = "Bullish"
            elif last_sma50 < last_sma200:
                trend = "Bearish"

    # Display trend
    trend_color = "green" if trend == "Bullish" else "red" if trend == "Bearish" else "gray"
    st.markdown(
        f"**Primary Trend:** <span style='color:{trend_color}'>{trend}</span>", unsafe_allow_html=True)

    # Display price vs. 52-week high/low
    if len(df) >= 52:
        high_52w = df['High'].rolling(window=52).max().iloc[-1]
        low_52w = df['Low'].rolling(window=52).min().iloc[-1]
        last_close = df['Close'].iloc[-1]

        pct_from_high = (last_close - high_52w) / high_52w * 100
        pct_from_low = (last_close - low_52w) / low_52w * 100

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("52-Week High",
                      f"{high_52w:.2f}", f"{pct_from_high:.1f}%")

        with col2:
            st.metric("52-Week Low", f"{low_52w:.2f}", f"{pct_from_low:.1f}%")

        with col3:
            st.metric("Current Price", f"{last_close:.2f}")

    # Display recent signals
    recent_buy = [date for date, _ in df.attrs.get(
        'buy_signals', []) if date > df.index[-30]] if len(df) > 30 else []
    recent_sell = [date for date, _ in df.attrs.get(
        'sell_signals', []) if date > df.index[-30]] if len(df) > 30 else []

    if recent_buy:
        st.write(
            f"**Recent Buy Signals:** {', '.join([date.strftime('%Y-%m-%d') for date in recent_buy])}")
    if recent_sell:
        st.write(
            f"**Recent Sell Signals:** {', '.join([date.strftime('%Y-%m-%d') for date in recent_sell])}")

    # Trading recommendation based on long-term trend
    st.subheader("Long-Term Recommendation")
    if trend == "Bullish":
        st.markdown(
            "💡 **Long-Term Trend is Bullish** - Consider buying on medium-term and short-term pullbacks.")
    elif trend == "Bearish":
        st.markdown(
            "💡 **Long-Term Trend is Bearish** - Consider selling rallies or avoiding long positions until trend reverses.")
    else:
        st.markdown(
            "💡 **Long-Term Trend is Neutral** - Wait for clearer direction or trade shorter timeframes with caution.")


def medium_term_analysis(df, ticker):
    """Display medium-term analysis (daily data)"""
    # Plot chart
    fig = plot_chart(df, TIMEFRAME_CONFIG["medium"]["title"], ticker)
    st.plotly_chart(fig, use_container_width=True)

    # Display key metrics
    st.subheader("Medium-Term Analysis")

    col1, col2, col3 = st.columns(3)

    # Check if we have enough data for RSI and MACD
    with col1:
        if 'RSI' in df.columns and not df['RSI'].isna().all():
            last_rsi = df['RSI'].iloc[-1]

            # RSI interpretation
            rsi_status = "Neutral"
            if last_rsi > 70:
                rsi_status = "Overbought"
            elif last_rsi < 30:
                rsi_status = "Oversold"

            st.metric("RSI (14)", f"{last_rsi:.1f}", rsi_status)

    # MACD status
    with col2:
        if all(col in df.columns for col in ['MACD', 'MACD_Signal']) and not df['MACD'].isna().all():
            last_macd = df['MACD'].iloc[-1]
            last_signal = df['MACD_Signal'].iloc[-1]
            macd_diff = last_macd - last_signal

            macd_status = "Neutral"
            if last_macd > last_signal:
                macd_status = "Bullish"
            elif last_macd < last_signal:
                macd_status = "Bearish"

            st.metric("MACD", f"{last_macd:.3f}",
                      f"{macd_diff:.3f}", delta_color="normal")

    # Moving Average Status
    with col3:
        last_close = df['Close'].iloc[-1]
        if 'EMA50' in df.columns and not df['EMA50'].isna().all():
            last_ema = df['EMA50'].iloc[-1]
            ema_diff_pct = (last_close - last_ema) / last_ema * 100

            status = "Above EMA50" if last_close > last_ema else "Below EMA50"
            st.metric("EMA50", f"{last_ema:.2f}",
                      f"{ema_diff_pct:.1f}%", delta_color="normal")

    # Latest signals
    if df.attrs.get('buy_signals') and df.attrs['buy_signals'][-1][0] > df.index[-20]:
        buy_date = df.attrs['buy_signals'][-1][0].strftime('%Y-%m-%d')
        st.success(f"🔔 **Latest Buy Signal:** {buy_date}")

    if df.attrs.get('sell_signals') and df.attrs['sell_signals'][-1][0] > df.index[-20]:
        sell_date = df.attrs['sell_signals'][-1][0].strftime('%Y-%m-%d')
        st.error(f"🔔 **Latest Sell Signal:** {sell_date}")

    # Medium-term recommendation
    st.subheader("Medium-Term Recommendation")

    # Determine recommendation based on multiple factors
    bullish_factors = 0
    bearish_factors = 0

    # Check MA trend
    if 'EMA50' in df.columns and 'EMA200' in df.columns and not df['EMA50'].isna().all() and not df['EMA200'].isna().all():
        if df['EMA50'].iloc[-1] > df['EMA200'].iloc[-1]:
            bullish_factors += 1
        else:
            bearish_factors += 1

    # Check RSI
    if 'RSI' in df.columns and not df['RSI'].isna().all():
        if df['RSI'].iloc[-1] > 50:
            bullish_factors += 1
        else:
            bearish_factors += 1

    # Check MACD
    if all(col in df.columns for col in ['MACD', 'MACD_Signal']) and not df['MACD'].isna().all():
        if df['MACD'].iloc[-1] > df['MACD_Signal'].iloc[-1]:
            bullish_factors += 1
        else:
            bearish_factors += 1

    # Recent buy/sell signal
    if df.attrs.get('buy_signals') and df.attrs['buy_signals'][-1][0] > df.index[-10]:
        bullish_factors += 1
    if df.attrs.get('sell_signals') and df.attrs['sell_signals'][-1][0] > df.index[-10]:
        bearish_factors += 1

    # Generate recommendation
    if bullish_factors > bearish_factors + 1:
        st.markdown(
            "💡 **Medium-Term Outlook is Bullish** - Consider buying or holding positions.")
    elif bearish_factors > bullish_factors + 1:
        st.markdown(
            "💡 **Medium-Term Outlook is Bearish** - Consider reducing exposure or short positions.")
    else:
        st.markdown(
            "💡 **Medium-Term Outlook is Mixed** - Look for confirmation on short-term chart before making decisions.")


def short_term_analysis(df, ticker):
    """Display short-term analysis (hourly data)"""
    # Plot chart
    fig = plot_chart(df, TIMEFRAME_CONFIG["short"]["title"], ticker)
    st.plotly_chart(fig, use_container_width=True)

    # Display key metrics for short-term trading
    st.subheader("Short-Term Analysis")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Recent price action
        last_close = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else None

        if prev_close is not None:
            pct_change = (last_close - prev_close) / prev_close * 100
            st.metric("Last Price", f"{last_close:.2f}", f"{pct_change:.2f}%")

    with col2:
        # RSI
        if 'RSI' in df.columns and not df['RSI'].isna().all():
            short_rsi = df['RSI'].iloc[-1]

            rsi_status = "Neutral"
            if short_rsi > 70:
                rsi_status = "Overbought"
            elif short_rsi < 30:
                rsi_status = "Oversold"

            st.metric("RSI (14)", f"{short_rsi:.1f}", rsi_status)

    with col3:
        # Bollinger Bands position
        if all(col in df.columns for col in ['BB_Upper', 'BB_Middle', 'BB_Lower']) and not df['BB_Upper'].isna().all():
            bb_upper = df['BB_Upper'].iloc[-1]
            bb_lower = df['BB_Lower'].iloc[-1]
            bb_width = (bb_upper - bb_lower) / df['BB_Middle'].iloc[-1]

            bb_position = (last_close - bb_lower) / (bb_upper -
                                                     bb_lower) if (bb_upper - bb_lower) > 0 else 0.5

            # Interpret BB position
            bb_status = "Mid"
            if bb_position > 0.8:
                bb_status = "Upper Band"
            elif bb_position < 0.2:
                bb_status = "Lower Band"

            st.metric("BB Position", f"{bb_position:.2f}", bb_status)

    # Check for divergences
    if 'RSI' in df.columns and len(df) > 20 and not df['RSI'].isna().all():
        # Check for bearish divergence
        if (df['Close'].iloc[-1] > df['Close'].iloc[-10] and
                df['RSI'].iloc[-1] < df['RSI'].iloc[-10]):
            st.warning(
                "⚠️ **Possible Bearish Divergence Detected** - Price making higher highs while RSI makes lower highs")

        # Check for bullish divergence
        if (df['Close'].iloc[-1] < df['Close'].iloc[-10] and
                df['RSI'].iloc[-1] > df['RSI'].iloc[-10]):
            st.success(
                "✅ **Possible Bullish Divergence Detected** - Price making lower lows while RSI makes higher lows")

    # Latest signals
    signal_found = False
    # Last day
    if df.attrs.get('buy_signals') and df.attrs['buy_signals'][-1][0] > df.index[-24]:
        buy_time = df.attrs['buy_signals'][-1][0].strftime('%Y-%m-%d %H:%M')
        st.success(f"🔔 **Latest Short-Term Buy Signal:** {buy_time}")
        signal_found = True

    # Last day
    if df.attrs.get('sell_signals') and df.attrs['sell_signals'][-1][0] > df.index[-24]:
        sell_time = df.attrs['sell_signals'][-1][0].strftime('%Y-%m-%d %H:%M')
        st.error(f"🔔 **Latest Short-Term Sell Signal:** {sell_time}")
        signal_found = True

    if not signal_found:
        st.info("No recent signals in the last 24 hours")

    # Support and resistance levels
    if len(df) > 20:
        st.subheader("Support & Resistance")

        # Simple support/resistance based on recent highs/lows
        recent_df = df.iloc[-20:]
        support_level = recent_df['Low'].min()
        resistance_level = recent_df['High'].max()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Support", f"{support_level:.2f}")
        with col2:
            st.metric("Resistance", f"{resistance_level:.2f}")

    # Short-term recommendation
    st.subheader("Short-Term Recommendation")

    # Generate short-term recommendation based on indicators
    if 'RSI' in df.columns and all(col in df.columns for col in ['BB_Upper', 'BB_Lower']):
        rsi = df['RSI'].iloc[-1]
        last_close = df['Close'].iloc[-1]

        if 'BB_Upper' in df.columns and 'BB_Lower' in df.columns:
            bb_upper = df['BB_Upper'].iloc[-1]
            bb_lower = df['BB_Lower'].iloc[-1]
            bb_position = (last_close - bb_lower) / (bb_upper -
                                                     bb_lower) if (bb_upper - bb_lower) > 0 else 0.5

            if rsi < 30 and bb_position < 0.2:
                st.markdown(
                    "💡 **Short-Term Oversold Condition** - Consider buying for short-term trade if medium/long-term trend permits.")
            elif rsi > 70 and bb_position > 0.8:
                st.markdown(
                    "💡 **Short-Term Overbought Condition** - Consider taking profits or short position if medium/long-term trend permits.")
            # Signal in last 12 hours
            elif df.attrs.get('buy_signals') and df.attrs['buy_signals'][-1][0] > df.index[-12]:
                st.markdown(
                    "💡 **Recent Buy Signal** - Consider entering long position with tight stop loss.")
            # Signal in last 12 hours
            elif df.attrs.get('sell_signals') and df.attrs['sell_signals'][-1][0] > df.index[-12]:
                st.markdown(
                    "💡 **Recent Sell Signal** - Consider exiting long positions or entering short position.")
            else:
                st.markdown(
                    "💡 **No Clear Short-Term Signal** - Wait for better setup or refer to medium-term trend for direction.")


@st.cache_data(ttl=3600)
def fetch_esg_data(ticker):
    """Fetch ESG data for a ticker from Yahoo Finance with better error handling"""
    try:
        stock = yf.Ticker(ticker)
        esg_df = stock.sustainability

        if esg_df is None or esg_df.empty:
            # Try alternative sources or formats
            info = stock.info

            # Some stocks have ESG data in the info dictionary
            alt_esg_data = {}
            esg_keys = [
                'esgScore', 'totalEsg', 'environmentScore', 'socialScore', 'governanceScore',
                'esgPerformance', 'environmentPerformance', 'socialPerformance', 'governancePerformance'
            ]

            for key in esg_keys:
                if key in info:
                    if key == 'esgScore' or key == 'totalEsg':
                        alt_esg_data['total_esg_score'] = info[key]
                    elif key == 'environmentScore':
                        alt_esg_data['environment_score'] = info[key]
                    elif key == 'socialScore':
                        alt_esg_data['social_score'] = info[key]
                    elif key == 'governanceScore':
                        alt_esg_data['governance_score'] = info[key]

            if alt_esg_data:
                return alt_esg_data
            return None

        # Yahoo Finance returns sustainability data with different formats/names
        # Convert to a standardized dictionary format
        esg_data = {}

        # Check for environment score with multiple possible keys
        env_score_keys = ['environmentScore', 'Environment Risk Score',
                          'environmentriskscores', 'Environmental Risk Score']
        for key in env_score_keys:
            if key in esg_df.index:
                esg_data['environment_score'] = esg_df.loc[key].iloc[0]
                break

        # Check for social score
        social_score_keys = ['socialScore', 'Social Risk Score',
                             'socialriskscores', 'Social Risk Score']
        for key in social_score_keys:
            if key in esg_df.index:
                esg_data['social_score'] = esg_df.loc[key].iloc[0]
                break

        # Check for governance score
        gov_score_keys = ['governanceScore', 'Governance Risk Score',
                          'governanceriskscores', 'Governance Risk Score']
        for key in gov_score_keys:
            if key in esg_df.index:
                esg_data['governance_score'] = esg_df.loc[key].iloc[0]
                break

        # Check for total ESG score
        total_score_keys = ['totalEsg', 'ESG Score',
                            'Total ESG Risk score', 'ESG Risk Score', 'esgScore']
        for key in total_score_keys:
            if key in esg_df.index:
                esg_data['total_esg_score'] = esg_df.loc[key].iloc[0]
                break

        # If we have any data, return it
        if esg_data:
            return esg_data
        return None

    except Exception as e:
        st.warning(f"Could not fetch ESG data: {str(e)}")
        return None


def display_esg_data(esg_data):
    """Display ESG data in a user-friendly format"""
    # Define color scales for ESG scores
    # For ESG scores, lower is typically better
    def get_color(score, inverse=False):
        if score is None:
            return "gray"

        if inverse:  # For cases where higher is better
            if score < 30:
                return "red"
            elif score < 70:
                return "orange"
            else:
                return "green"
        else:  # Normal case - lower is better
            if score < 10:
                return "green"
            elif score < 20:
                return "lightgreen"
            elif score < 30:
                return "yellow"
            elif score < 40:
                return "orange"
            else:
                return "red"

    # Function to get rating text
    def get_rating(score):
        if score is None:
            return "Unknown"

        if score < 10:
            return "Negligible Risk"
        elif score < 20:
            return "Low Risk"
        elif score < 30:
            return "Medium Risk"
        elif score < 40:
            return "High Risk"
        else:
            return "Severe Risk"

    # Create columns for the scores
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        env_score = esg_data.get('environment_score')
        env_color = get_color(env_score)
        env_rating = get_rating(env_score)

        if env_score is not None:
            st.metric("Environmental", f"{env_score:.1f}")
            st.markdown(
                f"<span style='color:{env_color}'>{env_rating}</span>", unsafe_allow_html=True)
        else:
            st.metric("Environmental", "N/A")

    with col2:
        social_score = esg_data.get('social_score')
        social_color = get_color(social_score)
        social_rating = get_rating(social_score)

        if social_score is not None:
            st.metric("Social", f"{social_score:.1f}")
            st.markdown(
                f"<span style='color:{social_color}'>{social_rating}</span>", unsafe_allow_html=True)
        else:
            st.metric("Social", "N/A")

    with col3:
        gov_score = esg_data.get('governance_score')
        gov_color = get_color(gov_score)
        gov_rating = get_rating(gov_score)

        if gov_score is not None:
            st.metric("Governance", f"{gov_score:.1f}")
            st.markdown(
                f"<span style='color:{gov_color}'>{gov_rating}</span>", unsafe_allow_html=True)
        else:
            st.metric("Governance", "N/A")

    with col4:
        total_score = esg_data.get('total_esg_score')
        total_color = get_color(total_score)
        total_rating = get_rating(total_score)

        if total_score is not None:
            st.metric("Total ESG", f"{total_score:.1f}")
            st.markdown(
                f"<span style='color:{total_color}'>{total_rating}</span>", unsafe_allow_html=True)
        else:
            st.metric("Total ESG", "N/A")

    # Display ESG risk explanation
    with st.expander("Understanding ESG Scores"):
        st.markdown("""
        ### ESG Risk Ratings
        
        ESG (Environmental, Social, Governance) scores measure a company's exposure to long-term risks related to environmental, social, and governance factors. Lower scores typically indicate lower risk.
        
        **Interpretation:**
        - **0-10**: Negligible Risk - Excellent sustainability practices
        - **10-20**: Low Risk - Good sustainability practices
        - **20-30**: Medium Risk - Average sustainability practices
        - **30-40**: High Risk - Poor sustainability practices
        - **>40**: Severe Risk - Very poor sustainability practices
        
        ESG data can help identify companies with sustainable business practices, which may indicate better long-term investment potential and reduced regulatory or reputational risks.
        """)
