"""
Database-backed watchlist manager that replaces the cookie-based system.
This version uses the DatabaseStorage class for persistence.
"""
import streamlit as st
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Union


class DBWatchlistManager:
    """
    Manages multiple watchlists for a user, stored in a SQLite database.
    Provides functionality for creating, renaming, deleting, and sharing watchlists.
    """

    def __init__(self, db_storage=None):
        """Initialize the watchlist manager with database storage"""
        # Use the provided db_storage or get it from session state
        self.db_storage = db_storage or st.session_state.get('db_storage')
        self.debug_mode = False  # For debugging

        if not self.db_storage:
            raise ValueError(
                "Database storage not initialized. Please initialize it first.")

        # Initialize watchlists in session state if not present
        if 'watchlists' not in st.session_state:
            # Try to load from database first
            db_data = self.db_storage.load_watchlists()

            if db_data and "watchlists" in db_data:
                st.session_state.watchlists = db_data["watchlists"]
                st.session_state.active_watchlist_index = db_data.get(
                    "active_index", 0)
                if self.debug_mode:
                    st.write(
                        f"Loaded {len(st.session_state.watchlists)} watchlists from database")
            else:
                # Create default structure with one empty watchlist
                st.session_state.watchlists = [{
                    "id": str(uuid.uuid4()),
                    "name": "Min Watchlist",
                    "stocks": []
                }]
                st.session_state.active_watchlist_index = 0

                # Save the initial state to database
                self._save_to_database()
                if self.debug_mode:
                    st.write("Created default watchlist and saved to database")

        # Make sure active index is valid
        if st.session_state.active_watchlist_index >= len(st.session_state.watchlists):
            st.session_state.active_watchlist_index = 0

    def _save_to_database(self) -> bool:
        """Save watchlists to the database"""
        if not self.db_storage:
            if self.debug_mode:
                st.error("Database storage not available")
            return False

        success = self.db_storage.save_watchlists(
            st.session_state.watchlists,
            st.session_state.active_watchlist_index
        )

        if self.debug_mode:
            if success:
                st.write(
                    f"Saved {len(st.session_state.watchlists)} watchlists to database")
            else:
                st.write("Failed to save watchlists to database")

        return success

    def debug_watchlists(self) -> None:
        """Debug method to print current watchlist state"""
        st.write("## Current Watchlist State")
        st.write(f"Number of watchlists: {len(st.session_state.watchlists)}")
        st.write(
            f"Active watchlist index: {st.session_state.active_watchlist_index}")

        for i, watchlist in enumerate(st.session_state.watchlists):
            st.write(f"### Watchlist {i}: {watchlist['name']}")
            st.write(f"ID: {watchlist['id']}")
            st.write(
                f"Stocks: {', '.join(watchlist['stocks']) if watchlist['stocks'] else 'None'}")

        # Also check what's saved in database
        db_data = self.db_storage.load_watchlists() if self.db_storage else None
        if db_data and "watchlists" in db_data:
            st.write("### Database Data")
            st.write(
                f"Number of watchlists in database: {len(db_data['watchlists'])}")
            st.write(
                f"Active index in database: {db_data.get('active_index', 'Not set')}")
        else:
            st.write("No watchlist data found in database!")

    def get_all_watchlists(self) -> List[Dict[str, Any]]:
        """Get all watchlists"""
        return st.session_state.watchlists

    def get_active_watchlist_index(self) -> int:
        """Get the index of the active watchlist"""
        return st.session_state.active_watchlist_index

    def get_active_watchlist(self) -> Dict[str, Any]:
        """Get the active watchlist object"""
        if self.get_all_watchlists():
            return self.get_all_watchlists()[self.get_active_watchlist_index()]
        return {"id": "", "name": "", "stocks": []}

    def get_watchlist(self) -> List[str]:
        """Get stocks from the active watchlist (compatibility with old code)"""
        return self.get_active_watchlist().get("stocks", [])

    def set_active_watchlist(self, index: int) -> bool:
        """Set the active watchlist by index"""
        if 0 <= index < len(self.get_all_watchlists()):
            st.session_state.active_watchlist_index = index
            self._save_to_database()
            return True
        return False

    def add_watchlist(self, name: str = "Ny Watchlist") -> int:
        """Add a new watchlist"""
        if not name:
            name = "Ny Watchlist"

        new_watchlist = {
            "id": str(uuid.uuid4()),
            "name": name,
            "stocks": []
        }

        st.session_state.watchlists.append(new_watchlist)
        self._save_to_database()
        # Return index of new watchlist
        return len(st.session_state.watchlists) - 1

    def rename_watchlist(self, index: int, new_name: str) -> bool:
        """Rename a watchlist"""
        if not new_name:
            return False

        if 0 <= index < len(self.get_all_watchlists()):
            st.session_state.watchlists[index]["name"] = new_name
            self._save_to_database()
            return True
        return False

    def delete_watchlist(self, index: int) -> bool:
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

            self._save_to_database()
            return True
        return False

    def add_stock(self, ticker: str) -> bool:
        """Add a stock to the active watchlist (compatibility with old code)"""
        return self.add_stock_to_watchlist(self.get_active_watchlist_index(), ticker)

    def add_stock_to_watchlist(self, index: int, ticker: str) -> bool:
        """Add a stock to a specific watchlist"""
        if not ticker:
            return False

        # Normalize ticker (uppercase and strip whitespace)
        ticker = ticker.strip().upper()

        if 0 <= index < len(self.get_all_watchlists()):
            watchlist = st.session_state.watchlists[index]
            if ticker not in watchlist["stocks"]:
                watchlist["stocks"].append(ticker)
                self._save_to_database()
                return True
        return False

    def remove_stock(self, ticker: str) -> bool:
        """Remove a stock from the active watchlist (compatibility with old code)"""
        return self.remove_stock_from_watchlist(self.get_active_watchlist_index(), ticker)

    def remove_stock_from_watchlist(self, index: int, ticker: str) -> bool:
        """Remove a stock from a specific watchlist"""
        if 0 <= index < len(self.get_all_watchlists()):
            watchlist = st.session_state.watchlists[index]
            if ticker in watchlist["stocks"]:
                watchlist["stocks"].remove(ticker)
                self._save_to_database()
                return True
        return False

    def export_watchlist(self, index: Optional[int] = None) -> Optional[str]:
        """Export a watchlist as a JSON string"""
        if index is None:
            index = self.get_active_watchlist_index()

        if 0 <= index < len(self.get_all_watchlists()):
            watchlist = st.session_state.watchlists[index].copy()
            # We don't need to include the ID in the export
            export_data = {
                "name": watchlist["name"],
                "stocks": watchlist["stocks"],
                "export_date": datetime.now().isoformat()
            }
            import json
            return json.dumps(export_data)
        return None

    def import_watchlist(self, json_string: str) -> Optional[int]:
        """Import a watchlist from a JSON string"""
        try:
            import json
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
                self._save_to_database()
                # Return index of new watchlist
                return len(st.session_state.watchlists) - 1
        except Exception as e:
            if self.debug_mode:
                st.error(f"Fel vid import: {str(e)}")
        return None

    def generate_share_link(self, index: Optional[int] = None) -> Optional[str]:
        """Generate a shareable link for a watchlist"""
        if index is None:
            index = self.get_active_watchlist_index()

        json_data = self.export_watchlist(index)
        if json_data:
            # Encode the JSON data to be used in a URL
            import base64
            encoded = base64.b64encode(json_data.encode()).decode()
            return f"?shared_watchlist={encoded}"
        return None

    def import_from_share_link(self, encoded_data: str) -> Optional[int]:
        """Import a watchlist from an encoded share link"""
        try:
            # Decode the data from the URL
            import base64
            json_string = base64.b64decode(encoded_data).decode()
            return self.import_watchlist(json_string)
        except Exception as e:
            if self.debug_mode:
                st.error(f"Fel vid import från delad länk: {str(e)}")
            return None

    def export_all_watchlists(self) -> str:
        """Export all watchlists as a JSON string"""
        export_data = {
            "watchlists": st.session_state.watchlists,
            "active_index": st.session_state.active_watchlist_index,
            "export_date": datetime.now().isoformat()
        }
        import json
        return json.dumps(export_data, indent=2)

    def import_all_watchlists(self, json_string: str) -> bool:
        """Import all watchlists from a JSON string"""
        try:
            import json
            data = json.loads(json_string)
            if isinstance(data, dict) and "watchlists" in data:
                # Replace all watchlists
                st.session_state.watchlists = data["watchlists"]

                # Set active index if provided
                if "active_index" in data:
                    st.session_state.active_watchlist_index = data["active_index"]

                # Validate active index
                if st.session_state.active_watchlist_index >= len(st.session_state.watchlists):
                    st.session_state.active_watchlist_index = 0

                # Save to database
                self._save_to_database()
                return True
        except Exception as e:
            if self.debug_mode:
                st.error(f"Error importing watchlists: {str(e)}")
        return False
