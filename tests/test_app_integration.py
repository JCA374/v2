from app import create_streamlit_app
from v2.old.strategy import ValueMomentumStrategy
# Updated to use MultiWatchlistManager
from v2.old.watchlist import MultiWatchlistManager
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules we want to test


# Create a custom class to mock Streamlit's session_state with dot notation access
class MockSessionState(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getattr__(self, key):
        if key in self:
            return self[key]
        return None

    def __setattr__(self, key, value):
        self[key] = value


class TestAppFunctionality(unittest.TestCase):
    """Test basic functionality of the app"""

    def setUp(self):
        # Create a mock session state
        self.mock_session_state = MockSessionState()
        self.session_patcher = patch(
            'streamlit.session_state', self.mock_session_state)
        self.session_patcher.start()

        # Mock other modules as needed
        self.mock_patchers = []
        for module in ['streamlit.title', 'streamlit.set_page_config', 'streamlit.tabs',
                       'streamlit.sidebar', 'streamlit.columns', 'streamlit.selectbox',
                       'streamlit.button', 'streamlit.success', 'streamlit.error']:
            patcher = patch(module, MagicMock())
            patcher.start()
            self.mock_patchers.append(patcher)

    def tearDown(self):
        # Stop all patchers
        self.session_patcher.stop()
        for patcher in self.mock_patchers:
            patcher.stop()

    @patch('app.ValueMomentumStrategy')
    @patch('app.MultiWatchlistManager')  # Updated to use MultiWatchlistManager
    def test_app_initialization(self, mock_watchlist_cls, mock_strategy_cls):
        """Test that the app initializes correctly with the required components"""
        # Configure mocks
        mock_strategy = MagicMock()
        mock_watchlist = MagicMock()
        mock_strategy_cls.return_value = mock_strategy
        mock_watchlist_cls.return_value = mock_watchlist

        # Call the app creation function
        with patch('app.st.rerun', MagicMock()):
            create_streamlit_app()

        # Check that the strategy and watchlist manager were initialized
        mock_strategy_cls.assert_called_once()
        mock_watchlist_cls.assert_called_once()

    @patch('app.ValueMomentumStrategy')
    @patch('app.MultiWatchlistManager')  # Updated to use MultiWatchlistManager
    def test_add_stock_to_watchlist(self, mock_watchlist_cls, mock_strategy_cls):
        """Test adding a stock to the watchlist"""
        # Configure mocks
        mock_strategy = MagicMock()
        mock_watchlist = MagicMock()
        mock_strategy_cls.return_value = mock_strategy
        mock_watchlist_cls.return_value = mock_watchlist
        mock_watchlist.get_watchlist.return_value = []

        # Mock text input for ticker
        with patch('streamlit.text_input', return_value="AAPL"):
            # Mock button click
            with patch('streamlit.button', lambda *args, **kwargs:
                       args and args[0] == "Lägg till"):
                # Call the app
                with patch('app.st.rerun', MagicMock()):
                    create_streamlit_app()

        # Check that add_stock was called with the ticker
        mock_watchlist.add_stock.assert_called_with("AAPL")


if __name__ == '__main__':
    unittest.main()
