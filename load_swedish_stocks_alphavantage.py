"""
Script to load data for Swedish stocks into the Supabase database using Alpha Vantage API.
Updated version that uses the ticker mapping service to find correct ticker formats.
"""
import pandas as pd
import time
import logging
import sys
import os
import toml
import requests
from datetime import datetime, timedelta
from supabase import create_client

# Import our ticker mapping service
from services.ticker_mapping_service import TickerMappingService

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.StreamHandler(),
                        logging.FileHandler(
                            "swedish_stocks_alphavantage_load.log")
                    ])
logger = logging.getLogger(__name__)

# List of Swedish stocks to load with Yahoo Finance tickers
SWEDISH_STOCKS = [
    {"yahoo": "ERIC-B.ST", "name": "Ericsson"},
    {"yahoo": "VOLV-B.ST", "name": "Volvo"},
    {"yahoo": "SAND.ST", "name": "Sandvik"},
    {"yahoo": "SEB-A.ST", "name": "SEB"},
    {"yahoo": "ASSA-B.ST", "name": "ASSA ABLOY"},
    {"yahoo": "ATCO-A.ST", "name": "Atlas Copco"},
    {"yahoo": "SHB-A.ST", "name": "Handelsbanken"},
    {"yahoo": "INVE-B.ST", "name": "Investor"},
    {"yahoo": "EVO.ST", "name": "Evolution Gaming"},
    {"yahoo": "SWED-A.ST", "name": "Swedbank"}
]

# Alternatively, let's add some US stocks that we know work well with Alpha Vantage
US_STOCKS = [
    {"yahoo": "AAPL", "name": "Apple"},
    {"yahoo": "MSFT", "name": "Microsoft"},
    {"yahoo": "GOOGL", "name": "Google"},
    {"yahoo": "AMZN", "name": "Amazon"},
    {"yahoo": "NVDA", "name": "NVIDIA"}
]


class SupabaseClientWrapper:
    """Simplified wrapper for Supabase client when running standalone scripts"""

    def __init__(self, supabase_url, supabase_key):
        """Initialize Supabase connection"""
        self.supabase = create_client(supabase_url, supabase_key)

    def save_fundamental_data(self, ticker, data, source='alphavantage'):
        """Save fundamental data to Supabase"""
        try:
            # Prepare the data
            fundamental_data = {
                "ticker": ticker,  # Use Yahoo ticker format for consistency
                "name": data.get('name', ticker),
                "pe_ratio": data.get('pe_ratio'),
                "market_cap": data.get('market_cap'),
                "revenue_growth": data.get('revenue_growth'),
                "profit_margin": data.get('profit_margin'),
                "dividend_yield": data.get('dividend_yield'),
                "sector": data.get('sector'),
                "industry": data.get('industry'),
                "last_updated": datetime.now().isoformat(),
                "source": source
            }

            # Check if record exists
            response = self.supabase.table("stock_fundamentals") \
                .select("ticker") \
                .eq("ticker", ticker) \
                .execute()

            if response.data:
                # Update existing record
                self.supabase.table("stock_fundamentals") \
                    .update(fundamental_data) \
                    .eq("ticker", ticker) \
                    .execute()
            else:
                # Insert new record
                self.supabase.table("stock_fundamentals") \
                    .insert(fundamental_data) \
                    .execute()

            logger.info(f"Saved fundamental data for {ticker}")
            return True
        except Exception as e:
            logger.error(f"Error saving fundamental data: {e}")
            return False

    def save_price_data(self, ticker, df, source='alphavantage'):
        """Save price data to Supabase"""
        if df is None or df.empty:
            return False

        try:
            # Get the timeframe/interval from DataFrame attributes or default to '1d'
            timeframe = getattr(df, 'attrs', {}).get('interval', '1d')

            # Prepare data for insertion
            data_rows = []
            for idx, row in df.iterrows():
                # Handle different column naming conventions
                open_val = row.get('Open', row.get('open', None))
                high_val = row.get('High', row.get('high', None))
                low_val = row.get('Low', row.get('low', None))
                close_val = row.get('Close', row.get('close', None))
                volume_val = row.get('Volume', row.get('volume', None))
                adj_close_val = row.get(
                    'Adj Close', row.get('adjusted_close', close_val))

                # Convert index to string date if needed
                if isinstance(idx, pd.Timestamp):
                    date_val = idx.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    date_val = str(idx)

                data_rows.append({
                    "ticker": ticker,  # Use Yahoo ticker format for consistency
                    "date": date_val,
                    "timeframe": timeframe,
                    "open": float(open_val) if open_val is not None else None,
                    "high": float(high_val) if high_val is not None else None,
                    "low": float(low_val) if low_val is not None else None,
                    "close": float(close_val) if close_val is not None else None,
                    "volume": int(volume_val) if volume_val is not None else None,
                    "adjusted_close": float(adj_close_val) if adj_close_val is not None else None,
                    "last_updated": datetime.now().isoformat(),
                    "source": source
                })

            # Get existing dates for this ticker and timeframe
            response = self.supabase.table("stock_prices") \
                .select("date") \
                .eq("ticker", ticker) \
                .eq("timeframe", timeframe) \
                .execute()

            existing_dates = [row['date'] for row in response.data]

            # Process each row - either update or insert
            batch_size = 25  # Process in smaller batches to avoid timeouts
            for i in range(0, len(data_rows), batch_size):
                batch = data_rows[i:i+batch_size]

                for row in batch:
                    if row['date'] in existing_dates:
                        # Delete existing row
                        self.supabase.table("stock_prices") \
                            .delete() \
                            .eq("ticker", ticker) \
                            .eq("date", row['date']) \
                            .eq("timeframe", timeframe) \
                            .execute()

                    # Insert new row
                    self.supabase.table("stock_prices").insert(row).execute()

                # Sleep briefly between batches to avoid overloading the API
                if i + batch_size < len(data_rows):
                    time.sleep(0.5)

            logger.info(
                f"Saved {len(data_rows)} price data points for {ticker} ({timeframe})")
            return True
        except Exception as e:
            logger.error(f"Error saving price data: {e}")
            return False


