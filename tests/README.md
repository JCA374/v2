# Test Suite for Value and Momentum Stock Strategy App

This directory contains all the tests for the Value and Momentum Stock Strategy application, including tests for the new multiple watchlists feature.

## Test Structure

The test suite is organized as follows:

```
tests/
├── __init__.py                 # Makes the directory a Python package
├── README.md                   # This file
├── test_watchlist_manager.py   # Tests for MultiWatchlistManager and CookieManager
└── test_app_integration.py     # Integration tests for the application UI
```

## Running the Tests

You can run all tests from the project root using:

```bash
python run_tests.py
```

Or run individual test files directly:

```bash
python -m unittest tests.test_watchlist_manager
python -m unittest tests.test_app_integration
```

## Test Descriptions

### test_watchlist_manager.py

Tests for the watchlist management system:

- **TestMultiWatchlistManager**: Tests the functionality of the `MultiWatchlistManager` class
  - Creating, renaming, and deleting watchlists
  - Adding and removing stocks from watchlists
  - Switching between active watchlists
  - Exporting and importing watchlists
  - Generating and using share links

- **TestCookieManager**: Tests the cookie-based storage system
  - Saving data to browser cookies
  - Loading data from cookies
  - Clearing cookie data

### test_app_integration.py

Integration tests for the application UI:

- **TestAppIntegration**: Tests the UI components and interactions
  - App initialization and setup
  - Watchlist dropdown selection
  - Adding and managing watchlists through the UI
  - Stock addition and removal from the UI
  - Batch analysis with different watchlists
  - Import/export functionality via the UI

- **TestWatchlistSharingWorkflow**: Tests the complete sharing workflow
  - Creating and sharing a watchlist
  - Importing a shared watchlist

## Adding New Tests

To add new tests:

1. Create a new test file in this directory with a name starting with `test_`
2. Import the necessary modules from the parent directory using:
   ```python
   import sys
   import os
   sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
   ```
3. Create test classes that inherit from `unittest.TestCase`
4. Add individual test methods starting with `test_`

## Test Coverage

The test suite aims to cover all aspects of the multiple watchlists feature:

- Core functionality of managing multiple watchlists
- Cookie-based storage for persistence
- Sharing functionality via links and JSON
- UI components and interactions

New tests should be added when implementing new features or fixing bugs to maintain comprehensive test coverage.