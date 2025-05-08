# tabs/diagnostics_component.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os


def render_diagnostics_component():
    """Render a diagnostics component for stock data caching"""
    st.subheader("Stock Data Cache Status")

    # Get database storage from session state
    db_storage = st.session_state.get('db_storage')
    if db_storage is None:
        st.error("Database storage not initialized")
        return

    try:
        # Connect to database
        with sqlite3.connect(db_storage.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get stock data stats
            cursor.execute("SELECT COUNT(*) FROM stock_price_history")
            price_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stock_fundamentals")
            fund_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(DISTINCT ticker) FROM stock_price_history")
            price_tickers = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(DISTINCT ticker) FROM stock_fundamentals")
            fund_tickers = cursor.fetchone()[0]

            # Get source distribution
            cursor.execute(
                "SELECT source, COUNT(*) FROM stock_price_history GROUP BY source")
            price_sources = {row['source']: row[1]
                             for row in cursor.fetchall()}

            cursor.execute(
                "SELECT source, COUNT(*) FROM stock_fundamentals GROUP BY source")
            fund_sources = {row['source']: row[1] for row in cursor.fetchall()}

            # Show stats in columns
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Price Records", price_count)
                st.metric("Tickers with Price Data", price_tickers)

            with col2:
                st.metric("Fundamental Records", fund_count)
                st.metric("Tickers with Fundamentals", fund_tickers)

            with col3:
                # Get database file size
                if os.path.exists(db_storage.db_path):
                    size_bytes = os.path.getsize(db_storage.db_path)
                    if size_bytes < 1024:
                        size_str = f"{size_bytes} bytes"
                    elif size_bytes < 1024 * 1024:
                        size_str = f"{size_bytes/1024:.1f} KB"
                    else:
                        size_str = f"{size_bytes/(1024*1024):.1f} MB"
                else:
                    size_str = "Unknown"

                st.metric("Database Size", size_str)

                # Last updated
                cursor.execute(
                    "SELECT MAX(last_updated) FROM stock_price_history")
                last_price = cursor.fetchone()[0]

                if last_price:
                    last_dt = datetime.fromisoformat(last_price)
                    age = datetime.now() - last_dt
                    st.metric("Last Price Update",
                              f"{age.total_seconds()/3600:.1f} hours ago")

            # Show source distribution
            st.subheader("Data Sources")

            source_data = {
                "Yahoo Finance": {
                    "Price Data": price_sources.get('yahoo', 0),
                    "Fundamentals": fund_sources.get('yahoo', 0)
                },
                "Alpha Vantage": {
                    "Price Data": price_sources.get('alphavantage', 0),
                    "Fundamentals": fund_sources.get('alphavantage', 0)
                }
            }

            st.dataframe(pd.DataFrame(source_data))

            # Add cache management buttons
            st.subheader("Cache Management")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Clear Old Data", help="Remove data older than 30 days"):
                    cutoff = (datetime.now() - timedelta(days=30)).isoformat()

                    cursor.execute(
                        "DELETE FROM stock_price_history WHERE last_updated < ?", (cutoff,))
                    price_deleted = cursor.rowcount

                    cursor.execute(
                        "DELETE FROM stock_fundamentals WHERE last_updated < ?", (cutoff,))
                    fund_deleted = cursor.rowcount

                    conn.commit()

                    st.success(
                        f"Deleted {price_deleted} price records and {fund_deleted} fundamental records")

            with col2:
                if st.button("Optimize Database", help="Optimize database size and performance"):
                    conn.execute("VACUUM")
                    st.success("Database optimized")

    except Exception as e:
        st.error(f"Error getting database stats: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
