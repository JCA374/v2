# tabs/debug_tab.py (update)
# Add this to the render_debug_tab function

# Alpha Vantage API key configuration
with st.expander("API Configuration", expanded=False):
    st.subheader("Alpha Vantage API")

    # Get current API key from session state
    current_key = st.session_state.get('alpha_vantage_api_key', '')

    # Add a mask to show/hide API key
    show_key = st.checkbox("Show API Key", value=False)

    # Create a text input for the API key
    new_key = st.text_input(
        "Alpha Vantage API Key",
        value=current_key,
        type="password" if not show_key else "default",
        help="Enter your Alpha Vantage API key for fallback data source"
    )

    # Save button
    if st.button("Save API Key", key="save_api_key_debug"):
        if new_key:
            st.session_state.alpha_vantage_api_key = new_key
            st.success("Alpha Vantage API key saved successfully!")
        else:
            if 'alpha_vantage_api_key' in st.session_state:
                del st.session_state.alpha_vantage_api_key
            st.warning("Alpha Vantage API key cleared")
