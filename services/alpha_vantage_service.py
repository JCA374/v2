# services/alpha_vantage_service.py
import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('alpha_vantage_service')

# Constants
CACHE_TTL = 7200  # 2 hour cache for API responses
MAX_RETRIES = 2   # Max retries for API calls
DEFAULT_DELAY = 15  # Default delay between API calls in seconds

# Define MockStock at the module level so it can be pickled


class MockStock:
    """Mock stock object to provide compatibility with yfinance Ticker objects"""

    def __init__(self, ticker, info):
        self.ticker = ticker
        self.info = info


def get_api_key():
    """Get Alpha Vantage API key from session state"""
    if 'alpha_vantage_api_key' in st.session_state:
        return st.session_state.alpha_vantage_api_key
    return None


@st.cache_data(ttl=CACHE_TTL)
def fetch_ticker_info(ticker):
    """
    Fetch basic information for a single ticker.
    
    Args:
        ticker (str): The ticker symbol
        
    Returns:
        tuple: (stock object, info dictionary)
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("Alpha Vantage API key not configured")

    logger.info(f"Alpha Vantage: Fetching company overview for {ticker}")

    for retry in range(MAX_RETRIES):
        try:
            url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={api_key}"
            response = requests.get(url)
            data = response.json()

            if "Information" in data and "API call frequency" in data["Information"]:
                # Rate limit hit
                wait_time = 60  # Wait 60 seconds for rate limit reset
                logger.warning(
                    f"Rate limit hit, waiting {wait_time}s before retry {retry+1}/{MAX_RETRIES}")
                time.sleep(wait_time)
                continue

            if "Symbol" not in data:
                raise ValueError(f"No data returned for {ticker}")

            # Format data to match Yahoo Finance service format
            info = {
                "symbol": data.get("Symbol"),
                "shortName": data.get("Name"),
                "longName": data.get("Name"),
                "sector": data.get("Sector"),
                "industry": data.get("Industry"),
                "marketCap": float(data.get("MarketCapitalization", 0)) if data.get("MarketCapitalization") else None,
                "trailingPE": float(data.get("PERatio", 0)) if data.get("PERatio") else None,
                "forwardPE": float(data.get("ForwardPE", 0)) if data.get("ForwardPE") else None,
                "dividendYield": float(data.get("DividendYield", 0)) if data.get("DividendYield") else None,
                "profitMargins": float(data.get("ProfitMargin", 0)) if data.get("ProfitMargin") else None,
                "revenueGrowth": float(data.get("QuarterlyRevenueGrowthYOY", 0)) if data.get("QuarterlyRevenueGrowthYOY") else None,
                "source": "alphavantage"  # Add source tracking
            }

            # Create a mock stock object using the module-level class
            stock = MockStock(ticker, info)
            return stock, info

        except Exception as e:
            logger.error(
                f"Error fetching Alpha Vantage company data for {ticker}: {str(e)}")
            if retry < MAX_RETRIES - 1:
                time.sleep(5 * (retry + 1))
            else:
                raise RuntimeError(
                    f"Failed to fetch Alpha Vantage data for {ticker}: {str(e)}")

    raise RuntimeError(
        f"Failed to fetch Alpha Vantage data for {ticker} after {MAX_RETRIES} retries")


@st.cache_data(ttl=CACHE_TTL)
def fetch_history(ticker, period="1y", interval="1wk"):
    """
    Fetch historical price data for a single ticker.
    
    Args:
        ticker (str): The ticker symbol
        period (str): Time period to fetch (e.g., "1y", "3mo", "5y")
        interval (str): Data interval (e.g., "1d", "1wk")
        
    Returns:
        DataFrame: Historical price data
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("Alpha Vantage API key not configured")

    logger.info(
        f"Alpha Vantage: Fetching history for {ticker} ({period}, {interval})")

    # Convert ticker object to symbol if needed
    if hasattr(ticker, 'ticker'):
        ticker = ticker.ticker

    # Convert Yahoo Finance interval format to Alpha Vantage format
    alpha_interval = {
        "1d": "daily",
        "1wk": "weekly",
        "1mo": "monthly"
    }.get(interval, "daily")

    # Alpha Vantage function based on interval
    function = {
        "daily": "TIME_SERIES_DAILY_ADJUSTED",
        "weekly": "TIME_SERIES_WEEKLY_ADJUSTED",
        "monthly": "TIME_SERIES_MONTHLY_ADJUSTED"
    }.get(alpha_interval)

    # Determine output size based on period
    output_size = "full" if period in ["5y", "10y"] else "compact"

    for retry in range(MAX_RETRIES):
        try:
            url = f"https://www.alphavantage.co/query?function={function}&symbol={ticker}&outputsize={output_size}&apikey={api_key}"
            response = requests.get(url)
            data = response.json()

            if "Information" in data and "API call frequency" in data["Information"]:
                # Rate limit hit
                wait_time = 60  # Wait 60 seconds for rate limit reset
                logger.warning(
                    f"Rate limit hit, waiting {wait_time}s before retry {retry+1}/{MAX_RETRIES}")
                time.sleep(wait_time)
                continue

            # Extract the time series data
            time_series_key = next(
                (k for k in data.keys() if "Time Series" in k), None)
            if not time_series_key or not data.get(time_series_key):
                raise ValueError(f"No time series data returned for {ticker}")

            time_series = data[time_series_key]

            # Convert to DataFrame
            df = pd.DataFrame.from_dict(time_series, orient='index')

            # Rename columns to match Yahoo Finance format
            column_map = {
                '1. open': 'Open',
                '2. high': 'High',
                '3. low': 'Low',
                '4. close': 'Close',
                '5. adjusted close': 'Adj Close',
                '6. volume': 'Volume',
                '7. dividend amount': 'Dividends',
                '8. split coefficient': 'Stock Splits'
            }

            # Only keep columns that exist
            valid_columns = {k: v for k,
                             v in column_map.items() if k in df.columns}
            df = df.rename(columns=valid_columns)

            # Convert values to numeric
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Convert index to datetime
            df.index = pd.to_datetime(df.index)

            # Sort by date (newest first to match Yahoo Finance)
            df = df.sort_index(ascending=False)

            # Limit data based on period
            if period == "1mo":
                df = df.iloc[:30]
            elif period == "3mo":
                df = df.iloc[:90]
            elif period == "6mo":
                df = df.iloc[:180]
            elif period == "1y":
                df = df.iloc[:365]
            elif period == "2y":
                df = df.iloc[:730]

            # Add source column for tracking
            df['source'] = 'alphavantage'

            return df

        except Exception as e:
            logger.error(
                f"Error fetching Alpha Vantage history for {ticker}: {str(e)}")
            if retry < MAX_RETRIES - 1:
                time.sleep(5 * (retry + 1))
            else:
                raise RuntimeError(
                    f"Failed to fetch Alpha Vantage history for {ticker}: {str(e)}")

    raise RuntimeError(
        f"Failed to fetch Alpha Vantage history for {ticker} after {MAX_RETRIES} retries")
