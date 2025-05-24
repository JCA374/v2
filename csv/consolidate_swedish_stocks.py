import pandas as pd
import os

def consolidate_swedish_stocks():
    """
    Consolidate Swedish stock data from multiple CSV files into a single file.
    Adds a 'size_category' column based on the source file.
    """
    # File paths
    csv_files = {
        'small': 'csv/updated_small.csv',
        'mid': 'csv/updated_mid.csv',
        'large': 'csv/updated_large.csv',
        'valid': 'csv/valid_swedish_company_data.csv'
    }
    
    # Load each CSV file
    dfs = {}
    for category, file_path in csv_files.items():
        try:
            dfs[category] = pd.read_csv(file_path)
            print(f"Loaded {len(dfs[category])} rows from {file_path}")
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    # Process and combine dataframes
    combined_data = []
    
    # Process small cap stocks
    if 'small' in dfs:
        df = dfs['small']
        df['size_category'] = 'Small Cap'
        combined_data.append(df)
    
    # Process mid cap stocks
    if 'mid' in dfs:
        df = dfs['mid']
        df['size_category'] = 'Mid Cap'
        combined_data.append(df)
    
    # Process large cap stocks
    if 'large' in dfs:
        df = dfs['large']
        df['size_category'] = 'Large Cap'
        combined_data.append(df)
    
    # Process valid Swedish company data (if not categorized in the above)
    if 'valid' in dfs:
        # Create a set of all tickers already added
        added_tickers = set()
        for df in combined_data:
            if 'YahooTicker' in df.columns:
                added_tickers.update(df['YahooTicker'].tolist())
            elif 'Tickersymbol' in df.columns:
                added_tickers.update(df['Tickersymbol'].tolist())
        
        # Add only tickers not already included
        valid_df = dfs['valid']
        valid_df['size_category'] = 'Unknown'  # Default category
        
        # Filter out already added tickers
        if 'YahooTicker' in valid_df.columns:
            valid_df = valid_df[~valid_df['YahooTicker'].isin(added_tickers)]
            combined_data.append(valid_df)
    
    # Combine all dataframes
    if combined_data:
        combined_df = pd.concat(combined_data, ignore_index=True)
        
        # Make sure all required columns exist
        required_columns = ['YahooTicker', 'CompanyName', 'YahooExchange', 'size_category']
        for col in required_columns:
            if col not in combined_df.columns:
                if col == 'YahooTicker' and 'Tickersymbol' in combined_df.columns:
                    combined_df['YahooTicker'] = combined_df['Tickersymbol']
                elif col == 'CompanyName' and 'Tickersymbol' in combined_df.columns:
                    combined_df['CompanyName'] = combined_df['Tickersymbol']
                elif col == 'YahooExchange' and 'YahooTicker' in combined_df.columns:
                    # Try to determine exchange from ticker format
                    combined_df['YahooExchange'] = combined_df['YahooTicker'].apply(
                        lambda x: 'Stockholm Stock Exchange' if str(x).endswith('.ST') else 'US Markets (default)'
                    )
                else:
                    combined_df[col] = 'Unknown'
        
        # Check for duplicates
        duplicate_count = combined_df.duplicated(subset=['YahooTicker']).sum()
        if duplicate_count > 0:
            print(f"Found {duplicate_count} duplicate tickers. Removing duplicates...")
            combined_df = combined_df.drop_duplicates(subset=['YahooTicker'])
        
        # Add sector information if available (for stocks from valid_swedish_company_data.csv)
        if 'valid' in dfs and 'sector' in dfs['valid'].columns:
            sector_map = dict(zip(dfs['valid']['YahooTicker'], dfs['valid']['sector']))
            if 'sector' not in combined_df.columns:
                combined_df['sector'] = 'Unknown'
            # Update sectors where available
            for ticker, sector in sector_map.items():
                if pd.notna(sector):
                    combined_df.loc[combined_df['YahooTicker'] == ticker, 'sector'] = sector
        
        # Save to new CSV file
        output_file = 'swedish_stocks_consolidated.csv'
        combined_df.to_csv(output_file, index=False)
        print(f"Successfully saved {len(combined_df)} stocks to {output_file}")
        
        # Print summary
        print("\nSummary by size category:")
        summary = combined_df['size_category'].value_counts()
        for category, count in summary.items():
            print(f"{category}: {count} stocks")
            
        # Print exchange summary
        print("\nSummary by exchange:")
        exchange_summary = combined_df['YahooExchange'].value_counts()
        for exchange, count in exchange_summary.items():
            print(f"{exchange}: {count} stocks")
    else:
        print("No data to combine.")

if __name__ == "__main__":
    consolidate_swedish_stocks()
