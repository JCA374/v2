# services/yahoo_finance_service.py
"""
Centralized service for fetching financial data from Yahoo Finance API.
This module provides a unified interface for all Yahoo Finance API calls in the application.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('yahoo_finance_service')

# Constants
CACHE_TTL = 7200  # 2 hour cache
RATE_LIMIT_WAIT = 30  # Base wait time in seconds when rate limited
MAX_RETRIES = 3  # Maximum number of retries for API failures
DEFAULT_BATCH_SIZE = 25  # Default batch size for bulk requests


@st.cache_data(ttl=CACHE_TTL)
def fetch_ticker_info(ticker):
    """
    Fetch basic information for a single ticker.
    
    Args:
        ticker (str): The ticker symbol
        
    Returns:
        tuple: (stock object, info dictionary) or raises exception
    """
    logger.info(f"Fetching info for {ticker}")

    for retry in range(MAX_RETRIES):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            if not isinstance(info, dict):
                raise RuntimeError("No basic info returned")

            return stock, info

        except Exception as e:
            if "rate" in str(e).lower() or "limit" in str(e).lower():
                # Exponential backoff for rate limits
                wait_time = RATE_LIMIT_WAIT * (2 ** retry)
                logger.warning(
                    f"Rate limit hit fetching {ticker}. Waiting {wait_time}s before retry {retry+1}/{MAX_RETRIES}")
                time.sleep(wait_time)
            elif retry < MAX_RETRIES - 1:
                # For other errors, wait a bit less
                wait_time = 5 * (retry + 1)
                logger.warning(
                    f"Error fetching {ticker}: {str(e)}. Retrying in {wait_time}s ({retry+1}/{MAX_RETRIES})")
                time.sleep(wait_time)
            else:
                # Last retry failed
                logger.error(
                    f"Failed to fetch info for {ticker} after {MAX_RETRIES} retries: {str(e)}")
                raise RuntimeError(
                    f"Failed to fetch info for {ticker}: {str(e)}")

    # This should never be reached due to the raise in the loop
    raise RuntimeError(
        f"Failed to fetch info for {ticker} after {MAX_RETRIES} retries")


@st.cache_data(ttl=CACHE_TTL)
def fetch_history(ticker, period="1y", interval="1wk", auto_adjust=True, actions=False):
    """
    Fetch historical price data for a single ticker.
    
    Args:
        ticker (str): The ticker symbol
        period (str): Time period to fetch (e.g., "1y", "3mo", "5y")
        interval (str): Data interval (e.g., "1d", "1wk")
        auto_adjust (bool): Whether to adjust prices automatically
        actions (bool): Whether to include dividends and splits
        
    Returns:
        DataFrame: Historical price data or raises exception
    """
    logger.info(f"Fetching history for {ticker} ({period}, {interval})")

    for retry in range(MAX_RETRIES):
        try:
            # If we have a stock object, use it directly
            if isinstance(ticker, yf.Ticker):
                stock = ticker
                ticker_symbol = stock.ticker
            else:
                stock = yf.Ticker(ticker)
                ticker_symbol = ticker

            hist = stock.history(
                period=period, interval=interval, auto_adjust=auto_adjust, actions=actions)

            if hist is None or hist.empty:
                raise RuntimeError(
                    f"No historical data available for {ticker_symbol}")

            return hist

        except Exception as e:
            if "rate" in str(e).lower() or "limit" in str(e).lower():
                # Exponential backoff for rate limits
                wait_time = RATE_LIMIT_WAIT * (2 ** retry)
                logger.warning(
                    f"Rate limit hit fetching history for {ticker_symbol}. Waiting {wait_time}s before retry {retry+1}/{MAX_RETRIES}")
                time.sleep(wait_time)
            elif retry < MAX_RETRIES - 1:
                # For other errors, wait a bit less
                wait_time = 5 * (retry + 1)
                logger.warning(
                    f"Error fetching history for {ticker_symbol}: {str(e)}. Retrying in {wait_time}s ({retry+1}/{MAX_RETRIES})")
                time.sleep(wait_time)
            else:
                # Last retry failed
                logger.error(
                    f"Failed to fetch history for {ticker_symbol} after {MAX_RETRIES} retries: {str(e)}")
                raise RuntimeError(
                    f"Failed to fetch history for {ticker_symbol}: {str(e)}")

    # This should never be reached due to the raise in the loop
    raise RuntimeError(
        f"Failed to fetch history for {ticker_symbol} after {MAX_RETRIES} retries")


@st.cache_data(ttl=CACHE_TTL)
def fetch_bulk_data(tickers, period="1y", interval="1wk", batch_size=DEFAULT_BATCH_SIZE,
                    auto_adjust=True, group_by='ticker', progress_callback=None):
    """
    Fetch data for multiple tickers with intelligent batching and retry logic.
    
    Args:
        tickers (list): List of ticker symbols or (original_id, ticker_symbol) tuples
        period (str): Time period to fetch (e.g., "1y", "3mo", "5y")
        interval (str): Data interval (e.g., "1d", "1wk")
        batch_size (int): Number of tickers to fetch in each batch
        auto_adjust (bool): Whether to adjust prices automatically
        group_by (str): How to group the data ('ticker' or 'column')
        progress_callback (callable): Function to call with progress updates
        
    Returns:
        dict: Dictionary mapping ticker symbols to their historical data
    """
    result = {}
    total_tickers = len(tickers)

    # Process tickers to ensure consistent format
    processed_tickers = []
    for ticker in tickers:
        if isinstance(ticker, (list, tuple)):
            processed_tickers.append((ticker[0], ticker[1]))
        else:
            processed_tickers.append((ticker, ticker))

    # Process in batches to avoid rate limits
    for batch_idx, batch_start in enumerate(range(0, total_tickers, batch_size)):
        # Check if process should be stopped (if callback returns False)
        if progress_callback and not progress_callback(batch_idx / ((total_tickers + batch_size - 1) // batch_size),
                                                       f"Processing batch {batch_idx+1}/{(total_tickers + batch_size - 1) // batch_size}"):
            logger.info("Bulk data fetch stopped by user")
            break

        batch_end = min(batch_start + batch_size, total_tickers)
        batch = processed_tickers[batch_start:batch_end]

        # Extract just the ticker symbols for the API call
        batch_symbols = [t[1] for t in batch]

        logger.info(
            f"Fetching batch {batch_idx+1}/{(total_tickers + batch_size - 1) // batch_size} ({len(batch_symbols)} tickers)")

        # Try to fetch data with retries
        for retry in range(MAX_RETRIES):
            try:
                data = yf.download(
                    tickers=batch_symbols,
                    period=period,
                    interval=interval,
                    group_by=group_by,
                    auto_adjust=auto_adjust,
                    progress=False
                )

                # Process the results
                if isinstance(data.columns, pd.MultiIndex):
                    # Multiple tickers returned
                    for i, (orig, sym) in enumerate(batch):
                        if sym in data.columns.levels[0]:
                            df_sym = data[sym].copy()
                            if not df_sym.empty:
                                result[orig] = df_sym
                else:
                    # Single ticker returned
                    if len(batch_symbols) == 1 and not data.empty:
                        result[batch[0][0]] = data.copy()

                # Success! Break the retry loop
                break

            except Exception as e:
                error_msg = str(e).lower()

                if "rate" in error_msg or "limit" in error_msg:
                    # Exponential backoff for rate limits
                    wait_time = RATE_LIMIT_WAIT * (2 ** retry)
                    logger.warning(
                        f"Rate limit hit. Waiting {wait_time}s before retry {retry+1}/{MAX_RETRIES}")

                    if progress_callback:
                        progress_callback(batch_idx / ((total_tickers + batch_size - 1) // batch_size),
                                          f"Rate limit hit. Waiting {wait_time}s before retry {retry+1}/{MAX_RETRIES}")

                    time.sleep(wait_time)
                elif retry < MAX_RETRIES - 1:
                    # For other errors, wait a bit less
                    wait_time = 5 * (retry + 1)
                    logger.warning(
                        f"Error fetching batch: {str(e)}. Retrying in {wait_time}s ({retry+1}/{MAX_RETRIES})")

                    if progress_callback:
                        progress_callback(batch_idx / ((total_tickers + batch_size - 1) // batch_size),
                                          f"Error: {str(e)}. Retrying in {wait_time}s ({retry+1}/{MAX_RETRIES})")

                    time.sleep(wait_time)
                else:
                    # Log failures but keep going
                    logger.error(
                        f"Failed to fetch batch after {MAX_RETRIES} retries: {str(e)}")

                    # If we have a way to report failures, do so
                    failed_tickers = [t[0] for t in batch]
                    if hasattr(st.session_state, 'failed_tickers'):
                        st.session_state.failed_tickers.extend(failed_tickers)

                    if progress_callback:
                        progress_callback(batch_idx / ((total_tickers + batch_size - 1) // batch_size),
                                          f"Failed to fetch batch after {MAX_RETRIES} retries")

        # Add a small random delay between batches to avoid rate limiting
        if batch_idx < (total_tickers + batch_size - 1) // batch_size - 1:
            time.sleep(random.uniform(1.0, 3.0))

    return result


@st.cache_data(ttl=CACHE_TTL)
def fetch_company_earnings(ticker):
    """
    Fetch earnings data for a company.
    
    Args:
        ticker (str or yf.Ticker): The ticker symbol or Ticker object
        
    Returns:
        DataFrame: Earnings data or None if not available
    """
    try:
        # If we have a stock object, use it directly
        if isinstance(ticker, yf.Ticker):
            stock = ticker
        else:
            stock = yf.Ticker(ticker)

        earnings = stock.earnings

        if earnings is None or earnings.empty:
            logger.warning(f"No earnings data available for {ticker}")
            return None

        return earnings

    except Exception as e:
        logger.error(f"Error fetching earnings for {ticker}: {str(e)}")
        return None


@st.cache_data(ttl=CACHE_TTL)
def fetch_sustainability_data(ticker):
    """
    Fetch ESG (Environmental, Social, Governance) data for a company.
    
    Args:
        ticker (str or yf.Ticker): The ticker symbol or Ticker object
        
    Returns:
        DataFrame: Sustainability data or None if not available
    """
    try:
        # If we have a stock object, use it directly
        if isinstance(ticker, yf.Ticker):
            stock = ticker
        else:
            stock = yf.Ticker(ticker)

        esg = stock.sustainability

        if esg is None or esg.empty:
            logger.warning(f"No ESG data available for {ticker}")
            return None

        return esg

    except Exception as e:
        logger.error(f"Error fetching ESG data for {ticker}: {str(e)}")
        return None


def extract_fundamental_data(info):
    """
    Extract key fundamental data from ticker info dictionary.
    
    Args:
        info (dict): The ticker info dictionary from yfinance
        
    Returns:
        dict: Dictionary of fundamental metrics
    """
    fundamentals = {}

    # Financial Performance
    fundamentals['pe_ratio'] = info.get('trailingPE') or info.get('forwardPE')
    fundamentals['revenue_growth'] = info.get('revenueGrowth')
    fundamentals['profit_margin'] = info.get('profitMargins')
    fundamentals['is_profitable'] = info.get('netIncomeToCommon', 0) > 0

    # Valuation Metrics
    fundamentals['market_cap'] = info.get('marketCap')
    fundamentals['book_value'] = info.get('bookValue')
    fundamentals['price_to_book'] = info.get('priceToBook')
    fundamentals['dividend_yield'] = info.get('dividendYield')
    fundamentals['peg_ratio'] = info.get('pegRatio')

    # Business Info
    fundamentals['sector'] = info.get('sector')
    fundamentals['industry'] = info.get('industry')
    fundamentals['full_time_employees'] = info.get('fullTimeEmployees')
    fundamentals['country'] = info.get('country')

    return fundamentals
