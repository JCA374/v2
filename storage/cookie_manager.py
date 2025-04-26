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
        self.debug_mode = True  # Always enable debugging initially to diagnose issues

    def save_cookie(self, data):
        """Save data to a browser localStorage mechanism"""
        try:
            # Convert data to JSON string
            json_data = json.dumps(data)

            # Encode to base64 to make it URL-safe
            encoded_data = base64.b64encode(json_data.encode()).decode()

            # Store in session state as a cache
            st.session_state[f"{self.cookie_name}_encoded"] = encoded_data

            # Log info about what we're trying to save (always show for debugging)
            st.write(
                f"Attempting to save {len(encoded_data)} bytes to localStorage")

            # For persistence between sessions, we need to use localStorage via JavaScript
            js = f'''
            <script>
                (function() {{
                    try {{
                        localStorage.setItem("{self.cookie_name}", "{encoded_data}");
                        console.log("Data saved to localStorage: {self.cookie_name} ({len(encoded_data)} bytes)");
                        
                        // Verify save by reading it back
                        const verifyData = localStorage.getItem("{self.cookie_name}");
                        if (verifyData === "{encoded_data}") {{
                            console.log("Data verification successful");
                            document.getElementById('save-status').innerHTML = 'Save successful!';
                        }} else {{
                            console.error("Data verification failed - data doesn't match");
                            document.getElementById('save-status').innerHTML = 'Save failed - data mismatch';
                        }}
                    }} catch (e) {{
                        console.error("Error saving to localStorage:", e);
                        document.getElementById('save-status').innerHTML = 'Save error: ' + e.message;
                    }}
                }})();
            </script>
            <div id="save-status"></div>
            '''
            st.markdown(js, unsafe_allow_html=True)

            return True
        except Exception as e:
            st.error(f"Error saving cookie: {str(e)}")
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
                        st.write(
                            f"Data loaded from session state cache ({len(encoded_data)} bytes)")
                    return parsed_data
                except Exception as e:
                    if self.debug_mode:
                        st.write(
                            f"Error decoding data from session state: {str(e)}")
                    # Continue to try loading from localStorage if session state fails

            # Log that we're trying to load from localStorage
            if self.debug_mode:
                st.write("Attempting to load data from localStorage...")

            # If not in session state, we need to request it from localStorage
            # This will only work after the page is fully loaded
            js = f'''
            <script>
                (function() {{
                    try {{
                        const data = localStorage.getItem("{self.cookie_name}");
                        console.log("Checking localStorage for: {self.cookie_name}");
                        
                        if (data) {{
                            console.log("Found data in localStorage: {self.cookie_name} (length: " + data.length + ")");
                            const inputElement = window.parent.document.querySelector('input[aria-label="{self.cookie_name}_callback"]');
                            if (inputElement) {{
                                inputElement.value = data;
                                inputElement.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                console.log("Data sent to Streamlit callback");
                                document.getElementById('load-status').innerHTML = 'Data loaded from localStorage';
                            }} else {{
                                console.error("Could not find the callback input element");
                                document.getElementById('load-status').innerHTML = 'Error: Callback element not found';
                            }}
                        }} else {{
                            console.log("No data found in localStorage for {self.cookie_name}");
                            document.getElementById('load-status').innerHTML = 'No data found in localStorage';
                        }}
                    }} catch (e) {{
                        console.error("Error loading from localStorage:", e);
                        document.getElementById('load-status').innerHTML = 'Error loading: ' + e.message;
                    }}
                }})();
            </script>
            <div id="load-status"></div>
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
                        st.write(
                            f"Data loaded from localStorage via callback ({len(callback_data)} bytes)")
                    return parsed_data
                except Exception as e:
                    if self.debug_mode:
                        st.write(
                            f"Error decoding data from localStorage: {str(e)}")
            else:
                if self.debug_mode:
                    st.write(f"No data received from callback")

            return None
        except Exception as e:
            st.error(f"Error loading cookie: {str(e)}")
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
                    document.getElementById('clear-status').innerHTML = 'Data cleared from localStorage';
                }} catch (e) {{
                    console.error("Error removing from localStorage:", e);
                    document.getElementById('clear-status').innerHTML = 'Error clearing data: ' + e.message;
                }}
            </script>
            <div id="clear-status"></div>
            '''
            st.markdown(js, unsafe_allow_html=True)

            if self.debug_mode:
                st.write(f"Cookie {self.cookie_name} cleared")

            return True
        except Exception as e:
            st.error(f"Error clearing cookie: {str(e)}")
            return False

    def test_localstorage(self):
        """Run a simple test to check if localStorage is working"""
        test_value = f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        js = f'''
        <script>
            (function() {{
                try {{
                    // Try setting a test value
                    localStorage.setItem('streamlit_test', '{test_value}');
                    
                    // Read it back
                    const readValue = localStorage.getItem('streamlit_test');
                    
                    // Check if it matches
                    if (readValue === '{test_value}') {{
                        document.getElementById('storage-test').innerHTML = 
                            '<div style="color:green;font-weight:bold;">✓ localStorage is working properly</div>';
                    }} else {{
                        document.getElementById('storage-test').innerHTML = 
                            '<div style="color:orange;font-weight:bold;">⚠ localStorage returned wrong value</div>';
                    }}
                    
                    // Clean up
                    localStorage.removeItem('streamlit_test');
                }} catch (e) {{
                    document.getElementById('storage-test').innerHTML = 
                        '<div style="color:red;font-weight:bold;">✗ localStorage error: ' + e.message + '</div>';
                }}
            }})();
        </script>
        <div id="storage-test"></div>
        '''

        st.markdown(js, unsafe_allow_html=True)
        st.write("Testing localStorage functionality...")