def load_secrets():
    """Load credentials from secrets.toml"""
    secrets_path = os.path.join(os.path.dirname(__file__), 'secrets.toml')

    if os.path.exists(secrets_path):
        return toml.load(secrets_path)
    else:
        logger.error(f"secrets.toml not found at {secrets_path}")
        return None


def fetch_company_overview(api_key, ticker):
    """
    Fetch company overview data from Alpha Vantage API.
    
    Args:
        api_key: Alpha Vantage API key
        ticker: Stock ticker symbol in Alpha Vantage format
        
    Returns:
        Dictionary with company data or None if failed
    """
    logger.info(f"Fetching company overview for {ticker}")

    url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={api_key}"

    try:
        response = requests.get(url)
        data = response.json()

        # Check if we got valid data
        if "Symbol" in data and data["Symbol"]:
            logger.info(f"Successfully fetched overview for {ticker}")

            # Extract and format the fundamental data
            fundamental_data = {
                "name": data.get("Name", ticker),
                "sector": data.get("Sector"),
                "industry": data.get("Industry"),
                "pe_ratio": float(data.get("PERatio", 0)) if data.get("PERatio") else None,
                "market_cap": float(data.get("MarketCapitalization", 0)) if data.get("MarketCapitalization") else None,
                "dividend_yield": float(data.get("DividendYield", 0)) if data.get("DividendYield") else None,
                "profit_margin": float(data.get("ProfitMargin", 0)) if data.get("ProfitMargin") else None,
                "revenue_growth": None  # Alpha Vantage doesn't provide this directly
            }

            return fundamental_data
        else:
            logger.error(
                f"Failed to get company overview for {ticker}: {data}")
            return None

    except Exception as e:
        logger.error(f"Error fetching company overview for {ticker}: {e}")
        return None


