# services/ticker_mapping_service.py
"""
Ticker mapping service for handling different ticker formats across APIs.
This service provides functions to convert between Yahoo Finance, Alpha Vantage,
and other API formats, as well as to search for tickers by company name.
"""
import streamlit as st
import pandas as pd
import logging
import requests
import time
import json
import os
from typing import Dict, List, Tuple, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ticker_mapping_service')

# Constants for the different API stock symbol formats
API_SOURCES = ["yahoo", "alphavantage"]

# Cache for ticker mappings
CACHE_TTL = 86400  # 24 hours cache duration


class TickerMappingService:
    """
    Service for mapping between different ticker formats and finding stocks by name.
    """

    def __init__(self, db_storage=None):
        """
        Initialize the mapping service.
        
        Args:
            db_storage: Optional Supabase database connection
        """
        self.db_storage = db_storage
        self.mapping_data = None
        self.load_mapping_data()

    def load_mapping_data(self) -> None:
        """Load mapping data from local CSVs and database."""
        # Load from session state if available
        if 'ticker_mappings' in st.session_state:
            self.mapping_data = st.session_state.ticker_mappings
            return

        # Try to load from Supabase first
        if self.db_storage and self.db_storage.supabase:
            try:
                # Query the company_mappings table
                response = self.db_storage.supabase.table(
                    "company_mappings").select("*").execute()

                if response.data:
                    # Convert to DataFrame
                    self.mapping_data = pd.DataFrame(response.data)
                    # Store in session state
                    st.session_state.ticker_mappings = self.mapping_data
                    logger.info(
                        f"Loaded {len(self.mapping_data)} ticker mappings from database")
                    return
            except Exception as e:
                logger.warning(
                    f"Error loading ticker mappings from database: {e}")

        # If no database data, load from CSV files
        try:
            # Load all CSV mapping files
            csv_files = [
                "csv/updated_small.csv",
                "csv/updated_mid.csv",
                "csv/updated_large.csv",
                "csv/valid_swedish_company_data.csv"
            ]

            frames = []
            for file in csv_files:
                try:
                    if os.path.exists(file):
                        df = pd.read_csv(file)
                        frames.append(df)
                    else:
                        logger.warning(f"CSV file not found: {file}")
                except Exception as e:
                    logger.warning(f"Error loading CSV file {file}: {e}")

            if frames:
                # Combine all DataFrames and drop duplicates
                combined_df = pd.concat(frames, ignore_index=True)
                combined_df = combined_df.drop_duplicates(
                    subset=['YahooTicker'])

                # Create mapping dataframe
                self.mapping_data = pd.DataFrame({
                    'company_name': combined_df['CompanyName'] if 'CompanyName' in combined_df.columns else "Unknown",
                    'yahoo_ticker': combined_df['YahooTicker'],
                    'alpha_ticker': self._yahoo_to_alpha_format(combined_df['YahooTicker'])
                })

                # Store in session state
                st.session_state.ticker_mappings = self.mapping_data
                logger.info(
                    f"Loaded {len(self.mapping_data)} ticker mappings from CSV files")

                # Save to database if available
                if self.db_storage and self.db_storage.supabase:
                    self._save_to_database()
            else:
                # Create empty DataFrame with the expected columns
                self.mapping_data = pd.DataFrame(columns=[
                    'company_name', 'yahoo_ticker', 'alpha_ticker'
                ])
                st.session_state.ticker_mappings = self.mapping_data
                logger.warning("No ticker mapping data loaded")
        except Exception as e:
            logger.error(f"Error initializing ticker mappings: {e}")
            # Create empty DataFrame if all else fails
            self.mapping_data = pd.DataFrame(columns=[
                'company_name', 'yahoo_ticker', 'alpha_ticker'
            ])
            st.session_state.ticker_mappings = self.mapping_data

    def _save_to_database(self) -> bool:
        """Save mapping data to Supabase database."""
        if not self.db_storage or not self.db_storage.supabase or self.mapping_data is None:
            return False

        try:
            # Prepare data for insertion
            records = []
            for _, row in self.mapping_data.iterrows():
                records.append({
                    "company_name": row["company_name"],
                    "yahoo_ticker": row["yahoo_ticker"],
                    "alpha_ticker": row["alpha_ticker"],
                    "last_updated": pd.Timestamp.now().isoformat()
                })

            # Insert in batches to avoid timeouts
            batch_size = 50
            for i in range(0, len(records), batch_size):
                batch = records[i:i+batch_size]

                for record in batch:
                    # Check if record exists
                    response = self.db_storage.supabase.table("company_mappings") \
                        .select("id") \
                        .eq("yahoo_ticker", record["yahoo_ticker"]) \
                        .execute()

                    if response.data:
                        # Update existing record
                        self.db_storage.supabase.table("company_mappings") \
                            .update(record) \
                            .eq("yahoo_ticker", record["yahoo_ticker"]) \
                            .execute()
                    else:
                        # Insert new record
                        self.db_storage.supabase.table("company_mappings") \
                            .insert(record) \
                            .execute()

                # Avoid rate limits
                time.sleep(0.1)

            logger.info(f"Saved {len(records)} ticker mappings to database")
            return True
        except Exception as e:
            logger.error(f"Error saving ticker mappings to database: {e}")
            return False

    def _yahoo_to_alpha_format(self, yahoo_tickers) -> pd.Series:
        """
        Convert Yahoo Finance ticker format to Alpha Vantage format.
        
        Examples:
        - "AAPL" -> "AAPL" (US stocks stay the same)
        - "ERIC-B.ST" -> "ERICB.STO" (Swedish stocks change format)
        
        Args:
            yahoo_tickers: Series or string of Yahoo Finance tickers
            
        Returns:
            Series or string of Alpha Vantage tickers
        """
        if isinstance(yahoo_tickers, pd.Series):
            return yahoo_tickers.apply(self._convert_single_yahoo_to_alpha)
        else:
            return self._convert_single_yahoo_to_alpha(yahoo_tickers)

    def _convert_single_yahoo_to_alpha(self, yahoo_ticker: str) -> str:
        """Convert a single Yahoo Finance ticker to Alpha Vantage format."""
        if not yahoo_ticker or not isinstance(yahoo_ticker, str):
            return ""

        # If it ends with .ST (Swedish stock), convert to Alpha Vantage format
        if yahoo_ticker.endswith(".ST"):
            # For Swedish stocks, Alpha Vantage simply uses the base ticker symbol
            # Strip .ST and remove the dash
            base = yahoo_ticker.replace(".ST", "")

            # Approach 1 - simplest: just remove dash
            return base.replace("-", "")

            # Approach 2 - trying to match format .STO
            # For now commenting out as it doesn't seem to work
            # return base + ".STO"

        # For US stocks, just return the ticker
        return yahoo_ticker

    def _alpha_to_yahoo_format(self, alpha_ticker: str) -> str:
        """Convert Alpha Vantage ticker format to Yahoo Finance format."""
        # For US stocks, the formats are the same
        if not "." in alpha_ticker:
            return alpha_ticker

        # For Swedish stocks, try to convert to Yahoo format
        if alpha_ticker.endswith(".STO"):
            # Extract base and add .ST
            base = alpha_ticker.replace(".STO", "")
            # Would need to add back the dash but we don't know where it goes
            # Best to look up in our mapping data
            matching_rows = self.mapping_data[self.mapping_data['alpha_ticker']
                                              == alpha_ticker]
            if not matching_rows.empty:
                return matching_rows.iloc[0]['yahoo_ticker']

            # Fallback - just replace .STO with .ST
            return base + ".ST"

        return alpha_ticker

    def get_ticker(self, company_name_or_ticker: str, source: str = "yahoo") -> Optional[str]:
        """
        Get the ticker for a given company name or ticker in the specified API format.
        
        Args:
            company_name_or_ticker: Company name or ticker in any format
            source: API source ("yahoo" or "alphavantage")
            
        Returns:
            Ticker symbol in the specified format, or None if not found
        """
        if self.mapping_data is None or self.mapping_data.empty:
            logger.warning("No mapping data available")
            return company_name_or_ticker

        # Check if it's already a ticker we know
        yahoo_matches = self.mapping_data[self.mapping_data['yahoo_ticker']
                                          == company_name_or_ticker]
        alpha_matches = self.mapping_data[self.mapping_data['alpha_ticker']
                                          == company_name_or_ticker]

        if not yahoo_matches.empty:
            # Already a Yahoo ticker
            if source == "yahoo":
                return company_name_or_ticker
            elif source == "alphavantage":
                return yahoo_matches.iloc[0]['alpha_ticker']
        elif not alpha_matches.empty:
            # Already an Alpha Vantage ticker
            if source == "alphavantage":
                return company_name_or_ticker
            elif source == "yahoo":
                return alpha_matches.iloc[0]['yahoo_ticker']

        # Try to find by company name (case-insensitive)
        name_matches = self.mapping_data[
            self.mapping_data['company_name'].str.lower(
            ) == company_name_or_ticker.lower()
        ]

        if not name_matches.empty:
            # Found by company name
            if source == "yahoo":
                return name_matches.iloc[0]['yahoo_ticker']
            elif source == "alphavantage":
                return name_matches.iloc[0]['alpha_ticker']

        # Try fuzzy match on company name
        fuzzy_matches = self.mapping_data[
            self.mapping_data['company_name'].str.lower().str.contains(
                company_name_or_ticker.lower(), regex=False, na=False
            )
        ]

        if not fuzzy_matches.empty:
            # Found by fuzzy company name match
            if source == "yahoo":
                return fuzzy_matches.iloc[0]['yahoo_ticker']
            elif source == "alphavantage":
                return fuzzy_matches.iloc[0]['alpha_ticker']

        # Fallback: just return the input - it might be correct or our mapping is incomplete
        if source == "yahoo":
            return company_name_or_ticker
        elif source == "alphavantage":
            # Try to convert Yahoo to Alpha format as a last resort
            return self._yahoo_to_alpha_format(company_name_or_ticker)

        return company_name_or_ticker

    def search_companies(self, query: str) -> pd.DataFrame:
        """
        Search for companies by name or ticker.
        
        Args:
            query: Search query (company name or partial ticker)
            
        Returns:
            DataFrame with matching companies
        """
        if self.mapping_data is None or self.mapping_data.empty:
            return pd.DataFrame(columns=['company_name', 'yahoo_ticker', 'alpha_ticker'])

        # Lowercase for case-insensitive search
        query_lower = query.lower()

        # Search in company name and tickers
        matches = self.mapping_data[
            self.mapping_data['company_name'].str.lower().str.contains(query_lower, regex=False, na=False) |
            self.mapping_data['yahoo_ticker'].str.lower().str.contains(
                query_lower, regex=False, na=False)
        ]

        return matches

    def add_mapping(self, company_name: str, yahoo_ticker: str, alpha_ticker: str = None) -> bool:
        """
        Add a new ticker mapping.
        
        Args:
            company_name: Company name
            yahoo_ticker: Yahoo Finance ticker
            alpha_ticker: Alpha Vantage ticker (will be generated if None)
            
        Returns:
            Success status
        """
        try:
            if alpha_ticker is None:
                alpha_ticker = self._yahoo_to_alpha_format(yahoo_ticker)

            # Check if already exists
            existing = self.mapping_data[self.mapping_data['yahoo_ticker']
                                         == yahoo_ticker]

            if not existing.empty:
                # Update existing mapping
                idx = existing.index[0]
                self.mapping_data.at[idx, 'company_name'] = company_name
                self.mapping_data.at[idx, 'alpha_ticker'] = alpha_ticker
            else:
                # Add new mapping
                new_row = pd.DataFrame({
                    'company_name': [company_name],
                    'yahoo_ticker': [yahoo_ticker],
                    'alpha_ticker': [alpha_ticker]
                })
                self.mapping_data = pd.concat(
                    [self.mapping_data, new_row], ignore_index=True)

            # Update session state
            st.session_state.ticker_mappings = self.mapping_data

            # Save to database if available
            if self.db_storage and self.db_storage.supabase:
                record = {
                    "company_name": company_name,
                    "yahoo_ticker": yahoo_ticker,
                    "alpha_ticker": alpha_ticker,
                    "last_updated": pd.Timestamp.now().isoformat()
                }

                # Check if record exists
                response = self.db_storage.supabase.table("company_mappings") \
                    .select("id") \
                    .eq("yahoo_ticker", yahoo_ticker) \
                    .execute()

                if response.data:
                    # Update existing record
                    self.db_storage.supabase.table("company_mappings") \
                        .update(record) \
                        .eq("yahoo_ticker", yahoo_ticker) \
                        .execute()
                else:
                    # Insert new record
                    self.db_storage.supabase.table("company_mappings") \
                        .insert(record) \
                        .execute()

            return True
        except Exception as e:
            logger.error(f"Error adding ticker mapping: {e}")
            return False

    def detect_api_format(self, ticker: str) -> Tuple[str, str]:
        """
        Detect which API format a ticker belongs to and return the normalized version.
        
        Args:
            ticker: Ticker symbol in any format
            
        Returns:
            Tuple of (api_source, normalized_ticker)
        """
        # Check if it's in our mapping data
        if self.mapping_data is not None and not self.mapping_data.empty:
            yahoo_matches = self.mapping_data[self.mapping_data['yahoo_ticker'] == ticker]
            alpha_matches = self.mapping_data[self.mapping_data['alpha_ticker'] == ticker]

            if not yahoo_matches.empty:
                return "yahoo", ticker
            elif not alpha_matches.empty:
                return "alphavantage", ticker

        # Heuristics based on ticker format
        if ticker.endswith(".ST"):
            return "yahoo", ticker
        elif ticker.endswith(".STO"):
            return "alphavantage", ticker

        # If no specific format detected, assume it's a US stock (works in both APIs)
        return "yahoo", ticker

    def ensure_ticker_format(self, ticker: str, target_source: str) -> str:
        """
        Ensure a ticker is in the correct format for the target API.
        
        Args:
            ticker: Ticker symbol in any format
            target_source: Target API source format
            
        Returns:
            Ticker symbol in the target format
        """
        source, _ = self.detect_api_format(ticker)

        if source == target_source:
            # Already in the correct format
            return ticker

        # Convert between formats
        if source == "yahoo" and target_source == "alphavantage":
            return self.get_ticker(ticker, "alphavantage")
        elif source == "alphavantage" and target_source == "yahoo":
            return self.get_ticker(ticker, "yahoo")

        # Fallback
        return ticker

    def get_company_data(self, ticker_or_name: str) -> Dict[str, str]:
        """
        Get all company data for a ticker or company name.
        
        Args:
            ticker_or_name: Ticker symbol or company name
            
        Returns:
            Dictionary with company data
        """
        if self.mapping_data is None or self.mapping_data.empty:
            return {
                'company_name': ticker_or_name,
                'yahoo_ticker': ticker_or_name,
                'alpha_ticker': self._yahoo_to_alpha_format(ticker_or_name)
            }

        # Try to find by ticker or name
        yahoo_matches = self.mapping_data[self.mapping_data['yahoo_ticker']
                                          == ticker_or_name]
        alpha_matches = self.mapping_data[self.mapping_data['alpha_ticker']
                                          == ticker_or_name]
        name_matches = self.mapping_data[
            self.mapping_data['company_name'].str.lower(
            ) == ticker_or_name.lower()
        ]

        if not yahoo_matches.empty:
            row = yahoo_matches.iloc[0]
            return {
                'company_name': row['company_name'],
                'yahoo_ticker': row['yahoo_ticker'],
                'alpha_ticker': row['alpha_ticker']
            }
        elif not alpha_matches.empty:
            row = alpha_matches.iloc[0]
            return {
                'company_name': row['company_name'],
                'yahoo_ticker': row['yahoo_ticker'],
                'alpha_ticker': row['alpha_ticker']
            }
        elif not name_matches.empty:
            row = name_matches.iloc[0]
            return {
                'company_name': row['company_name'],
                'yahoo_ticker': row['yahoo_ticker'],
                'alpha_ticker': row['alpha_ticker']
            }

        # Try fuzzy match on company name
        fuzzy_matches = self.mapping_data[
            self.mapping_data['company_name'].str.lower().str.contains(
                ticker_or_name.lower(), regex=False, na=False
            )
        ]

        if not fuzzy_matches.empty:
            row = fuzzy_matches.iloc[0]
            return {
                'company_name': row['company_name'],
                'yahoo_ticker': row['yahoo_ticker'],
                'alpha_ticker': row['alpha_ticker']
            }

        # No match found, create a default entry
        return {
            'company_name': ticker_or_name,
            'yahoo_ticker': ticker_or_name,
            'alpha_ticker': self._yahoo_to_alpha_format(ticker_or_name)
        }

    def validate_ticker(self, ticker: str, source: str = "yahoo") -> bool:
        """
        Validate if a ticker exists in the specified API.
        
        Args:
            ticker: Ticker symbol
            source: API source ("yahoo" or "alphavantage")
            
        Returns:
            True if the ticker exists, False otherwise
        """
        # First, ensure it's in the right format
        ticker = self.ensure_ticker_format(ticker, source)

        if source == "yahoo":
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
                response = requests.get(url, timeout=5)
                data = response.json()

                # Check if data contains error or valid chart data
                if "chart" in data and "result" in data["chart"] and data["chart"]["result"] is not None:
                    return True
                return False
            except Exception:
                return False
        elif source == "alphavantage":
            try:
                # We need an API key for Alpha Vantage
                api_key = st.session_state.get('alpha_vantage_api_key', None)
                if not api_key:
                    logger.warning(
                        "No Alpha Vantage API key available for validation")
                    return True  # Can't validate without API key, assume valid

                url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={api_key}"
                response = requests.get(url, timeout=5)
                data = response.json()

                # Check if data contains Symbol field
                if "Symbol" in data:
                    return True
                return False
            except Exception:
                return False

        return False


# Example usage:
if __name__ == "__main__":
    # Initialize the service with test data
    mapper = TickerMappingService()

    # Test conversions
    yahoo_ticker = "ERIC-B.ST"
    alpha_ticker = mapper.get_ticker(yahoo_ticker, "alphavantage")
    print(f"Yahoo: {yahoo_ticker} -> Alpha: {alpha_ticker}")

    # Test company search
    results = mapper.search_companies("Ericsson")
    print(f"Search results for 'Ericsson': {len(results)} matches")
    print(results)
