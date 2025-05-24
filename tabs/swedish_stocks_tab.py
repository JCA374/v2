import streamlit as st
import pandas as pd
import time
import logging
from datetime import datetime, timedelta
from services.yahoo_finance_service import fetch_history, fetch_ticker_info

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('swedish_stocks_tab')

def render_swedish_stocks_tab():
    """Render the Swedish Stocks tab for fetching and retrieving Swedish stock data."""
    st.header("Swedish Stocks Data Manager")
    
    # Access Supabase database from session state
    supabase_db = st.session_state.get('supabase_db')
    
    if not supabase_db or not supabase_db.supabase:
        st.error("Database connection is not available. Please check your connection settings.")
        
        # Show configuration help
        with st.expander("Database Configuration Instructions"):
            st.markdown("""
            ### Setting up Supabase Connection
            
            To use the Swedish Stocks Data Manager, you need to set up your Supabase database connection:
            
            1. Create a Supabase account at [supabase.com](https://supabase.com/)
            2. Create a new project
            3. Create the required tables for stock data (see the database setup guide in the Storage Settings tab)
            4. Set up your credentials in `.streamlit/secrets.toml`:
            
            ```toml
            supabase_url = "https://your-project-id.supabase.co"
            supabase_key = "your-supabase-anon-key"
            ```
            
            After setting up your database connection, restart the app.
            """)
        
        # Continue with limited functionality - allow users to fetch data even without database
        st.subheader("Limited Functionality Mode")
        st.warning("You can still fetch and view Swedish stock data, but you won't be able to save it to the database.")
        
        # Create tabs
        fetch_tab, stats_tab = st.tabs(["Fetch Data", "About"])
        
        with fetch_tab:
            st.subheader("Fetch Swedish Stock Data")
            
            # Input for stock ticker
            ticker_input = st.text_input(
                "Enter Yahoo Finance ticker for Swedish stock (e.g., ERIC-B.ST, SEB-A.ST):",
                placeholder="ERIC-B.ST"
            )
            
            # Time period options
            col1, col2 = st.columns(2)
            with col1:
                period = st.selectbox(
                    "Time Period:",
                    options=["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"],
                    index=3  # Default to 1y
                )
            
            with col2:
                interval = st.selectbox(
                    "Interval:",
                    options=["1d", "5d", "1wk", "1mo", "3mo"],
                    index=2  # Default to 1wk
                )
            
            # Fetch button
            if st.button("Fetch Stock Data"):
                if not ticker_input:
                    st.error("Please enter a valid ticker symbol.")
                else:
                    with st.spinner(f"Fetching data for {ticker_input}..."):
                        # Fetch price data
                        price_df = fetch_history(ticker_input, period=period, interval=interval)
                        
                        # Fetch fundamental data
                        info_dict = fetch_ticker_info(ticker_input)
                        
                        # Display results
                        if not price_df.empty:
                            st.success(f"Successfully fetched price data for {ticker_input}")
                            st.dataframe(price_df.head())
                            
                            # Plot the data
                            st.subheader("Price Chart")
                            st.line_chart(price_df['Close'])
                        else:
                            st.error(f"Failed to fetch price data for {ticker_input}")
                        
                        # Display fundamental data
                        if info_dict:
                            with st.expander("Fundamental Data"):
                                # Extract relevant info
                                company_name = info_dict.get('shortName', info_dict.get('longName', ticker_input))
                                sector = info_dict.get('sector', 'Unknown')
                                industry = info_dict.get('industry', 'Unknown')
                                market_cap = info_dict.get('marketCap', 'N/A')
                                
                                # Display info
                                st.write(f"**Company:** {company_name}")
                                st.write(f"**Sector:** {sector}")
                                st.write(f"**Industry:** {industry}")
                                st.write(f"**Market Cap:** {market_cap:,}" if isinstance(market_cap, (int, float)) else f"**Market Cap:** {market_cap}")
                        else:
                            st.warning(f"No fundamental data available for {ticker_input}")
                    
                    st.warning("Note: Data is not being saved to the database because the connection is not available.")
        
        with stats_tab:
            st.subheader("About Swedish Stocks")
            st.markdown("""
            The Stockholm Stock Exchange (Stockholmsbörsen) is the primary securities exchange of Sweden and the Nordic countries.
            
            Swedish stocks in Yahoo Finance typically have the ".ST" suffix, for example:
            
            - ERIC-B.ST (Ericsson B)
            - SEB-A.ST (SEB A)
            - VOLV-B.ST (Volvo B)
            - ATCO-A.ST (Atlas Copco A)
            - SHB-A.ST (Handelsbanken A)
            
            To fetch data for Swedish stocks, enter the ticker symbol with the ".ST" suffix in the "Fetch Data" tab.
            """)
            
        return
    
    # Create tabs for fetch and retrieve operations
    fetch_tab, retrieve_tab, stats_tab = st.tabs(["Fetch Data", "Retrieve Data", "Statistics"])
    
    with fetch_tab:
        st.subheader("Fetch Swedish Stock Data")
        
        # Input for stock ticker
        ticker_input = st.text_input(
            "Enter Yahoo Finance ticker for Swedish stock (e.g., ERIC-B.ST, SEB-A.ST):",
            placeholder="ERIC-B.ST"
        )
        
        # Time period options
        col1, col2 = st.columns(2)
        with col1:
            period = st.selectbox(
                "Time Period:",
                options=["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"],
                index=3  # Default to 1y
            )
        
        with col2:
            interval = st.selectbox(
                "Interval:",
                options=["1d", "5d", "1wk", "1mo", "3mo"],
                index=2  # Default to 1wk
            )
        
        # Fetch button
        if st.button("Fetch Stock Data"):
            if not ticker_input:
                st.error("Please enter a valid ticker symbol.")
            else:
                with st.spinner(f"Fetching data for {ticker_input}..."):
                    # Fetch price data
                    price_df = fetch_history(ticker_input, period=period, interval=interval)
                    
                    # Fetch fundamental data
                    info_dict = fetch_ticker_info(ticker_input)
                    
                    # Display results
                    if not price_df.empty:
                        st.success(f"Successfully fetched price data for {ticker_input}")
                        st.dataframe(price_df.head())
                        
                        # Save to database
                        save_success = supabase_db.save_price_data(ticker_input, price_df, 'yahoo')
                        if save_success:
                            st.success(f"Price data saved to database for {ticker_input}")
                        else:
                            st.error("Failed to save price data to database")
                    else:
                        st.error(f"Failed to fetch price data for {ticker_input}")
                    
                    # Display and save fundamental data
                    if info_dict:
                        with st.expander("Fundamental Data"):
                            # Extract relevant info
                            company_name = info_dict.get('shortName', info_dict.get('longName', ticker_input))
                            sector = info_dict.get('sector', 'Unknown')
                            industry = info_dict.get('industry', 'Unknown')
                            market_cap = info_dict.get('marketCap', 'N/A')
                            
                            # Display info
                            st.write(f"**Company:** {company_name}")
                            st.write(f"**Sector:** {sector}")
                            st.write(f"**Industry:** {industry}")
                            st.write(f"**Market Cap:** {market_cap:,}" if isinstance(market_cap, (int, float)) else f"**Market Cap:** {market_cap}")
                            
                            # Save fundamental data
                            save_success = supabase_db.save_fundamental_data(ticker_input, info_dict, 'yahoo')
                            if save_success:
                                st.success(f"Fundamental data saved to database for {ticker_input}")
                            else:
                                st.error("Failed to save fundamental data to database")
                    else:
                        st.warning(f"No fundamental data available for {ticker_input}")
    
    with retrieve_tab:
        st.subheader("Retrieve Swedish Stock Data")
        
        # Search for available tickers
        search_term = st.text_input("Search for ticker or company name:", placeholder="Ericsson")
        
        if search_term:
            # Search in price data table
            try:
                # Try to find matching tickers in the price data
                response = supabase_db.supabase.table("stock_prices") \
                    .select("ticker") \
                    .ilike("ticker", f"%{search_term}%") \
                    .limit(20) \
                    .execute()
                
                price_tickers = set(row['ticker'] for row in response.data)
                
                # Also search in fundamentals for company names
                # Use two separate queries and combine the results
                response1 = supabase_db.supabase.table("stock_fundamentals") \
                    .select("ticker", "name") \
                    .ilike("ticker", f"%{search_term}%") \
                    .limit(10) \
                    .execute()
                
                response2 = supabase_db.supabase.table("stock_fundamentals") \
                    .select("ticker", "name") \
                    .ilike("name", f"%{search_term}%") \
                    .limit(10) \
                    .execute()
                
                # Combine the results
                combined_data = response1.data + response2.data
                # Create a mock response object with the combined data
                response = type('obj', (object,), {'data': combined_data})
                
                fundamental_tickers = {row['ticker']: row.get('name', row['ticker']) for row in response.data}
                
                # Combine results
                all_tickers = list(price_tickers.union(set(fundamental_tickers.keys())))
                
                if all_tickers:
                    st.success(f"Found {len(all_tickers)} matching stocks")
                    
                    # Create a display list with names when available
                    display_options = []
                    for ticker in all_tickers:
                        name = fundamental_tickers.get(ticker, ticker)
                        display_options.append(f"{ticker} - {name}" if ticker != name else ticker)
                    
                    # Let user select a ticker
                    selected_option = st.selectbox("Select a stock:", options=display_options)
                    
                    # Extract ticker from selection
                    selected_ticker = selected_option.split(" - ")[0] if " - " in selected_option else selected_option
                    
                    # Time period for retrieval
                    period_options = {
                        "1 Month": "1mo",
                        "3 Months": "3mo", 
                        "6 Months": "6mo",
                        "1 Year": "1y",
                        "2 Years": "2y"
                    }
                    
                    period = st.radio("Time Period:", options=list(period_options.keys()), horizontal=True)
                    timeframe = st.radio("Interval:", options=["1d", "1wk", "1mo"], horizontal=True)
                    
                    if st.button("Retrieve Data"):
                        
                        with st.spinner(f"Retrieving data for {selected_ticker}..."):
                            # Get price data
                            price_data = supabase_db.get_price_data(
                                selected_ticker, 
                                timeframe=timeframe,
                                period=period_options[period]
                            )
                            
                            # Get fundamental data
                            fundamental_data = supabase_db.get_fundamental_data(selected_ticker)
                            
                            # Display results
                            if price_data is not None and not price_data.empty:
                                st.subheader("Price Data")
                                st.dataframe(price_data)
                                
                                # Plot the data
                                st.subheader("Price Chart")
                                st.line_chart(price_data['Close'])
                            else:
                                st.warning(f"No price data found for {selected_ticker}")
                            
                            if fundamental_data:
                                st.subheader("Fundamental Data")
                                # Display in a more readable format
                                cols = st.columns(2)
                                with cols[0]:
                                    st.write("**Company Name:**", fundamental_data.get('name', 'N/A'))
                                    st.write("**Sector:**", fundamental_data.get('sector', 'N/A'))
                                    st.write("**Industry:**", fundamental_data.get('industry', 'N/A'))
                                    st.write("**Last Updated:**", fundamental_data.get('last_updated', 'N/A'))
                                
                                with cols[1]:
                                    st.write("**P/E Ratio:**", fundamental_data.get('pe_ratio', 'N/A'))
                                    st.write("**Market Cap:**", fundamental_data.get('market_cap', 'N/A'))
                                    st.write("**Dividend Yield:**", fundamental_data.get('dividend_yield', 'N/A'))
                                    st.write("**Profit Margin:**", fundamental_data.get('profit_margin', 'N/A'))
                            else:
                                st.warning(f"No fundamental data found for {selected_ticker}")
                else:
                    st.warning("No matching stocks found. Try a different search term.")
            except Exception as e:
                st.error(f"Error searching for tickers: {str(e)}")
    
    with stats_tab:
        st.subheader("Swedish Stocks Database Statistics")
        
        # Show statistics about Swedish stocks in the database
        try:
            # Count Swedish stocks (.ST suffix)
            response = supabase_db.supabase.table("stock_prices") \
                .select("ticker") \
                .ilike("ticker", "%.ST") \
                .execute()
            
            swedish_tickers = set(row['ticker'] for row in response.data)
            
            if swedish_tickers:
                st.metric("Swedish Stocks in Database", len(swedish_tickers))
                
                # List the tickers
                with st.expander("View All Swedish Tickers"):
                    for ticker in sorted(swedish_tickers):
                        st.write(ticker)
                
                # Get data freshness information
                st.subheader("Data Freshness")
                
                # Get most recent update times
                response = supabase_db.supabase.table("stock_prices") \
                    .select("ticker", "last_updated", "timeframe") \
                    .ilike("ticker", "%.ST") \
                    .order("last_updated", desc=True) \
                    .limit(10) \
                    .execute()
                
                if response.data:
                    freshness_df = pd.DataFrame(response.data)
                    freshness_df['last_updated'] = pd.to_datetime(freshness_df['last_updated'])
                    freshness_df['hours_since_update'] = (datetime.now() - freshness_df['last_updated']).dt.total_seconds() / 3600
                    
                    # Display the freshness info
                    st.dataframe(freshness_df[['ticker', 'timeframe', 'hours_since_update']].rename(
                        columns={'hours_since_update': 'Hours Since Update'}
                    ))
            else:
                st.info("No Swedish stocks found in the database. Use the Fetch Data tab to add some!")
                
        except Exception as e:
            st.error(f"Error retrieving database statistics: {str(e)}")

if __name__ == "__main__":
    # For testing purposes
    render_swedish_stocks_tab()