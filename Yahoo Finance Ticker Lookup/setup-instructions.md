# Yahoo Finance Ticker Lookup Tool - Setup Instructions

This guide will walk you through setting up and running the Yahoo Finance Ticker Lookup tool in VS Code.

## Prerequisites

- [Node.js](https://nodejs.org/) (v14 or higher)
- [VS Code](https://code.visualstudio.com/)
- Basic knowledge of the command line

## Setup Instructions

1. **Create a new folder** for your project:
   ```bash
   mkdir yahoo-ticker-tool
   cd yahoo-ticker-tool
   ```

2. **Initialize a new Node.js project**:
   ```bash
   npm init -y
   ```

3. **Install the required dependencies**:
   ```bash
   npm install papaparse
   ```

4. **Create the script file**:
   - Create a new file named `yahoo-finance-ticker-lookup.js`
   - Copy and paste the entire code from the script I provided

5. **Prepare your CSV file**:
   - Make sure your CSV file has a header row
   - The default column name for ticker symbols is "Tickersymbol"
   - If your CSV uses a different column name, you'll specify that when running the script

## Running the Tool

1. **Basic usage**:
   ```bash
   node yahoo-finance-ticker-lookup.js input.csv output.csv
   ```

2. **If your ticker column has a different name**:
   ```bash
   node yahoo-finance-ticker-lookup.js input.csv output.csv YourColumnName
   ```

3. **Examples**:
   ```bash
   # Using the default column name (Tickersymbol)
   node yahoo-finance-ticker-lookup.js stocks.csv yahoo-stocks.csv

   # Using a custom column name
   node yahoo-finance-ticker-lookup.js nasdaq.csv yahoo-nasdaq.csv Symbol
   ```

## Output

The script will generate a CSV file with the following columns:

- `OriginalTicker`: The ticker symbol from your input file
- `CleanedTicker`: The ticker with spaces replaced by hyphens
- `YahooTicker1` through `YahooTicker5`: Potential Yahoo Finance ticker formats
- `Exchange1` through `Exchange5`: Corresponding exchange descriptions
- `URL1` through `URL5`: Direct links to the Yahoo Finance pages

## Customizing the Tool

You can modify the script to:

1. **Add more exchanges**: Edit the `exchangeSuffixes` array
2. **Change the output format**: Modify the `outputRows` construction
3. **Filter for specific exchanges**: Add conditions in the processing logic

## Troubleshooting

- **"Column not found" error**: Make sure you're specifying the correct column name
- **Empty results**: Check that your CSV file is properly formatted
- **Parsing errors**: Ensure your CSV doesn't have unusual formatting or special characters

## Using with Different CSV Files

1. **Prepare each CSV file** with ticker symbols
2. **Run the script** for each file separately:
   ```bash
   node yahoo-finance-ticker-lookup.js file1.csv output1.csv
   node yahoo-finance-ticker-lookup.js file2.csv output2.csv
   ```
3. **Review the output files** to find the correct Yahoo Finance tickers
