"""
Storage Settings tab for configuring and managing database storage.
"""
import streamlit as st
import os
import json
import shutil
from datetime import datetime
from pathlib import Path


def render_storage_settings_tab():
    """Render the storage settings tab for managing database configuration."""
    st.header("Storage Settings")

    # Access database storage from session state
    db_storage = st.session_state.get('db_storage')
    watchlist_manager = st.session_state.get('watchlist_manager')

    if not db_storage:
        st.error(
            "Database storage is not initialized. Please restart the application.")
        return

    # Database information and status
    st.subheader("Database Status")
    db_info = db_storage.get_database_info()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Watchlists", db_info.get("watchlist_count", 0))
    with col2:
        st.metric("Total Stocks", db_info.get("stock_count", 0))
    with col3:
        st.metric("Database Size", db_info.get("size_formatted", "0 KB"))

    st.info(f"Database location: {db_info.get('path', 'Unknown')}")

    # Database settings
    st.subheader("Storage Location")

    new_location = st.text_input(
        "Custom database location (leave empty for default)",
        value="",
        help="Specify a custom location for the database file. Leave empty to use the default location."
    )

    if st.button("Change Database Location"):
        if new_location:
            try:
                # Create directory if it doesn't exist
                new_dir = os.path.dirname(new_location)
                if new_dir and not os.path.exists(new_dir):
                    os.makedirs(new_dir, exist_ok=True)

                # Copy current database to new location
                if os.path.exists(db_info.get('path', '')):
                    shutil.copy2(db_info.get('path', ''), new_location)
                    # Update database path in session state
                    st.session_state['db_path'] = new_location
                    st.success(f"Database moved to {new_location}")
                    st.info(
                        "Please restart the application for changes to take effect.")
                else:
                    # Create a new database at the specified location
                    from storage.db_storage import DatabaseStorage
                    new_db = DatabaseStorage(new_location)
                    # Save current watchlists to the new database
                    if 'watchlists' in st.session_state:
                        new_db.save_watchlists(
                            st.session_state.watchlists,
                            st.session_state.get('active_watchlist_index', 0)
                        )
                    st.success(f"New database created at {new_location}")
                    st.info(
                        "Please restart the application for changes to take effect.")
            except Exception as e:
                st.error(f"Error changing database location: {str(e)}")

    # Backup and restore section
    st.subheader("Backup & Restore")

    col1, col2 = st.columns(2)

    with col1:
        st.write("### Create Backup")
        backup_filename = f"watchlists_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Generate backup JSON for download
        data = db_storage.load_watchlists()
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
                            success = db_storage.save_watchlists(
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
                            current_data = db_storage.load_watchlists()
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
                            success = db_storage.save_watchlists(
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
        st.warning("These actions can result in data loss. Use with caution.")

        # Reset database
        if st.button("Reset Database", help="Delete all watchlists and start fresh"):
            if st.session_state.get('watchlists'):
                if db_storage.save_watchlists([], 0):
                    st.session_state.watchlists = []
                    st.session_state.active_watchlist_index = 0
                    st.success("Database reset successfully!")
                    st.info("Please reload the app to see the changes.")
                else:
                    st.error("Failed to reset database")

        # Enable/disable debug mode
        debug_mode = st.checkbox(
            "Debug Mode",
            value=db_storage.debug_mode,
            help="Show detailed logging for database operations"
        )

        if debug_mode != db_storage.debug_mode:
            db_storage.debug_mode = debug_mode
            st.success(f"Debug mode {'enabled' if debug_mode else 'disabled'}")

    # Display tips for mobile/cross-device usage
    st.subheader("Cross-Device Usage")
    st.markdown("""
    ### How to access your watchlists on multiple devices:
    
    1. **Using the same computer**: Your watchlists are stored in a local database that persists between sessions.
    
    2. **Accessing from another computer**:
       - Create a backup file using the "Download Backup File" button above
       - Transfer the backup file to the other computer
       - On the other computer, use "Restore from Backup" to import your watchlists
    
    3. **Accessing from mobile devices**:
       - For advanced users: Set up your database in a cloud-synced folder (e.g., Dropbox, Google Drive)
       - Use the "Change Database Location" option to point to the synced folder
       - Ensure the Streamlit app is installed on all devices that need access
    
    *Note: A future version may include cloud synchronization for easier multi-device access.*
    """)
