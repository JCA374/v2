# tabs/watchlist_tab.py
import streamlit as st
import pandas as pd
from helpers import create_results_table, get_index_constituents


def render_watchlist_tab():
    """Render the watchlist and batch analysis tab"""
    # Access shared objects from session state
    strategy = st.session_state.strategy
    watchlist_manager = st.session_state.watchlist_manager

    # Handle stocks selected from Scanner tab
    if 'analyze_selected' in st.session_state and st.session_state.analyze_selected:
        if 'batch_analysis_tickers' in st.session_state and st.session_state.batch_analysis_tickers:
            selected_tickers = st.session_state.batch_analysis_tickers

            # Show analysis in progress
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Callback for progress
            def update_progress(progress, text):
                progress_bar.progress(progress)
                status_text.text(text)

            # Run batch analysis
            results = strategy.batch_analyze(selected_tickers, update_progress)
            st.session_state.analysis_results = results

            # Remove progress bar when done
            progress_bar.empty()
            status_text.empty()

            st.success(f"Analyzed {len(selected_tickers)} stocks from Scanner")

            # Clear the flags so it doesn't re-analyze on every rerun
            st.session_state.analyze_selected = False

    # Create the layout
    col1, col2 = st.columns([1, 3])

    with col1:
        render_watchlist_management(watchlist_manager, strategy)

    with col2:
        # Add debug toggle button
        show_debug = st.checkbox("Visa debug information", value=False)

        if show_debug and 'analysis_results' in st.session_state:
            # Show debug information if the checkbox is checked
            debug_analysis_results()
        else:
            # Normal display
            render_analysis_results(strategy)


