import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import streamlit as st
import time
import json
import os
from datetime import datetime, timedelta
import logging


class ValueMomentumStrategy:
    # … your __init__ etc.

    def _fetch_info(self, ticker):
        """Fetches yf.Ticker.info or raises RuntimeError."""
        stock = yf.Ticker(ticker)
        info = stock.info
        if not isinstance(info, dict):
            raise RuntimeError("No basic info returned")
        return stock, info

    def _fetch_history(self, stock, period="1y", interval="1wk"):
        """Fetches history DataFrame or raises RuntimeError."""
        hist = stock.history(period=period, interval=interval)
        if hist is None or hist.empty:
            raise RuntimeError("No historical data available")
        return hist

    def analyze_stock(self, ticker):
        """
        Analyze a single stock according to Value & Momentum strategy.
        
        Parameters:
        - ticker: Stock ticker symbol
        
        Returns:
        - Dictionary with analysis results
        """
        # Get stock data
        try:
            stock = yf.Ticker(ticker)

            # Get basic info
            info = stock.info

            # Handle missing name
            try:
                name = info.get('shortName', info.get('longName', ticker))
            except:
                name = ticker

            # Get historical data (weekly)
            hist = stock.history(period="1y", interval="1wk")

            if hist.empty:
                return {
                    "ticker": ticker,
                    "error": "No data available",
                    "error_message": f"Ingen data tillgänglig för {ticker}"
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
                "historical_data": hist
            }

            # Combine technical and fundamental indicators into result
            result.update(tech_analysis)
            result.update(fund_analysis)

            return result

        except Exception as e:
            return {
                "ticker": ticker,
                "error": str(e),
                "error_message": f"Fel vid analys: {str(e)}"
            }

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
        import streamlit as st
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

            # Add to results
            results.append(analysis)

            # Check if the result contains an error and add to failed analyses
            if isinstance(analysis, dict) and "error" in analysis and analysis["error"]:
                # Ensure error_message exists
                if "error_message" not in analysis:
                    analysis["error_message"] = f"Fel vid analys: {analysis['error']}"

                failed_analyses.append(analysis)
                print(f"Error analyzing {ticker}: {analysis['error']}")

        # Update progress to 100%
        if progress_callback:
            progress_callback(1.0, "Analys klar!")

        # Store failed analyses in session state for display
        st.session_state.failed_analyses = failed_analyses

        return results

    def _derive_signal(self, tech, score, fund):
        buy = score >= 70 and fund["fundamental_check"]
        sell = score < 40 or not tech["above_ma40"]
        return "KÖP" if buy else "SÄLJ" if sell else "HÅLL"

