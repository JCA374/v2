"""
Script to load data for Swedish stocks into the Supabase database.
This creates a standardized dataset that can be used by all parts of the application.
"""
import pandas as pd
import time
import logging
import sys
import os
import toml
from datetime import datetime
import streamlit as st
from supabase import create_client

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.StreamHandler(),
                        logging.FileHandler("swedish_stocks_load.log")
                    ])
logger = logging.getLogger(__name__)

# List of Swedish stocks to load (with Yahoo Finance tickers)
SWEDISH_STOCKS = [
    "ERIC-B.ST",    # Ericsson
    "VOLV-B.ST",    # Volvo
    "SAND.ST",      # Sandvik
    "SEB-A.ST",     # SEB
    "ASSA-B.ST",    # ASSA ABLOY
    "ATCO-A.ST",    # Atlas Copco
    "SHB-A.ST",     # Handelsbanken
    "INVE-B.ST",    # Investor
    "EVO.ST",       # Evolution Gaming
    "SWED-A.ST"     # Swedbank
]

class SupabaseClientWrapper:
    """Simplified wrapper for Supabase client when running standalone scripts"""
    
    def __init__(self, supabase_url, supabase_key):
        """Initialize Supabase connection"""
        self.supabase = create_client(supabase_url, supabase_key)
        
    def save_fundamental_data(self, ticker, data, source='yahoo'):
        """Save fundamental data to Supabase"""
        try:
            # Prepare the data
            fundamental_data = {
                "ticker": ticker,
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
            
    def save_price_data(self, ticker, df, source='yahoo'):
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
                adj_close_val = row.get('Adj Close', row.get('adjusted_close', close_val))

                # Convert index to string date if needed
                if isinstance(idx, pd.Timestamp):
                    date_val = idx.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    date_val = str(idx)

                data_rows.append({
                    "ticker": ticker,
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
            batch_size = 50  # Process in smaller batches to avoid timeouts
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
                    time.sleep(0.2)

            logger.info(f"Saved {len(data_rows)} price data points for {ticker} ({timeframe})")
            return True
        except Exception as e:
            logger.error(f"Error saving price data: {e}")
            return False

def load_secrets():
    """Load Supabase credentials from secrets.toml"""
    secrets_path = os.path.join(os.path.dirname(__file__), 'secrets.toml')
    
    if os.path.exists(secrets_path):
        return toml.load(secrets_path)
    else:
        logger.error(f"secrets.toml not found at {secrets_path}")
        return None

def load_stocks_from_yahoo(stock_symbols, db):
    """
    Load stock data from Yahoo Finance and store in Supabase.
    
    Args:
        stock_symbols: List of stock symbols to load
        db: SupabaseClientWrapper instance
    """
    import yfinance as yf
    
    for symbol in stock_symbols:
        try:
            logger.info(f"Processing {symbol}")
            
            # 1. Get company information
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Extract and format the fundamental data
            fundamental_data = {
                "name": info.get("shortName", info.get("longName", symbol)),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "pe_ratio": info.get("trailingPE"),
                "market_cap": info.get("marketCap"),
                "dividend_yield": info.get("dividendYield"),
                "profit_margin": info.get("profitMargins"),
                "revenue_growth": info.get("revenueGrowth")
            }
            
            # 2. Save fundamental data to Supabase
            success = db.save_fundamental_data(symbol, fundamental_data, source="yahoo")
            logger.info(f"Saved fundamental data for {symbol}: {success}")
            
            # 3. Get historical price data for different timeframes
            timeframes = [
                {"interval": "1d", "period": "1y"},
                {"interval": "1wk", "period": "5y"},
                {"interval": "1mo", "period": "10y"}
            ]
            
            for tf in timeframes:
                interval, period = tf["interval"], tf["period"]
                logger.info(f"Fetching {interval} data for {period} for {symbol}")
                
                try:
                    # Get historical data from Yahoo Finance
                    hist = ticker.history(period=period, interval=interval)
                    
                    if hist is not None and not hist.empty:
                        # Set the interval attribute for reference
                        hist.attrs['interval'] = interval
                        
                        # Save to Supabase
                        success = db.save_price_data(symbol, hist, source="yahoo")
                        logger.info(f"Saved {interval} price data for {symbol}: {success}")
                    else:
                        logger.warning(f"No {interval} data available for {symbol}")
                        
                except Exception as e:
                    logger.error(f"Error fetching {interval} history for {symbol}: {str(e)}")
            
            # Delay to avoid rate limiting
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {str(e)}")

def main():
    """Main function to load stock data"""
    logger.info("Starting Swedish stocks data load")
    
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
        
        # Load stock data into Supabase
        load_stocks_from_yahoo(SWEDISH_STOCKS, db)
        
        logger.info("Completed loading Swedish stocks data")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()