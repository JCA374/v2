"""
Utility script to look up stock ticker formats across different APIs.
Helps users understand the different ticker formats used by Yahoo Finance and Alpha Vantage.
"""
import os
import sys
import pandas as pd
import logging
import toml
import argparse
from services.ticker_mapping_service import TickerMappingService

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_secrets():
    """Load credentials from secrets.toml"""
    secrets_path = os.path.join(os.path.dirname(__file__), 'secrets.toml')

    if os.path.exists(secrets_path):
        return toml.load(secrets_path)
    else:
        logger.error(f"secrets.toml not found at {secrets_path}")
        return None


def search_company(query, ticker_mapper):
    """Search for a company by name or ticker."""
    results = ticker_mapper.search_companies(query)

    if results.empty:
        print(f"No results found for '{query}'")
        return []

    print(f"Found {len(results)} results for '{query}':")
    print(f"{'Company Name':<40} {'Yahoo Ticker':<15} {'Alpha Vantage Ticker':<20}")
    print("-" * 75)

    for _, row in results.iterrows():
        print(
            f"{row['company_name']:<40} {row['yahoo_ticker']:<15} {row['alpha_ticker']:<20}")

    return results


def lookup_ticker(ticker, ticker_mapper):
    """Look up ticker formats for all APIs."""
    company_data = ticker_mapper.get_company_data(ticker)

    print("\nTicker Format Information:")
    print(f"Company Name: {company_data['company_name']}")
    print(f"Yahoo Finance: {company_data['yahoo_ticker']}")
    print(f"Alpha Vantage: {company_data['alpha_ticker']}")

    # Validate the tickers
    yahoo_valid = ticker_mapper.validate_ticker(
        company_data['yahoo_ticker'], "yahoo")
    # Skip Alpha Vantage validation which requires API key and consumes quota
    alpha_valid = True

    print("\nValidation Status:")
    print(f"Yahoo Finance: {'✅ Valid' if yahoo_valid else '❌ Invalid'}")
    print(
        f"Alpha Vantage: {'⚠️ Not Verified (requires API call)' if alpha_valid else '❌ Invalid'}")

    return company_data


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Show ticker formats across different APIs')
    parser.add_argument('query', nargs='?',
                        help='Company name or ticker to look up')
    parser.add_argument('--search', '-s', action='store_true',
                        help='Search mode (find companies by name)')
    parser.add_argument('--csv', '-c', help='Load company data from CSV file')
    args = parser.parse_args()

    # Initialize ticker mapping service
    ticker_mapper = TickerMappingService()

    # Load companies from CSV if provided
    if args.csv:
        try:
            df = pd.read_csv(args.csv)

            if 'YahooTicker' in df.columns:
                company_name_col = 'CompanyName' if 'CompanyName' in df.columns else None
                count = 0

                for _, row in df.iterrows():
                    yahoo_ticker = row['YahooTicker']
                    company_name = row[company_name_col] if company_name_col else yahoo_ticker

                    # Add to mapping service
                    alpha_ticker = ticker_mapper._yahoo_to_alpha_format(
                        yahoo_ticker)
                    ticker_mapper.add_mapping(
                        company_name, yahoo_ticker, alpha_ticker)
                    count += 1

                print(f"Loaded {count} companies from {args.csv}")
            else:
                print(f"Error: CSV file must contain 'YahooTicker' column")
                sys.exit(1)
        except Exception as e:
            print(f"Error loading CSV: {e}")
            sys.exit(1)

    if not args.query:
        # Interactive mode
        while True:
            print("\n====== Stock Ticker Format Lookup ======")
            print("1. Search for company")
            print("2. Look up ticker")
            print("3. Exit")

            choice = input("Enter choice (1-3): ").strip()

            if choice == "1":
                query = input("Enter company name or partial ticker: ").strip()
                if query:
                    search_company(query, ticker_mapper)
            elif choice == "2":
                ticker = input("Enter ticker or company name: ").strip()
                if ticker:
                    lookup_ticker(ticker, ticker_mapper)
            elif choice == "3":
                break
            else:
                print("Invalid choice")
    else:
        # Command line mode
        if args.search:
            search_company(args.query, ticker_mapper)
        else:
            lookup_ticker(args.query, ticker_mapper)


if __name__ == "__main__":
    main()
