# tabs/scanner/analysis.py
"""
Analysis module for scanner functionality that integrates with ValueMomentumStrategy.
Replaces the custom scanning logic with the main strategy's analysis capability.
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
    
    try:
        # Process ticker list into a consistent format
        symbols = [t[0] if isinstance(t, (list, tuple)) else t for t in tickers]
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
            
            # Process the results
            for analysis in batch_analyses:
                if "error" in analysis:
                    failed_tickers.append(analysis["ticker"])
                    continue
                
                # Convert strategy analysis to scanner format
                # Check which score key to use based on what's available in the analysis
                score_key = "Tech Score"
                score_value = analysis.get("tech_score")
                
                # If tech_score doesn't exist but score does, use that instead
                if score_value is None and "score" in analysis:
                    score_value = analysis["score"]
                
                result = {
                    "Ticker": analysis["ticker"],
                    "Price": analysis["price"],
                    score_key: score_value,
                    "Fund OK": "Yes" if analysis["fundamental_check"] else "No",
                    "Signal": analysis["signal"],
                    # Add RSI if available
                    "RSI(14)": round(analysis.get("rsi", 0), 1) if analysis.get("rsi") is not None else "N/A",
                    # Add moving average states
                    "Above MA4": "Yes" if analysis.get("above_ma4", False) else "No",
                    "Above MA40": "Yes" if analysis.get("above_ma40", False) else "No",
                    # Add other indicators
                    "Near 52w High": "Yes" if analysis.get("near_52w_high", False) else "No",
                    "Higher Lows": "Yes" if analysis.get("higher_lows", False) else "No",
                    "Breakout": "Yes" if analysis.get("breakout", False) else "No"
                }
                all_results.append(result)
            
            # Wait between batches if continuous scanning enabled
            if continuous_scan and batch_idx < batch_count - 1 and st.session_state.scanner_running:
                wait_time = 3  # 3 second delay between batches
                for i in range(wait_time, 0, -1):
                    if not st.session_state.scanner_running:
                        status_text.warning("Scanner stopped during wait period")
                        break
                    status_text.text(f"Waiting {i}s before next batch...")
                    time.sleep(1)
        
        # Final progress update
        if st.session_state.scanner_running:
            progress_bar.progress(1.0)
            status_text.text(f"Completed scanning {total_tickers} tickers. Found {len(all_results)} results, {len(failed_tickers)} failed.")
            
        # Store results in session state
        if all_results:
            df_results = pd.DataFrame(all_results).sort_values("Tech Score", ascending=False)
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