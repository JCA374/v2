# test_db_storage.py

import os
import sqlite3
import pandas as pd
import json
from datetime import datetime
from storage.db_storage import DatabaseStorage


def main():
    # Create a test database
    db_path = "test_db.sqlite"

    # Remove existing file if any
    if os.path.exists(db_path):
        os.remove(db_path)

    try:
        # Initialize database storage
        db = DatabaseStorage(db_path)

        # Check if tables were created
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"Tables created: {tables}")

            # Test data insertion
            print("\nTesting data insertion...")

            # Stock price history
            cursor.execute('''
            INSERT INTO stock_price_history 
            (ticker, date, timeframe, open, high, low, close, volume, adjusted_close, last_updated, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('AAPL', '2023-01-01', '1d', 100.0, 105.0, 99.0, 102.0, 1000000, 102.0, datetime.now().isoformat(), 'test'))

            # Stock fundamentals
            cursor.execute('''
            INSERT INTO stock_fundamentals
            (ticker, company_name, sector, industry, pe_ratio, market_cap, revenue_growth, profit_margin, dividend_yield, last_updated, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('AAPL', 'Apple Inc.', 'Technology', 'Consumer Electronics', 25.5, 2500000000000, 0.15, 0.25, 0.005, datetime.now().isoformat(), 'test'))

            conn.commit()

            # Verify data
            cursor.execute("SELECT * FROM stock_price_history")
            price_data = cursor.fetchall()
            print(f"Price data inserted: {price_data}")

            cursor.execute("SELECT * FROM stock_fundamentals")
            fund_data = cursor.fetchall()
            print(f"Fundamental data inserted: {fund_data}")

            print("\nDatabase test completed successfully!")

    except Exception as e:
        print(f"Error during database test: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == "__main__":
    main()
