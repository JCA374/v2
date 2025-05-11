# tabs/ticker_mapping_component.py
import streamlit as st
import pandas as pd
import io
from services.ticker_mapping_service import TickerMappingService


def render_ticker_mapping_section():
    """Render the ticker mapping management section in the Storage Settings tab."""
    st.subheader("Stock Symbol Mapping")

    # Initialize ticker mapping service if not already in session state
    if 'ticker_mapper' not in st.session_state:
        db_storage = st.session_state.get('supabase_db')
        st.session_state.ticker_mapper = TickerMappingService(db_storage)

    ticker_mapper = st.session_state.ticker_mapper

    # Display current mapping data
    if ticker_mapper.mapping_data is not None and not ticker_mapper.mapping_data.empty:
        mapping_count = len(ticker_mapper.mapping_data)
        st.write(
            f"Currently have {mapping_count} ticker mappings in the database.")

        # Search and display
        with st.expander("View and Search Mappings", expanded=False):
            search_query = st.text_input(
                "Search by company name or ticker:", key="ticker_mapping_search")

            # Filter data based on search query
            filtered_data = ticker_mapper.mapping_data
            if search_query:
                filtered_data = ticker_mapper.search_companies(search_query)

            # Show the first 50 rows or all filtered rows
            if len(filtered_data) > 50 and not search_query:
                st.write(f"Showing first 50 of {len(filtered_data)} mappings.")
                display_data = filtered_data.head(50)
            else:
                display_data = filtered_data

            # Format the dataframe for display
            if not display_data.empty:
                st.dataframe(
                    display_data,
                    column_config={
                        "company_name": st.column_config.TextColumn("Company Name"),
                        "yahoo_ticker": st.column_config.TextColumn("Yahoo Finance"),
                        "alpha_ticker": st.column_config.TextColumn("Alpha Vantage")
                    },
                    use_container_width=True
                )
            else:
                st.info("No mappings found matching your search.")
    else:
        st.info("No ticker mappings loaded yet. You can add them below.")

    # Add new mapping
    with st.expander("Add New Ticker Mapping", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            company_name = st.text_input(
                "Company Name:", key="add_company_name")

        with col2:
            yahoo_ticker = st.text_input(
                "Yahoo Finance Ticker:", key="add_yahoo_ticker")

        with col3:
            alpha_ticker = st.text_input("Alpha Vantage Ticker:",
                                         value="" if not yahoo_ticker else ticker_mapper._yahoo_to_alpha_format(
                                             yahoo_ticker),
                                         key="add_alpha_ticker",
                                         help="Leave blank to auto-generate from Yahoo ticker")

        if st.button("Add Mapping", key="btn_add_mapping"):
            if company_name and yahoo_ticker:
                # Use the entered Alpha ticker or generate one
                alpha_to_use = alpha_ticker or ticker_mapper._yahoo_to_alpha_format(
                    yahoo_ticker)

                # Add to mapping service
                success = ticker_mapper.add_mapping(
                    company_name, yahoo_ticker, alpha_to_use)

                if success:
                    st.success(
                        f"Added mapping: {company_name} → Yahoo: {yahoo_ticker}, Alpha: {alpha_to_use}")
                    # Clear inputs
                    st.session_state.add_company_name = ""
                    st.session_state.add_yahoo_ticker = ""
                    st.session_state.add_alpha_ticker = ""
                else:
                    st.error("Failed to add mapping")
            else:
                st.warning("Company name and Yahoo ticker are required")

    # Batch import from CSV
    with st.expander("Import Mappings from CSV", expanded=False):
        st.markdown("""
        Upload a CSV file with ticker mappings. The file should have columns:
        - `company_name` (optional)
        - `yahoo_ticker` (required)
        - `alpha_ticker` (optional - will be auto-generated if missing)
        
        Alternatively, you can use a stock list CSV with a column named `YahooTicker`.
        """)

        uploaded_file = st.file_uploader("Choose a CSV file", type=[
                                         "csv"], key="ticker_mapping_upload")

        if uploaded_file is not None:
            try:
                # Read CSV
                df = pd.read_csv(uploaded_file)

                # Check if it has the required columns
                if 'yahoo_ticker' in df.columns:
                    # Standard mapping format
                    columns_to_use = ['company_name',
                                      'yahoo_ticker', 'alpha_ticker']

                    # Check for missing columns and add defaults
                    if 'company_name' not in df.columns:
                        df['company_name'] = df['yahoo_ticker']

                    if 'alpha_ticker' not in df.columns:
                        df['alpha_ticker'] = df['yahoo_ticker'].apply(
                            ticker_mapper._yahoo_to_alpha_format)

                    # Use only the columns we need
                    df_to_import = df[columns_to_use]

                elif 'YahooTicker' in df.columns:
                    # Stock list format
                    # Create standard format DataFrame
                    df_to_import = pd.DataFrame()

                    # Map company name if available
                    if 'CompanyName' in df.columns:
                        df_to_import['company_name'] = df['CompanyName']
                    else:
                        df_to_import['company_name'] = df['YahooTicker']

                    # Map tickers
                    df_to_import['yahoo_ticker'] = df['YahooTicker']
                    df_to_import['alpha_ticker'] = df['YahooTicker'].apply(
                        ticker_mapper._yahoo_to_alpha_format)
                else:
                    st.error(
                        "CSV file must have either 'yahoo_ticker' or 'YahooTicker' column.")
                    return

                # Preview data
                st.write("Preview of data to import:")
                st.dataframe(df_to_import.head(10))

                # Import button
                if st.button("Import Mappings", key="btn_import_mappings"):
                    # Import each row
                    count = 0
                    for _, row in df_to_import.iterrows():
                        success = ticker_mapper.add_mapping(
                            row['company_name'],
                            row['yahoo_ticker'],
                            row['alpha_ticker']
                        )
                        if success:
                            count += 1

                    if count > 0:
                        st.success(f"Successfully imported {count} mappings.")

                        # Update table display (force refresh)
                        st.session_state.ticker_mapper = ticker_mapper
                        st.experimental_rerun()
                    else:
                        st.error("No mappings were imported.")

            except Exception as e:
                st.error(f"Error processing CSV: {str(e)}")

    # Export to CSV
    with st.expander("Export Mappings to CSV", expanded=False):
        if ticker_mapper.mapping_data is not None and not ticker_mapper.mapping_data.empty:
            # Create a CSV string from the data
            csv_data = ticker_mapper.mapping_data.to_csv(index=False)

            st.download_button(
                "Download Mappings CSV",
                data=csv_data,
                file_name="ticker_mappings.csv",
                mime="text/csv"
            )
        else:
            st.info("No mappings available to export.")

    # Ticker format tester
    with st.expander("Ticker Format Converter", expanded=True):
        st.write("Convert between different API ticker formats:")

        test_ticker = st.text_input(
            "Enter ticker or company name:", key="test_ticker")

        if test_ticker:
            # Look up the ticker
            company_data = ticker_mapper.get_company_data(test_ticker)

            # Show results
            st.write("### Results")
            st.json({
                "company_name": company_data['company_name'],
                "yahoo_finance": company_data['yahoo_ticker'],
                "alpha_vantage": company_data['alpha_ticker']
            })

            # Show which format the input was in
            source, _ = ticker_mapper.detect_api_format(test_ticker)
            st.write(f"Input detected as: **{source.capitalize()}** format")

            # Add validation status
            yahoo_valid = ticker_mapper.validate_ticker(
                company_data['yahoo_ticker'], "yahoo")

            if yahoo_valid:
                st.success("✅ Yahoo Finance ticker is valid")
            else:
                st.warning("⚠️ Yahoo Finance ticker may not be valid")

            # We don't validate Alpha Vantage to avoid using API quota
            st.info("ℹ️ Alpha Vantage ticker not validated (would use API quota)")

    # Advanced: Ticker detection tool
    with st.expander("Ticker Format Detection Tool", expanded=False):
        st.write("""
        This tool helps detect the correct ticker format for Alpha Vantage 
        by testing different variations. Note that this will consume your 
        Alpha Vantage API quota.
        """)

        detect_ticker = st.text_input(
            "Yahoo Finance ticker to detect:", key="detect_ticker")

        if detect_ticker:
            # Show possible variations
            variations = ticker_mapper._convert_single_yahoo_to_alpha(
                detect_ticker)
            other_variations = ticker_mapper.generate_format_variations(
                detect_ticker) if hasattr(ticker_mapper, 'generate_format_variations') else []

            st.write("### Possible Alpha Vantage formats:")
            st.code(f"Standard conversion: {variations}")

            if other_variations:
                st.code("Other variations to try:\n" +
                        "\n".join(other_variations))

            # Button to test with Alpha Vantage API
            if st.button("Test with Alpha Vantage API", key="btn_test_alpha"):
                api_key = st.session_state.get('alpha_vantage_api_key')

                if not api_key:
                    st.error(
                        "Alpha Vantage API key not found. Please add it in the API Settings section.")
                else:
                    # This would require importing the testing function
                    st.warning(
                        "Testing with the API would consume your quota. This feature is disabled in the UI component.")
                    st.info(
                        "Use the standalone 'find_correct_tickers.py' script to test ticker formats.")


def generate_format_variations(yahoo_ticker):
    """
    Generate different possible formats for Alpha Vantage tickers.
    This is a basic version - the standalone script has a more comprehensive version.
    """
    variations = []

    # Original format
    variations.append(yahoo_ticker)

    # Remove .ST for Swedish stocks
    if yahoo_ticker.endswith(".ST"):
        base = yahoo_ticker.replace(".ST", "")
        variations.append(base)

        # Remove dash too
        if "-" in base:
            variations.append(base.replace("-", ""))

        # Try .STO instead of .ST
        variations.append(base + ".STO")

    return variations
