from app import create_streamlit_app
import streamlit as st

# Set page config FIRST before any other imports
st.set_page_config(
    page_title="Värde & Momentum Aktiestrategi",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Only after st.set_page_config, import other modules

if __name__ == "__main__":
    create_streamlit_app()
