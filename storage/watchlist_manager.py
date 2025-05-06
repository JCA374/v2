"""
Watchlist manager for storing and managing stock watchlists.
This file provides the MultiWatchlistManager class which is used in the original application.
It now works with both cookie storage and database storage for a smooth transition.
"""
import uuid
import base64
import json
from datetime import datetime
import streamlit as st

# storage/watchlist_manager.py - Updated version
"""
Watchlist manager for storing and managing stock watchlists.
This file provides the MultiWatchlistManager class which uses database storage.
"""


class MultiWatchlistManager:
    """
    Manages multiple watchlists for a user, stored in a database.
    Provides functionality for creating, renaming, deleting, and sharing watchlists.
    """

    def __init__(self):
        """Initialize the watchlist manager with database storage"""
        # Check if we have database storage available
        self.db_storage = st.session_state.get('db_storage', None)
        self.debug_mode = False  # For debugging
        self.storage_status = None  # Track storage status

        # Initialize watchlists in session state if not present
        if 'watchlists' not in st.session_state:
            watchlists_loaded = False

            # Try to load from database
            if self.db_storage:
                db_data = self.db_storage.load_watchlists()
                if db_data and "watchlists" in db_data:
                    st.session_state.watchlists = db_data["watchlists"]
                    st.session_state.active_watchlist_index = db_data.get(
                        "active_index", 0)
                    self.storage_status = "loaded from database"
                    watchlists_loaded = True
                    if self.debug_mode:
                        st.write(
                            f"Loaded {len(st.session_state.watchlists)} watchlists from database")

            # Create default structure if nothing was loaded
            if not watchlists_loaded:
                # Create default structure with one empty watchlist
                st.session_state.watchlists = [{
                    "id": str(uuid.uuid4()),
                    "name": "Min Watchlist",
                    "stocks": []
                }]
                st.session_state.active_watchlist_index = 0
                self.storage_status = "initialized"

                # Save the initial state to storage
                self._save_to_storage()

        # Make sure active index is valid
        if not isinstance(st.session_state.get('watchlists', []), list) or len(st.session_state.get('watchlists', [])) == 0:
            st.session_state.watchlists = [{
                "id": str(uuid.uuid4()),
                "name": "Min Watchlist",
                "stocks": []
            }]
            st.session_state.active_watchlist_index = 0
            self.storage_status = "reset due to invalid data"
            self._save_to_storage()
        elif st.session_state.get('active_watchlist_index', 0) >= len(st.session_state.get('watchlists', [])):
            st.session_state.active_watchlist_index = 0

    def _save_to_storage(self):
        """Save watchlists to database storage"""
        # Ensure we have valid watchlist data before saving
        if not isinstance(st.session_state.get('watchlists', []), list):
            st.session_state.watchlists = [{
                "id": str(uuid.uuid4()),
                "name": "Min Watchlist",
                "stocks": []
            }]
            st.session_state.active_watchlist_index = 0

        success = False

        # Save to database
        if self.db_storage:
            try:
                success = self.db_storage.save_watchlists(
                    st.session_state.watchlists,
                    st.session_state.active_watchlist_index
                )
                if success:
                    self.storage_status = "saved to database"
                    if self.debug_mode:
                        st.write(
                            f"Saved {len(st.session_state.watchlists)} watchlists to database")
            except Exception as e:
                if self.debug_mode:
                    st.error(f"Error saving to database: {str(e)}")
                success = False

        return success

    def _import_legacy_watchlist(self):
        """Import legacy watchlist.json if it exists"""
        try:
            import os
            if os.path.exists("watchlist.json"):
                with open("watchlist.json", 'r') as f:
                    legacy_stocks = json.load(f)

                    # If we have a legacy watchlist and no stocks in the first watchlist
                    if legacy_stocks and len(st.session_state.watchlists) > 0 and not st.session_state.watchlists[0]["stocks"]:
                        st.session_state.watchlists[0]["stocks"] = legacy_stocks
                        self._save_to_storage()
                        if self.debug_mode:
                            st.write(
                                f"Imported {len(legacy_stocks)} stocks from legacy watchlist")
        except Exception as e:
            if self.debug_mode:
                st.write(f"Error importing legacy watchlist: {str(e)}")
            pass

    def debug_watchlists(self):
        """Debug method to print current watchlist state"""
        st.write("## Current Watchlist State")
        st.write(f"Number of watchlists: {len(self.get_all_watchlists())}")
        st.write(
            f"Active watchlist index: {st.session_state.active_watchlist_index}")
        st.write(f"Storage status: {self.storage_status}")

        for i, watchlist in enumerate(self.get_all_watchlists()):
            st.write(f"### Watchlist {i}: {watchlist['name']}")
            st.write(f"ID: {watchlist['id']}")
            st.write(
                f"Stocks: {', '.join(watchlist['stocks']) if watchlist['stocks'] else 'None'}")

        # Check what's in different storage systems
        if self.db_storage:
            db_data = self.db_storage.load_watchlists()
            if db_data and "watchlists" in db_data:
                st.write("### Database Data")
                st.write(
                    f"Number of watchlists in database: {len(db_data['watchlists'])}")
                st.write(
                    f"Active index in database: {db_data.get('active_index', 'Not set')}")
            else:
                st.write("No watchlist data found in database!")

        # Also check what's saved in cookies
        cookie_data = self.cookie_manager.load_cookie()
        if cookie_data and "watchlists" in cookie_data:
            st.write("### Cookie Data")
            st.write(
                f"Number of watchlists in cookie: {len(cookie_data['watchlists'])}")
            st.write(
                f"Active index in cookie: {cookie_data.get('active_index', 'Not set')}")
            st.write(f"Timestamp: {cookie_data.get('timestamp', 'Not set')}")
        else:
            st.write("No watchlist data found in cookies!")

    def get_all_watchlists(self):
        """Get all watchlists"""
        watchlists = st.session_state.get('watchlists', [])
        # Ensure we always return a list, even if empty
        if not isinstance(watchlists, list):
            watchlists = []
            st.session_state.watchlists = watchlists
        return watchlists

    def get_active_watchlist_index(self):
        """Get the index of the active watchlist"""
        watchlists = self.get_all_watchlists()
        active_index = st.session_state.get('active_watchlist_index', 0)

        # Ensure the index is valid
        if not watchlists:
            return 0
        if active_index >= len(watchlists):
            active_index = 0
            st.session_state.active_watchlist_index = 0
        return active_index

    def get_active_watchlist(self):
        """Get the active watchlist object"""
        watchlists = self.get_all_watchlists()
        if not watchlists:
            # Create a default watchlist if none exists
            default_watchlist = {
                "id": str(uuid.uuid4()),
                "name": "Min Watchlist",
                "stocks": []
            }
            st.session_state.watchlists = [default_watchlist]
            st.session_state.active_watchlist_index = 0
            self._save_to_storage()
            return default_watchlist

        active_index = self.get_active_watchlist_index()
        return watchlists[active_index]

    def get_watchlist(self):
        """Get stocks from the active watchlist (compatibility with old code)"""
        active_watchlist = self.get_active_watchlist()
        return active_watchlist.get("stocks", [])

    def set_active_watchlist(self, index):
        """Set the active watchlist by index"""
        watchlists = self.get_all_watchlists()

        # Handle empty watchlists case
        if not watchlists:
            return False

        # Defensive check to ensure index is within bounds
        if 0 <= index < len(watchlists):
            st.session_state.active_watchlist_index = index
            self._save_to_storage()
            return True
        return False

    def add_watchlist(self, name="Ny Watchlist"):
        """Add a new watchlist"""
        if not name:
            name = "Ny Watchlist"

        new_watchlist = {
            "id": str(uuid.uuid4()),
            "name": name,
            "stocks": []
        }

        # Ensure watchlists exist
        if 'watchlists' not in st.session_state or not isinstance(st.session_state.watchlists, list):
            st.session_state.watchlists = []

        st.session_state.watchlists.append(new_watchlist)
        self._save_to_storage()
        # Return index of new watchlist
        return len(st.session_state.watchlists) - 1

    def rename_watchlist(self, index, new_name):
        """Rename a watchlist"""
        if not new_name:
            return False

        watchlists = self.get_all_watchlists()
        if 0 <= index < len(watchlists):
            st.session_state.watchlists[index]["name"] = new_name
            self._save_to_storage()
            return True
        return False

    def delete_watchlist(self, index):
        """Delete a watchlist by index"""
        watchlists = self.get_all_watchlists()
        if 0 <= index < len(watchlists):
            # Don't delete if it's the only watchlist
            if len(watchlists) <= 1:
                return False

            # Remove the watchlist
            st.session_state.watchlists.pop(index)

            # Adjust active index if needed
            if st.session_state.active_watchlist_index >= index:
                st.session_state.active_watchlist_index = max(
                    0, st.session_state.active_watchlist_index - 1)

            self._save_to_storage()
            return True
        return False

    def add_stock(self, ticker):
        """Add a stock to the active watchlist (compatibility with old code)"""
        # First save the current tab
        current_tab = st.session_state.get('current_tab')

        result = self.add_stock_to_watchlist(
            self.get_active_watchlist_index(), ticker)

        # After the operation, ensure the current tab is preserved
        if current_tab:
            st.session_state['current_tab'] = current_tab

        return result

    def add_stock_to_watchlist(self, index, ticker):
        """Add a stock to a specific watchlist"""
        if not ticker:
            return False

        # Save current tab
        current_tab = st.session_state.get('current_tab')

        # Normalize ticker (uppercase and strip whitespace)
        ticker = ticker.strip().upper()

        watchlists = self.get_all_watchlists()
        if 0 <= index < len(watchlists):
            watchlist = st.session_state.watchlists[index]
            # Ensure stocks is a list
            if not isinstance(watchlist.get("stocks", []), list):
                watchlist["stocks"] = []

            if ticker not in watchlist["stocks"]:
                watchlist["stocks"].append(ticker)
                self._save_to_storage()

                # Preserve current tab
                if current_tab:
                    st.session_state['current_tab'] = current_tab

                return True

        # Preserve current tab even if operation failed
        if current_tab:
            st.session_state['current_tab'] = current_tab

        return False

    def remove_stock(self, ticker):
        """Remove a stock from the active watchlist (compatibility with old code)"""
        # Save current tab
        current_tab = st.session_state.get('current_tab')

        result = self.remove_stock_from_watchlist(
            self.get_active_watchlist_index(), ticker)

        # Restore current tab
        if current_tab:
            st.session_state['current_tab'] = current_tab

        return result

    def remove_stock_from_watchlist(self, index, ticker):
        """Remove a stock from a specific watchlist"""
        # Save current tab
        current_tab = st.session_state.get('current_tab')

        watchlists = self.get_all_watchlists()
        if 0 <= index < len(watchlists):
            watchlist = st.session_state.watchlists[index]
            # Ensure stocks is a list
            if not isinstance(watchlist.get("stocks", []), list):
                watchlist["stocks"] = []
                # Restore tab even if we failed
                if current_tab:
                    st.session_state['current_tab'] = current_tab
                return False

            if ticker in watchlist["stocks"]:
                watchlist["stocks"].remove(ticker)
                self._save_to_storage()

                # Restore current tab
                if current_tab:
                    st.session_state['current_tab'] = current_tab

                return True

        # Restore current tab even if operation failed
        if current_tab:
            st.session_state['current_tab'] = current_tab

        return False

    def export_watchlist(self, index=None):
        """Export a watchlist as a JSON string"""
        if index is None:
            index = self.get_active_watchlist_index()

        watchlists = self.get_all_watchlists()
        if 0 <= index < len(watchlists):
            watchlist = watchlists[index].copy()
            # We don't need to include the ID in the export
            export_data = {
                "name": watchlist["name"],
                "stocks": watchlist["stocks"],
                "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            return json.dumps(export_data)
        return None

    def import_watchlist(self, json_string):
        """Import a watchlist from a JSON string"""
        try:
            data = json.loads(json_string)
            if isinstance(data, dict) and "name" in data and "stocks" in data:
                # Create new watchlist with imported data
                new_watchlist = {
                    "id": str(uuid.uuid4()),
                    "name": data["name"],
                    "stocks": data["stocks"]
                }

                # Add import date if not already present in name
                if "export_date" in data and "importerad" not in new_watchlist["name"]:
                    new_watchlist["name"] += f" (importerad {data['export_date']})"

                if not isinstance(st.session_state.get('watchlists', []), list):
                    st.session_state.watchlists = []

                st.session_state.watchlists.append(new_watchlist)
                self._save_to_storage()
                # Return index of new watchlist
                return len(st.session_state.watchlists) - 1
        except Exception as e:
            if self.debug_mode:
                st.error(f"Fel vid import: {str(e)}")
        return None

    def generate_share_link(self, index=None):
        """Generate a shareable link for a watchlist"""
        if index is None:
            index = self.get_active_watchlist_index()

        json_data = self.export_watchlist(index)
        if json_data:
            # Encode the JSON data to be used in a URL
            encoded = base64.b64encode(json_data.encode()).decode()
            return f"?shared_watchlist={encoded}"
        return None

    def import_from_share_link(self, encoded_data):
        """Import a watchlist from an encoded share link"""
        try:
            # Decode the data from the URL
            json_string = base64.b64decode(encoded_data).decode()
            return self.import_watchlist(json_string)
        except Exception as e:
            if self.debug_mode:
                st.error(f"Fel vid import från delad länk: {str(e)}")
            return None

    def export_all_watchlists(self):
        """Export all watchlists as a JSON string"""
        export_data = {
            "watchlists": self.get_all_watchlists(),
            "active_index": self.get_active_watchlist_index(),
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return json.dumps(export_data, indent=2)

    def import_all_watchlists(self, json_string):
        """Import all watchlists from a JSON string"""
        try:
            data = json.loads(json_string)
            if isinstance(data, dict) and "watchlists" in data:
                # Replace all watchlists
                st.session_state.watchlists = data["watchlists"]

                # Set active index if provided
                if "active_index" in data:
                    active_index = data["active_index"]
                    if 0 <= active_index < len(data["watchlists"]):
                        st.session_state.active_watchlist_index = active_index
                    else:
                        st.session_state.active_watchlist_index = 0

                # Save to storage
                self._save_to_storage()
                return True
        except Exception as e:
            if self.debug_mode:
                st.error(f"Error importing watchlists: {str(e)}")
        return False

    def get_storage_status(self):
        """Return the current storage status"""
        return self.storage_status
