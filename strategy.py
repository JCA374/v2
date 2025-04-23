import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import streamlit as st
import time
import json
import os

from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt


class ValueMomentumStrategy:
    def __init__(self):
        self.today = datetime.now()
        # 3 years of data for analysis
        self.start_date = self.today - timedelta(days=365*3)

    def get_stock_data(self, ticker, interval='1wk'):
        """Hämta aktiedata från Yahoo Finance"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=self.start_date,
                                 end=self.today, interval=interval)

            # Kontrollera om vi fått tillräckligt med data
            if len(hist) < 50:
                return None, "Otillräcklig data för analys"

            return stock, hist
        except Exception as e:
            return None, f"Fel vid hämtning av data: {e}"

    def get_fundamentals(self, stock):
        """Hämta fundamentala data för aktien"""
        try:
            # Hämta finansiell information
            info = stock.info

            # Beräkna relevanta nyckeltal
            fundamental_data = {
                "ticker": info.get('symbol', 'N/A'),
                "name": info.get('shortName', 'N/A'),
                "sector": info.get('sector', 'N/A'),
                "profitable": info.get('netIncomeToCommon', 0) > 0,
                "pe_ratio": info.get('trailingPE', None),
                "revenue_growth": info.get('revenueGrowth', None),
                "profit_margin": info.get('profitMargins', None),
                "earnings_growth": info.get('earningsGrowth', None)
            }

            # Hämta historiska kvartalssiffror för omsättning och vinst
            try:
                earnings = stock.earnings_history
                if not earnings.empty:
                    # Beräkna tillväxt och vinstmarginal trender
                    fundamental_data['earnings_trend'] = 'Stabil eller ökande' if earnings['Earnings'].diff(
                    ).mean() >= 0 else 'Minskande'
            except:
                fundamental_data['earnings_trend'] = 'Data saknas'

            return fundamental_data
        except Exception as e:
            return {"error": f"Kunde inte hämta fundamentala data: {e}"}

    # Egen implementation av RSI utan pandas_ta
    def calculate_rsi(self, prices, window=14):
        # Hantera edge case med för lite data
        if len(prices) <= window:
            return np.array([np.nan] * len(prices))

        # Beräkna förändringar
        deltas = np.diff(prices)
        seed = deltas[:window+1]

        # Initiala värden
        up = seed[seed >= 0].sum() / window
        down = -seed[seed < 0].sum() / window

        # Undvik division med noll
        if down == 0:
            return np.ones_like(prices) * 100

        rs = up / down
        rsi = np.zeros_like(prices)
        rsi[:window+1] = 100. - (100. / (1. + rs))

        # Beräkna RSI för resten av prisdata
        for i in range(window+1, len(prices)):
            delta = deltas[i-1]  # Justera index

            if delta > 0:
                upval = delta
                downval = 0
            else:
                upval = 0
                downval = -delta

            # Använd EMA för beräkning av medelvärden
            up = (up * (window - 1) + upval) / window
            down = (down * (window - 1) + downval) / window

            rs = up / down if down != 0 else 999  # Undvik division med noll
            rsi[i] = 100. - (100. / (1. + rs))

        return rsi

    def calculate_technical_indicators(self, df):
        """Beräkna tekniska indikatorer för aktien"""
        # Kopiera dataframe för att undvika varningar
        data = df.copy()

        # Kontrollera för tomma dataframes
        if data.empty:
            return data

        # Lägg till moving averages
        # 4-veckors MA (motsvarar ca 1 månad)
        data['MA4'] = data['Close'].rolling(window=4).mean()
        # 40-veckors MA (motsvarar ca 200 dagar)
        data['MA40'] = data['Close'].rolling(window=40).mean()

        # Beräkna RSI med egen funktion
        data['RSI'] = self.calculate_rsi(data['Close'].values, window=14)

        # Beräkna högre bottnar (higher lows)
        data['higher_lows'] = self._calculate_higher_lows(data)

        # 52-veckors högsta nivå
        data['52w_high'] = data['Close'].rolling(window=52).max()
        # Inom 2% av högsta nivån
        data['at_52w_high'] = (data['Close'] >= data['52w_high'] * 0.98)

        # Konsolideringsfas breakout (enkel implementering)
        data['volatility'] = data['Close'].pct_change().rolling(window=12).std()
        data['breakout'] = (data['volatility'].shift(4) < data['volatility']) & (
            data['Close'] > data['Close'].shift(4))

        return data

    def _calculate_higher_lows(self, data, lookback=10):
        """Hjälpfunktion för att identifiera högre bottnar"""
        if 'Low' not in data.columns or data.empty:
            return pd.Series(np.zeros(len(data)))

        highs_lows = pd.DataFrame()
        highs_lows['min'] = data['Low'].rolling(
            window=lookback, center=True).min()

        # En enkel heuristik för att identifiera högre bottnar
        higher_lows = np.zeros(len(data))

        for i in range(lookback*2, len(data)):
            min_values = highs_lows['min'].iloc[i-lookback:i].dropna()
            if len(min_values) >= 2:  # Säkerställ att vi har tillräckligt med data
                diffs = min_values.diff().dropna()
                if len(diffs) > 0 and (diffs > 0).all():
                    higher_lows[i] = 1

        return pd.Series(higher_lows, index=data.index)

    def analyze_stock(self, ticker):
        """Analysera en aktie enligt värde & momentum-strategin"""
        stock, hist_or_error = self.get_stock_data(ticker)

        if stock is None:
            return {"ticker": ticker, "error": hist_or_error}

        # Hämta fundamentala data
        fundamentals = self.get_fundamentals(stock)

        # Beräkna tekniska indikatorer
        technical = self.calculate_technical_indicators(hist_or_error)

        # Skapa analys baserat på senaste data
        try:
            latest = technical.iloc[-1]

            analysis = {
                "ticker": ticker,
                "name": fundamentals.get('name', ticker),
                "date": latest.name.strftime('%Y-%m-%d'),
                "price": latest['Close'],

                # Fundamentala villkor
                "is_profitable": fundamentals.get('profitable', False),
                "pe_ratio": fundamentals.get('pe_ratio', None),
                "revenue_growth": fundamentals.get('revenue_growth', None),
                "profit_margin": fundamentals.get('profit_margin', None),
                "earnings_trend": fundamentals.get('earnings_trend', 'N/A'),
                "fundamental_check": self._evaluate_fundamentals(fundamentals),

                # Tekniska villkor
                "above_ma40": latest['Close'] > latest['MA40'] if not np.isnan(latest['MA40']) else False,
                "above_ma4": latest['Close'] > latest['MA4'] if not np.isnan(latest['MA4']) else False,
                "rsi_above_50": latest['RSI'] > 50 if not np.isnan(latest['RSI']) else False,
                "higher_lows": bool(latest['higher_lows']),
                "near_52w_high": bool(latest['at_52w_high']),
                "breakout": bool(latest['breakout']),
                "technical_check": self._evaluate_technicals(latest),

                # Historisk data för diagram
                "history": technical.tail(52),

                # Scoring - ett sammanfattande värde 0-100
                "tech_score": self._calculate_tech_score(latest)
            }

            # Sammanfattande bedömning
            analysis["buy_signal"] = analysis["fundamental_check"] and analysis["technical_check"]
            analysis["sell_signal"] = not analysis["above_ma40"]
            analysis["hold_signal"] = not analysis["sell_signal"] and not analysis["buy_signal"]

            # Signal text
            if analysis["buy_signal"]:
                analysis["signal"] = "KÖP"
            elif analysis["sell_signal"]:
                analysis["signal"] = "SÄLJ"
            else:
                analysis["signal"] = "HÅLL"

            return analysis

        except Exception as e:
            return {"ticker": ticker, "error": f"Fel vid analys: {e}"}

    def _calculate_tech_score(self, latest_data):
        """Beräkna ett tekniskt score 0-100 för aktien"""
        score = 0

        # Grund-villkor
        if latest_data['Close'] > latest_data['MA40'] if not np.isnan(latest_data['MA40']) else False:
            score += 30

        if latest_data['RSI'] > 50 if not np.isnan(latest_data['RSI']) else False:
            score += 20

        if bool(latest_data['higher_lows']):
            score += 20

        # Extra poäng
        if latest_data['Close'] > latest_data['MA4'] if not np.isnan(latest_data['MA4']) else False:
            score += 10

        if bool(latest_data['at_52w_high']):
            score += 10

        if bool(latest_data['breakout']):
            score += 10

        return score

    def _evaluate_fundamentals(self, fundamentals):
        """Utvärdera om aktien uppfyller fundamentala kriterier"""
        if "error" in fundamentals:
            return False

        conditions = [
            fundamentals.get('profitable', False),  # Bolaget ska tjäna pengar

            # Ökande omsättning och vinst, eller ökande omsättning med stabil vinstmarginal
            fundamentals.get('revenue_growth', 0) > 0 and
            (fundamentals.get('earnings_growth', 0) > 0 or
             fundamentals.get('profit_margin', 0) > 0.05),

            # Rimligt P/E
            fundamentals.get('pe_ratio', 100) is not None and
            fundamentals.get('pe_ratio', 100) < 30 and
            fundamentals.get('pe_ratio', 0) > 0
        ]

        # Filtrera bort None-värden
        valid_conditions = [c for c in conditions if c is not None]

        # Om alla villkor är None, returnera False
        if not valid_conditions:
            return False

        return all(valid_conditions)

    def _evaluate_technicals(self, latest_data):
        """Utvärdera om aktien uppfyller tekniska kriterier"""
        conditions = [
            latest_data['Close'] > latest_data['MA40'] if not np.isnan(
                latest_data['MA40']) else False,  # Över 40-veckors MA
            latest_data['RSI'] > 50 if not np.isnan(
                latest_data['RSI']) else False,  # RSI över 50
            bool(latest_data['higher_lows'])  # Högre bottnar
        ]

        # Extra styrka om någon av dessa uppfylls
        extra_strength = [
            bool(latest_data['at_52w_high']),  # Nära 52v högsta
            bool(latest_data['breakout']),  # Breakout
            latest_data['Close'] > latest_data['MA4'] if not np.isnan(
                latest_data['MA4']) else False  # Över 4-veckors MA
        ]

        return all(conditions) and any(extra_strength)

    def batch_analyze(self, ticker_list, progress_callback=None):
        """Analysera en batch av aktier och returnera resultaten"""
        results = []

        total = len(ticker_list)
        for i, ticker in enumerate(ticker_list):
            # Uppdatera progress bar om callback finns
            if progress_callback:
                progress_callback(
                    i / total, f"Analyserar {ticker} ({i+1}/{total})")

            analysis = self.analyze_stock(ticker)
            results.append(analysis)

        return results

    def plot_analysis(self, analysis):
        """Skapa diagram för analys"""
        if "error" in analysis:
            return None

        hist = analysis["history"]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
        plt.style.use('ggplot')

        # Prischart med MA
        ax1.plot(hist.index, hist['Close'], label='Pris', linewidth=2)
        ax1.plot(hist.index, hist['MA4'], label='MA4 (4v)', linestyle='--')
        ax1.plot(hist.index, hist['MA40'], label='MA40 (40v)', linestyle=':')

        if analysis["buy_signal"]:
            ax1.scatter(hist.index[-1], hist['Close'].iloc[-1], color='green', marker='^', s=150, label='KÖP')
        elif analysis["sell_signal"]:
            ax1.scatter(hist.index[-1], hist['Close'].iloc[-1], color='red', marker='v', s=150, label='SÄLJ')

        ax1.set_title(f"{analysis['name']} ({analysis['ticker']}) - Pris & Signal", fontsize=14)
        ax1.set_ylabel("Pris")
        ax1.legend()
        ax1.grid(True, linestyle='--', alpha=0.5)

        # RSI chart
        ax2.plot(hist.index, hist['RSI'], label='RSI', color='purple', linewidth=1.5)
        ax2.axhline(y=70, color='red', linestyle='--', alpha=0.5)
        ax2.axhline(y=30, color='green', linestyle='--', alpha=0.5)
        ax2.axhline(y=50, color='black', linestyle='-', alpha=0.3)
        ax2.set_ylim(0, 100)
        ax2.set_ylabel("RSI")
        ax2.set_title("Relative Strength Index (RSI)")
        ax2.legend()
        ax2.grid(True, linestyle='--', alpha=0.5)

        fig.tight_layout()
        return fig


class WatchlistManager:
    def __init__(self, filename="watchlist.json"):
        self.filename = filename
        self.watchlist = self.load_watchlist()

    def load_watchlist(self):
        """Ladda watchlist från fil"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_watchlist(self):
        """Spara watchlist till fil"""
        with open(self.filename, 'w') as f:
            json.dump(self.watchlist, f)

    def add_stock(self, ticker):
        """Lägg till en aktie till watchlist"""
        if ticker and ticker not in self.watchlist:
            self.watchlist.append(ticker)
            self.save_watchlist()
            return True
        return False

    def remove_stock(self, ticker):
        """Ta bort en aktie från watchlist"""
        if ticker in self.watchlist:
            self.watchlist.remove(ticker)
            self.save_watchlist()
            return True
        return False

    def get_watchlist(self):
        """Hämta alla aktier i watchlist"""
        return self.watchlist