def render_watchlist_management(watchlist_manager, strategy):
    """Render the watchlist management section"""
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
        new_name = st.text_input("Nytt namn", value=active_watchlist["name"])
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
                st.markdown("Kopiera denna länk för att dela din watchlist:")
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
            import json
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
                                st.success("Watchlist importerad från länk!")
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
                            st.success("Watchlist importerad från JSON!")
                            st.rerun()
                        else:
                            st.error(
                                "Kunde inte importera watchlist från JSON")
                    else:
                        st.error("Ingen JSON data angiven")
                except Exception as e:
                    st.error(f"Fel vid import: {str(e)}")

    # Display current watchlist contents
    st.subheader(
        f"Aktier i {watchlist_manager.get_active_watchlist()['name']}")

    # Get watchlist
    watchlist = watchlist_manager.get_watchlist()

    # Visa vald indexlista för snabb-tillägg
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
        for ticker in selected_index_stocks:
            watchlist_manager.add_stock(ticker)
        st.success(
            f"Lade till {len(selected_index_stocks)} aktier till watchlist")
        # Uppdatera watchlist
        watchlist = watchlist_manager.get_watchlist()

    # Manuellt lägga till aktie
    st.subheader("Lägg till manuellt")
    new_ticker = st.text_input("Ticker (t.ex. AAPL, ERIC-B.ST)")

    col1_1, col1_2 = st.columns(2)
    with col1_1:
        if st.button("Lägg till"):
            if watchlist_manager.add_stock(new_ticker):
                st.success(f"Lade till {new_ticker}")
                # Uppdatera watchlist
                watchlist = watchlist_manager.get_watchlist()
            else:
                st.error("Kunde inte lägga till aktien")

    # Lista alla aktier i watchlist med remove-knappar
    st.subheader("Hantera Aktier")
    for ticker in watchlist:
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.write(ticker)
        with col_b:
            if st.button("Ta bort", key=f"remove_{ticker}"):
                watchlist_manager.remove_stock(ticker)
                st.success(f"Tog bort {ticker}")
                # Uppdatera sidan för att visa ändringen
                st.rerun()

    # Knapp för att köra batch-analys på hela watchlist
    if watchlist:
        if st.button("Analysera alla", key="analyze_all"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Callback för progress
            def update_progress(progress, text):
                progress_bar.progress(progress)
                status_text.text(text)

            # Kör batch-analys
            results = strategy.batch_analyze(
                watchlist, update_progress)
            st.session_state.analysis_results = results

            # Ta bort progress när klar
            progress_bar.empty()
            status_text.empty()

            st.success("Analys klar!")
    else:
        st.info(
            "Lägg till aktier i din watchlist för att kunna analysera dem")

    # Display failed analyses if any exist
    if 'failed_analyses' in st.session_state and st.session_state.failed_analyses:
        num_failed = len(st.session_state.failed_analyses)
        num_total = len(watchlist)
        num_success = num_total - num_failed

        # Create an expander to show failed analyses
        with st.expander(f"Aktier som inte kunde analyseras ({num_failed} av {num_total})"):
            for fail in st.session_state.failed_analyses:
                st.warning(f"**{fail['ticker']}**: {fail['error_message']}")

            # Show a summary
            if num_success > 0:
                st.info(
                    f"{num_success} av {num_total} aktier analyserades framgångsrikt.")
            else:
                st.error("Inga aktier kunde analyseras framgångsrikt.")

            # Option to clear the failed analyses
            if st.button("Rensa lista", key="clear_failed"):
                st.session_state.failed_analyses = []
                st.rerun()


def render_analysis_results(strategy):
    """Render the analysis results section"""
    st.subheader("Analysresultat")

    # Visa resultaten i en tabell om de finns
    if st.session_state.analysis_results:
        # Check if we have valid results to display
        valid_results = [
            r for r in st.session_state.analysis_results if "error" not in r]

        if valid_results:
            results_df = create_results_table(
                st.session_state.analysis_results)

            # Only proceed with filtering if we have a valid DataFrame with results
            if not results_df.empty and "Signal" in results_df.columns:
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

                # Applicera filter
                filtered_df = results_df.copy()

                if signal_filter:
                    filtered_df = filtered_df[filtered_df["Signal"].isin(
                        signal_filter)]

                if ma40_filter and "Över MA40" in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df["Över MA40"] == "Ja"]

                if "Tech Score" in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df["Tech Score"]
                                              >= tech_score_min]

                # Visa filtrerad tabell
                if not filtered_df.empty:
                    # Sortera efter Tech Score och Signal
                    if "Tech Score" in filtered_df.columns and "Signal" in filtered_df.columns:
                        filtered_df = filtered_df.sort_values(
                            by=["Tech Score", "Signal"], ascending=[False, True])

                    # Formatera tabellen
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
                            ) if "Tech Score" in filtered_df.columns else None
                        },
                        use_container_width=True,
                        hide_index=True
                    )

                    # Möjlighet att välja en aktie för djupare analys
                    st.subheader("Välj aktie för detaljerad analys")
                    selected_ticker = st.selectbox(
                        "Aktie",
                        filtered_df["Ticker"].tolist(
                        ) if "Ticker" in filtered_df.columns else []
                    )

                    if selected_ticker:
                        # Hitta analys för vald aktie
                        selected_analysis = next(
                            (r for r in st.session_state.analysis_results if r.get(
                                "ticker") == selected_ticker and "error" not in r),
                            None
                        )

                        if selected_analysis:
                            # Visa diagram
                            st.subheader(
                                f"{selected_analysis['name']} ({selected_analysis['ticker']})")
                            fig = strategy.plot_analysis(selected_analysis)
                            if fig:
                                st.pyplot(fig)

                            # Visa detaljer i expanderbart fält
                            with st.expander("Visa detaljer"):
                                col_x, col_y = st.columns(2)

                                with col_x:
                                    st.subheader("Fundamentala Data")
                                    st.write(
                                        f"Lönsamt bolag: {'Ja' if selected_analysis.get('is_profitable', False) else 'Nej'}")
                                    st.write(
                                        f"P/E-tal: {selected_analysis.get('pe_ratio', 0):.2f}" if selected_analysis.get('pe_ratio') else "P/E-tal: Data saknas")
                                    st.write(
                                        f"Omsättningstillväxt: {selected_analysis.get('revenue_growth', 0)*100:.1f}%" if selected_analysis.get('revenue_growth') else "Omsättningstillväxt: Data saknas")
                                    st.write(
                                        f"Vinstmarginal: {selected_analysis.get('profit_margin', 0)*100:.1f}%" if selected_analysis.get('profit_margin') else "Vinstmarginal: Data saknas")
                                    st.write(
                                        f"Vinstutveckling: {selected_analysis.get('earnings_trend', 'Okänd')}")

                                with col_y:
                                    st.subheader("Tekniska Indikatorer")
                                    st.write(
                                        f"Pris över MA40 (40-veckor): {'Ja' if selected_analysis.get('above_ma40', False) else 'Nej'}")
                                    st.write(
                                        f"Pris över MA4 (4-veckor): {'Ja' if selected_analysis.get('above_ma4', False) else 'Nej'}")
                                    st.write(
                                        f"RSI över 50: {'Ja' if selected_analysis.get('rsi_above_50', False) else 'Nej'}")
                                    st.write(
                                        f"Högre bottnar: {'Ja' if selected_analysis.get('higher_lows', False) else 'Nej'}")
                                    st.write(
                                        f"Nära 52-veckors högsta: {'Ja' if selected_analysis.get('near_52w_high', False) else 'Nej'}")
                                    st.write(
                                        f"Breakout från konsolidering: {'Ja' if selected_analysis.get('breakout', False) else 'Nej'}")
                else:
                    st.info("Inga aktier matchar valda filter")
            else:
                # If we don't have valid results to create a table
                st.warning(
                    "Ingen giltig data att visa. Antingen finns inga aktier att analysera eller så misslyckades alla analyser.")

                # List stocks that failed analysis
                if st.session_state.failed_analyses:
                    with st.expander("Aktier som inte kunde analyseras"):
                        for fail in st.session_state.failed_analyses:
                            st.error(
                                f"**{fail['ticker']}**: {fail.get('error_message', 'Okänt fel')}")
        else:
            # If all results contain errors
            st.warning(
                "Alla aktieanalyser misslyckades. Kontrollera dina aktiesymboler.")

            # List stocks that failed analysis
            if st.session_state.failed_analyses:
                with st.expander("Visa feldetaljer"):
                    for fail in st.session_state.failed_analyses:
                        st.error(
                            f"**{fail['ticker']}**: {fail.get('error_message', 'Okänt fel')}")

    else:
        st.info("Klicka på 'Analysera alla' för att se resultat")


