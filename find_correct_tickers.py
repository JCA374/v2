"""
Find correct ticker formats for different stock data APIs.
This script tests different ticker format variations to find the correct one for Alpha Vantage.
"""
import requests
import pandas as pd
import json
import time
import os
import logging
import toml
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.StreamHandler(),
                        logging.FileHandler("ticker_mapping.log")
                    ])
logger = logging.getLogger(__name__)

# Load API key from secrets.toml


def load_api_key():
    try:
        secrets_path = os.path.join(os.path.dirname(__file__), 'secrets.toml')
        if os.path.exists(secrets_path):
            secrets = toml.load(secrets_path)
            return secrets.get("alpha_vantage_api_key", "")
    except Exception as e:
        logger.error(f"Error loading API key: {e}")
    return ""

# Format variations to try for Alpha Vantage


def generate_format_variations(yahoo_ticker):
    """Generate different possible formats for a stock ticker."""
    variations = []

    # Original format
    variations.append(yahoo_ticker)

    # Remove .ST for Swedish stocks
    if yahoo_ticker.endswith(".ST"):
        base = yahoo_ticker.replace(".ST", "")
        variations.append(base)

        # Remove dash too
        if "-" in base:
            variations.append(base.replace("-", ""))

        # Try .STO instead of .ST
        variations.append(base + ".STO")

        # Try just part before the dash
        if "-" in base:
            variations.append(base.split("-")[0])

        # Try symbol format ERICB:STO
        if "-" in base:
            base_no_dash = base.replace("-", "")
            variations.append(f"{base_no_dash}:STO")

    # For non-Swedish stocks, try some variations just in case
    else:
        # Try with : separators
        if "." in yahoo_ticker:
            parts = yahoo_ticker.split(".")
            variations.append(f"{parts[0]}:{parts[1]}")

    return variations


def test_alpha_vantage_ticker(ticker, api_key):
    """Test if a ticker works with Alpha Vantage."""
    # First test the company overview endpoint (doesn't consume much API quota)
    url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={api_key}"

    try:
        response = requests.get(url, timeout=5)
        data = response.json()

        # Check if data contains Symbol field
        if "Symbol" in data:
            logger.info(
                f"✅ Found valid Alpha Vantage ticker: {ticker} -> {data.get('Name', 'Unknown')}")
            return ticker, data.get("Name", "Unknown"), True, "overview"

        # If we got an error about API call frequency, we need to wait
        if "Information" in data and "call frequency" in data.get("Information", ""):
            logger.warning(f"Rate limit hit for {ticker}. Need to wait.")
            return ticker, None, False, "rate_limit"

        # If OVERVIEW doesn't work, try TIME_SERIES_DAILY which works for more tickers
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={api_key}"
        response = requests.get(url, timeout=5)
        data = response.json()

        if "Time Series (Daily)" in data:
            logger.info(
                f"✅ Found valid Alpha Vantage ticker (daily): {ticker}")
            return ticker, "Unknown", True, "daily"

        # If we got an error about API call frequency, we need to wait
        if "Information" in data and "call frequency" in data.get("Information", ""):
            logger.warning(
                f"Rate limit hit for {ticker} in daily check. Need to wait.")
            return ticker, None, False, "rate_limit"

        logger.warning(f"❌ Invalid Alpha Vantage ticker: {ticker}")
        return ticker, None, False, "invalid"

    except Exception as e:
        logger.error(f"Error testing Alpha Vantage ticker {ticker}: {e}")
        return ticker, None, False, "error"


def test_yahoo_ticker(ticker):
    """Test if a ticker works with Yahoo Finance."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        response = requests.get(url, timeout=5)
        data = response.json()

        # Check if data contains error or valid chart data
        if "chart" in data and "result" in data["chart"] and data["chart"]["result"] is not None:
            # Try to get company name
            company_name = None
            try:
                meta = data["chart"]["result"][0]["meta"]
                company_name = meta.get("shortName", "Unknown")
            except:
                pass

            logger.info(f"✅ Valid Yahoo ticker: {ticker} -> {company_name}")
            return ticker, company_name, True
        else:
            logger.warning(f"❌ Invalid Yahoo ticker: {ticker}")
            return ticker, None, False
    except Exception as e:
        logger.error(f"Error testing Yahoo ticker {ticker}: {e}")
        return ticker, None, False


def find_matching_tickers(csv_file, api_key, max_tickers=None, start_from=0):
    """
    Test tickers from a CSV file and find matching formats for different APIs.

    Args:
        csv_file: Path to CSV file with Yahoo tickers
        api_key: Alpha Vantage API key
        max_tickers: Maximum number of tickers to test (None = all)
        start_from: Start from this index in the CSV
    """
    try:
        # Load the CSV file
        df = pd.read_csv(csv_file)

        # Ensure YahooTicker column exists
        if 'YahooTicker' not in df.columns:
            logger.error(
                f"CSV file {csv_file} does not contain YahooTicker column")
            return []

        # Extract relevant columns
        yahoo_tickers = df['YahooTicker'].tolist()
        company_names = df['CompanyName'].tolist() if 'CompanyName' in df.columns else [
            "Unknown"] * len(yahoo_tickers)

        # Limit tickers if specified
        if max_tickers is not None:
            yahoo_tickers = yahoo_tickers[start_from:start_from + max_tickers]
            company_names = company_names[start_from:start_from + max_tickers]

        logger.info(f"Testing {len(yahoo_tickers)} tickers from {csv_file}")

        # Create results list
        results = []
        rate_limit_hits = 0
        wait_time = 60  # seconds to wait on rate limit

        # Process each ticker
        for i, (yahoo_ticker, company_name) in enumerate(zip(yahoo_tickers, company_names)):
            logger.info(f"Processing {i+1}/{len
