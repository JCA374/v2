import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import streamlit as st
import time
import json
import os
from datetime import datetime, timedelta
import logging

class ValueMomentumStrategy:
    """
    Implementation of the Value & Momentum stock analysis strategy.
    Combines fundamental analysis with technical indicators to identify strong stocks.
    """
    
    def __init__(self):
        """Initialize the strategy with default parameters"""
        # Technical parameters
        self.ma_short = 4  # 4-week moving average
        self.ma_long = 40  # 40-week moving average
        self.rsi_period = 14  # RSI calculation period
        self.rsi_threshold = 50  # RSI threshold for bullish signal
        self.near_high_threshold = 0.85  # % of 52-week high to consider "near"
        
        # Fundamental parameters
        self.pe_max = 35  # Maximum P/E ratio for value
        
        # Configure yfinance logging (reduce verbosity)
        logging.getLogger('yfinance').setLevel(logging.ERROR)
    
    def batch_analyze(self, tickers, progress_callback=None):
        """
        Analyze multiple stocks and return a list of analysis results.
        
        Parameters:
        - tickers: List of stock ticker symbols
        - progress_callback: Function to call with progress updates (0-1.0 and text)
        
        Returns:
        - List of analysis result dictionaries
        """
        results = []
        failed_analyses = []  # Track failures for reporting
        
        # Store failed analyses in session state if it doesn't exist
        import streamlit as st
        if 'failed_analyses' not in st.session_state:
            st.session_state.failed_analyses = []
        
        for i, ticker in enumerate(tickers):
            # Update progress
            if progress_callback:
                progress = i / len(tickers)
                progress_callback(progress, f"Analyserar {ticker}... ({i+1}/{len(tickers)})")
            
            try:
                # Analyze this stock
                analysis = self.analyze_stock(ticker)
                results.append(analysis)
            except Exception as e:
                # Add error information
                error_info = {
                    "ticker": ticker,
                    "error": str(e),
                    "error_message": f"Fel vid analys: {str(e)}"
                }
                results.append(error_info)
                failed_analyses.append(error_info)
                print(f"Error analyzing {ticker}: {str(e)}")
            
        # Update progress to 100%
        if progress_callback:
            progress_callback(1.0, "Analys klar!")
        
        # Store failed analyses in session state for display
        st.session_state.failed_analyses = failed_analyses
        
        return results
    
    def analyze_stock(self, ticker):
        """
        Analyze a single stock according to Value & Momentum strategy.
        
        Parameters:
        - ticker: Stock ticker symbol
        
        Returns:
        - Dictionary with analysis results
        """
        # Get stock data
        try:
            stock = yf.Ticker(ticker)
            
            # Get basic info
            info = stock.info
            
            # Handle missing name
            try:
                name = info.get('shortName', info.get('longName', ticker))
            except:
                name = ticker
            
            # Get historical data (weekly)
            hist = stock.history(period="1y", interval="1wk")
            
            if hist.empty:
                return {"ticker": ticker, "error": "No data available"}
            
            # Calculate current price
            price = hist['Close'].iloc[-1]
            
            # Calculate technical indicators
            tech_analysis = self._calculate_technical_indicators(hist)
            
            # Calculate fundamental indicators
            fund_analysis = self._calculate_fundamental_indicators(stock, info)
            
            # Calculate signal
            tech_score = self._calculate_tech_score(tech_analysis)
            fund_check = fund_analysis['fundamental_check']
            
            # Determine overall signal
            buy_signal = tech_score >= 70 and fund_check
            sell_signal = tech_score < 40 or not tech_analysis['above_ma40']
            
            # Create results dictionary
            result = {
                "ticker": ticker,
                "name": name,
                "price": price,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "tech_score": tech_score,
                "signal": "KÖP" if buy_signal else "SÄLJ" if sell_signal else "HÅLL",
                "buy_signal": buy_signal,
                "sell_signal": sell_signal,
                "fundamental_check": fund_check,
                "technical_check": tech_score >= 60,
                "historical_data": hist
            }
            
            # Combine technical and fundamental indicators into result
            result.update(tech_analysis)
            result.update(fund_analysis)
            
            return result
            
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}
    
    def _calculate_technical_indicators(self, hist):
        """Calculate technical indicators from historical price data"""
        # Make sure we have enough data
        if len(hist) < 40:
            # If we don't have enough data, fill with some default values
            return {
                "above_ma40": False,
                "above_ma4": False,
                "rsi_above_50": False,
                "higher_lows": False,
                "near_52w_high": False,
                "breakout": False
            }
        
        # Calculate moving averages
        hist['MA4'] = hist['Close'].rolling(window=self.ma_short).mean()
        hist['MA40'] = hist['Close'].rolling(window=self.ma_long).mean()
        
        # Get current price and MAs
        current_price = hist['Close'].iloc[-1]
        ma4 = hist['MA4'].iloc[-1]
        ma40 = hist['MA40'].iloc[-1]
        
        # Check if price is above moving averages
        above_ma4 = current_price > ma4 if pd.notna(ma4) else False
        above_ma40 = current_price > ma40 if pd.notna(ma40) else False
        
        # Calculate RSI
        delta = hist['Close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=self.rsi_period-1, adjust=False).mean()
        ema_down = down.ewm(com=self.rsi_period-1, adjust=False).mean()
        
        # Handle division by zero
        rs = pd.Series(np.zeros(len(ema_up)))
        non_zero_mask = (ema_down != 0)
        if non_zero_mask.any():
            rs[non_zero_mask] = ema_up[non_zero_mask] / ema_down[non_zero_mask]
        
        hist['RSI'] = 100 - (100 / (1 + rs))
        
        # Check if RSI is above threshold
        current_rsi = hist['RSI'].iloc[-1]
        rsi_above_50 = current_rsi > self.rsi_threshold if pd.notna(current_rsi) else False
        
        # Check for higher lows (in the last 12 weeks)
        try:
            # Look at the last 12 weeks and identify local minima
            last_weeks = hist.iloc[-13:-1] if len(hist) > 13 else hist.iloc[:-1]
            lows = []
            
            for i in range(1, len(last_weeks)-1):
                if (pd.notna(last_weeks['Low'].iloc[i]) and 
                    pd.notna(last_weeks['Low'].iloc[i-1]) and 
                    pd.notna(last_weeks['Low'].iloc[i+1]) and
                    last_weeks['Low'].iloc[i] < last_weeks['Low'].iloc[i-1] and 
                    last_weeks['Low'].iloc[i] < last_weeks['Low'].iloc[i+1]):
                    lows.append(last_weeks['Low'].iloc[i])
            
            # Check if we have at least 2 lows and they're increasing
            higher_lows = len(lows) >= 2 and all(
                lows[i] > lows[i-1] for i in range(1, len(lows)))
        except:
            higher_lows = False
        
        # Check if price is near 52-week high
        try:
            high_52w = hist['High'].max()
            near_52w_high = (current_price > high_52w * self.near_high_threshold) if pd.notna(high_52w) else False
        except:
            near_52w_high = False
        
        # Check for breakout from consolidation
        try:
            # Look for a period of consolidation (low volatility) followed by a price increase
            # Calculate weekly volatility
            hist['Weekly_Range'] = (hist['High'] - hist['Low']) / hist['Low']
            
            # Look at the last 6 weeks and the 6 weeks before that
            if len(hist) >= 12:  # Ensure we have enough data
                recent_volatility = hist['Weekly_Range'].iloc[-6:].mean()
                previous_volatility = hist['Weekly_Range'].iloc[-12:-6].mean()
                
                # Recent price change
                recent_price_change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-6]) / 
                                       hist['Close'].iloc[-6]) if pd.notna(hist['Close'].iloc[-6]) and hist['Close'].iloc[-6] != 0 else 0
                
                # Breakout condition: lower recent volatility followed by strong price increase
                breakout = (pd.notna(recent_volatility) and 
                           pd.notna(previous_volatility) and 
                           previous_volatility != 0 and
                           recent_volatility < previous_volatility * 0.8 and 
                           recent_price_change > 0.05)
            else:
                breakout = False
        except:
            breakout = False
        
        return {
            "above_ma40": above_ma40,
            "above_ma4": above_ma4,
            "rsi_above_50": rsi_above_50,
            "higher_lows": higher_lows,
            "near_52w_high": near_52w_high,
            "breakout": breakout
        }
    
    def _calculate_fundamental_indicators(self, stock, info):
        """Calculate fundamental indicators from stock info"""
        # Initialize results dictionary with default values
        results = {
            "is_profitable": False,
            "pe_ratio": None,
            "revenue_growth": None,
            "profit_margin": None,
            "earnings_trend": "Okänd",
            "fundamental_check": False
        }
        
        try:
            # Check if company is profitable
            net_income = info.get('netIncomeToCommon')
            results["is_profitable"] = net_income is not None and net_income > 0
            
            # Get P/E ratio
            results["pe_ratio"] = info.get('trailingPE') or info.get('forwardPE')
            
            # Get revenue growth
            revenue_growth = info.get('revenueGrowth')
            if revenue_growth is not None and pd.notna(revenue_growth):
                results["revenue_growth"] = revenue_growth
            
            # Get profit margin
            profit_margin = info.get('profitMargins')
            if profit_margin is not None and pd.notna(profit_margin):
                results["profit_margin"] = profit_margin
            
            # Get earnings trend data
            try:
                earnings = stock.earnings
                if not earnings.empty and len(earnings) > 1:
                    # Calculate year-over-year earnings growth
                    yearly_growth = earnings['Earnings'].pct_change().dropna()
                    
                    if len(yearly_growth) > 0:
                        # Determine earnings trend
                        if all(yearly_growth > 0):
                            results["earnings_trend"] = "Ökande"
                        elif all(yearly_growth < 0):
                            results["earnings_trend"] = "Minskande"
                        elif yearly_growth.iloc[-1] > 0:
                            results["earnings_trend"] = "Nyligen ökande"
                        else:
                            results["earnings_trend"] = "Nyligen minskande"
            except:
                results["earnings_trend"] = "Data saknas"
            
            # Determine if fundamentals are good overall
            # Conditions:
            # 1. Company is profitable
            # 2. Either has reasonable P/E or good growth
            pe_check = results["pe_ratio"] is None or (pd.notna(results["pe_ratio"]) and results["pe_ratio"] < self.pe_max)
            growth_check = results["revenue_growth"] is not None and pd.notna(results["revenue_growth"]) and results["revenue_growth"] > 0
            
            results["fundamental_check"] = results["is_profitable"] and (pe_check or growth_check)
            
        except Exception as e:
            print(f"Error calculating fundamental indicators: {e}")
            # Leave default values
        
        return results
    
    def _calculate_tech_score(self, tech_analysis):
        """Calculate a technical score from 0-100 based on technical indicators"""
        score = 0
        
        # Moving averages (most important)
        if tech_analysis['above_ma40']:
            score += 30
        if tech_analysis['above_ma4']:
            score += 15
        
        # RSI
        if tech_analysis['rsi_above_50']:
            score += 15
        
        # Higher lows
        if tech_analysis['higher_lows']:
            score += 15
        
        # Near 52-week high
        if tech_analysis['near_52w_high']:
            score += 15
        
        # Breakout
        if tech_analysis['breakout']:
            score += 10
        
        return score
    
    def plot_analysis(self, analysis):
        """
        Create a plot visualizing the analysis results.
        
        Parameters:
        - analysis: Analysis result dictionary
        
        Returns:
        - Matplotlib figure
        """
        if "error" in analysis or "historical_data" not in analysis:
            return None
        
        hist = analysis["historical_data"]
        
        # Create the figure
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot price and moving averages
        ax.plot(hist.index, hist['Close'], label='Price', linewidth=2)
        
        if 'MA4' in hist.columns and 'MA40' in hist.columns:
            # Only plot data points that are not NaN
            ma4_data = hist['MA4'].dropna()
            ma40_data = hist['MA40'].dropna()
            
            if not ma4_data.empty:
                ax.plot(ma4_data.index, ma4_data, label='MA4', linestyle='--')
            
            if not ma40_data.empty:
                ax.plot(ma40_data.index, ma40_data, label='MA40', linestyle='-.')
        
        # Add title and labels
        title = f"{analysis['name']} ({analysis['ticker']}) - {analysis['signal']}"
        ax.set_title(title)
        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        ax.grid(True, alpha=0.3)
        
        # Add legend
        ax.legend()
        
        # Add annotations for key metrics
        annotation_text = (
            f"Tech Score: {analysis['tech_score']}/100\n"
            f"Above MA40: {'✓' if analysis['above_ma40'] else '✗'}\n"
            f"Above MA4: {'✓' if analysis['above_ma4'] else '✗'}\n"
            f"RSI > 50: {'✓' if analysis['rsi_above_50'] else '✗'}\n"
            f"P/E: {analysis['pe_ratio']:.1f}" if analysis['pe_ratio'] and pd.notna(analysis['pe_ratio']) else "P/E: N/A"
        )
        
        plt.figtext(0.02, 0.02, annotation_text, fontsize=9,
                   bbox=dict(facecolor='white', alpha=0.8))
        
        # Adjust layout
        plt.tight_layout()
        
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