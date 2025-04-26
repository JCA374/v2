# storage/cookie_manager.py
import streamlit as st
import json
import base64
from datetime import datetime, timedelta


class CookieManager:
    """
    A utility class to manage cookies in Streamlit
    Uses st.experimental_set_query_params as a workaround for cookie storage
    since Streamlit doesn't have built-in cookie management
    """

    def __init__(self, cookie_name="watchlist_data"):
        self.cookie_name = cookie_name

    def save_cookie(self, data):
        """Save data to a cookie-like mechanism using session state"""
        # Convert data to JSON string
        json_data = json.dumps(data)

        # Encode to base64 to make it URL-safe
        encoded_data = base64.b64encode(json_data.encode()).decode()

        # Store in session state
        st.session_state[f"{self.cookie_name}_encoded"] = encoded_data

        # For persistence between sessions, we need to use localStorage via JavaScript
        # This is a workaround since Streamlit doesn't have direct cookie access
        js = f'''
        <script>
            localStorage.setItem("{self.cookie_name}", "{encoded_data}");
        </script>
        '''
        st.markdown(js, unsafe_allow_html=True)

    def load_cookie(self):
        """Load data from cookie-like storage"""
        # Try to get data from JavaScript localStorage via a callback
        # This is complex in Streamlit, so we'll use a simplified approach

        # First check session state (for current session)
        if f"{self.cookie_name}_encoded" in st.session_state:
            encoded_data = st.session_state[f"{self.cookie_name}_encoded"]
            try:
                json_data = base64.b64decode(encoded_data).decode()
                return json.loads(json_data)
            except:
                return None

        # If not in session state, we need to request it from localStorage
        # This will only work after a page reload
        js = f'''
        <script>
            const data = localStorage.getItem("{self.cookie_name}");
            if (data) {{
                const inputElement = window.parent.document.querySelector('input[aria-label="{self.cookie_name}_callback"]');
                if (inputElement) {{
                    inputElement.value = data;
                    inputElement.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            }}
        </script>
        '''
        st.markdown(js, unsafe_allow_html=True)

        # Create a hidden input to receive the callback data
        callback_data = st.text_input(
            f"{self.cookie_name}_callback", "", key=f"{self.cookie_name}_callback", label_visibility="hidden")

        if callback_data:
            try:
                # Store in session state for future use
                st.session_state[f"{self.cookie_name}_encoded"] = callback_data

                # Decode and return
                json_data = base64.b64decode(callback_data).decode()
                return json.loads(json_data)
            except:
                return None

        return None

    def clear_cookie(self):
        """Clear the cookie data"""
        if f"{self.cookie_name}_encoded" in st.session_state:
            del st.session_state[f"{self.cookie_name}_encoded"]

        # Also clear from localStorage
        js = f'''
        <script>
            localStorage.removeItem("{self.cookie_name}");
        </script>
        '''
        st.markdown(js, unsafe_allow_html=True)
