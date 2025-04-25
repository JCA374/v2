import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import streamlit as st
import time
import json
import os
import base64
import uuid
from urllib.parse import quote, unquote

from strategy import ValueMomentumStrategy
from watchlist import MultiWatchlistManager  # Updated import
from helpers import create_results_table, get_index_constituents
from debug_utils import add_debug_section  # Import debug utilities


def create_streamlit_app():
    st.set_page_config(
        page_title="Värde & Momentum Aktiestrategi",
        page_icon="📈",
        layout="wide"
    )

    # Create a unique session ID if not already present
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    st.title("Värde & Momentum Aktiestrategi")

    # Check URL parameters for shared watchlist
    query_params = st.query_params
    has_shared_watchlist = "shared_watchlist" in query_params

    # Initialize strategy and watchlist manager with debug mode
    strategy = ValueMomentumStrategy()

    # Set debug_mode to True if needed for troubleshooting
    debug_mode = False  # Change to True for debugging
    watchlist_manager = MultiWatchlistManager(enable_debug=debug_mode)

    # Handle importing shared watchlist if present in URL
    if has_shared_watchlist:
        encoded_data = query_params["shared_watchlist"][0]
        imported_index = watchlist_manager.import_from_share_link(encoded_data)
        if imported_index is not None:
            watchlist_manager.set_active_watchlist(imported_index)
            st.success("Importerad watchlist från delad länk!")
            # Clear the parameter after import to avoid reimporting on refresh
            st.query_params.clear()

    # Create session variable for analysis results if it doesn't exist
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = []

    # Create UI sections
    tab1, tab2, tab3 = st.tabs(
        ["Watchlist & Batch Analysis", "Enskild Aktieanalys", "Inställningar"])

    # Tab 1 - Watchlist & Batch analysis
    with tab1:
        col1, col2 = st.columns([1, 3])

        with col1:
            # Watchlist selector and management
            st.subheader("Mina Watchlists")

            # Dropdown to select active watchlist
            all_watchlists = watchlist_manager.get_all_watchlists()
            watchlist_names = [w["name"] for w in all_watchlists]
            current_index = watchlist_manager.get_active_watchlist_index()

            col_ws1, col_ws2 = st.columns([3, 1])

            with col_ws1:
                selected_watchlist = st.selectbox(
                    "Välj watchlist",
                    options=range(len(watchlist_names)),
                    format_func=lambda i: watchlist_names[i],
                    index=current_index
                )

                if selected_watchlist != current_index:
                    watchlist_manager.set_active_watchlist(selected_watchlist)
                    st.rerun()

            with col_ws2:
                if st.button("+ Ny", key="add_new_watchlist"):
                    new_index = watchlist_manager.add_watchlist()
                    watchlist_manager.set_active_watchlist(new_index)
                    st.rerun()

            # Watchlist management (rename, delete, share)
            with st.expander("Hantera watchlist"):
                active_watchlist = watchlist_manager.get_active_watchlist()

                # Rename watchlist
                new_name = st.text_input(
                    "Nytt namn", value=active_watchlist["name"])
                if st.button("Byt namn"):
                    if watchlist_manager.rename_watchlist(current_index, new_name):
                        st.success(f"Bytte namn till {new_name}")
                        st.rerun()
                    else:
                        st.error("Kunde inte byta namn")

                # Delete watchlist
                if len(all_watchlists) > 1:  # Only show delete if there's more than one watchlist
                    if st.button("Ta bort denna watchlist", key="delete_watchlist"):
                        if watchlist_manager.delete_watchlist(current_index):
                            st.success("Watchlist borttagen")
                            st.rerun()
                        else:
                            st.error("Kunde inte ta bort watchlist")

                # Share watchlist
                st.subheader("Dela watchlist")
                active_watchlist = watchlist_manager.get_active_watchlist()
                share_export_tab1, share_export_tab2 = st.tabs(
                    ["Delningslänk", "JSON Export"])

                with share_export_tab1:
                    share_link = watchlist_manager.generate_share_link()

                    if share_link:
                        # Get the base URL from the browser
                        st.markdown(
                            "Kopiera denna länk för att dela din watchlist:")
                        st.code(share_link, language=None)

                        # Use JavaScript to help with copying
                        copy_js = f"""
                        <script>
                        function copyShareLink() {{
                            const text = '{share_link}';
                            navigator.clipboard.writeText(window.location.origin + window.location.pathname + text)
                                .then(() => alert('Länk kopierad!'))
                                .catch(err => alert('Kunde inte kopiera: ' + err));
                        }}
                        </script>
                        <button onclick="copyShareLink()" style="background-color:#4CAF50;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;">Kopiera delningslänk</button>
                        """
                        st.markdown(copy_js, unsafe_allow_html=True)

                with share_export_tab2:
                    json_data = watchlist_manager.export_watchlist()
                    if json_data:
                        st.markdown(
                            "Kopiera denna JSON kod för att dela din watchlist:")
                        st.code(json_data, language="json")

                        # Use JavaScript to help with copying
                        copy_js = f"""
                        <script>
                        function copyJsonCode() {{
                            const text = {json.dumps(json_data)};
                            navigator.clipboard.writeText(text)
                                .then(() => alert('JSON kopierad!'))
                                .catch(err => alert('Kunde inte kopiera: ' + err));
                        }}
                        </script>
                        <button onclick="copyJsonCode()" style="background-color:#4CAF50;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;">Kopiera JSON</button>
                        """
                        st.markdown(copy_js, unsafe_allow_html=True)

                # Import watchlist
                st.subheader("Importera watchlist")
                import_tab1, import_tab2 = st.tabs(["Från länk", "Från JSON"])

                with import_tab1:
                    import_link = st.text_input(
                        "Klistra in delningslänk eller kod", key="import_link")

                    if st.button("Importera från länk"):
                        try:
                            # Clean up the input to handle various formats
                            if "shared_watchlist=" in import_link:
                                # Extract the parameter from a full URL or just the query string
                                parts = import_link.split("shared_watchlist=")
                                if len(parts) > 1:
                                    encoded_data = parts[1].split(
                                        "&")[0]  # Handle additional params
                                    imported_index = watchlist_manager.import_from_share_link(
                                        encoded_data)

                                    if imported_index is not None:
                                        watchlist_manager.set_active_watchlist(
                                            imported_index)
                                        st.success(
                                            "Watchlist importerad från länk!")
                                        st.rerun()
                                    else:
                                        st.error(
                                            "Kunde inte importera watchlist från länk")
                                else:
                                    st.error("Ogiltig delningslänk format")
                            else:
                                st.error("Ingen giltig delningslänk hittades")
                        except Exception as e:
                            st.error(f"Fel vid import: {str(e)}")

                with import_tab2:
                    import_json = st.text_area(
                        "Klistra in JSON data", key="import_json")

                    if st.button("Importera från JSON"):
                        try:
                            if import_json:
                                imported_index = watchlist_manager.import_watchlist(
                                    import_json)

                                if imported_index is not None:
                                    watchlist_manager.set_active_watchlist(
                                        imported_index)
                                    st.success(
                                        "Watchlist importerad från JSON!")
                                    st.rerun()
                                else:
                                    st.error(
                                        "Kunde inte importera watchlist från JSON")
                            else:
                                st.error("Ingen JSON data angiven")
                        except Exception as e:
                            st.error(f"Fel vid import: {str(e)}")

            # Display current watchlist contents
            st.subheader(f"Aktier i {active_watchlist['name']}")

            # Display the watchlist
            watchlist = watchlist_manager.get_watchlist()

            # Show index list for quick addition
            st.subheader("Lägg till från Index")
            index_choice = st.selectbox(
                "Välj index",
                ["OMXS30", "S&P 500 Top 30", "Dow Jones"]
            )

            index_stocks = get_index_constituents(index_choice)
            selected_index_stocks = st.multiselect(
                "Välj aktier att lägga till",
                [s for s in index_stocks if s not in watchlist]
            )

            if st.button("Lägg till valda"):
                added_count = 0
                for ticker in selected_index_stocks:
                    if watchlist_manager.add_stock(ticker):
                        added_count += 1
                if added_count > 0:
                    st.success(
                        f"Lade till {added_count} aktier till watchlist")
                    # Update watchlist
                    watchlist = watchlist_manager.get_watchlist()
                else:
                    st.info("Inga nya aktier tillades")

            # Manually add stock
            st.subheader("Lägg till manuellt")
            new_ticker = st.text_input("Ticker (t.ex. AAPL, ERIC-B.ST)")

            col1_1, col1_2 = st.columns(2)
            with col1_1:
                if st.button("Lägg till"):
                    if new_ticker and watchlist_manager.add_stock(new_ticker):
                        st.success(f"Lade till {new_ticker}")
                        # Update watchlist
                        watchlist = watchlist_manager.get_watchlist()
                    else:
                        st.error("Kunde inte lägga till aktien")

            # List all stocks in watchlist with remove buttons
            st.subheader("Hantera Aktier")

            if watchlist:
                for ticker in watchlist:
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.write(ticker)
                    with col_b:
                        if st.button("Ta bort", key=f"remove_{ticker}"):
                            if watchlist_manager.remove_stock(ticker):
                                st.success(f"Tog bort {ticker}")
                                # Update the page to show the change
                                st.rerun()
                            else:
                                st.error(f"Kunde inte ta bort {ticker}")
            else:
                st.info("Inga aktier i denna watchlist")

            # Force save watchlist button for troubleshooting
            if debug_mode:
                if st.button("Spara watchlist manuellt"):
                    watchlist_manager._save_to_cookies()
                    st.success("Watchlist manuellt sparad till cookies")

            # Button to run batch analysis on the entire watchlist
            if watchlist:
                if st.button("Analysera alla", key="analyze_all"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    # Callback for progress
                    def update_progress(progress, text):
                        progress_bar.progress(progress)
                        status_text.text(text)

                    # Run batch analysis
                    results = strategy.batch_analyze(
                        watchlist, update_progress)
                    st.session_state.analysis_results = results

                    # Remove progress when done
                    progress_bar.empty()
                    status_text.empty()

                    st.success("Analys klar!")
            else:
                st.info(
                    "Lägg till aktier i din watchlist för att kunna analysera dem")

        with col2:
            st.subheader("Analysresultat")

            # Show the results in a table if they exist
            if st.session_state.analysis_results:
                results_df = create_results_table(
                    st.session_state.analysis_results)

                # Filter options
                st.subheader("Filtrera resultat")
                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    signal_filter = st.multiselect(
                        "Signal",
                        ["KÖP", "HÅLL", "SÄLJ"],
                        default=["KÖP", "HÅLL", "SÄLJ"]
                    )

                with col_b:
                    ma40_filter = st.checkbox(
                        "Bara aktier över MA40", value=False)

                with col_c:
                    tech_score_min = st.slider("Min Tech Score", 0, 100, 0)

                # Apply filters
                filtered_df = results_df.copy()

                if signal_filter:
                    filtered_df = filtered_df[filtered_df["Signal"].isin(
                        signal_filter)]

                if ma40_filter:
                    filtered_df = filtered_df[filtered_df["Över MA40"] == "Ja"]

                filtered_df = filtered_df[filtered_df["Tech Score"]
                                          >= tech_score_min]

                # Show filtered table
                if not filtered_df.empty:
                    # Sort by Tech Score and Signal
                    filtered_df = filtered_df.sort_values(
                        by=["Tech Score", "Signal"], ascending=[False, True])

                    # Format the table
                    st.dataframe(
                        filtered_df,
                        column_config={
                            "Signal": st.column_config.Column(
                                "Signal",
                                help="Köp, Sälj eller Håll signal baserat på strategin",
                                width="small"
                            ),
                            "Tech Score": st.column_config.ProgressColumn(
                                "Tech Score",
                                help="Tekniskt score 0-100",
                                min_value=0,
                                max_value=100,
                                format="%d"
                            )
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Inga aktier matchar valda filter")

                # Option to select a stock for deeper analysis
                if not filtered_df.empty:
                    st.subheader("Välj aktie för detaljerad analys")
                    selected_ticker = st.selectbox(
                        "Aktie",
                        filtered_df["Ticker"].tolist()
                    )

                    if selected_ticker:
                        # Find analysis for selected stock
                        selected_analysis = next(
                            (r for r in st.session_state.analysis_results if r["ticker"] == selected_ticker),
                            None
                        )

                        if selected_analysis and "error" not in selected_analysis:
                            # Show chart
                            st.subheader(
                                f"{selected_analysis['name']} ({selected_analysis['ticker']})")
                            fig = strategy.plot_analysis(selected_analysis)
                            if fig:
                                st.pyplot(fig)

                            # Show details in expandable field
                            with st.expander("Visa detaljer"):
                                col_x, col_y = st.columns(2)

                                with col_x:
                                    st.subheader("Fundamentala Data")
                                    st.write(
                                        f"Lönsamt bolag: {'Ja' if selected_analysis['is_profitable'] else 'Nej'}")
                                    st.write(
                                        f"P/E-tal: {selected_analysis['pe_ratio']:.2f}" if selected_analysis['pe_ratio'] else "P/E-tal: Data saknas")
                                    st.write(
                                        f"Omsättningstillväxt: {selected_analysis['revenue_growth']*100:.1f}%" if selected_analysis['revenue_growth'] else "Omsättningstillväxt: Data saknas")
                                    st.write(
                                        f"Vinstmarginal: {selected_analysis['profit_margin']*100:.1f}%" if selected_analysis['profit_margin'] else "Vinstmarginal: Data saknas")
                                    st.write(
                                        f"Vinstutveckling: {selected_analysis['earnings_trend']}")

                                with col_y:
                                    st.subheader("Tekniska Indikatorer")
                                    st.write(
                                        f"Pris över MA40 (40-veckor): {'Ja' if selected_analysis['above_ma40'] else 'Nej'}")
                                    st.write(
                                        f"Pris över MA4 (4-veckor): {'Ja' if selected_analysis['above_ma4'] else 'Nej'}")
                                    st.write(
                                        f"RSI över 50: {'Ja' if selected_analysis['rsi_above_50'] else 'Nej'}")
                                    st.write(
                                        f"Högre bottnar: {'Ja' if selected_analysis['higher_lows'] else 'Nej'}")
                                    st.write(
                                        f"Nära 52-veckors högsta: {'Ja' if selected_analysis['near_52w_high'] else 'Nej'}")
                                    st.write(
                                        f"Breakout från konsolidering: {'Ja' if selected_analysis['breakout'] else 'Nej'}")
            else:
                st.info("Klicka på 'Analysera alla' för att se resultat")

    # Tab 2 - Individual stock analysis
    with tab2:
        st.sidebar.header("Aktiesök")
        ticker = st.sidebar.text_input(
            "Aktiesymbol (t.ex. AAPL, ERIC-B.ST)", "AAPL")

        if st.sidebar.button("Analysera"):
            with st.spinner(f"Analyserar {ticker}..."):
                analysis = strategy.analyze_stock(ticker)

                if "error" in analysis:
                    st.error(f"Fel: {analysis['error']}")
                else:
                    # Show summary
                    signal_color = "green" if analysis["buy_signal"] else "red" if analysis["sell_signal"] else "orange"
                    signal_text = "KÖP" if analysis["buy_signal"] else "SÄLJ" if analysis["sell_signal"] else "HÅLL"

                    st.header(f"{analysis['name']} ({analysis['ticker']})")
                    st.subheader(f"Pris: {analysis['price']:.2f} SEK")

                    st.markdown(
                        f"<h3 style='color:{signal_color}'>Signal: {signal_text}</h3>", unsafe_allow_html=True)

                    # Show watchlist options - updated to allow adding to any watchlist
                    st.subheader("Lägg till i watchlist")

                    # Create a radio button to select which watchlist to add to
                    all_watchlists = watchlist_manager.get_all_watchlists()
                    watchlist_names = [w["name"] for w in all_watchlists]

                    target_watchlist = st.radio(
                        "Välj watchlist",
                        options=range(len(watchlist_names)),
                        format_func=lambda i: watchlist_names[i],
                        horizontal=True
                    )

                    if st.button("Lägg till i watchlist"):
                        if watchlist_manager.add_stock_to_watchlist(target_watchlist, analysis["ticker"]):
                            st.success(
                                f"Lade till {analysis['ticker']} i {watchlist_names[target_watchlist]}")
                        else:
                            st.error(
                                "Kunde inte lägga till aktien (finns redan eller ogiltigt namn)")

                    # Create tabs for details
                    tab2_1, tab2_2, tab2_3 = st.tabs(
                        ["Översikt", "Fundamenta", "Teknisk Analys"])

                    with tab2_1:
                        # Show chart
                        fig = strategy.plot_analysis(analysis)
                        if fig:
                            st.pyplot(fig)

                        # Show short summary
                        st.subheader("Sammanfattning")
                        st.write(f"Datum för analys: {analysis['date']}")
                        st.write(
                            "Fundamentala kriterier uppfyllda" if analysis["fundamental_check"] else "Fundamentala kriterier EJ uppfyllda")
                        st.write(
                            "Tekniska kriterier uppfyllda" if analysis["technical_check"] else "Tekniska kriterier EJ uppfyllda")
                        st.write(f"Tech Score: {analysis['tech_score']}/100")

                    with tab2_2:
                        st.subheader("Fundamentala Data")
                        st.write(
                            f"Lönsamt bolag: {'Ja' if analysis['is_profitable'] else 'Nej'}")
                        st.write(
                            f"P/E-tal: {analysis['pe_ratio']:.2f}" if analysis['pe_ratio'] else "P/E-tal: Data saknas")
                        st.write(
                            f"Omsättningstillväxt: {analysis['revenue_growth']*100:.1f}%" if analysis['revenue_growth'] else "Omsättningstillväxt: Data saknas")
                        st.write(
                            f"Vinstmarginal: {analysis['profit_margin']*100:.1f}%" if analysis['profit_margin'] else "Vinstmarginal: Data saknas")
                        st.write(
                            f"Vinstutveckling: {analysis['earnings_trend']}")

                    with tab2_3:
                        st.subheader("Tekniska Indikatorer")
                        st.write(
                            f"Pris över MA40 (40-veckor): {'Ja' if analysis['above_ma40'] else 'Nej'}")
                        st.write(
                            f"Pris över MA4 (4-veckor): {'Ja' if analysis['above_ma4'] else 'Nej'}")
                        st.write(
                            f"RSI över 50: {'Ja' if analysis['rsi_above_50'] else 'Nej'}")
                        st.write(
                            f"Högre bottnar: {'Ja' if analysis['higher_lows'] else 'Nej'}")
                        st.write(
                            f"Nära 52-veckors högsta: {'Ja' if analysis['near_52w_high'] else 'Nej'}")
                        st.write(
                            f"Breakout från konsolidering: {'Ja' if analysis['breakout'] else 'Nej'}")

    # Tab 3 - Settings and debug
    with tab3:
        st.header("Inställningar och verktyg")

        # Add cookie debug tools
        add_debug_section(watchlist_manager)

        # Information about the application
        with st.expander("Om applikationen", expanded=True):
            st.write("""
            ### Värde & Momentum Aktiestrategi
            
            Detta är en applikation för att analysera aktier baserat på en kombination av
            värde- och momentumstrategi. Applikationen låter dig:
            
            - Skapa och hantera flera olika watchlists
            - Analysera aktier individuellt eller i batch
            - Dela dina watchlists med andra
            - Filtrera analysresultat baserat på olika kriterier
            
            #### Cookiehantering
            
            Applikationen sparar dina watchlists i webbläsarens localStorage, vilket gör att:
            - Dina listor finns kvar när du stänger och öppnar webbläsaren igen
            - Olika enheter har olika watchlists
            - Ingen data sparas på servern
            
            Om du har problem med att dina watchlists inte sparas, kan du prova att:
            1. Kontrollera att din webbläsare inte blockerar cookies/localStorage
            2. Aktivera felsökningsläget i inställningarna
            3. Använda exportfunktionen för att manuellt säkerhetskopiera dina watchlists
            """)

    # Show information about the strategy
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
