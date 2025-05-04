# Stock Scanner User Guide

## Introduction

The Stock Scanner tab allows you to scan multiple stock universes for technical patterns and indicators. It's designed to help you find potential investment opportunities that match specific technical criteria, such as RSI levels, volume surges, and EMA crossovers.

## Key Features

- **Multiple Stock Universes**: Choose from Small Cap, Mid Cap, Large Cap, and Swedish Stocks
- **Technical Filtering**: Find stocks based on RSI range, volume multipliers, and EMA crossovers
- **Continuous Scanning**: Process stocks in batches to prevent API overloads
- **Retry Mechanism**: Failed API calls are saved and can be retried later
- **Watchlist Integration**: Add matching stocks directly to any existing watchlist

## How to Use

### 1. Select Stock Universe

Choose from one of the available stock universes:
- **Small Cap**: Smaller companies
- **Mid Cap**: Medium-sized companies
- **Large Cap**: Larger companies 
- **Swedish Stocks**: Stocks from the Swedish market
- **Failed Tickers**: Previously failed API calls that can be retried

### 2. Configure Scan Parameters

- **History**: How far back to analyze (3mo, 6mo, 1y)
- **Interval**: Time resolution of price data (daily, weekly)

### 3. Set Technical Filters

Either select a preset or customize your own filters:

**Presets**:
- **Conservative**: RSI 40-60, Vol×2.0, 20-day lookback
- **Balanced**: RSI 30-70, Vol×1.5, 30-day lookback
- **Aggressive**: RSI 20-80, Vol×1.2, 40-day lookback

**Custom**:
- **RSI Range**: Min and max RSI values to consider
- **Volume Multiplier**: Find stocks with volume above average (e.g., 1.5× means 50% above normal)
- **EMA Crossover Lookback**: Number of days to check for 50/200 EMA crossovers

### 4. Add Custom Tickers (Optional)

Enter additional tickers not included in the selected universe, separated by commas.

### 5. Set Processing Options

- **Process Batch Size**: Number of stocks to process at once (smaller batches reduce API errors)
- **Continuous Scanning**: Enable to process stocks in batches with pauses to avoid API limits

### 6. Run the Scanner

Click one of these buttons:
- **Run Scanner**: Start scanning with the current settings
- **Retry Failed**: Retry previously failed tickers
- **Stop Scanner**: Stop an in-progress scan
- **Clear Results**: Clear current scan results

### 7. Review Results

The scanner will display stocks that match your criteria, ranked by a composite score. For each stock, you'll see:
- **Ticker**: Stock symbol
- **Price**: Current price
- **RSI(14)**: Relative Strength Index value
- **Vol Ratio**: Volume compared to 20-day average
- **EMA Cross**: Whether a recent EMA crossover occurred
- **MACD Diff**: MACD histogram value
- **Score**: Composite technical score (higher is better)

### 8. Add to Watchlist

You can add promising stocks to any of your existing watchlists:
1. Select which watchlist to add to
2. Check the boxes next to the stocks you want to add
3. Click "Add to Watchlist"

## Tips for Effective Scanning

1. **Start with smaller universes** or use continuous scanning with smaller batch sizes to avoid API rate limits.

2. **Use presets first**, then adjust based on your preferences and market conditions.

3. **Enable "Scan All Stocks"** to process all stocks in the selected universe. For large datasets like the Swedish Stocks (1000+ stocks), the scanner will update the results table after every 100 stocks processed.

4. **Use "Continuous Scanning"** to add delays between batches, which helps prevent Yahoo Finance API rate limits.

5. **Adjust the "Process Batch Size"** based on your needs:
   - Larger batches (e.g., 100) process more stocks at once but may encounter API limits
   - Smaller batches (e.g., 25) are less likely to hit API limits but take longer to complete

6. **Combine multiple