def fetch_daily_prices(api_key, ticker, output_size='compact'):
    """
    Fetch daily price data from Alpha Vantage.
    
    Args:
        api_key: Alpha Vantage API key
        ticker: Stock ticker symbol in Alpha Vantage format
        output_size: 'compact' (last 100 data points) or 'full' (up to 20 years)
        
    Returns:
        DataFrame with price data or None if failed
    """
    logger.info(f"Fetching daily prices for {ticker}")

    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&outputsize={output_size}&apikey={api_key}"

    try:
        response = requests.get(url)
        data = response.json()

        # Check if we got valid data
        if "Time Series (Daily)" in data:
            time_series = data["Time Series (Daily)"]

            # Convert to DataFrame
            df = pd.DataFrame.from_dict(time_series, orient='index')

            # Rename columns
            df = df.rename(columns={
                '1. open': 'Open',
                '2. high': 'High',
                '3. low': 'Low',
                '4. close': 'Close',
                '5. volume': 'Volume'
            })

            # Add Adj Close (same as Close for this API)
            df['Adj Close'] = df['Close']

            # Convert data types
            for col in ['Open', 'High', 'Low', 'Close', 'Adj Close']:
                df[col] = pd.to_numeric(df[col])

            df['Volume'] = pd.to_numeric(df['Volume'], downcast='integer')

            # Convert index to datetime
            df.index = pd.to_datetime(df.index)

            # Sort by date
            df = df.sort_index()

            # Set interval attribute
            df.attrs['interval'] = '1d'

            logger.info(f"Got {len(df)} daily price records for {ticker}")
            return df
        else:
            logger.error(f"Failed to get daily prices for {ticker}: {data}")
            return None

    except Exception as e:
        logger.error(f"Error fetching daily prices for {ticker}: {e}")
        return None


def fetch_weekly_prices(api_key, ticker):
    """
    Fetch weekly price data from Alpha Vantage.
    
    Args:
        api_key: Alpha Vantage API key
        ticker: Stock ticker symbol in Alpha Vantage format
        
    Returns:
        DataFrame with price data or None if failed
    """
    logger.info(f"Fetching weekly prices for {ticker}")

    # For some reason, Alpha Vantage doesn't seem to support weekly data for many international stocks
    # Let's try using the standard TIME_SERIES_WEEKLY endpoint instead of adjusted
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_WEEKLY&symbol={ticker}&apikey={api_key}"

    try:
        response = requests.get(url)
        data = response.json()

        # Check if we got valid data
        if "Weekly Time Series" in data:
            time_series = data["Weekly Time Series"]

            # Convert to DataFrame
            df = pd.DataFrame.from_dict(time_series, orient='index')

            # Rename columns
            df = df.rename(columns={
                '1. open': 'Open',
                '2. high': 'High',
                '3. low': 'Low',
                '4. close': 'Close',
                '5. volume': 'Volume'
            })

            # Add Adj Close (same as Close for this API)
            df['Adj Close'] = df['Close']

            # Convert data types
            for col in ['Open', 'High', 'Low', 'Close', 'Adj Close']:
                df[col] = pd.to_numeric(df[col])

            df['Volume'] = pd.to_numeric(df['Volume'], downcast='integer')

            # Convert index to datetime
            df.index = pd.to_datetime(df.index)

            # Sort by date
            df = df.sort_index()

            # Set interval attribute
            df.attrs['interval'] = '1wk'

            logger.info(f"Got {len(df)} weekly price records for {ticker}")
            return df
        else:
            logger.error(f"Failed to get weekly prices for {ticker}: {data}")
            return None

    except Exception as e:
        logger.error(f"Error fetching weekly prices for {ticker}: {e}")
        return None


def fetch_monthly_prices(api_key, ticker):
    """
    Fetch monthly price data from Alpha Vantage.
    
    Args:
        api_key: Alpha Vantage API key
        ticker: Stock ticker symbol in Alpha Vantage format
        
    Returns:
        DataFrame with price data or None if failed
    """
    logger.info(f"Fetching monthly prices for {ticker}")

    # For some reason, Alpha Vantage doesn't seem to support monthly data for many international stocks
    # Let's try using the standard TIME_SERIES_MONTHLY endpoint instead of adjusted
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY&symbol={ticker}&apikey={api_key}"

    try:
        response = requests.get(url)
        data = response.json()

        # Check if we got valid data
        if "Monthly Time Series" in data:
            time_series = data["Monthly Time Series"]

            # Convert to DataFrame
            df = pd.DataFrame.from_dict(time_series, orient='index')

            # Rename columns
            df = df.rename(columns={
                '1. open': 'Open',
                '2. high': 'High',
                '3. low': 'Low',
                '4. close': 'Close',
                '5. volume': 'Volume'
            })

            # Add Adj Close (same as Close for this API)
            df['Adj Close'] = df['Close']

            # Convert data types
            for col in ['Open', 'High', 'Low', 'Close', 'Adj Close']:
                df[col] = pd.to_numeric(df[col])

            df['Volume'] = pd.to_numeric(df['Volume'], downcast='integer')

            # Convert index to datetime
            df.index = pd.to_datetime(df.index)

            # Sort by date
            df = df.sort_index()

            # Set interval attribute
            df.attrs['interval'] = '1mo'

            logger.info(f"Got {len(df)} monthly price records for {ticker}")
            return df
        else:
            logger.error(f"Failed to get monthly prices for {ticker}: {data}")
            return None

    except Exception as e:
        logger.error(f"Error fetching monthly prices for {ticker}: {e}")
        return None


