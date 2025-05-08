# Stock Data Services Documentation

This document provides detailed information about the stock data services implemented in the Value & Momentum Stock Strategy App. It covers the architecture, configuration options, and implementation details of the data retrieval and caching system.

## Table of Contents

1. [Overview](#overview)
2. [Service Architecture](#service-architecture)
3. [Data Sources](#data-sources)
4. [Caching System](#caching-system)
5. [Configuration Options](#configuration-options)
6. [Error Handling & Fallback](#error-handling--fallback)
7. [Performance Considerations](#performance-considerations)
8. [Implementation Examples](#implementation-examples)

## Overview

The stock data services provide a robust, fault-tolerant system for fetching and caching stock data from multiple sources. The system prioritizes:

- **Reliability**: Multiple data sources with automatic fallback
- **Performance**: Multi-level caching to minimize API calls
- **User Control**: Configurable data source priorities and API settings
- **Transparency**: Clear indication of where data is coming from

## Service Architecture

The data service architecture consists of three layers:

### 1. Provider Services

Individual services for each data provider:
- `yahoo_finance_service.py`: Yahoo Finance API via yfinance
- `alpha_vantage_service.py`: Alpha Vantage API via REST requests

### 2. Data Manager

Central coordinator for all stock data operations:
- `stock_data_manager.py`: Handles data source selection, caching, and fallback

### 3. Database Storage

Persistent storage for cached data:
- `db_storage.py`: SQLite database implementation

## Data Sources

### Yahoo Finance

- **Implementation**: Uses the yfinance library
- **API Key**: Not required
- **Rate Limits**: Undefined but enforced
- **Retry Strategy**: 3 retries with specific wait times (5s, 10s, 15s)
- **Data Coverage**: Comprehensive market data for most global exchanges
- **Strengths**: No API key required, good coverage
- **Weaknesses**: Undocumented rate limits, occasional reliability issues

### Alpha Vantage

- **Implementation**: Direct REST API calls
- **API Key**: Required (free tier available)
- **Rate Limits**: 
  - Free tier: 5 calls per minute, 500 calls per day
  - Premium tiers available with higher limits
- **Retry Strategy**: 2 retries with exponential backoff
- **Data Coverage**: US markets and major international exchanges
- **Strengths**: Consistent, well-documented API
- **Weaknesses**: Requires API key, limited free tier

## Caching System

The application uses a multi-level caching strategy:

### 1. In-Memory Cache (Streamlit's cache_data)

```python
@st.cache_data(ttl=7200)  # 2-hour cache time
def fetch_ticker_info(ticker):
    # Implementation...
```

- First level of caching
- TTL: 2 hours (7200 seconds)
- Cleared on app restart
- Improves performance for repeated queries in the same session

### 2. SQLite Database Cache

```python
def _save_fundamentals_to_db(self, ticker, info, source='yahoo'):
    # Implementation...
```

- Second level of caching
- Persists across app restarts
- Freshness threshold: 14 hours
- Includes source tracking and timestamps

### Data Freshness Policy

1. Check database cache first
2. If data exists and is less than 14 hours old, use it
3. Otherwise, fetch from API and update cache

## Configuration Options

Users can configure the following aspects of the data services:

### 1. Data Source Priority

```python
# In API settings component
preferred_source = 'yahoo' if data_source == "Yahoo Finance" else 'alphavantage'
st.session_state.preferred_data_source = preferred_source
```

- Choose which data source to try first
- Options: Yahoo Finance or Alpha Vantage
- Default: Yahoo Finance → Alpha Vantage (if Yahoo fails)

### 2. Alpha Vantage API Key

```python
# In API settings component
st.session_state.alpha_vantage_api_key = new_key
```

- Required to use Alpha Vantage
- Stored in session state
- Can be tested directly from the UI

### 3. Access From Storage Settings Tab

```python
# Example path to access settings
Storage Settings Tab → API Settings → Data Source Priority
```

## Error Handling & Fallback

The system implements a comprehensive error handling strategy:

### 1. Yahoo Finance Retry Logic

```python
RETRY_WAIT_TIMES = [5, 10, 15]  # Seconds to wait for each retry attempt
wait_time = RETRY_WAIT_TIMES[min(retry_idx, len(RETRY_WAIT_TIMES)-1)]
```

- Fixed wait times: 5s, 10s, and 15s
- Applies to rate limit errors and other failures
- Maximum of 3 retries

### 2. Alpha Vantage Retry Logic

```python
wait_time = 60  # Wait 60 seconds for rate limit reset
```

- Longer wait for rate limits (60s)
- Shorter waits for other errors
- Maximum of 2 retries

### 3. Service Fallback Flow

1. Try preferred data source
2. If it fails, try alternative data source
3. If both fail, use stale cache data if available
4. If no cache data, report error

## Performance Considerations

### API Call Minimization

- Cache results whenever possible
- Bulk fetching for multiple tickers
- Minimum 3-second delay between batch requests

### Database Optimization

- Indexes on frequently queried columns
- Automatic cleanup of old data
- Database vacuuming option for maintenance

### Memory Usage

- Streamlit's cache TTL prevents unlimited memory growth
- Database queries are optimized for specific period ranges

## Implementation Examples

### Initializing the Stock Data Manager

```python
def _ensure_data_manager(self):
    """Ensure the data manager is initialized"""
    if self.data_manager is None:
        # Access the database storage from session state
        db_storage = st.session_state.get('db_storage')
        if db_storage is None:
            raise RuntimeError("Database storage not initialized in session state")
        self.data_manager = StockDataManager(db_storage)
    return self.data_manager
```

### Fetching Stock Data with Automatic Fallback

```python
def fetch_ticker_info(self, ticker):
    """Fetch ticker info with caching and fallback"""
    # Check database cache first
    db_data = self._load_fundamentals_from_db(ticker)
    
    if db_data is not None and data_is_fresh(db_data):
        return create_mock_stock_from_db(db_data)
        
    # Try preferred data source
    try:
        return fetch_from_preferred_source(ticker)
    except Exception:
        # Try fallback source
        try:
            return fetch_from_fallback_source(ticker)
        except Exception:
            # Use stale data if available
            if db_data is not None:
                return create_mock_stock_from_db(db_data)
            # Otherwise, propagate the error
            raise
```

### Display Data Source in UI

```python
# In analysis_tab.py
source = analysis.get("data_source", "unknown")
source_display = {
    "yahoo": "Yahoo Finance",
    "alphavantage": "Alpha Vantage",
    "local": "Local Cache"
}.get(source, source)

st.markdown(f"<span>Data source: {source_display}</span>", unsafe_allow_html=True)
```