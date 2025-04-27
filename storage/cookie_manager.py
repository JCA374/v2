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
        self.debug_mode = False  # Set to True to enable debugging

    def save_cookie(self, data):
        """Save data to a browser localStorage mechanism"""
        try:
            # Convert data to JSON string
            json_data = json.dumps(data)

            # Encode to base64 to make it URL-safe
            encoded_data = base64.b64encode(json_data.encode()).decode()

            # Store in session state as a cache
            st.session_state[f"{self.cookie_name}_encoded"] = encoded_data

            # Log debug info if enabled
            if self.debug_mode:
                st.write(f"Saving {len(encoded_data)} bytes to localStorage")

            # For persistence between sessions, we need to use localStorage via JavaScript
            js = f'''
            <script>
                (function() {{
                    try {{
                        // Use JSON.stringify for proper escaping when saving
                        localStorage.setItem("{self.cookie_name}", "{encoded_data}");
                        console.log("Data saved to localStorage: {self.cookie_name} ({len(encoded_data)} bytes)");
                        
                        // Verify save by reading it back
                        const verifyData = localStorage.getItem("{self.cookie_name}");
                        if (verifyData === "{encoded_data}") {{
                            console.log("Data verification successful");
                            const statusEl = document.getElementById('save-status');
                            if (statusEl) statusEl.innerHTML = '<span style="color:green">✓ Save successful!</span>';
                        }} else {{
                            console.error("Data verification failed - data doesn't match");
                            const statusEl = document.getElementById('save-status');
                            if (statusEl) statusEl.innerHTML = '<span style="color:orange">⚠ Save verification failed</span>';
                        }}
                    }} catch (e) {{
                        console.error("Error saving to localStorage:", e);
                        const statusEl = document.getElementById('save-status');
                        if (statusEl) statusEl.innerHTML = '<span style="color:red">✗ Save error: ' + e.message + '</span>';
                    }}
                }})();
            </script>
            <div id="save-status"></div>
            '''
            st.markdown(js, unsafe_allow_html=True)

            return True
        except Exception as e:
            if self.debug_mode:
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

            # Create a placeholder for the text input
            placeholder = st.empty()

            # Hidden input to receive the callback data
            callback_data = placeholder.text_input(
                f"{self.cookie_name}_callback",
                "",
                key=f"{self.cookie_name}_callback",
                label_visibility="hidden"
            )

            # If debug mode is enabled, show debug info
            if self.debug_mode:
                st.write("Attempting to load data from localStorage...")

            # If not in session state, we need to request it from localStorage
            # This will only work after the page is fully loaded
            js = f'''
            <script>
                (function() {{
                    // Add a small delay to ensure the input is mounted in the DOM
                    setTimeout(function() {{
                        try {{
                            const data = localStorage.getItem("{self.cookie_name}");
                            console.log("Checking localStorage for: {self.cookie_name}");
                            
                            if (data) {{
                                console.log("Found data in localStorage: {self.cookie_name} (length: " + data.length + ")");
                                // FIXED: Use document instead of window.parent.document
                                const inputElement = document.querySelector('input[data-key="{self.cookie_name}_callback"]');
                                if (inputElement) {{
                                    inputElement.value = data;
                                    inputElement.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    console.log("Data sent to Streamlit callback");
                                    const statusEl = document.getElementById('load-status');
                                    if (statusEl) statusEl.innerHTML = '<span style="color:green">✓ Data loaded from localStorage</span>';
                                }} else {{
                                    console.error("Could not find the callback input element");
                                    const statusEl = document.getElementById('load-status');
                                    if (statusEl) statusEl.innerHTML = '<span style="color:red">✗ Error: Callback element not found</span>';
                                }}
                            }} else {{
                                console.log("No data found in localStorage for {self.cookie_name}");
                                const statusEl = document.getElementById('load-status');
                                if (statusEl) statusEl.innerHTML = '<span style="color:orange">⚠ No data found in localStorage</span>';
                            }}
                        }} catch (e) {{
                            console.error("Error loading from localStorage:", e);
                            const statusEl = document.getElementById('load-status');
                            if (statusEl) statusEl.innerHTML = '<span style="color:red">✗ Error loading: ' + e.message + '</span>';
                        }}
                    }}, 100); // Add a 100ms delay to ensure the DOM is ready
                }})();
            </script>
            <div id="load-status"></div>
            '''
            st.markdown(js, unsafe_allow_html=True)

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
            if self.debug_mode:
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
                (function() {{
                    try {{
                        localStorage.removeItem("{self.cookie_name}");
                        console.log("Data removed from localStorage: {self.cookie_name}");
                        const statusEl = document.getElementById('clear-status');
                        if (statusEl) statusEl.innerHTML = '<span style="color:green">✓ Data cleared from localStorage</span>';
                    }} catch (e) {{
                        console.error("Error removing from localStorage:", e);
                        const statusEl = document.getElementById('clear-status');
                        if (statusEl) statusEl.innerHTML = '<span style="color:red">✗ Error clearing data: ' + e.message + '</span>';
                    }}
                }})();
            </script>
            <div id="clear-status"></div>
            '''
            st.markdown(js, unsafe_allow_html=True)

            if self.debug_mode:
                st.write(f"Cookie {self.cookie_name} cleared")

            return True
        except Exception as e:
            if self.debug_mode:
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

        # Provide a more comprehensive browser environment check
        st.write("### Browser Storage Compatibility Check")

        js_check = '''
        <script>
        (function() {
            try {
                // General browser info
                const browserInfo = {
                    userAgent: navigator.userAgent,
                    cookiesEnabled: navigator.cookieEnabled,
                    localStorage: typeof localStorage !== 'undefined',
                    privateMode: "Unknown"
                };
                
                // Try detecting private browsing mode
                const testKey = 'streamlit_private_test';
                try {
                    localStorage.setItem(testKey, '1');
                    localStorage.removeItem(testKey);
                    browserInfo.privateMode = "Not detected";
                } catch (e) {
                    browserInfo.privateMode = "Likely (localStorage access error)";
                }
                
                // Storage quota info
                let storageInfo = "Unknown";
                if (navigator.storage && navigator.storage.estimate) {
                    navigator.storage.estimate().then(estimate => {
                        const percent = (estimate.usage / estimate.quota * 100).toFixed(2);
                        document.getElementById('quota-info').innerHTML = 
                            `Storage: ${formatBytes(estimate.usage)} used of ${formatBytes(estimate.quota)} (${percent}%)`;
                    });
                }
                
                // Show browser info
                document.getElementById('browser-check').innerHTML = 
                    `<strong>Browser:</strong> ${browserInfo.userAgent}<br>` +
                    `<strong>Cookies Enabled:</strong> ${browserInfo.cookiesEnabled}<br>` +
                    `<strong>localStorage Available:</strong> ${browserInfo.localStorage}<br>` +
                    `<strong>Private Mode:</strong> ${browserInfo.privateMode}`;
                    
                function formatBytes(bytes) {
                    if (bytes === 0) return '0 Bytes';
                    const k = 1024;
                    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
                }
            } catch (e) {
                document.getElementById('browser-check').innerHTML = 
                    `<div style="color:red">Error checking browser compatibility: ${e.message}</div>`;
            }
        })();
        </script>
        <div id="browser-check"></div>
        <div id="quota-info"></div>
        '''

        st.markdown(js_check, unsafe_allow_html=True)
        st.write("Testing localStorage functionality...")
