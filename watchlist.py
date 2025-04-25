import pandas as pd
import numpy as np
import json
import streamlit as st
import base64
import uuid
from datetime import datetime
from urllib.parse import quote, unquote
from cookie_manager import CookieManager


class MultiWatchlistManager:
    """
    Manages multiple watchlists for a user, stored in cookies/session state.
    Provides functionality for creating, renaming, deleting, and sharing watchlists.
    """

    def __init__(self):
        # Create cookie manager
        self.cookie_manager = CookieManager(cookie_name="watchlists_data")

        # Initialize watchlists in session state if not present
        if 'watchlists' not in st.session_state:
            # Try to load from cookies first
            cookie_data = self.cookie_manager.load_cookie()

            if cookie_data and "watchlists" in cookie_data:
                st.session_state.watchlists = cookie_data["watchlists"]
                st.session_state.active_watchlist_index = cookie_data.get(
                    "active_index", 0)
            else:
                # Create default structure with one empty watchlist
                st.session_state.watchlists = [{
                    "id": str(uuid.uuid4()),
                    "name": "Min Watchlist",
                    "stocks": []
                }]
                st.session_state.active_watchlist_index = 0

                # For compatibility with old version, check if watchlist.json exists
                # and import its contents as the first watchlist
                self._import_legacy_watchlist()

        # Make sure active index is valid
        if st.session_state.active_watchlist_index >= len(st.session_state.watchlists):
            st.session_state.active_watchlist_index = 0

    def _save_to_cookies(self):
        """Save watchlists to cookies"""
        data = {
            "watchlists": st.session_state.watchlists,
            "active_index": st.session_state.active_watchlist_index
        }
        self.cookie_manager.save_cookie(data)

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
                        self._save_to_cookies()
        except:
            pass

    def get_all_watchlists(self):
        """Get all watchlists"""
        return st.session_state.watchlists

    def get_active_watchlist_index(self):
        """Get the index of the active watchlist"""
        return st.session_state.active_watchlist_index

    def get_active_watchlist(self):
        """Get the active watchlist object"""
        if self.get_all_watchlists():
            return self.get_all_watchlists()[self.get_active_watchlist_index()]
        return {"id": "", "name": "", "stocks": []}

    def get_watchlist(self):
        """Get stocks from the active watchlist (compatibility with old code)"""
        return self.get_active_watchlist().get("stocks", [])

    def set_active_watchlist(self, index):
        """Set the active watchlist by index"""
        if 0 <= index < len(self.get_all_watchlists()):
            st.session_state.active_watchlist_index = index
            self._save_to_cookies()
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

        st.session_state.watchlists.append(new_watchlist)
        self._save_to_cookies()
        # Return index of new watchlist
        return len(st.session_state.watchlists) - 1

    def rename_watchlist(self, index, new_name):
        """Rename a watchlist"""
        if not new_name:
            return False

        if 0 <= index < len(self.get_all_watchlists()):
            st.session_state.watchlists[index]["name"] = new_name
            self._save_to_cookies()
            return True
        return False

    def delete_watchlist(self, index):
        """Delete a watchlist by index"""
        if 0 <= index < len(self.get_all_watchlists()):
            # Don't delete if it's the only watchlist
            if len(self.get_all_watchlists()) <= 1:
                return False

            # Remove the watchlist
            st.session_state.watchlists.pop(index)

            # Adjust active index if needed
            if st.session_state.active_watchlist_index >= index:
                st.session_state.active_watchlist_index = max(
                    0, st.session_state.active_watchlist_index - 1)

            self._save_to_cookies()
            return True
        return False

    def add_stock(self, ticker):
        """Add a stock to the active watchlist (compatibility with old code)"""
        return self.add_stock_to_watchlist(self.get_active_watchlist_index(), ticker)

    def add_stock_to_watchlist(self, index, ticker):
        """Add a stock to a specific watchlist"""
        if not ticker:
            return False

        if 0 <= index < len(self.get_all_watchlists()):
            watchlist = st.session_state.watchlists[index]
            if ticker not in watchlist["stocks"]:
                watchlist["stocks"].append(ticker)
                self._save_to_cookies()
                return True
        return False

    def remove_stock(self, ticker):
        """Remove a stock from the active watchlist (compatibility with old code)"""
        return self.remove_stock_from_watchlist(self.get_active_watchlist_index(), ticker)

    def remove_stock_from_watchlist(self, index, ticker):
        """Remove a stock from a specific watchlist"""
        if 0 <= index < len(self.get_all_watchlists()):
            watchlist = st.session_state.watchlists[index]
            if ticker in watchlist["stocks"]:
                watchlist["stocks"].remove(ticker)
                self._save_to_cookies()
                return True
        return False

    def export_watchlist(self, index=None):
        """Export a watchlist as a JSON string"""
        if index is None:
            index = self.get_active_watchlist_index()

        if 0 <= index < len(self.get_all_watchlists()):
            watchlist = st.session_state.watchlists[index].copy()
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

                st.session_state.watchlists.append(new_watchlist)
                self._save_to_cookies()
                # Return index of new watchlist
                return len(st.session_state.watchlists) - 1
        except Exception as e:
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
            st.error(f"Fel vid import från delad länk: {str(e)}")
            return None
