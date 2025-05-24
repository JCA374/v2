# tabs/scanner/analysis.py
"""
Analysis module for scanner functionality that integrates with ValueMomentumStrategy.
Updated with comprehensive scoring and ranking system.
"""
import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime
from .data import clear_completed_retries, save_failed_tickers
from .state import initialize_scanner_state


def perform_scan(tickers, period="1y", interval="1wk", rsi_range=(30, 70),
                 vol_multiplier=1.5, lookback=30, batch_size=25, continuous_scan=True):
    """
    Perform stock scanning using the ValueMomentumStrategy for comprehensive analysis.
    Updated to include comprehensive scoring and ranking.
    
    Args:
        tickers: List of tickers to scan
        period: Historical data period (e.g., "1y", "6mo") - passed to strategy
        interval: Data interval (e.g., "1d", "1wk") - passed to strategy
        rsi_range: Tuple of (min, max) RSI values (saved for UI filtering only)
        vol_multiplier: Volume multiplier threshold (saved for UI filtering only)
        lookback: Days to look back (saved for UI filtering only)
        batch_size: Number of tickers to process at once
        continuous_scan: Whether to add delays between batches to avoid rate limits
    """
    # Make sure state is initialized
    initialize_scanner_state()

    # Mark scanner as running
    st.session_state.scanner_running = True

    # Initialize progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Get strategy from session state
    strategy = st.session_state.strategy

    # Initialize scorer for comprehensive scoring
    scorer = StockScorer(strategy)

    try:
        # Process ticker list into a consistent format
        symbols = [t[0] if isinstance(
            t, (list, tuple)) else t for t in tickers]
        total_tickers = len(symbols)

        # Save settings for filtering in session state
        st.session_state.scanner_settings = {
            "rsi_range": rsi_range,
            "vol_multiplier": vol_multiplier,
            "lookback": lookback,
            "period": period,
            "interval": interval
        }

        # Define progress callback function for strategy
        def update_progress(progress, message):
            progress_bar.progress(progress)
            status_text.text(message)
            # Check if scanner was stopped
            if not st.session_state.get('scanner_running', True):
                return False  # Signal the strategy to stop processing
            return True  # Continue processing

        # Process in smaller batches to avoid API rate limits
        batch_count = (total_tickers + batch_size - 1) // batch_size
        all_results = []
        failed_tickers = []

        for batch_idx in range(batch_count):
            # Check if scanner was stopped
            if not st.session_state.scanner_running:
                status_text.warning("Scanner stopped by user")
                break

            # Get current batch
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_tickers)
            current_batch = symbols[start_idx:end_idx]

            # Update progress display
            batch_progress = batch_idx / batch_count
            progress_bar.progress(batch_progress)
            status_message = f"Processing batch {batch_idx+1}/{batch_count} ({start_idx+1}-{end_idx} of {total_tickers})"
            status_text.text(status_message)

            # Use the strategy to analyze this batch
            batch_analyses = strategy.batch_analyze(
                current_batch,
                progress_callback=lambda p, msg: update_progress(
                    batch_progress + (p * (1/batch_count)),
                    f"Batch {batch_idx+1}/{batch_count}: {msg}"
                )
            )

            # Process the results with comprehensive scoring
            for analysis in batch_analyses:
                if "error" in analysis:
                    failed_tickers.append(analysis["ticker"])
                    continue

                # Calculate comprehensive score
                comprehensive_score = scorer.calculate_comprehensive_score(
                    analysis)

                # Convert strategy analysis to scanner format with ranking
                result = {
                    "Rank": 0,  # Will be set after sorting all results
                    "Ticker": analysis["ticker"],
                    "Name": analysis.get("name", analysis["ticker"]),
                    "Price": round(analysis.get("price", 0), 2),
                    "Score": round(comprehensive_score, 1),
                    "Tech Score": analysis.get("tech_score", 0),
                    "Signal": analysis.get("signal", "HÅLL"),
                    "Fund OK": "Yes" if analysis.get("fundamental_check", False) else "No",
                    "RSI(14)": round(analysis.get("rsi", 0), 1) if analysis.get("rsi") is not None else "N/A",
                    "Above MA4": "Yes" if analysis.get("above_ma4", False) else "No",
                    "Above MA40": "Yes" if analysis.get("above_ma40", False) else "No",
                    "Near 52w High": "Yes" if analysis.get("near_52w_high", False) else "No",
                    "Higher Lows": "Yes" if analysis.get("higher_lows", False) else "No",
                    "Breakout": "Yes" if analysis.get("breakout", False) else "No",
                    "Profitable": "Yes" if analysis.get("is_profitable", False) else "No",
                    "P/E": round(analysis.get("pe_ratio", 0), 1) if analysis.get("pe_ratio") and pd.notna(analysis.get("pe_ratio")) else "N/A",
                    "Data Source": analysis.get("data_source", "unknown").title(),
                    "_analysis": analysis  # Keep full analysis for detailed view
                }
                all_results.append(result)

            # Wait between batches if continuous scanning enabled
            if continuous_scan and batch_idx < batch_count - 1 and st.session_state.scanner_running:
                wait_time = 3  # 3 second delay between batches
                for i in range(wait_time, 0, -1):
                    if not st.session_state.scanner_running:
                        status_text.warning(
                            "Scanner stopped during wait period")
                        break
                    status_text.text(f"Waiting {i}s before next batch...")
                    time.sleep(1)

        # Sort all results by comprehensive score (best to worst)
        all_results.sort(key=lambda x: x["Score"], reverse=True)

        # Assign ranks
        for i, result in enumerate(all_results):
            result["Rank"] = i + 1

        # Final progress update
        if st.session_state.scanner_running:
            progress_bar.progress(1.0)
            status_text.text(
                f"Completed scanning {total_tickers} tickers. Found {len(all_results)} results, {len(failed_tickers)} failed.")

        # Store results in session state
        if all_results:
            df_results = pd.DataFrame(all_results)
            st.session_state.scan_results = df_results

        # Store failed tickers
        if failed_tickers:
            st.session_state.failed_tickers = failed_tickers
            save_failed_tickers(failed_tickers)

        # Update retry file for any completed retries
        if all_results:
            completed_tickers = [r["Ticker"] for r in all_results]
            clear_completed_retries(completed_tickers)

    except Exception as e:
        st.error(f"Error during scanning: {e}")
        import traceback
        st.error(traceback.format_exc())

    finally:
        # Always set scanner to finished state
        st.session_state.scanner_running = False


