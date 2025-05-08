# tabs/api_settings_component.py
import streamlit as st


def render_api_settings_section():
    """Render the API settings section in the Storage Settings tab"""
    st.subheader("API Settings")

    # Alpha Vantage API key
    with st.expander("Alpha Vantage API Configuration", expanded=False):
        st.info("""
        Alpha Vantage is used as a fallback when Yahoo Finance API rate limits are hit. 
        Adding your API key will improve reliability when analyzing multiple stocks.
        
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

        # Usage information
        st.markdown("""
        #### API Usage Notes:
        - Free Alpha Vantage API keys are limited to 5 calls per minute and 500 calls per day
        - Data will be cached in the database to minimize API calls
        - Alpha Vantage will only be used when Yahoo Finance is unavailable
        """)