def load_stocks_from_alphavantage(stock_list, api_key, db, ticker_mapper):
    """
    Load stock data from Alpha Vantage API and store in Supabase.
    
    Args:
        stock_list: List of stock dictionary objects with yahoo tickers and names
        api_key: Alpha Vantage API key
        db: SupabaseClientWrapper instance
        ticker_mapper: TickerMappingService instance
    """
    # Track API calls to respect rate limits (5 calls per minute for free tier)
    call_count = 0
    call_start_time = time.time()

    for stock in stock_list:
        yahoo_ticker = stock['yahoo']
        company_name = stock.get('name', yahoo_ticker)

        try:
            # Get the Alpha Vantage ticker using the mapping service
            alpha_ticker = ticker_mapper.get_ticker(
                yahoo_ticker, source="alphavantage")

            if not alpha_ticker:
                logger.warning(
                    f"No Alpha Vantage ticker mapping found for {yahoo_ticker}")
                alpha_ticker = yahoo_ticker  # Fallback to using Yahoo ticker format

            logger.info(
                f"Processing {yahoo_ticker} (Alpha Vantage: {alpha_ticker})")

            # Check if we need to wait for rate limits
            current_time = time.time()
            if call_count >= 5 and current_time - call_start_time < 65:
                wait_time = 65 - (current_time - call_start_time)
                logger.info(
                    f"Waiting {wait_time:.1f} seconds to respect API rate limits...")
                time.sleep(wait_time)
                call_count = 0
                call_start_time = time.time()

            # 1. Get company overview
            fundamental_data = fetch_company_overview(api_key, alpha_ticker)
            call_count += 1

            if fundamental_data:
                # Add name from our list if not provided by API
                if not fundamental_data.get('name') or fundamental_data['name'] == alpha_ticker:
                    fundamental_data['name'] = company_name

                # Save fundamental data using Yahoo ticker for consistency
                success = db.save_fundamental_data(
                    yahoo_ticker, fundamental_data, source="alphavantage")
                logger.info(
                    f"Saved fundamental data for {yahoo_ticker}: {success}")
            else:
                # If company info failed, use the name from our list
                backup_data = {
                    "name": company_name,
                    "sector": "Unknown",
                    "industry": "Unknown"
                }
                logger.info(f"Using backup data for {yahoo_ticker}")
                db.save_fundamental_data(
                    yahoo_ticker, backup_data, source="alphavantage")

            # Check if we need to wait for rate limits again
            current_time = time.time()
            if call_count >= 5 and current_time - call_start_time < 65:
                wait_time = 65 - (current_time - call_start_time)
                logger.info(
                    f"Waiting {wait_time:.1f} seconds to respect API rate limits...")
                time.sleep(wait_time)
                call_count = 0
                call_start_time = time.time()

            # 2. Get daily price data
            daily_data = fetch_daily_prices(api_key, alpha_ticker)
            call_count += 1

            if daily_data is not None and not daily_data.empty:
                success = db.save_price_data(
                    yahoo_ticker, daily_data, source="alphavantage")
                logger.info(
                    f"Saved daily price data for {yahoo_ticker}: {success}")

            # Check if we need to wait for rate limits again
            current_time = time.time()
            if call_count >= 5 and current_time - call_start_time < 65:
                wait_time = 65 - (current_time - call_start_time)
                logger.info(
                    f"Waiting {wait_time:.1f} seconds to respect API rate limits...")
                time.sleep(wait_time)
                call_count = 0
                call_start_time = time.time()

            # 3. Get weekly price data
            weekly_data = fetch_weekly_prices(api_key, alpha_ticker)
            call_count += 1

            if weekly_data is not None and not weekly_data.empty:
                success = db.save_price_data(
                    yahoo_ticker, weekly_data, source="alphavantage")
                logger.info(
                    f"Saved weekly price data for {yahoo_ticker}: {success}")

            # Check if we need to wait for rate limits again
            current_time = time.time()
            if call_count >= 5 and current_time - call_start_time < 65:
                wait_time = 65 - (current_time - call_start_time)
                logger.info(
                    f"Waiting {wait_time:.1f} seconds to respect API rate limits...")
                time.sleep(wait_time)
                call_count = 0
                call_start_time = time.time()

            # 4. Get monthly price data
            monthly_data = fetch_monthly_prices(api_key, alpha_ticker)
            call_count += 1

            if monthly_data is not None and not monthly_data.empty:
                success = db.save_price_data(
                    yahoo_ticker, monthly_data, source="alphavantage")
                logger.info(
                    f"Saved monthly price data for {yahoo_ticker}: {success}")

            # Allow a bit of time between stocks
            time.sleep(2)

        except Exception as e:
            logger.error(f"Error processing {yahoo_ticker}: {str(e)}")

        # Log completion
        logger.info(f"Completed processing {yahoo_ticker}")


