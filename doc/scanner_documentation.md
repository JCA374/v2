# Stock Scanner Documentation

## Overview

The Stock Scanner tab provides a powerful screening tool that allows users to filter stocks based on technical indicators from preloaded CSV datasets. It enables discovery of potential investment opportunities matching specific technical criteria without requiring external API connections for stock discovery.

## Key Features

- **Pre-defined Stock Universes**: Choose between Small Cap, Mid Cap, and Large Cap stocks loaded from CSV files
- **Technical Filters**: Screen stocks based on RSI levels, volume surges, and EMA crossovers
- **Watchlist Integration**: Add matching stocks directly to any existing watchlist
- **Efficient API Usage**: Batch processing with rate limiting to prevent API throttling
- **User-friendly Interface**: Clear progress indicators and informative error handling

## How To Use

### 1. Select Stock Universe

Choose from three pre-defined universes:
- **Small Cap**: Smaller companies (loaded from `updated_small.csv`)
- **Mid Cap**: Medium-sized companies (loaded from `updated_mid.csv`) 
- **Large Cap**: Larger companies (loaded from `updated_large.csv`)

### 2. Configure Technical Filters

- **Historical Period**: How far back to analyze (3mo, 6mo, 1y)
- **Data Interval**: Time resolution of price data (daily, weekly)
- **RSI Range**: Set minimum and maximum RSI values (traditional range is 30-70)
- **Volume Multiplier**: Find stocks with volume above average (e.g., 1.5× means 50% above normal)
- **EMA Crossover Lookback**: Number of days to check for 50/200 EMA crossovers

### 3. Add Custom Tickers (Optional)

Enter additional tickers not included in the CSV files, separated by commas.

### 4. Run Scanner

Click the "Run Scanner" button to begin analysis. The scanner will:
1. Load tickers from the selected CSV file
2. Fetch price data in batches to avoid rate limiting
3. Calculate technical indicators
4. Filter stocks based on your criteria
5. Display matching results in a table

### 5. Add to Watchlist

From the results table:
1. Select the stocks you wish to add
2. Choose a destination watchlist from the dropdown
3. Click "Add Selected to Watchlist"

## Technical Details

### Data Processing

The scanner operates in three main phases:

1. **Data Loading**:
   - Reads ticker symbols and Yahoo Finance formatted tickers from CSV files
   - Processes custom tickers if provided
   - Organizes tickers for batch processing

2. **API Fetching**:
   - Fetches data in small batches (25 tickers at a time)
   - Implements delay between requests to avoid rate limiting
   - Caches results for one hour to prevent redundant API calls

3. **Technical Analysis**:
   - Calculates key indicators (RSI, EMA crossovers, volume ratios)
   - Applies filtering criteria to identify matching stocks
   - Formats and displays results with interactive controls

### Screening Criteria

Stocks must meet all of the following criteria to appear in results:

- RSI value within the specified min/max range
- Current volume at least X times the 20-day average volume (where X is the volume multiplier)
- Optionally, an EMA crossover within the lookback period (bullish signal when 50-day crosses above 200-day)

## Troubleshooting

### Issue: Scanner Returns No Results

**Potential Causes and Solutions:**
- **Criteria Too Restrictive**: Try widening the RSI range or lowering the volume multiplier
- **CSV Files Missing**: Ensure all required CSV files exist in the `/csv` directory
- **Yahoo Finance Tickers Invalid**: Verify tickers in CSV files have correct formats
- **API Rate Limiting**: Wait a few minutes and try again with a smaller stock universe

### Issue: API Errors

**Potential Causes and Solutions:**
- **Network Issues**: Check your internet connection
- **Yahoo Finance Limitations**: The scanner handles most API errors gracefully, but persistent failures may indicate temporary Yahoo Finance API issues
- **CSV Format Problems**: Ensure CSV files have "Tickersymbol" and "YahooTicker" columns

### Issue: Slow Performance

**Potential Causes and Solutions:**
- **Large Stock Universe**: Select a smaller universe (e.g., Small Cap instead of Large Cap)
- **Long Time Period**: Choose a shorter historical period (e.g., 3mo instead of 1y)
- **Clear Cache**: Use the "Clear Cache" button in Streamlit to reset the data cache

## Integration with Other Tabs

The Scanner Tab is designed to work seamlessly with other parts of the application:
- Stocks added to watchlists can be analyzed in the **Watchlist & Batch Analysis** tab
- Individual stocks can be further analyzed in the **Stock Analysis** tab
- Technical patterns discovered can be confirmed in the **Multi-Timeframe Analysis** tab

## Future Enhancements

Potential future improvements for the Scanner Tab:
- Fundamental data integration for combined technical-fundamental screening
- Custom indicator formulas
- Saving and loading scanner presets
- Export of scan results to CSV
- Automatic scheduled scanning with alerts
