import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import streamlit as st
import time
import json
import os


def create_results_table(results):
    """Create a table with batch analysis results"""
    import pandas as pd
    import numpy as np

    # Return empty DataFrame if no results
    if not results:
        print("No results provided to create_results_table")
        return pd.DataFrame()

    # Filter out errors and extract relevant fields
    valid_results = []

    for r in results:
        # Skip non-dictionary results or results with errors
        if not isinstance(r, dict) or "error" in r:
            continue

        # Make sure all required keys exist
        if "ticker" not in r:
            print(f"Warning: Result missing 'ticker' field: {r}")
            continue

        try:
            # Create a row with default values for all fields
            row = {
                "Ticker": r.get("ticker", ""),
                "Namn": r.get("name", r.get("ticker", "")),
                "Pris": float(r.get("price", 0)),
                "Signal": r.get("signal", "HÅLL"),
                "Tech Score": int(r.get("tech_score", 0)),
                "Över MA40": "Ja" if r.get("above_ma40", False) else "Nej",
                "Över MA4": "Ja" if r.get("above_ma4", False) else "Nej",
                "RSI > 50": "Ja" if r.get("rsi_above_50", False) else "Nej",
                "Högre bottnar": "Ja" if r.get("higher_lows", False) else "Nej",
                "52v Högsta": "Ja" if r.get("near_52w_high", False) else "Nej",
                "Breakout": "Ja" if r.get("breakout", False) else "Nej",
                "P/E": "N/A",
                "Lönsam": "Ja" if r.get("is_profitable", False) else "Nej"
            }

            # Special handling for P/E ratio with null check
            pe_ratio = r.get("pe_ratio")
            if pe_ratio is not None and pd.notna(pe_ratio):
                try:
                    row["P/E"] = f"{float(pe_ratio):.1f}"
                except (ValueError, TypeError):
                    row["P/E"] = "N/A"

            valid_results.append(row)
        except Exception as e:
            print(
                f"Error creating row for {r.get('ticker', 'unknown')}: {str(e)}")
            continue

    # If no valid results, return empty DataFrame
    if not valid_results:
        print("No valid results after filtering in create_results_table")
        return pd.DataFrame()

    # Create DataFrame from valid results
    df = pd.DataFrame(valid_results)

    # Convert Tech Score to numeric for sorting
    try:
        df["Tech Score"] = pd.to_numeric(
            df["Tech Score"], errors="coerce").fillna(0).astype(int)
    except Exception as e:
        print(f"Error converting Tech Score to numeric: {str(e)}")

    print(f"Created results table with {len(df)} rows")
    return df


