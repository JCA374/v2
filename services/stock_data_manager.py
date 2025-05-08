# services/stock_data_manager.py
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import logging
import traceback

# Import services
from services.yahoo_finance_service import fetch_ticker_info as yahoo_fetch_info
from services.yahoo_finance_service import fetch_history as yahoo_fetch_history
from services.alpha_vantage_service import fetch_ticker_info as alpha_fetch_info
from services.alpha_vantage_service import fetch_history as alpha_fetch_history
# Import MockStock from alpha_vantage_service
from services.alpha_vantage_service import MockStock

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('stock_data_manager')


class StockDataManager:
    """
    Central manager for stock data retrieval and caching.
    Handles service selection, database operations, and data consistency.
    """

    def __init__(self, db_storage):
        """
        Initialize the stock data manager.
        
        Args:
            db_storage: Instance of DatabaseStorage class
        """
        self.db_storage = db_storage
        self.data_freshness_hours = 14  # Data older than this will be refreshed
        self.debug_mode = db_storage.debug_mode

        # Get preferred data source from session state (default to yahoo)
        self.primary_source = st.session_state.get(
            'preferred_data_source', 'yahoo')

    def fetch_ticker_info(self, ticker):
        """
        Fetch company information with caching and fallback.
        
        Args:
            ticker (str): The ticker symbol
            
        Returns:
            tuple: (stock object, info dictionary)
        """
        try:
            # First check if we have fresh data in the database
            db_data = self._load_fundamentals_from_db(ticker)

            if db_data is not None:
                # Check if data is fresh enough
                last_updated = datetime.fromisoformat(db_data['last_updated'])
                if datetime.now() - last_updated < timedelta(hours=self.data_freshness_hours):
                    logger.info(f"Using cached fundamental data for {ticker}")

                    # Convert DB data to info dictionary
                    info = {
                        'symbol': ticker,
                        'shortName': db_data['company_name'],
                        'longName': db_data['company_name'],
                        'sector': db_data['sector'],
                        'industry': db_data['industry'],
                        'trailingPE': db_data['pe_ratio'],
                        'marketCap': db_data['market_cap'],
                        'revenueGrowth': db_data['revenue_growth'],
                        'profitMargins': db_data['profit_margin'],
                        'dividendYield': db_data['dividend_yield'],
                        'source': db_data['source']
                    }

                    # Create a mock stock object
                    stock = MockStock(ticker, info)
                    return stock, info

            # Determine which data source to try first based on configuration
            primary_fetch = yahoo_fetch_info if self.primary_source == 'yahoo' else alpha_fetch_info
            fallback_fetch = alpha_fetch_info if self.primary_source == 'yahoo' else yahoo_fetch_info

            primary_source_name = self.primary_source
            fallback_source_name = 'alphavantage' if self.primary_source == 'yahoo' else 'yahoo'

            # Try the primary source first
            try:
                stock, info = primary_fetch(ticker)
                # Save to database for future use
                self._save_fundamentals_to_db(
                    ticker, info, source=primary_source_name)
                return stock, info
            except Exception as primary_error:
                logger.warning(
                    f"{primary_source_name.capitalize()} failed for {ticker}: {str(primary_error)}")

                # Fall back to secondary source
                try:
                    stock, info = fallback_fetch(ticker)
                    # Save to database for future use
                    self._save_fundamentals_to_db(
                        ticker, info, source=fallback_source_name)
                    return stock, info
                except Exception as secondary_error:
                    # If both services fail and we have old data, use that
                    if db_data is not None:
                        logger.warning(
                            f"Using stale data for {ticker} as both services failed")

                        # Convert DB data to info dictionary
                        info = {
                            'symbol': ticker,
                            'shortName': db_data['company_name'],
                            'longName': db_data['company_name'],
                            'sector': db_data['sector'],
                            'industry': db_data['industry'],
                            'trailingPE': db_data['pe_ratio'],
                            'marketCap': db_data['market_cap'],
                            'revenueGrowth': db_data['revenue_growth'],
                            'profitMargins': db_data['profit_margin'],
                            'dividendYield': db_data['dividend_yield'],
                            'source': db_data['source']
                        }

                        # Create a mock stock object
                        stock = MockStock(ticker, info)
                        return stock, info
                    else:
                        # No data available at all
                        raise RuntimeError(
                            f"Failed to fetch data for {ticker} from all services: {str(primary_error)}, {str(secondary_error)}")

        except Exception as e:
            logger.error(f"Error in fetch_ticker_info for {ticker}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def fetch_history(self, ticker, period="1y", interval="1wk"):
        """
        Fetch historical price data with caching and fallback.
        
        Args:
            ticker: Stock ticker object or symbol string
            period: Time period to fetch
            interval: Data interval
            
        Returns:
            DataFrame: Historical price data
        """
        try:
            # Convert ticker object to symbol if needed
            if hasattr(ticker, 'ticker'):
                symbol = ticker.ticker
            else:
                symbol = ticker

            # First check if we have fresh data in the database
            db_data = self._load_history_from_db(symbol, interval, period)

            if db_data is not None and not db_data.empty:
                # Check if data is fresh enough (only check the newest data point)
                last_updated = db_data['last_updated'].iloc[0]
                if isinstance(last_updated, str):
                    last_updated = datetime.fromisoformat(last_updated)

                if datetime.now() - last_updated < timedelta(hours=self.data_freshness_hours):
                    logger.info(
                        f"Using cached history data for {symbol} ({period}, {interval})")
                    # Drop the last_updated and source columns for compatibility
                    return db_data.drop(['last_updated', 'source'], axis=1, errors='ignore')

            # Determine which data source to try first based on configuration
            primary_fetch = yahoo_fetch_history if self.primary_source == 'yahoo' else alpha_fetch_history
            fallback_fetch = alpha_fetch_history if self.primary_source == 'yahoo' else yahoo_fetch_history

            primary_source_name = self.primary_source
            fallback_source_name = 'alphavantage' if self.primary_source == 'yahoo' else 'yahoo'

            # Try the primary source first
            try:
                hist = primary_fetch(ticker, period=period, interval=interval)
                # Save to database for future use
                self._save_history_to_db(
                    symbol, hist, interval, source=primary_source_name)
                return hist
            except Exception as primary_error:
                logger.warning(
                    f"{primary_source_name.capitalize()} history failed for {symbol}: {str(primary_error)}")

                # Fall back to secondary source
                try:
                    hist = fallback_fetch(
                        symbol, period=period, interval=interval)
                    # Save to database for future use
                    self._save_history_to_db(
                        symbol, hist, interval, source=fallback_source_name)
                    return hist
                except Exception as secondary_error:
                    # If both services fail and we have old data, use that
                    if db_data is not None and not db_data.empty:
                        logger.warning(
                            f"Using stale history data for {symbol} as both services failed")
                        return db_data.drop(['last_updated', 'source'], axis=1, errors='ignore')
                    else:
                        # No data available at all
                        raise RuntimeError(
                            f"Failed to fetch history for {symbol} from all services: {str(primary_error)}, {str(secondary_error)}")

        except Exception as e:
            logger.error(f"Error in fetch_history for {ticker}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _save_fundamentals_to_db(self, ticker, info, source='yahoo'):
        """Save fundamental data to the database."""
        try:
            # Extract and standardize data
            market_cap = info.get('marketCap')
            if isinstance(market_cap, str):
                try:
                    market_cap = float(market_cap.replace(',', ''))
                except:
                    market_cap = None

            pe_ratio = info.get('trailingPE') or info.get('forwardPE')

            data = {
                'ticker': ticker,
                'company_name': info.get('shortName') or info.get('longName') or ticker,
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'pe_ratio': pe_ratio,
                'market_cap': market_cap,
                'revenue_growth': info.get('revenueGrowth'),
                'profit_margin': info.get('profitMargins'),
                'dividend_yield': info.get('dividendYield'),
                'last_updated': datetime.now().isoformat(),
                'source': source
            }

            # Insert or update in database
            with sqlite3.connect(self.db_storage.db_path) as conn:
                cursor = conn.cursor()

                # Use INSERT OR REPLACE to handle both new and updated records
                cursor.execute('''
                INSERT OR REPLACE INTO stock_fundamentals 
                (ticker, company_name, sector, industry, pe_ratio, market_cap, 
                revenue_growth, profit_margin, dividend_yield, last_updated, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data['ticker'], data['company_name'], data['sector'], data['industry'],
                    data['pe_ratio'], data['market_cap'], data['revenue_growth'],
                    data['profit_margin'], data['dividend_yield'], data['last_updated'], data['source']
                ))

                conn.commit()

            if self.debug_mode:
                logger.info(
                    f"Saved fundamental data for {ticker} from {source}")

            return True
        except Exception as e:
            logger.error(f"Error saving fundamental data: {str(e)}")
            if self.debug_mode:
                logger.error(traceback.format_exc())
            return False

    def _load_fundamentals_from_db(self, ticker):
        """Load fundamental data from the database."""
        try:
            with sqlite3.connect(self.db_storage.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                SELECT * FROM stock_fundamentals WHERE ticker = ?
                ''', (ticker,))

                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Error loading fundamental data: {str(e)}")
            if self.debug_mode:
                logger.error(traceback.format_exc())
            return None

    def _save_history_to_db(self, ticker, hist_df, interval, source='yahoo'):
        """Save historical price data to the database."""
        try:
            if hist_df is None or hist_df.empty:
                logger.warning(f"No history data to save for {ticker}")
                return False

            # Make a copy to avoid modifying the original
            df = hist_df.copy()

            # Add metadata columns if not already present
            if 'ticker' not in df.columns:
                df['ticker'] = ticker
            if 'timeframe' not in df.columns:
                df['timeframe'] = interval
            if 'last_updated' not in df.columns:
                df['last_updated'] = datetime.now().isoformat()
            if 'source' not in df.columns:
                df['source'] = source

            # Reset index to get date as column
            df = df.reset_index()

            # Ensure date column is string format for SQLite
            if 'Date' in df.columns:
                df['date'] = df['Date'].dt.strftime('%Y-%m-%d')
            elif 'index' in df.columns and pd.api.types.is_datetime64_any_dtype(df['index']):
                df['date'] = df['index'].dt.strftime('%Y-%m-%d')
                df = df.drop('index', axis=1)
            else:
                logger.error(
                    f"No date column found in history data for {ticker}")
                return False

            # Connect to database
            with sqlite3.connect(self.db_storage.db_path) as conn:
                # Delete existing data for this ticker and timeframe to avoid duplicates
                cursor = conn.cursor()
                cursor.execute('''
                DELETE FROM stock_price_history WHERE ticker = ? AND timeframe = ?
                ''', (ticker, interval))

                # Prepare column mapping (case-insensitive)
                required_columns = ['ticker', 'date',
                                    'timeframe', 'last_updated', 'source']

                # Price columns with fallbacks
                price_columns = {
                    'open': ['Open', 'open'],
                    'high': ['High', 'high'],
                    'low': ['Low', 'low'],
                    'close': ['Close', 'close'],
                    'volume': ['Volume', 'volume'],
                    'adjusted_close': ['Adj Close', 'adj_close', 'adjusted_close']
                }

                # Find matching columns
                column_mapping = {}
                for db_col, possible_cols in price_columns.items():
                    for col in possible_cols:
                        if col in df.columns:
                            column_mapping[db_col] = col
                            break

                # Check we have minimum required columns
                if not all(col in column_mapping for col in ['open', 'high', 'low', 'close']):
                    logger.error(
                        f"Missing required price columns for {ticker}")
                    return False

                # Prepare data rows for insertion
                rows = []
                for _, row in df.iterrows():
                    data_row = [
                        row['ticker'],
                        row['date'],
                        row['timeframe'],
                        row[column_mapping.get('open')],
                        row[column_mapping.get('high')],
                        row[column_mapping.get('low')],
                        row[column_mapping.get('close')],
                        row[column_mapping.get(
                            'volume')] if 'volume' in column_mapping else None,
                        row[column_mapping.get(
                            'adjusted_close')] if 'adjusted_close' in column_mapping else None,
                        row['last_updated'],
                        row['source']
                    ]
                    rows.append(data_row)

                # Bulk insert
                cursor.executemany('''
                INSERT INTO stock_price_history 
                (ticker, date, timeframe, open, high, low, close, volume, adjusted_close, last_updated, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', rows)

                conn.commit()

            if self.debug_mode:
                logger.info(
                    f"Saved {len(rows)} history data points for {ticker} from {source}")

            return True
        except Exception as e:
            logger.error(f"Error saving history data: {str(e)}")
            if self.debug_mode:
                logger.error(traceback.format_exc())
            return False

    def _load_history_from_db(self, ticker, interval, period):
        """Load historical price data from the database."""
        try:
            with sqlite3.connect(self.db_storage.db_path) as conn:
                # Set row factory to get column names
                conn.row_factory = sqlite3.Row

                # Determine how far back to look based on period
                period_days = {
                    "1mo": 30,
                    "3mo": 90,
                    "6mo": 180,
                    "1y": 365,
                    "2y": 730,
                    "5y": 1825,
                    "10y": 3650,
                    "max": 9999
                }.get(period, 365)

                # Create cutoff date
                cutoff_date = (
                    datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')

                # Query database
                query = '''
                SELECT date, open, high, low, close, volume, adjusted_close, last_updated, source
                FROM stock_price_history
                WHERE ticker = ? AND timeframe = ? AND date >= ?
                ORDER BY date DESC
                '''

                df = pd.read_sql_query(query, conn, params=(
                    ticker, interval, cutoff_date))

                if df.empty:
                    return None

                # Convert date column to index
                df['Date'] = pd.to_datetime(df['date'])
                df = df.set_index('Date')
                df = df.drop('date', axis=1)

                # Rename columns to match Yahoo Finance format
                column_map = {
                    'open': 'Open',
                    'high': 'High',
                    'low': 'Low',
                    'close': 'Close',
                    'volume': 'Volume',
                    'adjusted_close': 'Adj Close'
                }

                df = df.rename(
                    columns={k: v for k, v in column_map.items() if k in df.columns})

                return df
        except Exception as e:
            logger.error(f"Error loading history data: {str(e)}")
            if self.debug_mode:
                logger.error(traceback.format_exc())
            return None
