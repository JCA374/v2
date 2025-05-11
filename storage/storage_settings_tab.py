# tabs/storage_settings_tab.py
"""
Storage Settings tab for configuring and managing Supabase database storage.
Updated to include ticker mapping management.
"""
import streamlit as st
import os
import json
from datetime import datetime
from pathlib import Path
from tabs.api_settings_component import render_api_settings_section
from tabs.ticker_mapping_component import render_ticker_mapping_section
from storage.supabase_stock_db import render_database_status, show_supabase_setup


def render_storage_settings_tab():
    """Render the storage settings tab for managing Supabase database configuration."""
    st.header("Storage Settings")

    # Access database storage from session state
    supabase_db = st.session_state.get('supabase_db')
    watchlist_manager = st.session_state.get('watchlist_manager')

    # Create tab sections
    tab1, tab2, tab3 = st.tabs(
        ["API Settings", "Ticker Mappings", "Storage Management"])

    with tab1:
        # Add API settings section (for Alpha Vantage and other APIs)
        render_api_settings_section()

    with tab2:
        # Add ticker mapping management section
        render_ticker_mapping_section()

    with tab3:
        # Database information and status
        st.subheader("Database Status")
        render_database_status()

        # Database settings
        st.subheader("Supabase Configuration")

        # Show current configuration
        supabase_url = st.secrets.get("supabase_url", "")
        # Mask the beginning of the URL for security
        masked_url = supabase_url
        if supabase_url.startswith("https://"):
            project_id = supabase_url.split("https://")[1].split(".")[0]
            masked_url = f"https://{'*' * (len(project_id)-4)}{project_id[-4:]}.supabase.co"

        st.info(f"Current Supabase project: {masked_url}")
        st.markdown("""
        To change your Supabase configuration:
        
        1. Edit your `.streamlit/secrets.toml` file with the following:
        ```toml
        supabase_url = "https://your-project-id.supabase.co"
        supabase_key = "your-supabase-anon-key"
        ```
        
        2. Restart the Streamlit app
        """)

        # Backup and restore section
        st.subheader("Backup & Restore")

        col1, col2 = st.columns(2)

        with col1:
            st.write("### Create Backup")
            backup_filename = f"watchlists_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            # Generate backup JSON for download
            data = watchlist_manager._load_from_supabase()
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
                            ["Replace all watchlists",
                                "Merge with existing watchlists"],
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
                                    st.success(
                                        "Watchlists restored successfully!")
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

        # Advanced settings
        with st.expander("Advanced Settings", expanded=False):
            st.warning(
                "These actions can result in data loss. Use with caution.")

            # Reset database
            if st.button("Reset Watchlists", help="Delete all watchlists and start fresh"):
                if st.session_state.get('watchlists'):
                    if watchlist_manager._save_to_supabase([], 0):
                        st.session_state.watchlists = []
                        st.session_state.active_watchlist_index = 0
                        st.success("Watchlists reset successfully!")
                        st.info("Please reload the app to see the changes.")
                    else:
                        st.error("Failed to reset watchlists")

            # Reset price data
            if st.button("Clear Price Data", help="Delete all stored stock price history"):
                try:
                    if supabase_db.supabase:
                        supabase_db.supabase.table(
                            "stock_prices").delete().execute()
                        st.success("Price data cleared successfully!")
                    else:
                        st.error("Supabase connection not available")
                except Exception as e:
                    st.error(f"Error clearing price data: {str(e)}")

            # Reset fundamental data
            if st.button("Clear Fundamental Data", help="Delete all stored stock fundamentals"):
                try:
                    if supabase_db.supabase:
                        supabase_db.supabase.table(
                            "stock_fundamentals").delete().execute()
                        st.success("Fundamental data cleared successfully!")
                    else:
                        st.error("Supabase connection not available")
                except Exception as e:
                    st.error(f"Error clearing fundamental data: {str(e)}")

            # Enable/disable debug mode
            debug_mode = st.checkbox(
                "Debug Mode",
                value=getattr(watchlist_manager, 'debug_mode', False),
                help="Show detailed logging for database operations"
            )

            if debug_mode != getattr(watchlist_manager, 'debug_mode', False):
                watchlist_manager.debug_mode = debug_mode
                if supabase_db:
                    supabase_db.debug_mode = debug_mode
                st.success(
                    f"Debug mode {'enabled' if debug_mode else 'disabled'}")

        # Display information about cross-device usage
        st.subheader("Cloud Database Benefits")
        st.markdown("""
        ### Advantages of using Supabase cloud database:
        
        1. **Access from anywhere**: Your watchlists are stored in the cloud and accessible from any device.
        
        2. **No local storage limitations**: Data is stored in Supabase's PostgreSQL database, not on your local device.
        
        3. **Automatic backups**: Supabase includes automated backups of your data.
        
        4. **Data sharing**: Easily share watchlists between team members by using the same Supabase project.
        
        5. **Scalability**: As your data grows, the cloud database can handle it without performance issues.
        
        ### For extra safety, we recommend:
        
        - Periodically download backups using the "Download Backup File" button above
        - Store backups in a secure location like a cloud drive or external storage
        
        *For technical support or database issues, please contact the application administrator.*
        """)