class StockScorer:
    """
    Comprehensive stock scoring system that combines multiple factors
    """

    def __init__(self, strategy):
        self.strategy = strategy

    def calculate_comprehensive_score(self, analysis_result):
        """
        Calculate a comprehensive score from 0-100 based on multiple factors
        """
        if "error" in analysis_result:
            return 0

        score = 0

        # Technical Score (40% weight)
        tech_score = analysis_result.get('tech_score', 0)
        score += (tech_score / 100) * 40

        # Fundamental Score (30% weight)
        fund_score = self._calculate_fundamental_score(analysis_result)
        score += (fund_score / 100) * 30

        # Momentum Score (20% weight)
        momentum_score = self._calculate_momentum_score(analysis_result)
        score += (momentum_score / 100) * 20

        # Quality Score (10% weight)
        quality_score = self._calculate_quality_score(analysis_result)
        score += (quality_score / 100) * 10

        return min(100, max(0, score))

    def _calculate_fundamental_score(self, analysis):
        """Calculate fundamental score based on financial metrics"""
        score = 0

        # Profitability (40 points)
        if analysis.get('is_profitable', False):
            score += 20

        pe_ratio = analysis.get('pe_ratio')
        if pe_ratio and pd.notna(pe_ratio):
            if 5 <= pe_ratio <= 25:  # Reasonable P/E
                score += 20
            elif pe_ratio < 5 and pe_ratio > 0:
                score += 10  # Very cheap but risky

        # Growth (30 points)
        revenue_growth = analysis.get('revenue_growth', 0)
        if revenue_growth and pd.notna(revenue_growth):
            if revenue_growth > 0.1:  # 10%+ growth
                score += 15
            elif revenue_growth > 0.05:  # 5%+ growth
                score += 10

        profit_margin = analysis.get('profit_margin', 0)
        if profit_margin and pd.notna(profit_margin):
            if profit_margin > 0.15:  # 15%+ margin
                score += 15
            elif profit_margin > 0.05:  # 5%+ margin
                score += 10

        # Earnings trend (30 points)
        earnings_trend = analysis.get('earnings_trend', '')
        if 'ökande' in earnings_trend.lower():  # Increasing
            score += 30
        elif 'nyligen ökande' in earnings_trend.lower():  # Recently increasing
            score += 20

        return min(100, score)

    def _calculate_momentum_score(self, analysis):
        """Calculate momentum score based on price action"""
        score = 0

        # Price vs moving averages (50 points)
        if analysis.get('above_ma40', False):
            score += 25
        if analysis.get('above_ma4', False):
            score += 25

        # RSI momentum (25 points)
        if analysis.get('rsi_above_50', False):
            score += 25

        # Price patterns (25 points)
        if analysis.get('higher_lows', False):
            score += 10
        if analysis.get('near_52w_high', False):
            score += 10
        if analysis.get('breakout', False):
            score += 5

        return min(100, score)

    def _calculate_quality_score(self, analysis):
        """Calculate quality score based on business quality indicators"""
        score = 50  # Base score

        # Data source quality
        data_source = analysis.get('data_source', 'unknown')
        if data_source in ['yahoo', 'alphavantage']:
            score += 20

        # Fundamental data availability
        if analysis.get('pe_ratio') is not None and pd.notna(analysis.get('pe_ratio')):
            score += 15
        if analysis.get('revenue_growth') is not None and pd.notna(analysis.get('revenue_growth')):
            score += 15

        return min(100, score)
