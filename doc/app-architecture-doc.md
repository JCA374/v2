# Value & Momentum Stock Strategy App Architecture

This document describes the architecture of the Value & Momentum Stock Strategy application, designed to be modular and easy to extend. This architecture is specifically structured to make it easier for a Language Model (LLM) to add new features without disrupting existing functionality.

## Table of Contents

1. [Overall Architecture](#overall-architecture)
2. [Directory Structure](#directory-structure)
3. [Key Components](#key-components)
4. [Adding New Features](#adding-new-features)
5. [State Management](#state-management)
6. [Coding Standards](#coding-standards)
7. [Future Development Plans](#future-development-plans)

## Overall Architecture

The application uses a modular, tab-based architecture where:

- The main app (`app.py`) acts as an orchestration layer that initializes components and manages tabs
- Each UI tab is implemented in its own file
- State is shared via Streamlit's session state
- Persistence is handled by dedicated storage modules
- Core business logic (stock strategy) is separated from UI concerns

This architecture makes it possible to add new tabs or functionality without modifying existing code, reducing the risk of regression when updating through an LLM.

## Directory Structure

```
value_momentum_app/
├── app.py               # Main app configuration and tab orchestration
├── strategy.py          # Value momentum strategy implementation
├── helpers.py           # Helper functions for UI and data processing
├── main.py              # Application entry point
│
├── storage/             # Persistence layer
│   ├── __init__.py
│   ├── cookie_manager.py     # Browser storage functionality
│   └── watchlist_manager.py  # Watchlist management
│
└── tabs/                # UI tabs - each tab in its own file
    ├── __init__.py
    ├── watchlist_tab.py      # Watchlist & batch analysis
    ├── analysis_tab.py       # Individual stock analysis
    └── [future_tab].py       # Future tabs added here
```

## Key Components

### 1. App Orchestration (app.py)

This is the main entry point that:
- Initializes shared objects (strategy, watchlist_manager)
- Registers and renders tabs
- Handles shared UI elements like the sidebar
- Processes URL parameters

Example of how tabs are registered:
```python
# Define tabs - EASILY EXTENSIBLE HERE
tabs = {
    "Watchlist & Batch Analysis": render_watchlist_tab,
    "Enskild Aktieanalys": render_analysis_tab,
    # Add new tabs here by adding new entries to this dictionary
    # "New Tab Name": render_new_tab_function,
}
```

### 2. UI Tabs (tabs/*.py)

Each tab is a separate module with its own render function. Tabs:
- Access shared objects via session_state
- Handle their own UI layout and interactions
- Implement tab-specific functionality
- May be composed of smaller functions for clarity

Example tab render function:
```python
def render_watchlist_tab():
    """Render the watchlist and batch analysis tab"""
    # Access shared objects
    strategy = st.session_state.strategy
    watchlist_manager = st.session_state.watchlist_manager
    
    # Create the layout
    col1, col2 = st.columns([1, 3])
    
    with col1:
        render_watchlist_management(watchlist_manager, strategy)
    
    with col2:
        render_analysis_results(strategy)
```

### 3. Storage (storage/*.py)

The storage layer handles persistence:
- `cookie_manager.py` provides browser-based storage
- `watchlist_manager.py` manages watchlist data
- Uses session state for in-session storage and cookies for persistence

### 4. Strategy Logic (strategy.py)

Contains the core business logic:
- Stock analysis algorithms
- Technical indicators
- Trading signals
- Is independent of UI concerns

## Adding New Features

### Adding a New Tab

To add a new tab to the application:

1. Create a new file in the `tabs` directory (e.g., `tabs/comparison_tab.py`)
2. Implement a render function (e.g., `render_comparison_tab()`)
3. Add it to the tabs dictionary in `app.py`

Example of a new tab file:
```python
# tabs/comparison_tab.py
import streamlit as st

def render_comparison_tab():
    """Render the stock comparison tab"""
    st.subheader("Jämför Aktier")
    
    # Access shared objects
    strategy = st.session_state.strategy
    watchlist_manager = st.session_state.watchlist_manager
    
    # Implement tab UI and functionality
    stocks_to_compare = st.multiselect(
        "Välj aktier att jämföra",
        options=watchlist_manager.get_watchlist(),
        max_selections=5
    )
    
    if stocks_to_compare and st.button("Jämför"):
        with st.spinner("Jämför aktier..."):
            # Tab-specific functionality
            compare_stocks(strategy, stocks_to_compare)

def compare_stocks(strategy, tickers):
    """Compare multiple stocks"""
    # Implementation details
    pass
```

Then in `app.py`, add the new tab:
```python
# In app.py - import the new tab
from tabs.comparison_tab import render_comparison_tab

# Then in the create_streamlit_app function:
tabs = {
    "Watchlist & Batch Analysis": render_watchlist_tab,
    "Enskild Aktieanalys": render_analysis_tab,
    "Jämför Aktier": render_comparison_tab,  # New tab added here
}
```

### Adding Features to an Existing Tab

To add new features to an existing tab:

1. Locate the appropriate tab file
2. Add new functions or modify existing ones
3. Ensure the main render function incorporates the new functionality
4. Use session state to share data with other tabs if needed

## State Management

State in the application is managed through Streamlit's `session_state`:

- Core objects are stored in session_state during initialization
- All tabs access the same instance of these objects
- Examples of shared state:
  - `st.session_state.strategy`: The ValueMomentumStrategy instance
  - `st.session_state.watchlist_manager`: The MultiWatchlistManager instance
  - `st.session_state.analysis_results`: Results of batch analysis

## Coding Standards

When modifying or extending the application:

1. Maintain the separation of concerns:
   - UI logic in tab files
   - Data persistence in storage files
   - Business logic in strategy.py

2. Use descriptive function names:
   - Tab render functions should start with `render_`
   - Helper functions should be named for their purpose

3. Document extensively:
   - Every function should have a docstring
   - Complex logic should have inline comments
   - Update this documentation when adding features

4. Handle errors gracefully:
   - Use try/except blocks for error-prone operations
   - Show informative error messages to users

## Future Development Plans

The application is designed to be extended in the following ways:

### Planned Tabs

1. **Portfolio Management Tab**
   - Track portfolio performance
   - Calculate returns and metrics
   - Visualize asset allocation

2. **Stock Screener Tab**
   - Filter stocks based on criteria
   - Save and load screening configurations
   - Apply the Value & Momentum strategy to screening results

3. **Market Overview Tab**
   - Track market indices
   - Show sector performance
   - Display economic indicators

### Planned Features

1. **Enhanced Watchlist Management**
   - Add notes to stocks
   - Group stocks by industry or custom tags
   - Set price alerts

2. **Advanced Visualization**
   - Candlestick charts
   - Additional technical indicators
   - Custom date ranges

3. **Data Export**
   - Export analysis to PDF
   - Email reports
   - Schedule regular updates

## Implementation Guidelines for LLMs

When extending the application as an LLM:

1. Focus on one module at a time
2. Maintain the existing architectural pattern
3. Use the session state for shared objects
4. Add detailed comments explaining your changes
5. Ensure backward compatibility with existing features
6. Add comprehensive error handling

By following this architecture and these guidelines, the application can be continuously improved without risking regression or conflicts between features.
