from v2.storage.cookie_manager import CookieManager
from v2.old.watchlist import MultiWatchlistManager
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import sys
import os
from datetime import datetime
import base64

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


class TestMultiWatchlistManager(unittest.TestCase):

    def setUp(self):
        # Create a mock session_state that supports attribute access
        self.mock_session_state = MockSessionState()
        self.session_patcher = patch(
            'streamlit.session_state', self.mock_session_state)
        self.session_patcher.start()

        # Mock the CookieManager
        self.cookie_manager_mock = MagicMock()
        self.cookie_manager_mock.load_cookie.return_value = None

        # Create a patcher for the CookieManager
        self.cookie_manager_patcher = patch(
            'watchlist.CookieManager', return_value=self.cookie_manager_mock)
        self.cookie_manager_patcher.start()

        # Initialize the watchlist manager
        self.manager = MultiWatchlistManager()

    def tearDown(self):
        # Stop all patchers
        self.session_patcher.stop()
        self.cookie_manager_patcher.stop()

    def test_initialization(self):
        """Test that the watchlist manager initializes correctly"""
        # Check that we have a default watchlist
        self.assertEqual(len(self.manager.get_all_watchlists()), 1)
        self.assertEqual(self.manager.get_active_watchlist()
                         ["name"], "Min Watchlist")
        self.assertEqual(self.manager.get_active_watchlist()["stocks"], [])

    def test_add_watchlist(self):
        """Test adding a new watchlist"""
        # Add a new watchlist
        new_index = self.manager.add_watchlist("Test Watchlist")

        # Check that it was added
        self.assertEqual(len(self.manager.get_all_watchlists()), 2)
        self.assertEqual(self.manager.get_all_watchlists()[
                         new_index]["name"], "Test Watchlist")
        self.assertEqual(self.manager.get_all_watchlists()
                         [new_index]["stocks"], [])

        # Verify that save_to_cookies was called
        self.cookie_manager_mock.save_cookie.assert_called()

    def test_rename_watchlist(self):
        """Test renaming a watchlist"""
        # Add a watchlist first
        index = self.manager.add_watchlist("Old Name")

        # Rename it
        result = self.manager.rename_watchlist(index, "New Name")

        # Check that it was renamed
        self.assertTrue(result)
        self.assertEqual(self.manager.get_all_watchlists()
                         [index]["name"], "New Name")

        # Try to rename with an empty name (should fail)
        result = self.manager.rename_watchlist(index, "")
        self.assertFalse(result)

        # Try to rename with an invalid index (should fail)
        result = self.manager.rename_watchlist(99, "Invalid")
        self.assertFalse(result)

    def test_delete_watchlist(self):
        """Test deleting a watchlist"""
        # Add a couple watchlists
        self.manager.add_watchlist("Watchlist 1")
        self.manager.add_watchlist("Watchlist 2")

        # Should now have 3 watchlists (including default)
        self.assertEqual(len(self.manager.get_all_watchlists()), 3)

        # Delete the middle one
        result = self.manager.delete_watchlist(1)

        # Check that it was deleted
        self.assertTrue(result)
        self.assertEqual(len(self.manager.get_all_watchlists()), 2)
        self.assertEqual(self.manager.get_all_watchlists()
                         [1]["name"], "Watchlist 2")

        # Try to delete with an invalid index (should fail)
        result = self.manager.delete_watchlist(99)
        self.assertFalse(result)

        # Try to delete when there's only one watchlist left (should fail)
        # First delete the second watchlist
        self.manager.delete_watchlist(1)
        self.assertEqual(len(self.manager.get_all_watchlists()), 1)

        # Now try to delete the last one
        result = self.manager.delete_watchlist(0)
        self.assertFalse(result)
        self.assertEqual(len(self.manager.get_all_watchlists()), 1)

    def test_add_stock(self):
        """Test adding a stock to a watchlist"""
        # Add a stock to the default watchlist
        result = self.manager.add_stock("AAPL")

        # Check that it was added
        self.assertTrue(result)
        self.assertIn("AAPL", self.manager.get_watchlist())

        # Add another stock
        self.manager.add_stock("MSFT")
        self.assertIn("MSFT", self.manager.get_watchlist())

        # Try to add the same stock again (should fail)
        result = self.manager.add_stock("AAPL")
        self.assertFalse(result)

        # Try to add an empty ticker (should fail)
        result = self.manager.add_stock("")
        self.assertFalse(result)

        # Add a stock to a specific watchlist
        self.manager.add_watchlist("Tech Stocks")
        result = self.manager.add_stock_to_watchlist(1, "GOOG")
        self.assertTrue(result)
        self.assertIn("GOOG", self.manager.get_all_watchlists()[1]["stocks"])

        # The stock should not be in the default watchlist
        self.assertNotIn("GOOG", self.manager.get_watchlist())

    def test_remove_stock(self):
        """Test removing a stock from a watchlist"""
        # First add some stocks
        self.manager.add_stock("AAPL")
        self.manager.add_stock("MSFT")

        # Now remove one
        result = self.manager.remove_stock("AAPL")

        # Check that it was removed
        self.assertTrue(result)
        self.assertNotIn("AAPL", self.manager.get_watchlist())
        self.assertIn("MSFT", self.manager.get_watchlist())

        # Try to remove a stock that doesn't exist (should fail)
        result = self.manager.remove_stock("AAPL")
        self.assertFalse(result)

        # Remove from a specific watchlist
        self.manager.add_watchlist("Tech Stocks")
        self.manager.add_stock_to_watchlist(1, "GOOG")
        result = self.manager.remove_stock_from_watchlist(1, "GOOG")
        self.assertTrue(result)
        self.assertNotIn(
            "GOOG", self.manager.get_all_watchlists()[1]["stocks"])

    def test_set_active_watchlist(self):
        """Test setting the active watchlist"""
        # Add a couple watchlists
        self.manager.add_watchlist("Watchlist 1")
        self.manager.add_watchlist("Watchlist 2")

        # Set the second one as active
        result = self.manager.set_active_watchlist(1)

        # Check that it was set
        self.assertTrue(result)
        self.assertEqual(self.manager.get_active_watchlist_index(), 1)
        self.assertEqual(self.manager.get_active_watchlist()
                         ["name"], "Watchlist 1")

        # Try to set an invalid index (should fail)
        result = self.manager.set_active_watchlist(99)
        self.assertFalse(result)
        # Should not change
        self.assertEqual(self.manager.get_active_watchlist_index(), 1)

    @patch('watchlist.datetime')
    def test_export_import_watchlist(self, mock_datetime):
        """Test exporting and importing a watchlist"""
        # Set a fixed date for testing
        mock_datetime.now.return_value.strftime.return_value = "2025-04-24 12:00:00"

        # Add some stocks to the default watchlist
        self.manager.add_stock("AAPL")
        self.manager.add_stock("MSFT")

        # Export the watchlist
        export_data = self.manager.export_watchlist()

        # Check that the export data is valid JSON
        exported = json.loads(export_data)
        self.assertEqual(exported["name"], "Min Watchlist")
        self.assertEqual(exported["stocks"], ["AAPL", "MSFT"])
        self.assertEqual(exported["export_date"], "2025-04-24 12:00:00")

        # Add a new watchlist to import into
        self.manager.add_watchlist("Empty Watchlist")

        # Import the watchlist
        import_index = self.manager.import_watchlist(export_data)

        # Check that it was imported
        self.assertEqual(import_index, 2)  # Should be the third watchlist
        self.assertEqual(self.manager.get_all_watchlists()[import_index]["name"],
                         "Min Watchlist (importerad 2025-04-24 12:00:00)")
        self.assertEqual(self.manager.get_all_watchlists()[import_index]["stocks"],
                         ["AAPL", "MSFT"])

    def test_share_link(self):
        """Test generating and importing from a share link"""
        # Add a stock to the default watchlist
        self.manager.add_stock("AAPL")

        # Generate a share link
        share_link = self.manager.generate_share_link()

        # The link should start with the query parameter
        self.assertTrue(share_link.startswith("?shared_watchlist="))

        # Extract the encoded data
        encoded_data = share_link.replace("?shared_watchlist=", "")

        # Simulate importing from the share link
        with patch.object(self.manager, 'import_watchlist') as mock_import:
            mock_import.return_value = 1
            result = self.manager.import_from_share_link(encoded_data)

            # Check that import_watchlist was called with the decoded data
            decoded_data = base64.b64decode(encoded_data).decode()
            mock_import.assert_called_with(decoded_data)
            self.assertEqual(result, 1)

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='["AAPL", "MSFT"]')
    def test_import_legacy_watchlist(self, mock_file, mock_exists):
        """Test importing a legacy watchlist"""
        # Set up the mock to return True for os.path.exists
        mock_exists.return_value = True

        # Create a fresh session state for this test
        fresh_session_state = MockSessionState()
        fresh_session_state.watchlists = [{
            "id": "123",
            "name": "Min Watchlist",
            "stocks": []
        }]

        # Create a new instance to trigger the import
        with patch('streamlit.session_state', fresh_session_state):
            manager = MultiWatchlistManager()

            # Check that the legacy stocks were imported
            self.assertEqual(manager.get_watchlist(), ["AAPL", "MSFT"])


