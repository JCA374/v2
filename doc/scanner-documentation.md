# Stock Scanner Integration Documentation

## Overview

This document details the integration of a Stock Scanner tab into the Value & Momentum Stock Strategy App. The scanner provides technical analysis screening capabilities to identify potential stocks for investment based on multiple technical indicators.

## Files Modified/Created

1. **Created**: `tabs/scanner_tab.py` - New tab implementation
2. **Modified**: `app.py` - Added scanner tab to the app's tab definitions
3. **Modified**: `tabs/watchlist_tab.py` - Updated to handle batch analysis of stocks selected in the scanner

## Implementation Details

### 1. Scanner Tab Implementation (`tabs/scanner_tab.py`)

The scanner tab implements:

- Technical screening based on multiple indicators:
  - EMA 50/200 crossovers
  - RSI range filtering
  - Volume surge detection
  - MACD histogram positivity

- Efficient data fetching:
  - Batch downloading in chunks (up to 50 stocks at a time)
  - Caching with `@st.cache_data` to prevent API rate limiting
  - Organized data structure by ticker

- Integration with existing watchlists:
  - Add screened stocks to any of the user's watchlists
  - Send selected stocks for batch analysis

#### Key Functions:

- `render_scanner_tab()`: Main entry point rendering the scanner UI
- `fetch_bulk_data()`: Cached function to download data in batches
- `screen_stocks()`: Applies technical filters to find matching stocks
- `compute_rsi()`: Calculates RSI with proper error handling

### 2. App.py Updates

```python
# New import
from tabs.scanner_tab import render_scanner_tab

# Updated tabs dictionary
tabs = {
    "Watchlist & Batch Analysis": render_watchlist_tab,
    "Enskild Aktieanalys": render_analysis_tab,
    "Stock Scanner": render_scanner_tab,  # Added scanner tab
}
```

### 3. Watchlist Tab Integration (`tabs/watchlist_tab.py`)

The `render_watchlist_tab()` function was updated to handle batch analysis of stocks selected in the Scanner tab:

```python
def render_watchlist_tab():
    """Render the watchlist and batch analysis tab"""
    # Access shared objects from session state
    strategy = st.session_state.strategy
    watchlist_manager = st.session_state.watchlist_manager

    # Handle stocks selected from Scanner tab
    if 'analyze_selected' in st.session_state and st.session_state.analyze_selected:
        if 'batch_analysis_tickers' in st.session_state and st.session_state.batch_analysis_tickers:
            selected_tickers = st.session_state.batch_analysis_tickers
            
            # Show analysis in progress
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Callback for progress
            def update_progress(progress, text):
                progress_bar.progress(progress)
                status_text.text(text)

            # Run batch analysis
            results = strategy.batch_analyze(selected_tickers, update_progress)
            st.session_state.analysis_results = results

            # Remove progress bar when done
            progress_bar.empty()
            status_text.empty()

            st.success(f"Analyzed {len(selected_tickers)} stocks from Scanner")
            
            # Clear the flags so it doesn't re-analyze on every rerun
            st.session_state.analyze_selected = False
    
    # Rest of the original function...
```

## Integration Points and Session State

The scanner tab uses these session state variables:

- `st.session_state.batch_analysis_tickers`: List of ticker symbols selected for analysis
- `st.session_state.analyze_selected`: Flag indicating analysis should be performed
- `st.session_state.watchlist_manager`: Accesses the shared watchlist manager
- `st.session_state.strategy`: Accesses the shared strategy instance
- `st.session_state.current_tab`: Used to navigate between tabs

## Usage Instructions

1. Navigate to the "Stock Scanner" tab
2. Configure screening parameters:
   - Set history period (3mo, 6mo, 1y)
   - Set RSI range (min/max values)
   - Set volume multiplier threshold
   - Set lookback period for EMA crossovers
3. The scanner automatically processes stocks and displays matching results
4. From the results table:
   - Select stocks to add to a specific watchlist
   - Or select stocks for detailed batch analysis
5. When performing batch analysis, you'll be automatically redirected to the Watchlist tab where analysis will run

## Common Issues and Debugging

### Issue: Scanner doesn't display any results

**Troubleshooting**:
- Ensure watchlists contain valid ticker symbols
- Check if criteria are too restrictive (widen RSI range, lower volume threshold)
- Verify internet connection for API access

### Issue: Batch analysis doesn't run after selecting stocks

**Troubleshooting**:
- Verify session state variables are correctly set:
  ```python
  st.write(st.session_state.get('analyze_selected'))
  st.write(st.session_state.get('batch_analysis_tickers'))
  ```
- Ensure the `render_watchlist_tab()` function has the integration code
- Check for any errors in the browser console or Streamlit output

### Issue: Stock data fetching is slow or failing

**Troubleshooting**:
- Reduce the number of stocks in your watchlists
- Try changing the chunk_size parameter (default: 50)
- Use a more recent time period (e.g., '3mo' instead of '1y')
- Clear the cache with:
  ```python
  st.cache_data.clear()
  ```

## Code Preservation Notes

When updating the app, be careful not to remove:

1. The scanner tab import in `app.py`
2. The scanner tab entry in the tabs dictionary
3. The analysis integration code at the beginning of `render_watchlist_tab()`

If you're adding other features that modify the same files, ensure these sections are preserved. The scanner integration uses standard Streamlit session state patterns and follows the app's established architecture.
