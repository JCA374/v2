# services/stock_data_manager.py
import streamlit as st
import pandas as pd
import numpy as np
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
            db_storage: Database storage instance (SupabaseStockDB or SQLite)
        """
        self.db_storage = db_storage
        self.data_freshness_hours = 14  # Data older than this will be refreshed
        self.debug_mode = False

        # Get preferred data source from session state (default to yahoo)
        self.preferred_source = st.session_state.get(
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
            # Convert ticker to string if it's an object with 'ticker' attribute
            original_ticker = ticker
            if hasattr(ticker, 'ticker'):
                ticker = ticker.ticker

            # First check if we have fresh data in the database
            db_data = self._load_fundamentals_from_db(ticker)

            if db_data is not None:
                # Check if data is fresh enough
                last_updated = datetime.fromisoformat(db_data['last_updated'].replace(
                    'Z', '+00:00') if db_data['last_updated'].endswith('Z') else db_data['last_updated'])
                if datetime.now() - last_updated < timedelta(hours=self.data_freshness_hours):
                    logger.info(f"Using cached fundamental data for {ticker}")

                    # Convert DB data to info dictionary
                    info = {
                        'symbol': ticker,
                        'shortName': db_data['name'],
                        'longName': db_data['name'],
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

            # Determine which data source to try first based on user preference
            if self.preferred_source == 'yahoo':
                primary_fetch = yahoo_fetch_info
                fallback_fetch = alpha_fetch_info
                primary_source_name = 'yahoo'
                fallback_source_name = 'alphavantage'
            else:
                primary_fetch = alpha_fetch_info
                fallback_fetch = yahoo_fetch_info
                primary_source_name = 'alphavantage'
                fallback_source_name = 'yahoo'

            # Try the primary source first
            try:
                stock, info = primary_fetch(ticker)
                # Store the original ticker for reference
                info['original_ticker'] = original_ticker
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
                    # Store the original ticker for reference
                    info['original_ticker'] = original_ticker
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
                            'shortName': db_data['name'],
                            'longName': db_data['name'],
                            'sector': db_data['sector'],
                            'industry': db_data['industry'],
                            'trailingPE': db_data['pe_ratio'],
                            'marketCap': db_data['market_cap'],
                            'revenueGrowth': db_data['revenue_growth'],
                            'profitMargins': db_data['profit_margin'],
                            'dividendYield': db_data['dividend_yield'],
                            'source': db_data['source'],
                            'original_ticker': original_ticker
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
            original_ticker = ticker
            if hasattr(ticker, 'ticker'):
                symbol = ticker.ticker
            else:
                symbol = ticker

            # First check if we have fresh data in the database
            db_data = self._load_history_from_db(symbol, interval, period)

            if db_data is not None and not db_data.empty:
                # Check if data is fresh enough (using the database's is_data_fresh method)
                if self.db_storage.is_data_fresh(symbol, 'price', interval):
                    logger.info(
                        f"Using cached history data for {symbol} ({period}, {interval})")
                    return db_data

            # Determine which data source to try first based on user preference
            if self.preferred_source == 'yahoo':
                primary_fetch = yahoo_fetch_history
                fallback_fetch = alpha_fetch_history
                primary_source_name = 'yahoo'
                fallback_source_name = 'alphavantage'
            else:
                primary_fetch = alpha_fetch_history
                fallback_fetch = yahoo_fetch_history
                primary_source_name = 'alphavantage'
                fallback_source_name = 'yahoo'

            # Try the primary source first
            try:
                hist = primary_fetch(symbol, period=period, interval=interval)
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
                        return db_data
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
                'name': info.get('shortName') or info.get('longName') or ticker,
                'pe_ratio': pe_ratio,
                'market_cap': market_cap,
                'revenue_growth': info.get('revenueGrowth'),
                'profit_margin': info.get('profitMargins'),
                'dividend_yield': info.get('dividendYield'),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
            }

            # Save to database
            success = self.db_storage.save_fundamental_data(
                ticker, data, source)

            if success and self.debug_mode:
                logger.info(
                    f"Saved fundamental data for {ticker} from {source}")

            return success
        except Exception as e:
            logger.error(f"Error saving fundamental data: {str(e)}")
            if self.debug_mode:
                logger.error(traceback.format_exc())
            return False

    def _load_fundamentals_from_db(self, ticker):
        """Load fundamental data from the database."""
        try:
            return self.db_storage.get_fundamental_data(ticker)
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

            # Set the interval attribute on the dataframe
            hist_df.attrs['interval'] = interval

            # Save to database
            success = self.db_storage.save_price_data(ticker, hist_df, source)

            if success and self.debug_mode:
                logger.info(f"Saved history data for {ticker} from {source}")

            return success
        except Exception as e:
            logger.error(f"Error saving history data: {str(e)}")
            if self.debug_mode:
                logger.error(traceback.format_exc())
            return False

    def _load_history_from_db(self, ticker, interval, period):
        """Load historical price data from the database."""
        try:
            return self.db_storage.get_price_data(ticker, interval, period)
        except Exception as e:
            logger.error(f"Error loading history data: {str(e)}")
            if self.debug_mode:
                logger.error(traceback.format_exc())
            return None

    def set_debug_mode(self, enabled=True):
        """Enable or disable debug mode"""
        self.debug_mode = enabled
        return self.debug_mode

    def set_preferred_source(self, source):
        """
        Set the preferred data source.
        
        Args:
            source: Either 'yahoo' or 'alphavantage'
        
        Returns:
            bool: Success status
        """
        if source not in ['yahoo', 'alphavantage']:
            return False

        self.preferred_source = source
        # Also update in session state
        st.session_state.preferred_data_source = source
        return True
