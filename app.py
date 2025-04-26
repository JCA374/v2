# app.py
import streamlit as st
from strategy import ValueMomentumStrategy
from storage.watchlist_manager import MultiWatchlistManager
from helpers import create_results_table, get_index_constituents

# Import tabs
from tabs.watchlist_tab import render_watchlist_tab
from tabs.analysis_tab import render_analysis_tab


def create_streamlit_app():
    st.set_page_config(
        page_title="Värde & Momentum Aktiestrategi",
        page_icon="📈",
        layout="wide"
    )

    st.title("Värde & Momentum Aktiestrategi")

    # Initialize shared state objects if they don't exist
    if 'strategy' not in st.session_state:
        st.session_state.strategy = ValueMomentumStrategy()

    if 'watchlist_manager' not in st.session_state:
        st.session_state.watchlist_manager = MultiWatchlistManager()

    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = []

    # Check URL parameters for shared watchlist
    handle_url_params()

    # Define tabs - easily extensible
    tabs = {
        "Watchlist & Batch Analysis": render_watchlist_tab,
        "Enskild Aktieanalys": render_analysis_tab,
        # Add new tabs here
        # "New Tab Name": render_new_tab,
    }

    # Create the tabs
    tab_names = list(tabs.keys())
    streamlit_tabs = st.tabs(tab_names)

    # Render each tab's content
    for i, (name, render_function) in enumerate(tabs.items()):
        with streamlit_tabs[i]:
            render_function()

    # Render sidebar
    render_sidebar()


def handle_url_params():
    """Handle URL parameters like shared watchlist links"""
    query_params = st.query_params
    if "shared_watchlist" in query_params:
        encoded_data = query_params["shared_watchlist"][0]
        imported_index = st.session_state.watchlist_manager.import_from_share_link(
            encoded_data)
        if imported_index is not None:
            st.session_state.watchlist_manager.set_active_watchlist(
                imported_index)
            st.success("Importerad watchlist från delad länk!")
            # Clear the parameter after import to avoid reimporting on refresh
            st.query_params.clear()


def render_sidebar():
    """Render the sidebar content"""
    # Sidebar for stock analysis input in the second tab
    if st.session_state.get('current_tab') == 'Enskild Aktieanalys':
        st.sidebar.header("Aktiesök")
        ticker = st.sidebar.text_input(
            "Aktiesymbol (t.ex. AAPL, ERIC-B.ST)", "AAPL")

        if st.sidebar.button("Analysera"):
            st.session_state['analyze_ticker'] = ticker
            st.rerun()

    # Strategy information in the sidebar (shown on all tabs)
    with st.sidebar.expander("Om Värde & Momentum-strategin"):
        st.write("""
        **Värde & Momentum-strategin** kombinerar fundamentala och tekniska kriterier för aktier:
        
        **Fundamentala kriterier:**
        * Bolaget ska tjäna pengar
        * Bolaget ska öka omsättning och vinst, eller öka omsättning med stabil vinstmarginal
        * Bolaget ska handlas till ett rimligt P/E-tal jämfört med sig själv
        
        **Tekniska kriterier:**
        * Bolaget ska sätta högre bottnar
        * Bolaget ska handlas över MA40 (veckovis) och gärna MA4 för extra momentum
        * Bolaget ska ha ett RSI över 50
        * Starkt om bolaget bryter upp ur en konsolideringsfas
        * Starkt om bolaget handlas till sin högsta 52-veckorsnivå
        
        Strategin följer principen "Rid vinnarna och sälj förlorarna". Vid brott under MA40, sälj direkt eller bevaka hårt. Ta förluster tidigt.
        """)

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Utvecklad med Python och Streamlit**")


if __name__ == "__main__":
    create_streamlit_app()
