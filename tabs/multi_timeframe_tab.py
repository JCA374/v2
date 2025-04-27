# tabs/multi_timeframe_tab.py
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Define configuration for different timeframes
TIMEFRAME_CONFIG = {
    "long": {
        "period": "5y",
        "interval": "1wk",
        "title": "Long-Term Weekly Chart",
        "indicators": {
            "sma": [50, 200],
            "ema": [50, 200],
            "rsi_period": 14
        }
    },
    "medium": {
        "period": "1y",
        "interval": "1d",
        "title": "Medium-Term Daily Chart",
        "indicators": {
            "sma": [20, 50, 200],
            "ema": [20, 50, 200],
            "rsi_period": 14
        }
    },
    "short": {
        "period": "1mo",
        "interval": "60m",
        "title": "Short-Term Hourly Chart",
        "indicators": {
            "sma": [20, 50],
            "ema": [9, 20],
            "rsi_period": 14
        }
    }
}

# Default settings - can be overridden by user
DEFAULT_SETTINGS = {
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "ma_short": 20,
    "ma_medium": 50,
    "ma_long": 200
}


def render_multi_timeframe_tab():
    """Render the multi-timeframe technical analysis tab"""
    # Access shared objects from session state
    strategy = st.session_state.strategy
    watchlist_manager = st.session_state.watchlist_manager

    st.header("Multi-Timeframe Technical Analysis")

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

            # Reset to defaults button
            if st.button("Reset to Defaults"):
                st.session_state.mta_settings = DEFAULT_SETTINGS.copy()
                st.rerun()

        # Button to analyze
        analyze_clicked = st.button("Analyze", key="analyze_multi_timeframe")

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
            df[col_name] = df['Close'].rolling(window=period).mean()

        # EMA indicators
        for period in config["indicators"].get("ema", []):
            col_name = f'EMA{period}'
            df[col_name] = df['Close'].ewm(span=period, adjust=False).mean()

        # RSI calculation
        rsi_period = config["indicators"].get("rsi_period", 14)
        df['RSI'] = calculate_rsi(df['Close'], rsi_period)

        # MACD calculation
        df['MACD'] = df['Close'].ewm(span=12, adjust=False).mean(
        ) - df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        # Calculate buy/sell signals
        df['buy_signal'] = False
        df['sell_signal'] = False

        # Simple MA crossover strategy for signals
        if len(df) > 50:  # Make sure we have enough data
            # Get fast and slow MAs
            fast_ma = 'EMA50' if 'EMA50' in df.columns else 'SMA50' if 'SMA50' in df.columns else None
            slow_ma = 'EMA200' if 'EMA200' in df.columns else 'SMA200' if 'SMA200' in df.columns else None

            if fast_ma and slow_ma:
                # Identify crossovers (avoiding the first few rows with NaNs)
                for i in range(1, len(df)):
                    # Only process if both current and previous values are valid
                    if (pd.notna(df[fast_ma].iloc[i-1]) and pd.notna(df[slow_ma].iloc[i-1]) and
                            pd.notna(df[fast_ma].iloc[i]) and pd.notna(df[slow_ma].iloc[i])):

                        # Buy signal: Fast MA crosses above slow MA
                        if (df[fast_ma].iloc[i-1] <= df[slow_ma].iloc[i-1] and
                                df[fast_ma].iloc[i] > df[slow_ma].iloc[i]):
                            df.loc[df.index[i], 'buy_signal'] = True

                        # Sell signal: Fast MA crosses below slow MA
                        elif (df[fast_ma].iloc[i-1] >= df[slow_ma].iloc[i-1] and
                              df[fast_ma].iloc[i] < df[slow_ma].iloc[i]):
                            df.loc[df.index[i], 'sell_signal'] = True

        # Store buy/sell signals for plotting
        buy_signals = []
        sell_signals = []

        for idx, row in df.iterrows():
            if row['buy_signal']:
                buy_signals.append((idx, row['Close']))
            if row['sell_signal']:
                sell_signals.append((idx, row['Close']))

        df.attrs['buy_signals'] = buy_signals
        df.attrs['sell_signals'] = sell_signals

        return df

    except Exception as e:
        st.error(f"Error processing data: {str(e)}")
        return None


