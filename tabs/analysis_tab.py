# tabs/analysis_tab.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


def render_analysis_tab():
    """Render the individual stock analysis tab"""
    # Access shared objects from session state
    strategy = st.session_state.strategy
    watchlist_manager = st.session_state.watchlist_manager

    # Check if we should analyze a ticker (triggered from sidebar)
    if 'analyze_ticker' in st.session_state:
        ticker = st.session_state.analyze_ticker
        # Clear the trigger so it doesn't re-analyze on every rerun
        del st.session_state.analyze_ticker

        # Run the analysis
        with st.spinner(f"Analyserar {ticker}..."):
            analyze_and_display_stock(ticker, strategy, watchlist_manager)
    else:
        # No analysis in progress, show instructions
        st.info("Använd sidofältet till vänster för att analysera en aktie.")

        # Option to select from watchlist
        st.subheader("Eller välj en aktie från din watchlist")

        # Get all stocks from all watchlists
        all_watchlists = watchlist_manager.get_all_watchlists()
        all_stocks = []

        for watchlist in all_watchlists:
            all_stocks.extend([(ticker, watchlist["name"])
                              for ticker in watchlist["stocks"]])

        if all_stocks:
            # Format selection options
            options = [f"{ticker} ({wl_name})" for ticker,
                       wl_name in all_stocks]
            tickers = [ticker for ticker, _ in all_stocks]

            selected_option = st.selectbox(
                "Välj aktie",
                options=[""] + options
            )

            if selected_option:
                # Extract ticker from the selected option
                selected_index = options.index(selected_option)
                selected_ticker = tickers[selected_index]

                if st.button("Analysera vald aktie"):
                    with st.spinner(f"Analyserar {selected_ticker}..."):
                        analyze_and_display_stock(
                            selected_ticker, strategy, watchlist_manager)
        else:
            st.warning(
                "Din watchlist är tom. Lägg till aktier för att kunna välja från listan.")


def analyze_and_display_stock(ticker, strategy, watchlist_manager):
    """Analyze a stock and display the results"""
    analysis = strategy.analyze_stock(ticker)

    if "error" in analysis:
        st.error(f"Fel: {analysis['error']}")
        return

    # Display analysis results
    render_analysis_results(analysis, strategy, watchlist_manager)


def render_analysis_results(analysis, strategy, watchlist_manager):
    """Render the analysis results for a single stock"""
    # Visa sammanfattning
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

    # Check if the stock already exists in the selected watchlist
    selected_watchlist = all_watchlists[target_watchlist]
    already_in_watchlist = analysis["ticker"] in selected_watchlist["stocks"]

    if already_in_watchlist:
        st.info(
            f"{analysis['ticker']} finns redan i {selected_watchlist['name']}")
    else:
        if st.button("Lägg till i watchlist"):
            if watchlist_manager.add_stock_to_watchlist(target_watchlist, analysis["ticker"]):
                st.success(
                    f"Lade till {analysis['ticker']} i {watchlist_names[target_watchlist]}")
            else:
                st.error("Kunde inte lägga till aktien")

    # Skapa flikar för detaljer
    tab2_1, tab2_2, tab2_3 = st.tabs(
        ["Översikt", "Fundamenta", "Teknisk Analys"])

    with tab2_1:
        # Visa diagram
        fig = strategy.plot_analysis(analysis)
        if fig:
            st.pyplot(fig)

        # Visa kort sammanfattning
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

    # Add option to compare with another stock (enhancement example)
    with st.expander("Jämför med en annan aktie"):
        compare_ticker = st.text_input(
            "Jämför med (t.ex. MSFT, AAPL)", key="compare_input")
        if st.button("Jämför", key="compare_button"):
            if compare_ticker:
                st.session_state['compare_tickers'] = [
                    analysis["ticker"], compare_ticker]
                # This could trigger a comparison feature in a future tab
                st.info(
                    f"Jämförelse mellan {analysis['ticker']} och {compare_ticker} är inte implementerad ännu.")
            else:
                st.warning("Ange en ticker att jämföra med")
