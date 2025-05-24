import streamlit as st
from storage.supabase_stock_db import SupabaseStockDB


def initialize_db():
    """Initialize database connection"""
    if 'db' not in st.session_state:
        st.session_state.db = SupabaseStockDB()
    return st.session_state.db


def fetch_stock_data(ticker, period="1y", interval="1wk", force_refresh=False):
    """Fetch stock data with smart caching"""
    db = initialize_db()

    # Check for fresh data in database
    if not force_refresh and db.is_data_fresh(ticker, 'price', interval):
        cached_data = db.get_price_data(ticker, interval, period)
        if cached_data is not None and not cached_data.empty:
            return cached_data

    # Fetch from APIs if needed (existing code)
    # ...and save to database
    # ...