def render_analysis_results(strategy):
    """Render the analysis results section"""
    st.subheader("Analysresultat")

    # Check if we have analysis results
    if 'analysis_results' not in st.session_state or not st.session_state.analysis_results:
        st.info("Klicka på 'Analysera alla' för att se resultat")
        return

    # Convert the analysis results to a DataFrame
    try:
        results_df = create_results_table(st.session_state.analysis_results)
    except Exception as e:
        st.error(f"Fel vid skapande av resultattabell: {str(e)}")
        st.session_state.analysis_results = []
        return

    # Check if we have valid results to display
    if results_df.empty:
        # If all results contain errors
        st.warning(
            "Alla aktieanalyser misslyckades. Kontrollera dina aktiesymboler.")

        # Display failed analyses
        if 'failed_analyses' in st.session_state and st.session_state.failed_analyses:
            with st.expander("Visa feldetaljer"):
                for fail in st.session_state.failed_analyses:
                    st.error(
                        f"**{fail.get('ticker', 'Okänd')}**: {fail.get('error_message', fail.get('error', 'Okänt fel'))}")
        return

    # Filter options
    st.subheader("Filtrera resultat")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        signal_options = results_df["Signal"].unique().tolist()
        signal_filter = st.multiselect(
            "Signal",
            signal_options,
            default=signal_options
        )

    with col_b:
        ma40_filter = st.checkbox(
            "Bara aktier över MA40", value=False)

    with col_c:
        max_score = int(results_df["Tech Score"].max()
                        ) if not results_df.empty else 100
        tech_score_min = st.slider("Min Tech Score", 0, max_score, 0)

    # Apply filters
    filtered_df = results_df.copy()

    if signal_filter:
        filtered_df = filtered_df[filtered_df["Signal"].isin(signal_filter)]

    if ma40_filter:
        filtered_df = filtered_df[filtered_df["Över MA40"] == "Ja"]

    filtered_df = filtered_df[filtered_df["Tech Score"] >= tech_score_min]

    # Display filtered table
    if filtered_df.empty:
        st.info("Inga aktier matchar valda filter")
    else:
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

        # Option to select stock for detailed analysis
        if not filtered_df.empty:
            st.subheader("Välj aktie för detaljerad analys")
            selected_ticker = st.selectbox(
                "Aktie",
                filtered_df["Ticker"].tolist()
            )

            if selected_ticker:
                # Find analysis for selected stock
                selected_analysis = None
                for r in st.session_state.analysis_results:
                    if isinstance(r, dict) and r.get("ticker") == selected_ticker and "error" not in r:
                        selected_analysis = r
                        break

                if selected_analysis:
                    # Display chart
                    st.subheader(
                        f"{selected_analysis.get('name', selected_ticker)} ({selected_analysis.get('ticker', '')})")
                    try:
                        fig = strategy.plot_analysis(selected_analysis)
                        if fig:
                            st.pyplot(fig)
                    except Exception as e:
                        st.error(f"Kunde inte skapa diagram: {str(e)}")

                    # Display details in expandable field
                    with st.expander("Visa detaljer"):
                        col_x, col_y = st.columns(2)

                        with col_x:
                            st.subheader("Fundamentala Data")
                            st.write(
                                f"Lönsamt bolag: {'Ja' if selected_analysis.get('is_profitable', False) else 'Nej'}")
                            st.write(
                                f"P/E-tal: {selected_analysis.get('pe_ratio', 0):.2f}" if selected_analysis.get('pe_ratio') and pd.notna(selected_analysis.get('pe_ratio')) else "P/E-tal: Data saknas")
                            st.write(
                                f"Omsättningstillväxt: {selected_analysis.get('revenue_growth', 0)*100:.1f}%" if selected_analysis.get('revenue_growth') and pd.notna(selected_analysis.get('revenue_growth')) else "Omsättningstillväxt: Data saknas")
                            st.write(
                                f"Vinstmarginal: {selected_analysis.get('profit_margin', 0)*100:.1f}%" if selected_analysis.get('profit_margin') and pd.notna(selected_analysis.get('profit_margin')) else "Vinstmarginal: Data saknas")
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
                    st.warning(
                        f"Kunde inte hitta analys för {selected_ticker}")


# Funktion för att hjälpa till med förslag på aktier för watchlist
def get_index_constituents(index_name):
    """Få aktier som ingår i ett index"""
    indices = {
        "OMXS30": [
            "ALIV-SDB.ST", "ASSA-B.ST", "ATCO-A.ST", "ATCO-B.ST", "AXFO.ST",
            "BOL.ST", "ELUX-B.ST", "ERIC-B.ST", "ESSITY-B.ST", "EVO.ST",
            "GETI-B.ST", "HEXA-B.ST", "HM-B.ST", "INVE-B.ST", "KINV-B.ST",
            "NDA-SE.ST", "SAND.ST", "SCA-B.ST", "SEB-A.ST", "SHB-A.ST",
            "SINCH.ST", "SKA-B.ST", "SKF-B.ST", "SWED-A.ST", "SWMA.ST",
            "TEL2-B.ST", "TELIA.ST", "VOLV-B.ST"
        ],
        "S&P 500 Top 30": [
            "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "NVDA", "BRK-B",
            "TSLA", "UNH", "JPM", "V", "JNJ", "PG", "XOM", "MA", "HD", "BAC",
            "AVGO", "LLY", "CVX", "ADBE", "MRK", "ABBV", "KO", "PEP", "COST",
            "TMO", "MCD", "ACN"
        ],
        "Dow Jones": [
            "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW",
            "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
            "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WBA", "WMT"
        ]
    }

    return indices.get(index_name, [])
