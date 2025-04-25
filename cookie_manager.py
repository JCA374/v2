import streamlit as st
import json
import base64
from datetime import datetime, timedelta
import logging


class CookieManager:
    """
    A utility class to manage cookies in Streamlit
    Uses localStorage with JavaScript to persist data between sessions
    """

    def __init__(self, cookie_name="watchlist_data"):
        self.cookie_name = cookie_name
        self.debug_mode = False  # Set to True to enable debug messages

    def _debug(self, message):
        """Print debug messages if debug mode is on"""
        if self.debug_mode:
            st.write(f"Debug - CookieManager: {message}")

    def save_cookie(self, data):
        """Save data to browser localStorage"""
        try:
            # Convert data to JSON string
            json_data = json.dumps(data)

            # Encode to base64 to make it URL-safe and handle special characters
            encoded_data = base64.b64encode(json_data.encode()).decode()

            # Store in session state for current session access
            st.session_state[f"{self.cookie_name}_encoded"] = encoded_data

            # Use JavaScript to save to localStorage
            js = f"""
            <script>
                (function() {{
                    try {{
                        localStorage.setItem("{self.cookie_name}", "{encoded_data}");
                        console.log("Data saved to localStorage: {self.cookie_name}");
                    }} catch (e) {{
                        console.error("Failed to save to localStorage:", e);
                    }}
                }})();
            </script>
            """
            st.markdown(js, unsafe_allow_html=True)
            return True
        except Exception as e:
            self._debug(f"Error saving cookie: {str(e)}")
            return False

    def load_cookie(self):
        """Load data from localStorage"""
        # First check session state (for current session)
        if f"{self.cookie_name}_encoded" in st.session_state:
            try:
                encoded_data = st.session_state[f"{self.cookie_name}_encoded"]
                json_data = base64.b64decode(encoded_data).decode()
                data = json.loads(json_data)
                self._debug("Loaded data from session state")
                return data
            except Exception as e:
                self._debug(f"Error loading from session state: {str(e)}")

        # If not in session state, request from localStorage using JavaScript
        # This creates a hidden element to receive the data
        callback_key = f"{self.cookie_name}_callback"

        # JavaScript to load data from localStorage and set it to the callback element
        js = f"""
        <script>
            (function() {{
                document.addEventListener('DOMContentLoaded', function() {{
                    setTimeout(function() {{
                        try {{
                            const data = localStorage.getItem("{self.cookie_name}");
                            const inputElement = window.parent.document.querySelector('textarea[data-testid="{callback_key}"]');
                            if (inputElement && data) {{
                                inputElement.value = data;
                                inputElement.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                console.log("Data loaded from localStorage: {self.cookie_name}");
                            }}
                        }} catch (e) {{
                            console.error("Failed to load from localStorage:", e);
                        }}
                    }}, 500); // Small delay to ensure elements are loaded
                }});
            }})();
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)

        # Create a hidden input to receive the data
        callback_data = st.text_area(
            "Cookie data callback (do not edit)",
            "",
            key=callback_key,
            label_visibility="collapsed",
            height=100
        )

        if callback_data:
            try:
                # Store in session state for future use
                st.session_state[f"{self.cookie_name}_encoded"] = callback_data

                # Decode and return
                json_data = base64.b64decode(callback_data).decode()
                data = json.loads(json_data)
                self._debug("Loaded data from localStorage")
                return data
            except Exception as e:
                self._debug(f"Error loading from localStorage: {str(e)}")

        return None

    def clear_cookie(self):
        """Clear the cookie data"""
        if f"{self.cookie_name}_encoded" in st.session_state:
            del st.session_state[f"{self.cookie_name}_encoded"]

        # Also clear from localStorage
        js = f"""
        <script>
            try {{
                localStorage.removeItem("{self.cookie_name}");
                console.log("Removed from localStorage: {self.cookie_name}");
            }} catch (e) {{
                console.error("Failed to remove from localStorage:", e);
            }}
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)
        return True

    def display_debug_info(self):
        """Display debug information about cookies"""
        self.debug_mode = True

        st.write("### Cookie Debug Information")

        # Check session state
        if f"{self.cookie_name}_encoded" in st.session_state:
            st.write("✅ Data exists in session state")
            try:
                encoded_data = st.session_state[f"{self.cookie_name}_encoded"]
                json_data = base64.b64decode(encoded_data).decode()
                data = json.loads(json_data)
                st.write("Data preview:", data)
            except:
                st.write("❌ Error decoding session state data")
        else:
            st.write("❌ No data in session state")

        # JavaScript to check localStorage
        js = f"""
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                const debugElement = document.getElementById('localstorage-debug');
                if (debugElement) {{
                    try {{
                        const data = localStorage.getItem("{self.cookie_name}");
                        if (data) {{
                            debugElement.textContent = "✅ Data exists in localStorage";
                        }} else {{
                            debugElement.textContent = "❌ No data in localStorage";
                        }}
                    }} catch (e) {{
                        debugElement.textContent = "❌ Error accessing localStorage: " + e.message;
                    }}
                }}
            }});
        </script>
        <div id="localstorage-debug">Checking localStorage...</div>
        """
        st.markdown(js, unsafe_allow_html=True)