###
    def _calculate_technical_indicators(self, hist):
        """Calculate technical indicators from historical price data"""
        # Make sure we have enough data
        if len(hist) < 40:
            # If we don't have enough data, fill with some default values
            return {
                "above_ma40": False,
                "above_ma4": False,
                "rsi_above_50": False,
                "higher_lows": False,
                "near_52w_high": False,
                "breakout": False
            }

        # Calculate moving averages
        hist['MA4'] = hist['Close'].rolling(window=self.ma_short).mean()
        hist['MA40'] = hist['Close'].rolling(window=self.ma_long).mean()

        # Get current price and MAs
        current_price = hist['Close'].iloc[-1]
        ma4 = hist['MA4'].iloc[-1]
        ma40 = hist['MA40'].iloc[-1]

        # Check if price is above moving averages
        above_ma4 = current_price > ma4 if pd.notna(ma4) else False
        above_ma40 = current_price > ma40 if pd.notna(ma40) else False

        # Calculate RSI - COMPLETELY REWRITTEN FOR SAFETY
        try:
            # Alternative implementation of RSI calculation without boolean indexing
            delta = hist['Close'].diff()

            # Calculate gains (up) and losses (down)
            gains = delta.copy()
            gains[gains < 0] = 0.0

            losses = -delta.copy()
            losses[losses < 0] = 0.0

            # Calculate exponential moving averages of gains and losses
            avg_gain = gains.ewm(com=self.rsi_period-1, adjust=False).mean()
            avg_loss = losses.ewm(com=self.rsi_period-1, adjust=False).mean()

            # Calculate RS (relative strength) carefully to avoid division by zero
            rs = pd.Series(np.zeros(len(avg_gain)), index=avg_gain.index)
            for i in range(len(avg_gain)):
                if avg_loss.iloc[i] > 0:
                    rs.iloc[i] = avg_gain.iloc[i] / avg_loss.iloc[i]

            # Calculate RSI
            hist['RSI'] = 100 - (100 / (1 + rs))

            # Check if RSI is above threshold
            current_rsi = hist['RSI'].iloc[-1]
            rsi_above_50 = current_rsi > self.rsi_threshold if pd.notna(
                current_rsi) else False
        except Exception as e:
            print(f"Error calculating RSI: {e}")
            rsi_above_50 = False
            hist['RSI'] = pd.Series(np.zeros(len(hist)), index=hist.index)

        # Check for higher lows (in the last 12 weeks)
        try:
            # Look at the last 12 weeks and identify local minima
            last_weeks = hist.iloc[-13:-
                                1] if len(hist) > 13 else hist.iloc[:-1]
            lows = []

            for i in range(1, len(last_weeks)-1):
                if (pd.notna(last_weeks['Low'].iloc[i]) and
                    pd.notna(last_weeks['Low'].iloc[i-1]) and
                    pd.notna(last_weeks['Low'].iloc[i+1]) and
                    last_weeks['Low'].iloc[i] < last_weeks['Low'].iloc[i-1] and
                        last_weeks['Low'].iloc[i] < last_weeks['Low'].iloc[i+1]):
                    lows.append(last_weeks['Low'].iloc[i])

            # Check if we have at least 2 lows and they're increasing
            higher_lows = len(lows) >= 2 and all(
                lows[i] > lows[i-1] for i in range(1, len(lows)))
        except Exception as e:
            print(f"Error calculating higher lows: {e}")
            higher_lows = False

        # Check if price is near 52-week high
        try:
            high_52w = hist['High'].max()
            near_52w_high = (current_price > high_52w *
                            self.near_high_threshold) if pd.notna(high_52w) else False
        except Exception as e:
            print(f"Error calculating 52 week high: {e}")
            near_52w_high = False

        # Check for breakout from consolidation
        try:
            # Calculate weekly volatility safely
            hist['Weekly_Range'] = pd.Series(
                np.zeros(len(hist)), index=hist.index)
            for i in range(len(hist)):
                if pd.notna(hist['High'].iloc[i]) and pd.notna(hist['Low'].iloc[i]) and hist['Low'].iloc[i] > 0:
                    hist['Weekly_Range'].iloc[i] = (
                        hist['High'].iloc[i] - hist['Low'].iloc[i]) / hist['Low'].iloc[i]

            # Look at the last 6 weeks and the 6 weeks before that
            if len(hist) >= 12:  # Ensure we have enough data
                recent_volatility = hist['Weekly_Range'].iloc[-6:].mean()
                previous_volatility = hist['Weekly_Range'].iloc[-12:-6].mean()

                # Recent price change
                recent_price_change = 0
                if pd.notna(hist['Close'].iloc[-6]) and hist['Close'].iloc[-6] > 0:
                    recent_price_change = (
                        hist['Close'].iloc[-1] - hist['Close'].iloc[-6]) / hist['Close'].iloc[-6]

                # Breakout condition: lower recent volatility followed by strong price increase
                breakout = (pd.notna(recent_volatility) and
                            pd.notna(previous_volatility) and
                            previous_volatility > 0 and
                            recent_volatility < previous_volatility * 0.8 and
                            recent_price_change > 0.05)
            else:
                breakout = False
        except Exception as e:
            print(f"Error calculating breakout: {e}")
            breakout = False

        return {
            "above_ma40": above_ma40,
            "above_ma4": above_ma4,
            "rsi_above_50": rsi_above_50,
            "higher_lows": higher_lows,
            "near_52w_high": near_52w_high,
            "breakout": breakout
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

            # Get earnings trend data
            try:
                earnings = stock.earnings
                if not earnings.empty and len(earnings) > 1:
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
            except:
                results["earnings_trend"] = "Data saknas"

            # Determine if fundamentals are good overall
            # Conditions:
            # 1. Company is profitable
            # 2. Either has reasonable P/E or good growth
            pe_check = results["pe_ratio"] is None or (
                pd.notna(results["pe_ratio"]) and results["pe_ratio"] < self.pe_max)
            growth_check = results["revenue_growth"] is not None and pd.notna(
                results["revenue_growth"]) and results["revenue_growth"] > 0

            results["fundamental_check"] = results["is_profitable"] and (
                pe_check or growth_check)

        except Exception as e:
            print(f"Error calculating fundamental indicators: {e}")
            # Leave default values

        return results

    def _calculate_tech_score(self, tech_analysis):
        """Calculate a technical score from 0-100 based on technical indicators"""
        score = 0

        # Moving averages (most important)
        if tech_analysis['above_ma40']:
            score += 30
        if tech_analysis['above_ma4']:
            score += 15

        # RSI
        if tech_analysis['rsi_above_50']:
            score += 15

        # Higher lows
        if tech_analysis['higher_lows']:
            score += 15

        # Near 52-week high
        if tech_analysis['near_52w_high']:
            score += 15

        # Breakout
        if tech_analysis['breakout']:
            score += 10

        return score

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

        # Create the figure
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot price and moving averages
        ax.plot(hist.index, hist['Close'], label='Price', linewidth=2)

        if 'MA4' in hist.columns and 'MA40' in hist.columns:
            # Only plot data points that are not NaN
            ma4_data = hist['MA4'].dropna()
            ma40_data = hist['MA40'].dropna()

            if not ma4_data.empty:
                ax.plot(ma4_data.index, ma4_data, label='MA4', linestyle='--')

            if not ma40_data.empty:
                ax.plot(ma40_data.index, ma40_data,
                        label='MA40', linestyle='-.')

        # Add title and labels
        title = f"{analysis['name']} ({analysis['ticker']}) - {analysis['signal']}"
        ax.set_title(title)
        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        ax.grid(True, alpha=0.3)

        # Add legend
        ax.legend()

        # Add annotations for key metrics
        annotation_text = (
            f"Tech Score: {analysis['tech_score']}/100\n"
            f"Above MA40: {'✓' if analysis['above_ma40'] else '✗'}\n"
            f"Above MA4: {'✓' if analysis['above_ma4'] else '✗'}\n"
            f"RSI > 50: {'✓' if analysis['rsi_above_50'] else '✗'}\n"
            f"P/E: {analysis['pe_ratio']:.1f}" if analysis['pe_ratio'] and pd.notna(
                analysis['pe_ratio']) else "P/E: N/A"
        )

        plt.figtext(0.02, 0.02, annotation_text, fontsize=9,
                    bbox=dict(facecolor='white', alpha=0.8))

        # Adjust layout
        plt.tight_layout()

        return fig

#