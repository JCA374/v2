# helpers/enhanced_data_loader.py
"""
Enhanced data loading functions for the enhanced scanner
"""
import pandas as pd
import os
import streamlit as st
import logging

logger = logging.getLogger(__name__)


def load_stock_universe(universe_name, limit_stocks=False):
    """
    Load stock tickers from various CSV sources with enhanced error handling
    
    Args:
        universe_name: Name of the CSV file or predefined universe
        limit_stocks: Whether to limit to first 20 stocks for testing
        
    Returns:
        List of ticker symbols
    """

    # Map common universe names to file paths
    universe_mapping = {
        "small": "updated_small.csv",
        "mid": "updated_mid.csv",
        "large": "updated_large.csv",
        "swedish": "valid_swedish_company_data.csv",
        "all_swedish": "swedish_stocks_consolidated.csv"
    }

    # Get the actual filename
    if universe_name in universe_mapping:
        filename = universe_mapping[universe_name]
    else:
        filename = universe_name

    # Try different paths to find the CSV file
    possible_paths = [
        f"csv/{filename}",
        filename,
        f"../{filename}",
        f"../csv/{filename}",
        os.path.join(os.getcwd(), "csv", filename)
    ]

    df = None
    used_path = None

    for path in possible_paths:
        try:
            if os.path.exists(path):
                df = pd.read_csv(path, encoding='utf-8')
                used_path = path
                break
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(path, encoding='latin-1')
                used_path = path
                break
            except Exception:
                continue
        except Exception as e:
            logger.debug(f"Failed to load {path}: {e}")
            continue

    if df is None:
        st.error(f"Could not find or load file: {filename}")
        st.info(f"Tried paths: {possible_paths}")
        return []

    logger.info(f"Loaded data from: {used_path}")

    # Extract tickers based on available columns
    tickers = extract_tickers_from_dataframe(df)

    if limit_stocks and len(tickers) > 20:
        original_count = len(tickers)
        tickers = tickers[:20]
        st.info(
            f"Limited to first 20 stocks for testing (out of {original_count} total)")

    return tickers


def extract_tickers_from_dataframe(df):
    """
    Extract ticker symbols from a dataframe, handling various column formats
    
    Args:
        df: Pandas DataFrame with stock data
        
    Returns:
        List of ticker symbols
    """
    tickers = []

    # Priority order for ticker columns
    ticker_columns = [
        'YahooTicker',
        'Tickersymbol',
        'Symbol',
        'Ticker',
        'yahoo_ticker',
        'ticker'
    ]

    # Find the first available ticker column
    ticker_column = None
    for col in ticker_columns:
        if col in df.columns:
            ticker_column = col
            break

    if ticker_column:
        tickers = df[ticker_column].dropna().astype(str).tolist()
    else:
        # Fall back to first column if no standard ticker column found
        if len(df.columns) > 0:
            tickers = df.iloc[:, 0].dropna().astype(str).tolist()
            st.warning(
                f"No standard ticker column found. Using first column: {df.columns[0]}")

    # Clean up tickers (remove whitespace, empty strings)
    tickers = [t.strip() for t in tickers if t and str(
        t).strip() and str(t).strip().lower() != 'nan']

    logger.info(
        f"Extracted {len(tickers)} tickers from {ticker_column or 'first column'}")

    return tickers


