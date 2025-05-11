# services/yahoo_finance_service.py
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('yahoo_finance_service')

# Constants
CACHE_TTL = 7200  # 2 hour cache

@st.cache_data(ttl=CACHE_TTL)
def fetch_history(ticker_symbol, period="1y", interval="1wk"):
    """
    Fetch historical price data for a ticker symbol.
    
    Args:
        ticker_symbol (str): The stock ticker symbol
        period (str): Time period to fetch (e.g., "1y", "3mo", "5y")
        interval (str): Data interval (e.g., "1d", "1wk")
        
    Returns:
        DataFrame: Historical price data
    """
    logger.info(f"Yahoo Finance: Fetching history for {ticker_symbol} ({period}, {interval})")
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        
        if df.empty:
            logger.warning(f"No data returned for {ticker_symbol}")
            return pd.DataFrame()
            
        # Add source column
        df['source'] = 'yahoo'
        return df
        
    except Exception as e:
        logger.error(f"Error fetching data for {ticker_symbol}: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=CACHE_TTL)
def fetch_ticker_info(ticker_symbol):
    """
    Fetch basic information for a ticker symbol.
    
    Args:
        ticker_symbol (str): The stock ticker symbol
        
    Returns:
        dict: Stock information dictionary
    """
    logger.info(f"Yahoo Finance: Fetching info for {ticker_symbol}")
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        
        if not isinstance(info, dict):
            logger.warning(f"No info returned for {ticker_symbol}")
            return {}
            
        # Add source information
        info['source'] = 'yahoo'
        return info
        
    except Exception as e:
        logger.error(f"Error fetching info for {ticker_symbol}: {str(e)}")
        return {}

@st.cache_data(ttl=CACHE_TTL)
def fetch_bulk_data(ticker_symbols, period="1y", interval="1wk"):
    """
    Fetch data for multiple ticker symbols at once.
    
    Args:
        ticker_symbols (list): List of ticker symbols
        period (str): Time period to fetch (e.g., "1y", "3mo", "5y")
        interval (str): Data interval (e.g., "1d", "1wk")
        
    Returns:
        dict: Dictionary mapping ticker symbols to their historical data
    """
    logger.info(f"Yahoo Finance: Fetching {len(ticker_symbols)} tickers")
    
    try:
        data = yf.download(
            tickers=ticker_symbols,
            period=period,
            interval=interval,
            group_by='ticker',
            auto_adjust=True,
            progress=False
        )
        
        result = {}
        
        # Process the results
        if isinstance(data.columns, pd.MultiIndex):
            # Multiple tickers returned
            for symbol in ticker_symbols:
                if symbol in data.columns.levels[0]:
                    df_sym = data[symbol].copy()
                    if not df_sym.empty:
                        # Add source info
                        df_sym['source'] = 'yahoo'
                        result[symbol] = df_sym
        else:
            # Single ticker returned
            if len(ticker_symbols) == 1 and not data.empty:
                # Add source info
                data_copy = data.copy()
                data_copy['source'] = 'yahoo'
                result[ticker_symbols[0]] = data_copy
                
        return result
        
    except Exception as e:
        logger.error(f"Error fetching bulk data: {str(e)}")
        return {}

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