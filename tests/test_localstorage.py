# tests/test_localstorage.py
# A simple Streamlit app to test localStorage functionality
import streamlit as st
import json
import base64
from datetime import datetime

st.set_page_config(page_title="LocalStorage Test", layout="wide")

st.title("Browser localStorage Test Tool")
st.write("This simple app tests if your browser supports localStorage for the Value & Momentum Stock App")

# Test basic localStorage
st.subheader("1. Basic localStorage Test")

js_test = """
<script>
(function() {
    const testValue = "test-" + Date.now();
    let result = "";
    let color = "red";
    
    try {
        // Test setting a value
        localStorage.setItem('streamlit_test', testValue);
        
        // Test reading the value
        const readValue = localStorage.getItem('streamlit_test');
        
        if (readValue === testValue) {
            result = "✓ SUCCESS: localStorage is working properly";
            color = "green";
        } else {
            result = "⚠ WARNING: Value mismatch - localStorage may be corrupted";
            color = "orange";
        }
        
        // Clean up
        localStorage.removeItem('streamlit_test');
    } catch (e) {
        result = "✗ ERROR: " + e.message;
        color = "red";
    }
    
    document.getElementById('test-result').innerHTML = 
        `<div style="color:${color};font-weight:bold;padding:10px;background:#f0f0f0;border-radius:5px;">
            ${result}
        </div>`;
})();
</script>
<div id="test-result">Running test...</div>
"""

st.markdown(js_test, unsafe_allow_html=True)

# Test with larger data
st.subheader("2. Storage Size Test")

test_data = {
    "test_array": list(range(1000)),
    "test_string": "A" * 1000,
    "timestamp": str(datetime.now())
}

# Fixed version - removing Python f-string and using JavaScript template literals only
js_size_test = """
<script>
(function() {
    const testData = '""" + json.dumps(test_data) + """';
    let result = "";
    let color = "red";
    
    try {
        // Test setting a large value
        localStorage.setItem('streamlit_size_test', testData);
        
        // Get the size
        const size = testData.length;
        
        // Test reading the value
        const readValue = localStorage.getItem('streamlit_size_test');
        
        if (readValue === testData) {
            result = `✓ SUCCESS: Successfully stored and retrieved ${size} bytes`;
            color = "green";
        } else {
            result = `⚠ WARNING: Data mismatch when storing ${size} bytes`;
            color = "orange";
        }
        
        // Clean up
        localStorage.removeItem('streamlit_size_test');
    } catch (e) {
        result = `✗ ERROR: ${e.message}`;
        color = "red";
    }
    
    document.getElementById('size-test-result').innerHTML = 
        `<div style="color:${color};font-weight:bold;padding:10px;background:#f0f0f0;border-radius:5px;">
            ${result}
        </div>`;
})();
</script>
<div id="size-test-result">Running test...</div>
"""

st.markdown(js_size_test, unsafe_allow_html=True)

# Test base64 encoding (used by the cookie manager)
st.subheader("3. Base64 Encoding Test")

encoded_data = base64.b64encode(json.dumps(test_data).encode()).decode()

# Fixed version - removing Python f-string and using JavaScript template literals only
js_base64_test = """
<script>
(function() {
    const encodedData = '""" + encoded_data + """';
    let result = "";
    let color = "red";
    
    try {
        // Test setting base64 encoded value
        localStorage.setItem('streamlit_base64_test', encodedData);
        
        // Test reading the value
        const readValue = localStorage.getItem('streamlit_base64_test');
        
        if (readValue === encodedData) {
            result = "✓ SUCCESS: Base64 encoded data stored and retrieved successfully";
            color = "green";
        } else {
            result = "⚠ WARNING: Base64 data mismatch - potential encoding issues";
            color = "orange";
        }
        
        // Clean up
        localStorage.removeItem('streamlit_base64_test');
    } catch (e) {
        result = "✗ ERROR: " + e.message;
        color = "red";
    }
    
    document.getElementById('base64-test-result').innerHTML = 
        `<div style="color:${color};font-weight:bold;padding:10px;background:#f0f0f0;border-radius:5px;">
            ${result}
        </div>`;
})();
</script>
<div id="base64-test-result">Running test...</div>
"""

st.markdown(js_base64_test, unsafe_allow_html=True)

# Check browser information
st.subheader("4. Browser Information")

js_browser_info = """
<script>
(function() {
    const browserInfo = {
        userAgent: navigator.userAgent,
        cookiesEnabled: navigator.cookieEnabled,
        platform: navigator.platform,
        language: navigator.language,
        localStorage: typeof localStorage !== 'undefined',
        sessionStorage: typeof sessionStorage !== 'undefined'
    };
    
    document.getElementById('browser-info').innerText = JSON.stringify(browserInfo, null, 2);
})();
</script>
<pre id="browser-info">Fetching browser information...</pre>
"""

st.markdown(js_browser_info, unsafe_allow_html=True)

# Instructions for fixing issues
st.subheader("Troubleshooting")
st.markdown("""
If the tests above indicate problems with localStorage, try these steps:

1. **Check browser settings:**
   - Ensure cookies and site data are enabled
   - Make sure you're not in private/incognito browsing mode
   - Disable any privacy extensions that might block localStorage

2. **Try a different browser:**
   - Chrome and Edge generally have good localStorage support
   - Firefox with default settings should work well

3. **Alternative storage option:**
   - If localStorage doesn't work in your environment, use the manual JSON download/upload 
     feature in the Debug tab of the Value & Momentum Stock App

4. **Clear browser data:**
   - Sometimes clearing your browser cache can resolve localStorage issues
""")

if st.button("Check if this is a Streamlit Cloud environment"):
    import os
    # Check for environment variables commonly found in Streamlit Cloud
    cloud_env = any(env in os.environ for env in [
                    'STREAMLIT_SHARING', 'STREAMLIT_SERVER_URL'])

    if cloud_env:
        st.info(
            "This appears to be running on Streamlit Cloud, which has full localStorage support.")
    else:
        st.info("This appears to be running locally or in another environment.")

st.markdown("---")
st.markdown(
    "This test tool helps diagnose localStorage issues in the Value & Momentum Stock App.")