def get_available_universes():
    """
    Get a list of available stock universes (CSV files)
    
    Returns:
        Dictionary mapping display names to filenames
    """
    universes = {}

    # Standard universes
    standard_files = {
        "Small Cap Stocks": "updated_small.csv",
        "Mid Cap Stocks": "updated_mid.csv",
        "Large Cap Stocks": "updated_large.csv",
        "Swedish Companies": "valid_swedish_company_data.csv"
    }

    # Check which files actually exist
    for display_name, filename in standard_files.items():
        possible_paths = [f"csv/{filename}", filename]

        for path in possible_paths:
            if os.path.exists(path):
                try:
                    # Quick test to make sure file is readable
                    test_df = pd.read_csv(path, nrows=1)
                    universes[display_name] = filename
                    break
                except Exception:
                    continue

    # Look for other CSV files in the csv directory
    csv_dir = "csv"
    if os.path.exists(csv_dir):
        for file in os.listdir(csv_dir):
            if file.endswith('.csv') and file not in standard_files.values():
                try:
                    # Test if it's a valid stock CSV
                    test_df = pd.read_csv(os.path.join(csv_dir, file), nrows=5)
                    if has_ticker_column(test_df):
                        display_name = file.replace(
                            '.csv', '').replace('_', ' ').title()
                        universes[display_name] = file
                except Exception:
                    continue

    return universes


def has_ticker_column(df):
    """
    Check if a dataframe has a column that looks like it contains stock tickers
    
    Args:
        df: Pandas DataFrame
        
    Returns:
        Boolean indicating if ticker column found
    """
    ticker_indicators = [
        'ticker', 'symbol', 'yahoo', 'stock'
    ]

    for col in df.columns:
        col_lower = col.lower()
        if any(indicator in col_lower for indicator in ticker_indicators):
            return True

    return False


def validate_tickers(tickers, max_invalid=5):
    """
    Basic validation of ticker symbols
    
    Args:
        tickers: List of ticker symbols
        max_invalid: Maximum number of invalid tickers to show
        
    Returns:
        Tuple of (valid_tickers, invalid_tickers)
    """
    valid_tickers = []
    invalid_tickers = []

    for ticker in tickers:
        # Basic validation rules
        if (len(ticker) >= 1 and
            len(ticker) <= 10 and
                ticker.replace('-', '').replace('.', '').isalnum()):
            valid_tickers.append(ticker)
        else:
            invalid_tickers.append(ticker)

    if invalid_tickers and len(invalid_tickers) <= max_invalid:
        st.warning(
            f"Found {len(invalid_tickers)} potentially invalid tickers: {', '.join(invalid_tickers[:max_invalid])}")
    elif invalid_tickers:
        st.warning(
            f"Found {len(invalid_tickers)} potentially invalid tickers (showing first {max_invalid}): {', '.join(invalid_tickers[:max_invalid])}")

    return valid_tickers, invalid_tickers


def preview_universe(universe_name, num_rows=5):
    """
    Preview a stock universe for debugging
    
    Args:
        universe_name: Name of the universe to preview
        num_rows: Number of rows to show
    """
    tickers = load_stock_universe(universe_name, limit_stocks=False)

    if tickers:
        st.write(
            f"**Preview of {universe_name}** (showing first {num_rows} of {len(tickers)} total):")
        preview_tickers = tickers[:num_rows]

        # Create a simple dataframe for display
        preview_df = pd.DataFrame({
            'Index': range(1, len(preview_tickers) + 1),
            'Ticker': preview_tickers
        })

        st.dataframe(preview_df, hide_index=True)

        if len(tickers) > num_rows:
            st.caption(f"... and {len(tickers) - num_rows} more tickers")
    else:
        st.error(f"No tickers found in {universe_name}")


# Usage example and testing function
def test_data_loading():
    """Test function for data loading capabilities"""
    st.subheader("Data Loading Test")

    # Show available universes
    universes = get_available_universes()
    st.write("Available universes:", list(universes.keys()))

    # Test loading
    if universes:
        test_universe = list(universes.keys())[0]
        st.write(f"Testing load of: {test_universe}")

        tickers = load_stock_universe(
            universes[test_universe], limit_stocks=True)
        st.write(f"Loaded {len(tickers)} tickers")

        if tickers:
            st.write("Sample tickers:", tickers[:5])

            # Validate tickers
            valid, invalid = validate_tickers(tickers)
            st.write(f"Valid: {len(valid)}, Invalid: {len(invalid)}")


if __name__ == "__main__":
    # Run test if executed directly
    test_data_loading()