def calculate_rsi(price_series, period=14):
    """Calculate Relative Strength Index (RSI)"""
    # Make a copy of the price series to avoid modifying the original
    prices = price_series.copy()

    # Calculate price changes
    delta = prices.diff()

    # Separate gains (up) and losses (down)
    gain = delta.copy()
    loss = delta.copy()

    gain[gain < 0] = 0
    loss[loss > 0] = 0
    loss = -loss  # Make losses positive values

    # Calculate average gain and loss over the period
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    # Calculate RS
    rs = pd.Series(np.zeros(len(avg_gain)), index=avg_gain.index)
    # Handle division by zero
    for i in range(len(avg_gain)):
        if avg_loss.iloc[i] > 0:
            rs.iloc[i] = avg_gain.iloc[i] / avg_loss.iloc[i]

    # Calculate RSI
    rsi = 100 - (100 / (1 + rs))

    return rsi


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
        # Moving average relationship
        if 'EMA9' in df.columns and 'EMA20' in df.columns and not df['EMA9'].isna().all() and not df['EMA20'].isna().all():
            ema9 = df['EMA9'].iloc[-1]
            ema20 = df['EMA20'].iloc[-1]

            ma_status = "EMA9 > EMA20" if ema9 > ema20 else "EMA9 < EMA20"
            ma_diff = ((ema9 / ema20) - 1) * 100

            st.metric("EMA Relationship", ma_status, f"{ma_diff:.2f}%")

    # Check for potential reversals
    st.subheader("Short-Term Signals")

    # Check for oversold conditions
    if 'RSI' in df.columns and not df['RSI'].isna().all():
        if df['RSI'].iloc[-1] < 30:
            st.info("⚠️ **Oversold Condition** - Potential for short-term bounce")
        elif df['RSI'].iloc[-1] > 70:
            st.info("⚠️ **Overbought Condition** - Potential for short-term pullback")

    # Latest signals
    signal_found = False

    # Last day (24 data points for hourly data)
    if df.attrs.get('buy_signals') and len(df.attrs['buy_signals']) > 0:
        # Find the most recent signal
        most_recent_buy = df.attrs['buy_signals'][-1]
        if most_recent_buy[0] > df.index[-24]:
            buy_time = most_recent_buy[0].strftime('%Y-%m-%d %H:%M')
            st.success(f"🔔 **Latest Short-Term Buy Signal:** {buy_time}")
            signal_found = True

    # Last day
    if df.attrs.get('sell_signals') and len(df.attrs['sell_signals']) > 0:
        # Find the most recent signal
        most_recent_sell = df.attrs['sell_signals'][-1]
        if most_recent_sell[0] > df.index[-24]:
            sell_time = most_recent_sell[0].strftime('%Y-%m-%d %H:%M')
            st.error(f"🔔 **Latest Short-Term Sell Signal:** {sell_time}")
            signal_found = True

    if not signal_found:
        st.info("No recent signals in the last 24 hours")

    # Short-term recommendation
    st.subheader("Short-Term Recommendation")

    # Generate short-term recommendation based on indicators
    if 'RSI' in df.columns:
        rsi = df['RSI'].iloc[-1]

        if rsi < 30:
            st.markdown(
                "💡 **Short-Term Oversold Condition** - Consider buying for short-term trade if medium/long-term trend permits.")
        elif rsi > 70:
            st.markdown(
                "💡 **Short-Term Overbought Condition** - Consider taking profits or short position if medium/long-term trend permits.")
        # Signal in last 12 hours
        elif df.attrs.get('buy_signals') and len(df.attrs['buy_signals']) > 0 and df.attrs['buy_signals'][-1][0] > df.index[-12]:
            st.markdown(
                "💡 **Recent Buy Signal** - Consider entering long position with tight stop loss.")
        # Signal in last 12 hours
        elif df.attrs.get('sell_signals') and len(df.attrs['sell_signals']) > 0 and df.attrs['sell_signals'][-1][0] > df.index[-12]:
            st.markdown(
                "💡 **Recent Sell Signal** - Consider exiting long positions or entering short position.")
        else:
            st.markdown(
                "💡 **No Clear Short-Term Signal** - Wait for better setup or refer to medium-term trend for direction.")