def debug_analysis_results():
    """Debug function to display raw analysis results"""
    import streamlit as st
    import pandas as pd

    st.write("## DEBUG INFORMATION")

    # Check if analysis_results exists in session state
    if 'analysis_results' not in st.session_state:
        st.error("No analysis_results in session_state!")
        return

    # Check if it has any data
    if not st.session_state.analysis_results:
        st.error("analysis_results is empty!")
        return

    # Display count and summary
    st.write(f"Total results: {len(st.session_state.analysis_results)}")

    # Count valid vs error results
    valid_count = 0
    error_count = 0

    for result in st.session_state.analysis_results:
        if isinstance(result, dict):
            if "error" in result:
                error_count += 1
            else:
                valid_count += 1

    st.write(f"Valid results: {valid_count}, Error results: {error_count}")

    # Display sample of valid results (if any)
    if valid_count > 0:
        st.write("## Sample of valid results:")
        for result in st.session_state.analysis_results:
            if isinstance(result, dict) and "error" not in result:
                st.json(result)
                break

    # Display sample of errors (if any)
    if error_count > 0:
        st.write("## Sample of error results:")
        for result in st.session_state.analysis_results:
            if isinstance(result, dict) and "error" in result:
                st.json(result)
                break

    # Try to create the results table directly
    from helpers import create_results_table

    try:
        results_df = create_results_table(st.session_state.analysis_results)
        st.write(f"Results DataFrame has {len(results_df)} rows")

        if not results_df.empty:
            st.write("Columns:", list(results_df.columns))
            st.dataframe(results_df)
        else:
            st.warning("create_results_table returned an empty DataFrame")
    except Exception as e:
        st.error(f"Error in create_results_table: {e}")
        import traceback
        st.code(traceback.format_exc())

