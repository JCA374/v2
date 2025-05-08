# test_alpha_service.py

import os
import streamlit as st
import pandas as pd
from services.alpha_vantage_service import fetch_ticker_info, fetch_history


def main():
    # Mock session state
    st.session_state = {}

    # Get API key from environment or input
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        api_key = input("Enter Alpha Vantage API key: ")

    # Store in session state
    st.session_state.alpha_vantage_api_key = api_key

    # Test ticker info
    print("Testing fetch_ticker_info...")
    try:
        stock, info = fetch_ticker_info("AAPL")
        print(f"Success! Got info for {info.get('shortName')}")
        print(f"Market cap: {info.get('marketCap')}")
        print(f"P/E: {info.get('trailingPE')}")
    except Exception as e:
        print(f"Error fetching ticker info: {str(e)}")

    # Test history
    print("\nTesting fetch_history...")
    try:
        hist = fetch_history("AAPL", period="1mo", interval="1d")
        print(f"Success! Got {len(hist)} data points")
        print(f"Columns: {hist.columns.tolist()}")
        print(f"First row:\n{hist.iloc[0]}")
    except Exception as e:
        print(f"Error fetching history: {str(e)}")


if __name__ == "__main__":
    main()
