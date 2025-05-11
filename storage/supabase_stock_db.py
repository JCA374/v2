import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from supabase import create_client

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stock_app")


class SupabaseStockDB:
    """
    Supabase database connector for shared stock data.
    Uses Supabase's free tier PostgreSQL database.
    """

    def __init__(self):
        """Initialize Supabase connection"""
        self.supabase = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Connect to Supabase"""
        try:
            # Get connection parameters from Streamlit secrets
            supabase_url = st.secrets.get("supabase_url", "")
            supabase_key = st.secrets.get("supabase_key", "")

            if not supabase_url or not supabase_key:
                raise ValueError(
                    "Supabase URL and key must be provided in secrets")

            # Connect to Supabase
            self.supabase = create_client(supabase_url, supabase_key)
            logger.info("Supabase connection established")
            return True
        except Exception as e:
            logger.error(f"Supabase connection error: {e}")
            return False

    def create_tables(self):
        """
        Create necessary tables if they don't exist.
        
        Note: In Supabase, you need to create tables through the dashboard
        or SQL editor first. This function just checks if they exist.
        """
        if not self.supabase:
            return False

        try:
            # Check if tables exist by attempting a simple query
            self.supabase.table("stock_prices").select(
                "ticker").limit(1).execute()
            self.supabase.table("stock_fundamentals").select(
                "ticker").limit(1).execute()
            self.supabase.table("company_mappings").select(
                "id").limit(1).execute()

            logger.info("Tables exist in Supabase")
            return True
        except Exception as e:
            logger.error(f"Error checking tables: {e}")
            logger.warning(
                "Please create tables manually in Supabase dashboard")
            return False

    def save_price_data(self, ticker, df, source='yahoo'):
        """
        Save price data to Supabase
        
        Args:
            ticker: Stock ticker symbol
            df: DataFrame with price data
            source: Data source (e.g., 'yahoo', 'alphavantage')
            
        Returns:
            Success status (boolean)
        """
        if df is None or df.empty or not self.supabase:
            return False

        try:
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

                # Get timeframe from DataFrame attributes or default to '1d'
                timeframe = getattr(df, 'attrs', {}).get('interval', '1d')

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

            # Supabase doesn't support native upsert the same way as PostgreSQL
            # Handle this by deleting existing rows and inserting new ones
            # First, get all existing dates for this ticker and timeframe
            response = self.supabase.table("stock_prices") \
                .select("date") \
                .eq("ticker", ticker) \
                .eq("timeframe", timeframe) \
                .execute()

            existing_dates = [row['date'] for row in response.data]

            # For each data point, either delete and insert or just insert
            for row in data_rows:
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

            logger.info(
                f"Saved {len(data_rows)} price data points for {ticker}")
            return True

        except Exception as e:
            logger.error(f"Error saving price data: {e}")
            return False

    def get_price_data(self, ticker, timeframe='1d', period='1y'):
        """
        Get price data from Supabase
        
        Args:
            ticker: Stock ticker symbol
            timeframe: Data interval (e.g., '1d', '1wk')
            period: Time period (e.g., '1mo', '1y')
            
        Returns:
            DataFrame with price data or None if not found
        """
        if not self.supabase:
            return None

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
            else:
                start_date = end_date - \
                    timedelta(days=365)  # Default to 1 year

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

    def save_fundamental_data(self, ticker, data, source='yahoo'):
        """
        Save fundamental data to Supabase
        
        Args:
            ticker: Stock ticker symbol
            data: Dictionary with fundamental data
            source: Data source (e.g., 'yahoo', 'alphavantage')
            
        Returns:
            Success status (boolean)
        """
        if not data or not self.supabase:
            return False

        try:
            # Extract fields from data
            fundamental_data = {
                "ticker": ticker,
                "name": data.get('name', data.get('shortName', ticker)),
                "pe_ratio": data.get('pe_ratio', data.get('trailingPE')),
                "market_cap": data.get('market_cap', data.get('marketCap')),
                "revenue_growth": data.get('revenue_growth', data.get('revenueGrowth')),
                "profit_margin": data.get('profit_margin', data.get('profitMargins')),
                "dividend_yield": data.get('dividend_yield', data.get('dividendYield')),
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

    def get_fundamental_data(self, ticker):
        """
        Get fundamental data from Supabase
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with fundamental data or None if not found
        """
        if not self.supabase:
            return None

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

    def is_data_fresh(self, ticker, data_type='price', timeframe='1d'):
        """
        Check if data in Supabase is fresh (less than 12 hours old)
        
        Args:
            ticker: Stock ticker symbol
            data_type: Type of data ('price' or 'fundamental')
            timeframe: Timeframe for price data
            
        Returns:
            Boolean indicating if fresh data exists
        """
        if not self.supabase:
            return False

        try:
            if data_type == 'price':
                response = self.supabase.table("stock_prices") \
                    .select("last_updated") \
                    .eq("ticker", ticker) \
                    .eq("timeframe", timeframe) \
                    .order("last_updated", desc=True) \
                    .limit(1) \
                    .execute()
            else:
                response = self.supabase.table("stock_fundamentals") \
                    .select("last_updated") \
                    .eq("ticker", ticker) \
                    .execute()

            if not response.data:
                return False

            last_updated = response.data[0]['last_updated']
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(
                    last_updated.replace('Z', '+00:00'))

            # Check if data is less than 12 hours old
            return (datetime.now() - last_updated) < timedelta(hours=12)

        except Exception as e:
            logger.error(f"Error checking data freshness: {e}")
            return False

# Example usage and database status UI


def render_database_status():
    """Show Supabase database status"""
    st.subheader("Database Status")

    if 'supabase_db' not in st.session_state:
        st.session_state.supabase_db = SupabaseStockDB()

    db = st.session_state.supabase_db

    # Check if connected
    if not db.supabase:
        st.error("Not connected to Supabase. Please check your secrets.")

        # Show configuration help
        st.info("""
        Add these to your `.streamlit/secrets.toml` file:
        
        ```
        supabase_url = "https://your-project-id.supabase.co"
        supabase_key = "your-supabase-anon-key"
        ```
        
        You can get these from your Supabase project dashboard.
        """)
        return

    # Show database status
    st.success("✅ Connected to Supabase")

    # Try to get some stats
    try:
        # Price data stats
        response = db.supabase.table("stock_prices") \
            .select("ticker", "last_updated") \
            .execute()

        if response.data:
            unique_tickers = len(set(row['ticker'] for row in response.data))
            data_points = len(response.data)

            latest_update = max([row['last_updated'] for row in response.data])
            if isinstance(latest_update, str):
                latest_update = datetime.fromisoformat(
                    latest_update.replace('Z', '+00:00'))

            hours_ago = (datetime.now() - latest_update).total_seconds() / 3600

            # Display stats
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Stocks with Price Data", unique_tickers)
                st.write(f"Total data points: {data_points}")

            with col2:
                st.write(f"Last update: {latest_update}")
                st.write(f"{hours_ago:.1f} hours ago")
        else:
            st.info("No price data in database yet")
    except Exception as e:
        st.warning(f"Error getting database stats: {e}")

# Setup instructions function


def show_supabase_setup():
    """Show Supabase setup instructions"""
    st.subheader("Supabase Setup Instructions")

    st.markdown("""
    ### 1. Create a Supabase Account
    
    1. Go to [Supabase.com](https://supabase.com/) and sign up
    2. It's completely free for small projects
    
    ### 2. Create a New Project
    
    1. Click "New Project"
    2. Choose organization (or create one)
    3. Give your project a name (e.g., "stockapp")
    4. Set a secure database password
    5. Choose a free tier region close to you
    6. Click "Create new project"
    
    ### 3. Set Up Database Tables
    
    In the Supabase dashboard:
    
    1. Go to "SQL Editor"
    2. Create a new query
    3. Paste this SQL and run it:
    
    ```sql
    -- Stock price data
    CREATE TABLE stock_prices (
        ticker TEXT,
        date TEXT,
        timeframe TEXT,
        open NUMERIC,
        high NUMERIC,
        low NUMERIC,
        close NUMERIC,
        volume BIGINT,
        adjusted_close NUMERIC,
        last_updated TIMESTAMP,
        source TEXT,
        PRIMARY KEY (ticker, date, timeframe)
    );

    -- Stock fundamental data
    CREATE TABLE stock_fundamentals (
        ticker TEXT PRIMARY KEY,
        name TEXT,
        pe_ratio NUMERIC,
        market_cap NUMERIC,
        revenue_growth NUMERIC,
        profit_margin NUMERIC,
        dividend_yield NUMERIC,
        sector TEXT,
        industry TEXT,
        last_updated TIMESTAMP,
        source TEXT
    );

    -- Company name mappings
    CREATE TABLE company_mappings (
        id SERIAL PRIMARY KEY,
        company_name TEXT NOT NULL,
        yahoo_ticker TEXT,
        alpha_ticker TEXT,
        finnhub_ticker TEXT,
        exchange TEXT,
        last_updated TIMESTAMP
    );

    -- Create indexes
    CREATE INDEX idx_stock_prices_ticker ON stock_prices(ticker);
    CREATE INDEX idx_company_name ON company_mappings(company_name);
    ```
    
    ### 4. Get Your API Keys
    
    1. Go to "Project Settings" > "API"
    2. Copy the "URL" and "anon" (public) key
    
    ### 5. Add Keys to Streamlit Secrets
    
    Add these to your `.streamlit/secrets.toml` file:
    
    ```toml
    supabase_url = "https://your-project-id.supabase.co"
    supabase_key = "your-supabase-anon-key"
    
    # API keys still in secrets
    alpha_vantage_api_key = "YOUR_KEY_HERE"
    ```
    
    ### 6. Install the Supabase Python Client
    
    ```bash
    pip install supabase
    ```
    
    That's it! You now have a free cloud database for your stock app.
    """)
