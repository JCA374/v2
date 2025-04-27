# storage/file_storage.py
import streamlit as st
import json
import os
import tempfile
from datetime import datetime
import uuid
import base64


class FileStorage:
    """
    A fallback storage solution that uses file downloads/uploads 
    when browser localStorage is not working.
    """

    def __init__(self):
        self.debug_mode = False

    def save_watchlists(self, watchlists, active_index=0):
        """Create a download button for watchlist data"""
        data = {
            "watchlists": watchlists,
            "active_index": active_index,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "id": str(uuid.uuid4())
        }

        # Convert to JSON
        json_data = json.dumps(data, indent=2)

        # Create a download button
        download_clicked = st.download_button(
            "Save Watchlists to File",
            json_data,
            "watchlists_backup.json",
            "application/json",
            key=f"download_{datetime.now().strftime('%H%M%S')}"
        )

        if download_clicked and self.debug_mode:
            st.success("Watchlists saved to file")

        return download_clicked

    def load_watchlists(self):
        """Create an upload widget for watchlist data"""
        uploaded_file = st.file_uploader(
            "Load Watchlists from File",
            type=['json'],
            key=f"upload_{datetime.now().strftime('%H%M%S')}"
        )

        if uploaded_file is not None:
            try:
                # Read and parse the JSON data
                import_data = json.loads(uploaded_file.getvalue().decode())

                # Validate the data structure
                if "watchlists" in import_data and "active_index" in import_data:
                    # Return the imported data
                    if self.debug_mode:
                        st.success(
                            f"Loaded {len(import_data['watchlists'])} watchlists from file")
                    return import_data
                else:
                    st.error("Invalid backup file format")
            except Exception as e:
                st.error(f"Error loading file: {str(e)}")

        return None

    def create_share_link(self, watchlist_data):
        """Create a shareable link for a watchlist"""
        try:
            # Convert data to JSON
            json_data = json.dumps(watchlist_data)

            # Encode to base64
            encoded = base64.b64encode(json_data.encode()).decode()

            # Create the link
            link = f"?shared_watchlist={encoded}"

            # Display the link
            st.code(link, language=None)

            # Helper to copy
            st.markdown("""
            <script>
            function copyToClipboard(text) {
                navigator.clipboard.writeText(text).then(
                    function() {
                        alert('Link copied!');
                    }, 
                    function() {
                        alert('Failed to copy');
                    }
                );
            }
            </script>
            """, unsafe_allow_html=True)

            if st.button("Copy Link"):
                st.markdown(
                    f"""
                    <script>
                    copyToClipboard(window.location.origin + window.location.pathname + "{link}");
                    </script>
                    """,
                    unsafe_allow_html=True
                )

            return link
        except Exception as e:
            st.error(f"Error creating share link: {str(e)}")
            return None

    def import_from_share_link(self, encoded_data):
        """Import watchlist data from an encoded share link"""
        try:
            # Decode the data
            json_string = base64.b64decode(encoded_data).decode()
            data = json.loads(json_string)

            # Validate the data
            if "name" in data and "stocks" in data:
                return data
            else:
                st.error("Invalid shared watchlist data")
                return None
        except Exception as e:
            st.error(f"Error importing from link: {str(e)}")
            return None