def main():
    """Main function to load stock data"""
    logger.info("Starting stock data load using Alpha Vantage API")

    # Load secrets
    secrets = load_secrets()
    if not secrets:
        logger.error("Failed to load secrets")
        sys.exit(1)

    # Extract credentials
    supabase_url = secrets.get("supabase_url")
    supabase_key = secrets.get("supabase_key")
    alpha_vantage_api_key = secrets.get("alpha_vantage_api_key")

    if not supabase_url or not supabase_key:
        logger.error("Supabase credentials not found in secrets.toml")
        sys.exit(1)

    if not alpha_vantage_api_key:
        logger.error("Alpha Vantage API key not found in secrets.toml")
        sys.exit(1)

    # Initialize Supabase connection
    try:
        logger.info("Connecting to Supabase")
        db = SupabaseClientWrapper(supabase_url, supabase_key)

        if not db.supabase:
            logger.error("Failed to connect to Supabase")
            sys.exit(1)

        # Initialize ticker mapping service
        logger.info("Initializing ticker mapping service")
        ticker_mapper = TickerMappingService()

        logger.info("Connected to Supabase successfully")

        # Ask user which stocks to load
        print("\nChoose which stocks to load:")
        print("1. US Stocks (5 stocks)")
        print("2. Swedish Stocks (10 stocks)")
        print("3. All Stocks (15 stocks)")
        print("4. Load from CSV file")

        choice = input("Enter choice (1-4): ").strip()

        if choice == "1":
            logger.info("Loading US stocks")
            load_stocks_from_alphavantage(
                US_STOCKS, alpha_vantage_api_key, db, ticker_mapper)
        elif choice == "2":
            logger.info("Loading Swedish stocks")
            load_stocks_from_alphavantage(
                SWEDISH_STOCKS, alpha_vantage_api_key, db, ticker_mapper)
        elif choice == "3":
            logger.info("Loading all stocks")
            all_stocks = US_STOCKS + SWEDISH_STOCKS
            load_stocks_from_alphavantage(
                all_stocks, alpha_vantage_api_key, db, ticker_mapper)
        elif choice == "4":
            # Load from CSV
            csv_file = input("Enter CSV file path: ").strip()
            if not csv_file:
                csv_file = "csv/updated_mid.csv"

            try:
                df = pd.read_csv(csv_file)

                # Check required columns
                if 'YahooTicker' not in df.columns:
                    logger.error(
                        f"CSV file {csv_file} does not contain YahooTicker column")
                    sys.exit(1)

                # Create stock list from CSV data
                company_name_col = 'CompanyName' if 'CompanyName' in df.columns else None
                csv_stocks = []

                for _, row in df.iterrows():
                    stock = {
                        "yahoo": row['YahooTicker'],
                        "name": row[company_name_col] if company_name_col else row['YahooTicker']
                    }
                    csv_stocks.append(stock)

                # Limit to first 10 if many
                if len(csv_stocks) > 10:
                    print(
                        f"CSV has {len(csv_stocks)} stocks. Loading first 10 only.")
                    print("Press Y to continue or N to cancel.")
                    proceed = input().strip().upper()
                    if proceed != 'Y':
                        sys.exit(0)
                    csv_stocks = csv_stocks[:10]

                logger.info(f"Loading {len(csv_stocks)} stocks from CSV")
                load_stocks_from_alphavantage(
                    csv_stocks, alpha_vantage_api_key, db, ticker_mapper)
            except Exception as e:
                logger.error(f"Error loading CSV: {e}")
                sys.exit(1)
        else:
            logger.error("Invalid choice")
            sys.exit(1)

        logger.info("Completed loading stock data")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