# Funktion för att skapa resultat-tabell


def create_results_table(results):
    """Skapa en tabell med resultat från batch-analys"""
    if not results:
        return pd.DataFrame()

    # Filtrera bort fel och plocka ut relevanta fält
    valid_results = []
    for r in results:
        if "error" not in r:
            valid_results.append({
                "Ticker": r["ticker"],
                "Namn": r["name"],
                "Pris": r["price"],
                "Signal": r["signal"],
                "Tech Score": r["tech_score"],
                "Över MA40": "Ja" if r["above_ma40"] else "Nej",
                "Över MA4": "Ja" if r["above_ma4"] else "Nej",
                "RSI > 50": "Ja" if r["rsi_above_50"] else "Nej",
                "Högre bottnar": "Ja" if r["higher_lows"] else "Nej",
                "52v Högsta": "Ja" if r["near_52w_high"] else "Nej",
                "Breakout": "Ja" if r["breakout"] else "Nej",
                "P/E": f"{r['pe_ratio']:.1f}" if r["pe_ratio"] else "N/A",
                "Lönsam": "Ja" if r["is_profitable"] else "Nej"
            })

    if not valid_results:
        return pd.DataFrame()

    return pd.DataFrame(valid_results)

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

# Streamlit app funktioner


def create_streamlit_app():
    st.set_page_config(
        page_title="Värde & Momentum Aktiestrategi",
        page_icon="📈",
        layout="wide"
    )

    st.title("Värde & Momentum Aktiestrategi")

    # Initiera strategiklassen och watchlist manager
    strategy = ValueMomentumStrategy()
    watchlist_manager = WatchlistManager()

    # Skapa sessionsvariabel för analysresultat om den inte finns
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = []

    # Skapa UI-sektioner
    tab1, tab2 = st.tabs(["Watchlist & Batch Analysis", "Enskild Aktieanalys"])

    # Tab 1 - Watchlist & Batch analysis
    with tab1:
        col1, col2 = st.columns([1, 3])

        with col1:
            st.subheader("Min Watchlist")

            # Visa watchlist
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
            st.subheader("Hantera Watchlist")
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

        with col2:
            st.subheader("Analysresultat")

            # Visa resultaten i en tabell om de finns
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

                # Applicera filter
                filtered_df = results_df.copy()

                if signal_filter:
                    filtered_df = filtered_df[filtered_df["Signal"].isin(
                        signal_filter)]

                if ma40_filter:
                    filtered_df = filtered_df[filtered_df["Över MA40"] == "Ja"]

                filtered_df = filtered_df[filtered_df["Tech Score"]
                                          >= tech_score_min]

                # Visa filtrerad tabell
                if not filtered_df.empty:
                    # Sortera efter Tech Score och Signal
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
                            )
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Inga aktier matchar valda filter")

                # Möjlighet att välja en aktie för djupare analys
                if not filtered_df.empty:
                    st.subheader("Välj aktie för detaljerad analys")
                    selected_ticker = st.selectbox(
                        "Aktie",
                        filtered_df["Ticker"].tolist()
                    )

                    if selected_ticker:
                        # Hitta analys för vald aktie
                        selected_analysis = next(
                            (r for r in st.session_state.analysis_results if r["ticker"] == selected_ticker),
                            None
                        )

                        if selected_analysis and "error" not in selected_analysis:
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

    # Tab 2 - Enskild aktieanalys
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
                    # Visa sammanfattning
                    signal_color = "green" if analysis["buy_signal"] else "red" if analysis["sell_signal"] else "orange"
                    signal_text = "KÖP" if analysis["buy_signal"] else "SÄLJ" if analysis["sell_signal"] else "HÅLL"

                    st.header(f"{analysis['name']} ({analysis['ticker']})")
                    st.subheader(f"Pris: {analysis['price']:.2f} SEK")

                    st.markdown(
                        f"<h3 style='color:{signal_color}'>Signal: {signal_text}</h3>", unsafe_allow_html=True)

                    # Lägg till i watchlist-knapp
                    if analysis["ticker"] not in watchlist_manager.get_watchlist():
                        if st.button("Lägg till i watchlist"):
                            watchlist_manager.add_stock(analysis["ticker"])
                            st.success(
                                f"Lade till {analysis['ticker']} i watchlist")

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

    # Visa information om strategin
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