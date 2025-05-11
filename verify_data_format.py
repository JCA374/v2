"""
Verify that data stored in Supabase follows the standard format
regardless of the original data source (Yahoo Finance, Alpha Vantage, etc.)
"""
import pandas as pd
import logging
import os
import sys
import toml
from datetime import datetime, timedelta
from supabase import create_client

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SupabaseClientWrapper:
    """Simplified wrapper for Supabase client to retrieve data"""
    
    def __init__(self, supabase_url, supabase_key):
        """Initialize Supabase connection"""
        self.supabase = create_client(supabase_url, supabase_key)
        
    def get_fundamental_data(self, ticker):
        """Get fundamental data from Supabase"""
        try:
            response = self.supabase.table("stock_fundamentals") \
                .select("*") \
                .eq("ticker", ticker) \
                .execute()

            if not response.data:
                return None

            # Return the first (and should be only) result
            return response.data[0]
        except Exception as e:
            logger.error(f"Error getting fundamental data: {e}")
            return None
            
    def get_price_data(self, ticker, timeframe='1d', period='1y'):
        """Get price data from Supabase"""
        try:
            # Calculate start date based on period
            end_date = datetime.now()

            if period == '1mo':
                start_date = end_date - timedelta(days=30)
            elif period == '3mo':
                start_date = end_date - timedelta(days=90)
            elif period == '6mo':
                start_date = end_date - timedelta(days=180)
            elif period == '1y':
                start_date = end_date - timedelta(days=365)
            elif period == '2y':
                start_date = end_date - timedelta(days=730)
            elif period == '5y':
                start_date = end_date - timedelta(days=1825)
            elif period == '10y':
                start_date = end_date - timedelta(days=3650)
            else:
                start_date = end_date - timedelta(days=365)  # Default to 1 year

            # Format dates for query
            start_str = start_date.strftime('%Y-%m-%d')

            # Query Supabase
            response = self.supabase.table("stock_prices") \
                .select("*") \
                .eq("ticker", ticker) \
                .eq("timeframe", timeframe) \
                .gte("date", start_str) \
                .order("date") \
                .execute()

            if not response.data:
                return None

            # Convert to DataFrame
            df = pd.DataFrame(response.data)

            # Set date as index
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')

            # Rename columns to match expected format
            df = df.rename(columns={
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume',
                'adjusted_close': 'Adj Close'
            })

            # Set interval attribute for compatibility
            df.attrs['interval'] = timeframe

            return df
        except Exception as e:
            logger.error(f"Error getting price data: {e}")
            return None

def load_secrets():
    """Load Supabase credentials from secrets.toml"""
    secrets_path = os.path.join(os.path.dirname(__file__), 'secrets.toml')
    
    if os.path.exists(secrets_path):
        return toml.load(secrets_path)
    else:
        logger.error(f"secrets.toml not found at {secrets_path}")
        return None

def check_data_format(symbol, db):
    """Check data format for a stock symbol"""
    logger.info(f"Checking data format for {symbol}")
    
    # Check fundamental data
    fundamental = db.get_fundamental_data(symbol)
    if fundamental:
        print(f"\n--- Fundamental data for {symbol} ---")
        # Check that all expected fields are present
        expected_fields = [
            "ticker", "name", "sector", "industry", "pe_ratio", 
            "market_cap", "dividend_yield", "profit_margin", 
            "revenue_growth", "last_updated", "source"
        ]
        
        # Verify fields
        present_fields = []
        missing_fields = []
        for field in expected_fields:
            if field in fundamental:
                present_fields.append(field)
            else:
                missing_fields.append(field)
        
        print(f"Fields present: {', '.join(present_fields)}")
        if missing_fields:
            print(f"Fields missing: {', '.join(missing_fields)}")
        
        # Print some sample data
        for key in present_fields[:6]:  # Show first 6 fields
            print(f"{key}: {fundamental[key]}")
    else:
        print(f"No fundamental data for {symbol}")
    
    # Check price data in standard timeframes
    timeframes = ["1d", "1wk", "1mo"]
    periods = ["1y"]  # Just check 1y for simplicity
    
    for interval in timeframes:
        for period in periods:
            price_data = db.get_price_data(symbol, interval, period)
            
            if price_data is not None and not price_data.empty:
                print(f"\n--- Price data for {symbol} ({interval}, {period}) ---")
                
                # Verify expected columns are present
                expected_columns = ["Open", "High", "Low", "Close", "Volume", "Adj Close"]
                present_columns = []
                missing_columns = []
                
                for col in expected_columns:
                    if col in price_data.columns:
                        present_columns.append(col)
                    else:
                        missing_columns.append(col)
                
                print(f"Columns present: {', '.join(present_columns)}")
                if missing_columns:
                    print(f"Columns missing: {', '.join(missing_columns)}")
                
                # Print sample data
                print("Data shape:", price_data.shape)
                print("Index type:", type(price_data.index).__name__)
                if len(price_data) > 0:
                    print("First row sample:")
                    first_row = price_data.iloc[0]
                    print(f"  Open: {first_row.get('Open')}")
                    print(f"  High: {first_row.get('High')}")
                    print(f"  Low: {first_row.get('Low')}")
                    print(f"  Close: {first_row.get('Close')}")
                
                # Verify interval attribute
                if hasattr(price_data, 'attrs') and 'interval' in price_data.attrs:
                    print(f"Interval attribute: {price_data.attrs['interval']}")
                else:
                    print("Missing interval attribute")
            else:
                print(f"No price data for {symbol} ({interval}, {period})")

def main():
    """Main function to verify data formats"""
    # Load secrets
    secrets = load_secrets()
    if not secrets:
        logger.error("Failed to load secrets")
        sys.exit(1)
    
    # Extract Supabase credentials
    supabase_url = secrets.get("supabase_url")
    supabase_key = secrets.get("supabase_key")
    
    if not supabase_url or not supabase_key:
        logger.error("Supabase credentials not found in secrets.toml")
        sys.exit(1)
    
    # Initialize Supabase connection
    try:
        logger.info("Connecting to Supabase")
        db = SupabaseClientWrapper(supabase_url, supabase_key)
        
        if not db.supabase:
            logger.error("Failed to connect to Supabase")
            sys.exit(1)
        
        logger.info("Connected to Supabase successfully")
        
        # Test with both Swedish and US stocks
        symbols = ["ERIC-B.ST", "AAPL"]
        
        for symbol in symbols:
            check_data_format(symbol, db)
            print("\n" + "="*60 + "\n")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()