class TestCookieManager(unittest.TestCase):

    def setUp(self):
        # Initialize the cookie manager
        self.manager = CookieManager("test_cookie")

    @patch('streamlit.markdown')
    def test_save_cookie(self, mock_markdown):
        """Test saving a cookie"""
        # Create a mock session state
        mock_session_state = MockSessionState()

        with patch('streamlit.session_state', mock_session_state):
            # Save some data
            test_data = {"test": "data"}
            self.manager.save_cookie(test_data)

            # Check that the data was encoded and stored in session state
            cookie_key = "test_cookie_encoded"
            self.assertIn(cookie_key, mock_session_state)

            # The data should be encoded as base64
            encoded_data = mock_session_state[cookie_key]
            decoded_data = json.loads(base64.b64decode(encoded_data).decode())
            self.assertEqual(decoded_data, test_data)

            # Check that markdown was called with JavaScript to store in localStorage
            mock_markdown.assert_called()
            js_call = mock_markdown.call_args[0][0]
            self.assertIn("localStorage.setItem", js_call)
            self.assertIn("test_cookie", js_call)

    @patch('streamlit.markdown')
    @patch('streamlit.text_input')
    def test_load_cookie_from_session(self, mock_text_input, mock_markdown):
        """Test loading a cookie from session state"""
        # First store some data in session state
        test_data = {"test": "data"}
        encoded_data = base64.b64encode(
            json.dumps(test_data).encode()).decode()

        # Create a mock session state with the encoded data
        mock_session_state = MockSessionState()
        mock_session_state["test_cookie_encoded"] = encoded_data

        with patch('streamlit.session_state', mock_session_state):
            # Now load the cookie
            result = self.manager.load_cookie()

            # Check that the correct data was returned
            self.assertEqual(result, test_data)

            # JavaScript should still be injected for future loads
            mock_markdown.assert_called()

    @patch('streamlit.markdown')
    @patch('streamlit.text_input')
    def test_load_cookie_from_callback(self, mock_text_input, mock_markdown):
        """Test loading a cookie from a callback"""
        # Set up the text input to return encoded data
        test_data = {"test": "data"}
        encoded_data = base64.b64encode(
            json.dumps(test_data).encode()).decode()
        mock_text_input.return_value = encoded_data

        # Create an empty mock session state
        mock_session_state = MockSessionState()

        with patch('streamlit.session_state', mock_session_state):
            # Load the cookie (with empty session state)
            result = self.manager.load_cookie()

            # Check that the correct data was returned
            self.assertEqual(result, test_data)

            # The data should now be in session state
            cookie_key = "test_cookie_encoded"
            self.assertIn(cookie_key, mock_session_state)
            self.assertEqual(mock_session_state[cookie_key], encoded_data)

    @patch('streamlit.markdown')
    def test_clear_cookie(self, mock_markdown):
        """Test clearing a cookie"""
        # Create a mock session state with some cookie data
        mock_session_state = MockSessionState()
        mock_session_state["test_cookie_encoded"] = "data"

        with patch('streamlit.session_state', mock_session_state):
            # Clear the cookie
            self.manager.clear_cookie()

            # Check that the data was removed from session state
            cookie_key = "test_cookie_encoded"
            self.assertNotIn(cookie_key, mock_session_state)

            # Check that markdown was called with JavaScript to remove from localStorage
            mock_markdown.assert_called()
            js_call = mock_markdown.call_args[0][0]
            self.assertIn("localStorage.removeItem", js_call)
            self.assertIn("test_cookie", js_call)


if __name__ == '__main__':
    unittest.main()
