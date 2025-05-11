# tabs/storage_settings_tab.py
import streamlit as st
import os
import json
from datetime import datetime
from pathlib import Path
from tabs.api_settings_component import render_api_settings_section


def render_storage_settings_tab():
    """Render the storage settings tab for managing database configuration."""
    st.header("Storage Settings")

    # Access database storage from session state
    supabase_db = st.session_state.get('supabase_db')
    watchlist_manager = st.session_state.get('watchlist_manager')

    # Add API settings section (for Alpha Vantage and other APIs)
    render_api_settings_section()

    # Database information and status
    st.subheader("Database Status")

    if supabase_db and supabase_db.supabase:
        st.success("✅ Connected to Supabase database")

        # Try to get some stats
        try:
            # Price data stats
            response = supabase_db.supabase.table("stock_prices") \
                .select("ticker", "last_updated", "timeframe") \
                .limit(1000) \
                .execute()

            if response.data:
                # Get unique tickers and timeframes
                unique_tickers = len(set(row['ticker']
                                     for row in response.data))
                unique_timeframes = len(
                    set(row['timeframe'] for row in response.data))
                data_points = len(response.data)

                # Get most recent update time
                update_times = [row['last_updated']
                                for row in response.data if row['last_updated']]
                if update_times:
                    latest_update = max(update_times)
                    try:
                        latest_dt = datetime.fromisoformat(latest_update.replace(
                            'Z', '+00:00')) if latest_update.endswith('Z') else datetime.fromisoformat(latest_update)
                        hours_ago = (datetime.now() -
                                     latest_dt).total_seconds() / 3600
                    except:
                        hours_ago = None
                else:
                    hours_ago = None

                # Show statistics
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Stocks with Price Data", unique_tickers)
                    st.metric("Data Points", f"{data_points:,}")

                with col2:
                    st.metric("Timeframes", unique_timeframes)
                    if hours_ago is not None:
                        st.metric("Last Update", f"{hours_ago:.1f} hours ago")

                # Show timeframe breakdown
                if unique_timeframes > 0:
                    st.subheader("Data by Timeframe")
                    timeframe_counts = {}
                    for row in response.data:
                        tf = row.get('timeframe', 'unknown')
                        timeframe_counts[tf] = timeframe_counts.get(tf, 0) + 1

                    # Create simple bar chart
                    st.bar_chart(timeframe_counts)
            else:
                st.info("No price data has been cached yet.")
        except Exception as e:
            st.warning(f"Could not retrieve database statistics: {str(e)}")
    else:
        st.error("Not connected to Supabase database.")
        st.info("""
        To use cloud database storage, you need to set up Supabase credentials in your secrets.toml file:
        ```
        supabase_url = "https://your-project-id.supabase.co"
        supabase_key = "your-supabase-anon-key"
        ```
        """)

    # Backup and restore section
    st.subheader("Backup & Restore")

    col1, col2 = st.columns(2)

    with col1:
        st.write("### Create Backup")
        backup_filename = f"watchlists_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Generate backup JSON for download
        data = watchlist_manager._load_from_supabase() if hasattr(
            watchlist_manager, '_load_from_supabase') else None

        if data:
            data['export_date'] = datetime.now().isoformat()
            json_data = json.dumps(data, indent=2)

            st.download_button(
                "Download Backup File",
                json_data,
                file_name=backup_filename,
                mime="application/json"
            )

            # Option to save backup to disk
            backup_dir = st.text_input(
                "Backup directory (optional)",
                value=str(Path.home() / "watchlist_backups"),
                help="Directory to store backup files"
            )

            if st.button("Save Backup to Disk"):
                try:
                    os.makedirs(backup_dir, exist_ok=True)
                    backup_path = os.path.join(backup_dir, backup_filename)
                    with open(backup_path, 'w') as f:
                        f.write(json_data)
                    st.success(f"Backup saved to {backup_path}")
                except Exception as e:
                    st.error(f"Error saving backup: {str(e)}")

    with col2:
        st.write("### Restore from Backup")

        uploaded_file = st.file_uploader(
            "Upload backup file",
            type=["json"],
            help="Upload a previously created backup file"
        )

        if uploaded_file is not None:
            try:
                json_data = json.loads(uploaded_file.getvalue().decode())

                if "watchlists" not in json_data:
                    st.error("Invalid backup file format")
                else:
                    # Show summary of what will be imported
                    st.info(
                        f"Found {len(json_data['watchlists'])} watchlists in backup")

                    # Let user choose how to restore
                    restore_mode = st.radio(
                        "Restore mode",
                        ["Replace all watchlists", "Merge with existing watchlists"],
                        help="Replace will remove all existing watchlists before importing. Merge will add new watchlists and update existing ones."
                    )

                    if st.button("Restore Watchlists"):
                        if restore_mode == "Replace all watchlists":
                            # Replace existing watchlists
                            success = watchlist_manager._save_to_supabase(
                                json_data['watchlists'],
                                json_data.get('active_index', 0)
                            )
                            if success:
                                st.session_state.watchlists = json_data['watchlists']
                                st.session_state.active_watchlist_index = json_data.get(
                                    'active_index', 0)
                                st.success("Watchlists restored successfully!")
                                st.info(
                                    "Please reload the app to see the changes.")
                            else:
                                st.error("Failed to restore watchlists")
                        else:
                            # Merge with existing watchlists
                            current_data = watchlist_manager._load_from_supabase()
                            if not current_data:
                                current_data = {
                                    "watchlists": [], "active_index": 0}

                            # Create lookup for existing watchlists by ID
                            existing_wl_by_id = {
                                wl['id']: wl for wl in current_data['watchlists']}

                            # Merge watchlists
                            for wl in json_data['watchlists']:
                                if wl['id'] in existing_wl_by_id:
                                    # If watchlist exists, merge stocks
                                    existing_stocks = set(
                                        existing_wl_by_id[wl['id']]['stocks'])
                                    new_stocks = set(wl['stocks'])
                                    # Update name and merge stock lists
                                    existing_wl_by_id[wl['id']
                                                      ]['name'] = wl['name']
                                    existing_wl_by_id[wl['id']]['stocks'] = list(
                                        existing_stocks.union(new_stocks))
                                else:
                                    # Add new watchlist
                                    existing_wl_by_id[wl['id']] = wl

                            # Convert back to list and save
                            merged_watchlists = list(
                                existing_wl_by_id.values())
                            success = watchlist_manager._save_to_supabase(
                                merged_watchlists,
                                current_data['active_index']
                            )

                            if success:
                                st.session_state.watchlists = merged_watchlists
                                st.success(
                                    f"Merged {len(json_data['watchlists'])} watchlists successfully!")
                                st.info(
                                    "Please reload the app to see the changes.")
                            else:
                                st.error("Failed to merge watchlists")
            except Exception as e:
                st.error(f"Error processing backup file: {str(e)}")

    # Database management section
    with st.expander("Database Management", expanded=False):
        st.warning("These actions will modify the database. Use with caution.")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Clear Price Data Cache", help="Delete all stored stock price history"):
                try:
                    if supabase_db and supabase_db.supabase:
                        # Use a confirmation dialog
                        confirm = st.checkbox("Confirm deletion", value=False)
                        if confirm:
                            supabase_db.supabase.table(
                                "stock_prices").delete().execute()
                            st.success(
                                "Price data cache cleared successfully!")
                except Exception as e:
                    st.error(f"Error clearing price data: {str(e)}")

        with col2:
            if st.button("Clear Fundamental Data Cache", help="Delete all stored stock fundamentals"):
                try:
                    if supabase_db and supabase_db.supabase:
                        # Use a confirmation dialog
                        confirm = st.checkbox("Confirm deletion", value=False)
                        if confirm:
                            supabase_db.supabase.table(
                                "stock_fundamentals").delete().execute()
                            st.success(
                                "Fundamental data cache cleared successfully!")
                except Exception as e:
                    st.error(f"Error clearing fundamental data: {str(e)}")

        # Enable debug mode
        debug_mode = st.checkbox(
            "Debug Mode",
            value=st.session_state.get('debug_mode', False),
            help="Show detailed logging for data operations"
        )

        if debug_mode != st.session_state.get('debug_mode', False):
            st.session_state.debug_mode = debug_mode

            # Update debug mode in components
            if supabase_db:
                supabase_db.debug_mode = debug_mode

            if 'strategy' in st.session_state:
                if hasattr(st.session_state.strategy, 'data_manager'):
                    st.session_state.strategy.data_manager.set_debug_mode(
                        debug_mode)

            st.success(f"Debug mode {'enabled' if debug_mode else 'disabled'}")

    # Display information about cloud database
    st.subheader("Cloud Database Information")
    st.markdown("""
    ### Benefits of Cloud Database Storage:
    
    1. **Persistent Caching**: Data is stored between sessions, reducing API calls and improving performance.
    
    2. **Cross-Device Access**: Your stock data and watchlists are available on any device.
    
    3. **Reduced API Usage**: Minimizes the need to repeatedly fetch data from external services.
    
    4. **Better Reliability**: If one data source fails, the system can use cached data as a fallback.
    
    ### Data Sources:
    
    - **Yahoo Finance**: Primary source for most stock data, no API key required but may have rate limits.
    
    - **Alpha Vantage**: Secondary source that requires an API key, with limited free tier (5 calls/minute, 500 calls/day).
    
    The app will try your preferred source first, then fall back to the secondary source if needed. If both fail, it will use cached data when available.
    """)
