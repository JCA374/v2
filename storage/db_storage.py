"""
Database storage module for persisting watchlists and app data using SQLite.
This provides a reliable local storage solution that works across sessions.
"""
import os
import json
import sqlite3
import pathlib
import datetime
from typing import Dict, List, Any, Optional, Union
import streamlit as st

class DatabaseStorage:
    """
    SQLite-based storage for the Value & Momentum Stock Strategy App.
    Stores data in the user's home directory by default, but location is configurable.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database storage connection.
        
        Args:
            db_path: Optional path to database file. If None, will use default location
                    in user's home directory.
        """
        self.db_path = db_path or self._get_default_db_path()
        self.debug_mode = False
        self._ensure_db_exists()
        
    def _get_default_db_path(self) -> str:
        """Get the default database path in user's home directory."""
        home_dir = pathlib.Path.home()
        app_dir = home_dir / ".value_momentum_app"
        os.makedirs(app_dir, exist_ok=True)
        return str(app_dir / "watchlists.db")
    
    def _ensure_db_exists(self) -> None:
        """Create the database and tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create tables if they don't exist
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlists (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                ''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS stocks (
                    watchlist_id TEXT,
                    ticker TEXT,
                    added_at TEXT NOT NULL,
                    PRIMARY KEY (watchlist_id, ticker),
                    FOREIGN KEY (watchlist_id) REFERENCES watchlists(id)
                )
                ''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                ''')
                
                # Insert or update active_watchlist_id setting if it doesn't exist
                cursor.execute('''
                INSERT OR IGNORE INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ''', ('active_watchlist_id', '', datetime.datetime.now().isoformat()))
                
                conn.commit()
                
                if self.debug_mode:
                    st.success(f"Database initialized at {self.db_path}")
                    
        except sqlite3.Error as e:
            if self.debug_mode:
                st.error(f"Database initialization error: {str(e)}")
            raise
    
    def save_watchlists(self, watchlists: List[Dict[str, Any]], active_index: int = 0) -> bool:
        """
        Save watchlists to the database.
        
        Args:
            watchlists: List of watchlist dictionaries with 'id', 'name', and 'stocks' keys
            active_index: Index of the active watchlist
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                now = datetime.datetime.now().isoformat()
                
                # First, get existing watchlists to track deletions
                cursor.execute("SELECT id FROM watchlists")
                existing_ids = {row[0] for row in cursor.fetchall()}
                current_ids = {wl['id'] for wl in watchlists}
                
                # Delete watchlists that no longer exist
                for wl_id in existing_ids - current_ids:
                    cursor.execute("DELETE FROM stocks WHERE watchlist_id = ?", (wl_id,))
                    cursor.execute("DELETE FROM watchlists WHERE id = ?", (wl_id,))
                
                # Update active watchlist ID
                if len(watchlists) > active_index:
                    active_id = watchlists[active_index]['id']
                    cursor.execute(
                        "UPDATE app_settings SET value = ?, updated_at = ? WHERE key = ?",
                        (active_id, now, 'active_watchlist_id')
                    )
                
                # Insert or update watchlists
                for watchlist in watchlists:
                    # Check if watchlist exists
                    cursor.execute("SELECT 1 FROM watchlists WHERE id = ?", (watchlist['id'],))
                    exists = cursor.fetchone() is not None
                    
                    if exists:
                        # Update existing watchlist
                        cursor.execute(
                            "UPDATE watchlists SET name = ?, updated_at = ? WHERE id = ?",
                            (watchlist['name'], now, watchlist['id'])
                        )
                    else:
                        # Insert new watchlist
                        cursor.execute(
                            "INSERT INTO watchlists (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                            (watchlist['id'], watchlist['name'], now, now)
                        )
                    
                    # Get existing stocks for this watchlist
                    cursor.execute("SELECT ticker FROM stocks WHERE watchlist_id = ?", (watchlist['id'],))
                    existing_stocks = {row[0] for row in cursor.fetchall()}
                    current_stocks = set(watchlist['stocks'])
                    
                    # Delete stocks that are no longer in the watchlist
                    for ticker in existing_stocks - current_stocks:
                        cursor.execute(
                            "DELETE FROM stocks WHERE watchlist_id = ? AND ticker = ?", 
                            (watchlist['id'], ticker)
                        )
                    
                    # Add new stocks
                    for ticker in current_stocks - existing_stocks:
                        cursor.execute(
                            "INSERT INTO stocks (watchlist_id, ticker, added_at) VALUES (?, ?, ?)",
                            (watchlist['id'], ticker, now)
                        )
                
                conn.commit()
                
                if self.debug_mode:
                    st.success(f"Saved {len(watchlists)} watchlists to database")
                return True
        except sqlite3.Error as e:
            if self.debug_mode:
                st.error(f"Error saving watchlists: {str(e)}")
            return False
    
    def load_watchlists(self) -> Optional[Dict[str, Any]]:
        """
        Load watchlists from the database.
        
        Returns:
            Dict with 'watchlists' list and 'active_index' integer,
            or None if an error occurred
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Use row factory for dict-like rows
                cursor = conn.cursor()
                
                # Get active watchlist ID
                cursor.execute("SELECT value FROM app_settings WHERE key = ?", ('active_watchlist_id',))
                row = cursor.fetchone()
                active_id = row['value'] if row else ""
                
                # Get all watchlists
                cursor.execute("SELECT id, name FROM watchlists ORDER BY name")
                watchlists = []
                active_index = 0
                
                for i, wl_row in enumerate(cursor.fetchall()):
                    # Get stocks for this watchlist
                    wl_id = wl_row['id']
                    cursor.execute("SELECT ticker FROM stocks WHERE watchlist_id = ? ORDER BY ticker", (wl_id,))
                    stocks = [row['ticker'] for row in cursor.fetchall()]
                    
                    watchlist = {
                        'id': wl_id,
                        'name': wl_row['name'],
                        'stocks': stocks
                    }
                    watchlists.append(watchlist)
                    
                    # Check if this is the active watchlist
                    if wl_id == active_id:
                        active_index = i
                
                result = {
                    'watchlists': watchlists,
                    'active_index': active_index
                }
                
                if self.debug_mode:
                    st.success(f"Loaded {len(watchlists)} watchlists from database")
                return result
                
        except sqlite3.Error as e:
            if self.debug_mode:
                st.error(f"Error loading watchlists: {str(e)}")
            return None
    
    def export_to_json(self, file_path: str) -> bool:
        """
        Export all watchlist data to a JSON file.
        
        Args:
            file_path: Path to save the JSON file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            data = self.load_watchlists()
            if not data:
                return False
                
            data['export_date'] = datetime.datetime.now().isoformat()
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            if self.debug_mode:
                st.success(f"Exported watchlists to {file_path}")
            return True
        except Exception as e:
            if self.debug_mode:
                st.error(f"Error exporting watchlists: {str(e)}")
            return False
    
    def import_from_json(self, file_path: str) -> bool:
        """
        Import watchlist data from a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            if 'watchlists' not in data:
                if self.debug_mode:
                    st.error("Invalid JSON format - missing watchlists")
                return False
                
            return self.save_watchlists(
                data['watchlists'], 
                data.get('active_index', 0)
            )
        except Exception as e:
            if self.debug_mode:
                st.error(f"Error importing watchlists: {str(e)}")
            return False
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get information about the database for diagnostics.
        
        Returns:
            Dict with database statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM watchlists")
                watchlist_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM stocks")
                stock_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT watchlist_id) FROM stocks")
                populated_watchlists = cursor.fetchone()[0]
                
                # Get database file size
                db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                return {
                    "path": self.db_path,
                    "size_bytes": db_size,
                    "size_formatted": f"{db_size/1024:.1f} KB",
                    "watchlist_count": watchlist_count,
                    "stock_count": stock_count,
                    "populated_watchlists": populated_watchlists,
                    "last_modified": datetime.datetime.fromtimestamp(
                        os.path.getmtime(self.db_path)
                    ).isoformat() if os.path.exists(self.db_path) else None
                }
                
        except sqlite3.Error as e:
            if self.debug_mode:
                st.error(f"Error getting database info: {str(e)}")
            return {"error": str(e)}