# tabs/api_settings_component.py
import streamlit as st


def render_api_settings_section():
    """Render the API settings section in the Storage Settings tab"""
    st.subheader("API Settings")

    # Data source preference
    st.write("### Data Source Priority")

    # Get current preference from session state (default to yahoo)
    current_preference = st.session_state.get('preferred_data_source', 'yahoo')

    # Create radio buttons for selection
    data_source = st.radio(
        "Choose which data source to try first:",
        options=["Yahoo Finance", "Alpha Vantage"],
        index=0 if current_preference == 'yahoo' else 1,
        help="Select which data service should be tried first when fetching stock data"
    )

    # Map selection to internal value
    preferred_source = 'yahoo' if data_source == "Yahoo Finance" else 'alphavantage'

    # Save preference if it changed
    if preferred_source != current_preference:
        st.session_state.preferred_data_source = preferred_source
        st.success(f"Data source priority set to {data_source} first")

    # Display current status
    if preferred_source == 'yahoo':
        st.info("Current order: 1) Yahoo Finance → 2) Alpha Vantage (if Yahoo fails)")
    else:
        st.info(
            "Current order: 1) Alpha Vantage → 2) Yahoo Finance (if Alpha Vantage fails)")

    # Alpha Vantage API key
    with st.expander("Alpha Vantage API Configuration", expanded=(preferred_source == 'alphavantage')):
        st.info("""
        Alpha Vantage is used as a fallback or primary source for stock data.
        Adding your API key is required to use Alpha Vantage.
        
        [Get a free API key from Alpha Vantage](https://www.alphavantage.co/support/#api-key)
        """)

        # Get current API key from session state
        current_key = st.session_state.get('alpha_vantage_api_key', '')

        # Add a mask to show/hide API key
        show_key = st.checkbox("Show API Key", value=False)

        # Create a text input for the API key
        new_key = st.text_input(
            "Alpha Vantage API Key",
            value=current_key,
            type="password" if not show_key else "default",
            help="Enter your Alpha Vantage API key"
        )

        # Save button
        if st.button("Save API Key"):
            if new_key:
                st.session_state.alpha_vantage_api_key = new_key
                st.success("Alpha Vantage API key saved successfully!")
            else:
                if 'alpha_vantage_api_key' in st.session_state:
                    del st.session_state.alpha_vantage_api_key
                st.warning("Alpha Vantage API key cleared")

        # Test button
        if st.button("Test API Key"):
            if not new_key and not current_key:
                st.error("No API key provided. Please enter an API key first.")
            else:
                key_to_test = new_key or current_key
                with st.spinner("Testing API key..."):
                    try:
                        # Import here to avoid circular imports
                        from services.alpha_vantage_service import fetch_ticker_info
                        # Store key temporarily in session state for the test
                        st.session_state.alpha_vantage_api_key = key_to_test
                        # Try a simple test call
                        stock, info = fetch_ticker_info("AAPL")
                        st.success(
                            f"✅ API key is valid! Successfully fetched data for {info.get('shortName', 'AAPL')}")
                    except Exception as e:
                        st.error(f"❌ API key test failed: {str(e)}")

        # Usage information
        st.markdown("""
        #### API Usage Notes:
        - Free Alpha Vantage API keys are limited to 5 calls per minute and 500 calls per day
        - Premium API keys have higher limits and can be purchased from Alpha Vantage
        - Data will be cached in the database to minimize API calls
        """)

        # Warning if Alpha Vantage is preferred but no key is set
        if preferred_source == 'alphavantage' and not current_key:
            st.warning(
                "⚠️ You've selected Alpha Vantage as the primary data source but no API key is set. Please enter an API key above.")
