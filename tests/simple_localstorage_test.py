# simple_localstorage_test.py
import streamlit as st

st.title("Simple localStorage Test")

# Very basic test that uses Streamlit components to communicate with JS
st.write("This test checks if localStorage works in your browser")

# Create a button to run the test
if st.button("Run Simple Test"):
    # Create a simple callback mechanism
    st.session_state.test_result = "waiting_for_js"

    # Very simple JS that just tries to use localStorage
    js = """
    <script>
        // Function to set results in the hidden input
        function setTestResult(result) {
            const input = document.querySelector('input[aria-label="test_callback"]');
            if (input) {
                input.value = result;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            } else {
                console.error("Could not find test callback input");
            }
        }
        
        // Try basic localStorage operations
        try {
            // Set a value
            localStorage.setItem('streamlit_simple_test', 'test_value');
            
            // Get the value back
            const value = localStorage.getItem('streamlit_simple_test');
            
            // Check if it worked
            if (value === 'test_value') {
                setTestResult("success");
            } else {
                setTestResult("value_mismatch");
            }
            
            // Clean up
            localStorage.removeItem('streamlit_simple_test');
        } catch (error) {
            setTestResult("error: " + error.message);
        }
    </script>
    """
    st.markdown(js, unsafe_allow_html=True)

    # Create a hidden input for the callback
    test_result = st.text_input(
        "test_callback", "", key="test_callback", label_visibility="hidden")

    if test_result:
        if test_result == "success":
            st.success("localStorage is working properly! ✅")
        elif test_result == "value_mismatch":
            st.warning(
                "localStorage stored the value but returned something different ⚠️")
        elif test_result.startswith("error"):
            st.error(f"localStorage error: {test_result} ❌")
        else:
            st.info(f"Unexpected result: {test_result}")
    else:
        st.info("Waiting for test results...")

st.write("---")
st.write("If you see no results after clicking the button, JavaScript might be disabled in your browser.")

# Also directly tell us what browsers you're using
st.subheader("Browser Information")
st.write("Please provide the following information:")

browser_name = st.text_input("Browser name (e.g., Chrome, Firefox, Edge):")
browser_version = st.text_input("Browser version (if known):")
operating_system = st.text_input("Operating system (e.g., Windows 10, macOS):")

if st.button("Submit Browser Info"):
    st.write("Thank you for providing your browser information:")
    st.json({
        "browser": browser_name,
        "version": browser_version,
        "os": operating_system
    })
    st.write("This information helps diagnose localStorage compatibility issues.")
