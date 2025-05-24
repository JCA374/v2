"""
Find correct ticker formats for different stock data APIs.
This script tests different ticker format variations to find the correct one for Alpha Vantage.

Usage:
    python find_correct_tickers.py [--max=10] [--start=0] [--file=csv/updated_mid.csv]

Arguments:
    --max     Maximum number of tickers to test (default: all)
    --start   Start from this index in the CSV (default: 0)
    --file    CSV file with stock tickers (default: csv/updated_mid.csv)
"""
import requests
import pandas as pd
import json
import time
import os
import logging
import toml
import sys
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
    """
    Generate different possible formats for a stock ticker.
    
    Args:
        yahoo_ticker: Yahoo Finance ticker format
        
    Returns:
        List of possible format variations for Alpha Vantage
    """
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
    """
    Test if a ticker works with Alpha Vantage.
    
    Args:
        ticker: Alpha Vantage ticker symbol to test
        api_key: Alpha Vantage API key
        
    Returns:
        Tuple of (ticker, company_name, valid_status, status_code)
        Status code can be: "overview", "daily", "rate_limit", "invalid", or "error"
    """
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
    """
    Test if a ticker works with Yahoo Finance.
    
    Args:
        ticker: Yahoo ticker symbol to test
        
    Returns:
        Tuple of (ticker, company_name, valid_status)
    """
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
        
    Returns:
        List of dictionaries with ticker mappings
    """
    # Create results list
    results = []

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

        rate_limit_hits = 0
        wait_time = 60  # seconds to wait on rate limit

        # Process each ticker
        for i, (yahoo_ticker, company_name) in enumerate(zip(yahoo_tickers, company_names)):
            logger.info(
                f"Processing {i+1}/{len(yahoo_tickers)}: {yahoo_ticker} ({company_name})")

            # Check if Yahoo ticker is valid
            yahoo_result = test_yahoo_ticker(yahoo_ticker)
            valid_yahoo = yahoo_result[2]
            yahoo_company = yahoo_result[1] or company_name

            # Generate variations for Alpha Vantage
            variations = generate_format_variations(yahoo_ticker)

            # Find a working Alpha Vantage ticker
            valid_alpha = None
            alpha_company = None

            for variation in variations:
                # Check if we've hit rate limits too many times
                if rate_limit_hits >= 3:
                    logger.warning(
                        f"Hit rate limit 3 times, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    rate_limit_hits = 0

                # Test this variation
                alpha_result = test_alpha_vantage_ticker(variation, api_key)

                if alpha_result[3] == "rate_limit":
                    rate_limit_hits += 1
                    logger.warning(
                        f"Rate limit hit, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    # Retry this variation
                    alpha_result = test_alpha_vantage_ticker(
                        variation, api_key)

                if alpha_result[2]:  # Found a valid ticker
                    valid_alpha = alpha_result[0]
                    alpha_company = alpha_result[1]
                    logger.info(
                        f"Found valid Alpha Vantage ticker: {valid_alpha}")
                    break

                # Add a small delay between tests to avoid rate limits
                time.sleep(0.5)

            # Store the results
            results.append({
                "company_name": yahoo_company or alpha_company or company_name,
                "yahoo_ticker": yahoo_ticker,
                "yahoo_valid": valid_yahoo,
                "alpha_ticker": valid_alpha,
                "alpha_valid": valid_alpha is not None
            })

            # Save intermediate results to avoid losing progress
            if (i + 1) % 10 == 0:
                output_file = f"ticker_mapping_results_{start_from}_{i+1}.csv"
                pd.DataFrame(results).to_csv(output_file, index=False)
                logger.info(f"Saved intermediate results to {output_file}")

            # Add a delay between tickers to avoid rate limits
            time.sleep(2)

    except Exception as e:
        logger.error(f"Error processing CSV: {e}")

    return results


def main():
    """Main entry point for the script."""
    # Parse command line arguments
    max_tickers = None
    start_from = 0
    csv_file = "csv/updated_mid.csv"

    for arg in sys.argv[1:]:
        if arg.startswith("--max="):
            max_tickers = int(arg.split("=")[1])
        elif arg.startswith("--start="):
            start_from = int(arg.split("=")[1])
        elif arg.startswith("--file="):
            csv_file = arg.split("=")[1]

    # Load API key
    api_key = load_api_key()
    if not api_key:
        logger.error(
            "No Alpha Vantage API key found. Please add it to secrets.toml.")
        return

    # Find matching tickers
    results = find_matching_tickers(csv_file, api_key, max_tickers, start_from)

    # Save final results
    output_file = f"ticker_mapping_results_{start_from}.csv"
    pd.DataFrame(results).to_csv(output_file, index=False)
    logger.info(f"Saved final results to {output_file}")

    # Print summary
    if results:
        valid_yahoo = sum(1 for r in results if r["yahoo_valid"])
        valid_alpha = sum(1 for r in results if r["alpha_valid"])

        logger.info(f"Results Summary:")
        logger.info(f"Total tickers tested: {len(results)}")
        logger.info(
            f"Valid Yahoo tickers: {valid_yahoo} ({valid_yahoo/len(results)*100:.1f}%)")
        logger.info(
            f"Valid Alpha Vantage tickers: {valid_alpha} ({valid_alpha/len(results)*100:.1f}%)")

        # Create consolidated mapping file
        create_mapping_file(results)
    else:
        logger.warning("No results generated.")


def create_mapping_file(results):
    """Create a consolidated mapping file from results."""
    # Load any existing mapping files
    existing_files = [f for f in os.listdir() if f.startswith(
        "ticker_mapping_results_") and f.endswith(".csv")]

    all_results = []
    for file in existing_files:
        try:
            df = pd.read_csv(file)
            all_results.append(df)
        except Exception as e:
            logger.error(f"Error loading {file}: {e}")

    # Add current results
    all_results.append(pd.DataFrame(results))

    # Combine all results and drop duplicates
    if all_results:
        combined = pd.concat(all_results, ignore_index=True)
        combined = combined.drop_duplicates(subset=["yahoo_ticker"])

        # Filter to valid mappings only
        valid_mappings = combined[combined["alpha_valid"] == True].copy()

        # Keep only necessary columns and rename
        mapping_df = valid_mappings[["company_name",
                                     "yahoo_ticker", "alpha_ticker"]].copy()

        # Save final mapping file
        mapping_df.to_csv("ticker_mapping.csv", index=False)
        logger.info(
            f"Created consolidated mapping file with {len(mapping_df)} tickers")


if __name__ == "__main__":
    main()
