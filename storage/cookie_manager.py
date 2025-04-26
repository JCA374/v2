# storage/cookie_manager.py
import streamlit as st
import json
import base64
from datetime import datetime, timedelta


class CookieManager:
    """
    A utility class to manage cookies in Streamlit
    Uses localStorage via JavaScript as a workaround for cookie storage
    since Streamlit doesn't have built-in cookie management
    """

    def __init__(self, cookie_name="watchlist_data"):
        """Initialize the cookie manager with the given cookie name"""
        self.cookie_name = cookie_name
        self.debug_mode = False  # Enable for debugging

    def save_cookie(self, data):
        """Save data to a browser localStorage mechanism"""
        try:
            # Convert data to JSON string
            json_data = json.dumps(data)

            # Encode to base64 to make it URL-safe
            encoded_data = base64.b64encode(json_data.encode()).decode()

            # Store in session state as a cache
            st.session_state[f"{self.cookie_name}_encoded"] = encoded_data

            # For persistence between sessions, we need to use localStorage via JavaScript
            js = f'''
            <script>
                try {{
                    localStorage.setItem("{self.cookie_name}", "{encoded_data}");
                    console.log("Data saved to localStorage: {self.cookie_name}");
                }} catch (e) {{
                    console.error("Error saving to localStorage:", e);
                }}
            </script>
            '''
            st.markdown(js, unsafe_allow_html=True)

            if self.debug_mode:
                st.write(f"Data saved to cookies ({len(encoded_data)} bytes)")

            return True
        except Exception as e:
            if self.debug_mode:
                st.write(f"Error saving cookie: {str(e)}")
            return False

    def load_cookie(self):
        """Load data from localStorage"""
        try:
            # First check session state (for current session)
            if f"{self.cookie_name}_encoded" in st.session_state:
                encoded_data = st.session_state[f"{self.cookie_name}_encoded"]
                try:
                    json_data = base64.b64decode(encoded_data).decode()
                    parsed_data = json.loads(json_data)
                    if self.debug_mode:
                        st.write(f"Data loaded from session state cache")
                    return parsed_data
                except Exception as e:
                    if self.debug_mode:
                        st.write(
                            f"Error decoding data from session state: {str(e)}")
                    # Continue to try loading from localStorage if session state fails

            # If not in session state, we need to request it from localStorage
            # This will only work after the page is fully loaded
            js = f'''
            <script>
                try {{
                    const data = localStorage.getItem("{self.cookie_name}");
                    if (data) {{
                        const inputElement = window.parent.document.querySelector('input[aria-label="{self.cookie_name}_callback"]');
                        if (inputElement) {{
                            inputElement.value = data;
                            inputElement.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            console.log("Data loaded from localStorage: {self.cookie_name}");
                        }}
                    }}
                }} catch (e) {{
                    console.error("Error loading from localStorage:", e);
                }}
            </script>
            '''
            st.markdown(js, unsafe_allow_html=True)

            # Create a hidden input to receive the callback data
            callback_data = st.text_input(
                f"{self.cookie_name}_callback",
                "",
                key=f"{self.cookie_name}_callback",
                label_visibility="hidden"
            )

            if callback_data:
                try:
                    # Store in session state for future use
                    st.session_state[f"{self.cookie_name}_encoded"] = callback_data

                    # Decode and return
                    json_data = base64.b64decode(callback_data).decode()
                    parsed_data = json.loads(json_data)
                    if self.debug_mode:
                        st.write(f"Data loaded from localStorage via callback")
                    return parsed_data
                except Exception as e:
                    if self.debug_mode:
                        st.write(
                            f"Error decoding data from localStorage: {str(e)}")
            else:
                if self.debug_mode:
                    st.write(
                        f"No data found in localStorage for {self.cookie_name}")

            return None
        except Exception as e:
            if self.debug_mode:
                st.write(f"Error loading cookie: {str(e)}")
            return None

    def clear_cookie(self):
        """Clear the cookie data"""
        try:
            if f"{self.cookie_name}_encoded" in st.session_state:
                del st.session_state[f"{self.cookie_name}_encoded"]

            # Also clear from localStorage
            js = f'''
            <script>
                try {{
                    localStorage.removeItem("{self.cookie_name}");
                    console.log("Data removed from localStorage: {self.cookie_name}");
                }} catch (e) {{
                    console.error("Error removing from localStorage:", e);
                }}
            </script>
            '''
            st.markdown(js, unsafe_allow_html=True)

            if self.debug_mode:
                st.write(f"Cookie {self.cookie_name} cleared")

            return True
        except Exception as e:
            if self.debug_mode:
                st.write(f"Error clearing cookie: {str(e)}")
            return False
