# strategy.py (updated with Yahoo Finance service integration)
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
import time
import json
import os
from datetime import datetime, timedelta
import logging

# Import the Yahoo Finance service instead of yfinance directly
from services.yahoo_finance_service import (
    fetch_ticker_info,
    fetch_history,
    fetch_company_earnings,
    extract_fundamental_data
)


class ValueMomentumStrategy:
    def __init__(self):
        """Initialize the Value Momentum Strategy"""
        # Configuration parameters
        self.today = datetime.now()
        self.start_date = self.today - timedelta(days=365*3)  # 3 years of data

        # Strategy parameters
        self.ma_short = 4   # 4-week MA (approx. 1 month)
        self.ma_long = 40   # 40-week MA (approx. 200 days)
        self.rsi_period = 14
        self.rsi_threshold = 50  # RSI above this is bullish
        self.near_high_threshold = 0.98  # Within 2% of 52-week high
        self.pe_max = 30    # Maximum P/E ratio considered reasonable

        # Set up logging
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger('ValueMomentumStrategy')

    def _fetch_info(self, ticker):
        """Fetches ticker info using the Yahoo Finance service."""
        return fetch_ticker_info(ticker)

    def _fetch_history(self, stock, period="1y", interval="1wk"):
        """Fetches history using the Yahoo Finance service."""
        return fetch_history(stock, period=period, interval=interval)

    # Improved RSI calculation from the new code
    def calculate_rsi(self, prices, window=14):
        """Calculate Relative Strength Index without using pandas_ta"""
        # Handle edge case with insufficient data
        if len(prices) <= window:
            return np.array([np.nan] * len(prices))

        # Calculate price changes
        deltas = np.diff(prices)
        seed = deltas[:window+1]

        # Initial values
        up = seed[seed >= 0].sum() / window
        down = -seed[seed < 0].sum() / window

        # Avoid division by zero
        if down == 0:
            return np.ones_like(prices) * 100

        rs = up / down
        rsi = np.zeros_like(prices)
        rsi[:window+1] = 100. - (100. / (1. + rs))

        # Calculate RSI for the rest of the price data
        for i in range(window+1, len(prices)):
            delta = deltas[i-1]  # Adjust index

            if delta > 0:
                upval = delta
                downval = 0
            else:
                upval = 0
                downval = -delta

            # Use EMA for calculating averages
            up = (up * (window - 1) + upval) / window
            down = (down * (window - 1) + downval) / window

            rs = up / down if down != 0 else 999  # Avoid division by zero
            rsi[i] = 100. - (100. / (1. + rs))

        return rsi

    def _calculate_higher_lows(self, data, lookback=10):
        """Helper function to identify higher lows"""
        if 'Low' not in data.columns or data.empty:
            return pd.Series(np.zeros(len(data)))

        highs_lows = pd.DataFrame()
        highs_lows['min'] = data['Low'].rolling(
            window=lookback, center=True).min()

        # Simple heuristic to identify higher lows
        higher_lows = np.zeros(len(data))

        for i in range(lookback*2, len(data)):
            min_values = highs_lows['min'].iloc[i-lookback:i].dropna()
            if len(min_values) >= 2:  # Ensure we have enough data
                diffs = min_values.diff().dropna()
                if len(diffs) > 0 and (diffs > 0).all():
                    higher_lows[i] = 1

        return pd.Series(higher_lows, index=data.index)

    def analyze_stock(self, ticker):
        """
        Analyze a single stock according to Value & Momentum strategy.
        
        Parameters:
        - ticker: Stock ticker symbol
        
        Returns:
        - Dictionary with analysis results
        """
        result = {"ticker": ticker, "error": None, "error_message": None}
        try:
            # Get stock data using our centralized service
            stock, info = self._fetch_info(ticker)

            # Handle missing name
            try:
                name = info.get('shortName', info.get('longName', ticker))
            except:
                name = ticker

            # Get historical data (weekly) using our centralized service
            hist = self._fetch_history(stock, period="1y", interval="1wk")

            if hist is None or hist.empty:
                return {
                    "ticker": ticker,
                    "error": "No data available",
                    "error_message": f"Fel vid analys: ingen historik för {ticker}"
                }

            # Calculate current price
            price = hist['Close'].iloc[-1]

            # Calculate technical indicators
            tech_analysis = self._calculate_technical_indicators(hist)

            # Calculate fundamental indicators
            fund_analysis = self._calculate_fundamental_indicators(stock, info)

            # Calculate signal
            tech_score = self._calculate_tech_score(tech_analysis)
            fund_check = fund_analysis['fundamental_check']

            # Determine overall signal
            buy_signal = tech_score >= 70 and fund_check
            sell_signal = tech_score < 40 or not tech_analysis['above_ma40']

            # Process historical data to add indicators
            processed_hist = hist.copy()
            # Add moving averages
            processed_hist['MA4'] = processed_hist['Close'].rolling(
                window=self.ma_short).mean()
            processed_hist['MA40'] = processed_hist['Close'].rolling(
                window=self.ma_long).mean()
            # Add RSI
            processed_hist['RSI'] = self.calculate_rsi(
                processed_hist['Close'].values, window=self.rsi_period)
            # Add other indicators as needed for charting

            # Create results dictionary
            result = {
                "ticker": ticker,
                "name": name,
                "price": price,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "tech_score": tech_score,
                "signal": "KÖP" if buy_signal else "SÄLJ" if sell_signal else "HÅLL",
                "buy_signal": buy_signal,
                "sell_signal": sell_signal,
                "fundamental_check": fund_check,
                "technical_check": tech_score >= 60,
                "historical_data": processed_hist,  # Use the processed data with indicators
                # Add the latest RSI value directly
                "rsi": tech_analysis.get('rsi', None),
            }

            # Combine technical and fundamental indicators into result
            result.update(tech_analysis)
            result.update(fund_analysis)

            return result

        except Exception as e:
            err = str(e)
            logging.error(f"Error analyzing {ticker}: {err}")
            return {
                "ticker": ticker,
                "error": err,
                "error_message": f"Fel vid analys: {err}"
            }

    def _calculate_technical_indicators(self, hist):
        """Calculate technical indicators from historical price data"""
        # Make a copy of the dataframe to avoid warnings
        data = hist.copy()

        # Check for empty dataframes
        if data.empty:
            return {
                "above_ma40": False,
                "above_ma4": False,
                "rsi_above_50": False,
                "higher_lows": False,
                "near_52w_high": False,
                "breakout": False
            }

        # Ensure we have enough data
        if len(hist) < max(self.ma_long, 52):  # Need at least 40 weeks (or as specified for MA40)
            return {
                "above_ma40": False,
                "above_ma4": False,
                "rsi_above_50": False,
                "higher_lows": False,
                "near_52w_high": False,
                "breakout": False
            }

        # Calculate moving averages
        data['MA4'] = data['Close'].rolling(window=self.ma_short).mean()
        data['MA40'] = data['Close'].rolling(window=self.ma_long).mean()

        # Calculate RSI with our improved function
        data['RSI'] = self.calculate_rsi(
            data['Close'].values, window=self.rsi_period)

        # Calculate higher lows (using new function)
        data['higher_lows'] = self._calculate_higher_lows(data)

        # 52-week highest level
        data['52w_high'] = data['High'].rolling(window=52).max()
        # Within 2% of highest level
        data['at_52w_high'] = (
            data['Close'] >= data['52w_high'] * self.near_high_threshold)

        # Consolidation phase breakout (simple implementation)
        data['volatility'] = data['Close'].pct_change().rolling(window=12).std()
        data['breakout'] = (data['volatility'].shift(4) < data['volatility']) & (
            data['Close'] > data['Close'].shift(4))

        # Get the latest data point
        latest = data.iloc[-1]

        # Return technical indicators as a dictionary
        return {
            "above_ma40": latest['Close'] > latest['MA40'] if not np.isnan(latest['MA40']) else False,
            "above_ma4": latest['Close'] > latest['MA4'] if not np.isnan(latest['MA4']) else False,
            "rsi_above_50": latest['RSI'] > self.rsi_threshold if not np.isnan(latest['RSI']) else False,
            # Add actual RSI value
            "rsi": float(latest['RSI']) if not np.isnan(latest['RSI']) else None,
            "higher_lows": bool(latest['higher_lows']),
            "near_52w_high": bool(latest['at_52w_high']),
            "breakout": bool(latest['breakout'])
        }

    def _calculate_fundamental_indicators(self, stock, info):
        """Calculate fundamental indicators from stock info"""
        # Initialize results dictionary with default values
        results = {
            "is_profitable": False,
            "pe_ratio": None,
            "revenue_growth": None,
            "profit_margin": None,
            "earnings_trend": "Okänd",
            "fundamental_check": False
        }

        try:
            # Check if company is profitable
            net_income = info.get('netIncomeToCommon')
            results["is_profitable"] = net_income is not None and net_income > 0

            # Get P/E ratio
            results["pe_ratio"] = info.get(
                'trailingPE') or info.get('forwardPE')

            # Get revenue growth
            revenue_growth = info.get('revenueGrowth')
            if revenue_growth is not None and pd.notna(revenue_growth):
                results["revenue_growth"] = revenue_growth

            # Get profit margin
            profit_margin = info.get('profitMargins')
            if profit_margin is not None and pd.notna(profit_margin):
                results["profit_margin"] = profit_margin

            # Get earnings trend data - now using our centralized service
            try:
                earnings = fetch_company_earnings(stock)
                if earnings is not None and not earnings.empty and len(earnings) > 1:
                    # Calculate year-over-year earnings growth
                    yearly_growth = earnings['Earnings'].pct_change().dropna()

                    if len(yearly_growth) > 0:
                        # Determine earnings trend
                        if all(yearly_growth > 0):
                            results["earnings_trend"] = "Ökande"
                        elif all(yearly_growth < 0):
                            results["earnings_trend"] = "Minskande"
                        elif yearly_growth.iloc[-1] > 0:
                            results["earnings_trend"] = "Nyligen ökande"
                        else:
                            results["earnings_trend"] = "Nyligen minskande"
            except Exception as e:
                self.logger.warning(f"Error getting earnings data: {e}")
                results["earnings_trend"] = "Data saknas"

            # Determine if fundamentals are good overall using the improved evaluation
            results["fundamental_check"] = self._evaluate_fundamentals(results)

        except Exception as e:
            self.logger.error(f"Error calculating fundamental indicators: {e}")
            # Leave default values

        return results

    def _evaluate_fundamentals(self, fundamentals):
        """Evaluate if the stock meets fundamental criteria"""
        if "error" in fundamentals:
            return False

        # Using the improved evaluation logic from the new code
        conditions = [
            # Company should be profitable
            fundamentals.get('is_profitable', False),

            # Increasing revenue and earnings, or increasing revenue with stable profit margin
            fundamentals.get('revenue_growth', 0) > 0 and
            (fundamentals.get('earnings_growth', 0) > 0 or
             fundamentals.get('profit_margin', 0) > 0.05),

            # Reasonable P/E
            fundamentals.get('pe_ratio', 100) is not None and
            fundamentals.get('pe_ratio', 100) < self.pe_max and
            fundamentals.get('pe_ratio', 0) > 0
        ]

        # Filter out None values
        valid_conditions = [c for c in conditions if c is not None]

        # If all conditions are None, return False
        if not valid_conditions:
            return False

        return all(valid_conditions)

    def _evaluate_technicals(self, latest_data):
        """Evaluate if the stock meets technical criteria"""
        # Using the improved evaluation logic from the new code
        conditions = [
            latest_data['Close'] > latest_data['MA40'] if not np.isnan(
                latest_data['MA40']) else False,  # Above 40-week MA
            latest_data['RSI'] > 50 if not np.isnan(
                latest_data['RSI']) else False,  # RSI above 50
            bool(latest_data['higher_lows'])  # Higher lows
        ]

        # Extra strength if any of these are met
        extra_strength = [
            bool(latest_data['at_52w_high']),  # Near 52w high
            bool(latest_data['breakout']),  # Breakout
            latest_data['Close'] > latest_data['MA4'] if not np.isnan(
                latest_data['MA4']) else False  # Above 4-week MA
        ]

        return all(conditions) and any(extra_strength)

    def _calculate_tech_score(self, tech_analysis):
        """Calculate a technical score from 0-100 based on technical indicators"""
        # Using the improved scoring logic from the new code
        score = 0

        # Core criteria
        if tech_analysis['above_ma40']:
            score += 30

        if tech_analysis['rsi_above_50']:
            score += 20

        if tech_analysis['higher_lows']:
            score += 20

        # Extra points
        if tech_analysis['above_ma4']:
            score += 10

        if tech_analysis['near_52w_high']:
            score += 10

        if tech_analysis['breakout']:
            score += 10

        return score

    def batch_analyze(self, tickers, progress_callback=None):
        """
        Analyze multiple stocks and return a list of analysis results.
        
        Parameters:
        - tickers: List of stock ticker symbols
        - progress_callback: Function to call with progress updates (0-1.0 and text)
        
        Returns:
        - List of analysis result dictionaries
        """
        results = []
        failed_analyses = []  # Track failures for reporting

        # Store failed analyses in session state if it doesn't exist
        if 'failed_analyses' not in st.session_state:
            st.session_state.failed_analyses = []

        for i, ticker in enumerate(tickers):
            # Update progress
            if progress_callback:
                progress = i / len(tickers)
                progress_callback(
                    progress, f"Analyserar {ticker}... ({i+1}/{len(tickers)})")

            # Analyze this stock
            analysis = self.analyze_stock(ticker)
            results.append(analysis)

            # Check if the result contains an error and add to failed analyses
            if analysis.get("error"):
                failed_analyses.append({
                    "ticker": ticker,
                    "error": analysis["error"],
                    "error_message": analysis.get(
                        "error_message",
                        f"Fel vid analys: {analysis['error']}"
                    )
                })

        # Update progress to 100%
        if progress_callback:
            progress_callback(1.0, "Analys klar!")

        # Store failed analyses in session state for display
        st.session_state.failed_analyses = failed_analyses

        return results

    def plot_analysis(self, analysis):
        """
        Create a plot visualizing the analysis results.
        
        Parameters:
        - analysis: Analysis result dictionary
        
        Returns:
        - Matplotlib figure
        """
        if "error" in analysis or "historical_data" not in analysis:
            return None

        hist = analysis["historical_data"]

        # Create a more detailed chart with both price and RSI plots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(
            12, 8), gridspec_kw={'height_ratios': [3, 1]})
        plt.style.use('ggplot')

        # Price chart with MAs
        ax1.plot(hist.index, hist['Close'], label='Pris', linewidth=2)

        # Add moving averages if they exist in the data
        if 'MA4' in hist.columns and not hist['MA4'].isnull().all():
            ax1.plot(hist.index, hist['MA4'], label='MA4 (4v)', linestyle='--')

        if 'MA40' in hist.columns and not hist['MA40'].isnull().all():
            ax1.plot(hist.index, hist['MA40'],
                     label='MA40 (40v)', linestyle=':')

        # Add buy/sell signals
        if analysis["buy_signal"]:
            ax1.scatter(hist.index[-1], hist['Close'].iloc[-1],
                        color='green', marker='^', s=150, label='KÖP')
        elif analysis["sell_signal"]:
            ax1.scatter(hist.index[-1], hist['Close'].iloc[-1],
                        color='red', marker='v', s=150, label='SÄLJ')

        # Add current RSI value to the title
        rsi_value = analysis.get('rsi', None)
        rsi_text = f" (RSI: {rsi_value:.1f})" if rsi_value is not None else ""

        ax1.set_title(
            f"{analysis['name']} ({analysis['ticker']}) - {analysis.get('signal', 'HÅLL')}{rsi_text}", fontsize=14)
        ax1.set_ylabel("Pris")
        ax1.legend()
        ax1.grid(True, linestyle='--', alpha=0.5)

        # RSI chart
        if 'RSI' in hist.columns and not hist['RSI'].isnull().all():
            ax2.plot(hist.index, hist['RSI'],
                     label='RSI', color='purple', linewidth=1.5)
            ax2.axhline(y=70, color='red', linestyle='--', alpha=0.5)
            ax2.axhline(y=30, color='green', linestyle='--', alpha=0.5)
            ax2.axhline(y=50, color='black', linestyle='-', alpha=0.3)
            ax2.set_ylim(0, 100)
            ax2.set_ylabel("RSI")
            ax2.set_title("Relative Strength Index (RSI)")
            ax2.legend()
            ax2.grid(True, linestyle='--', alpha=0.5)

        fig.tight_layout()
        return fig
