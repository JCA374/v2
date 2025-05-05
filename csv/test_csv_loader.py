"""
CSV Test Utility

This script tests loading all the CSV files to ensure they can be properly loaded
by the stock scanner. It attempts different encoding options and reports any issues.
"""
import os
import pandas as pd
import sys

def test_load_csv(file_path):
    """Test loading a CSV file with different encodings and report results."""
    print(f"\nTesting CSV file: {file_path}")
    print("-" * 60)
    
    if not os.path.exists(file_path):
        print(f"❌ ERROR: File does not exist at path: {file_path}")
        return False
    
    # Try loading with different encodings
    encodings = ['utf-8', 'latin-1', 'ISO-8859-1', 'cp1252']
    success = False
    
    for encoding in encodings:
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            success = True
            row_count = len(df)
            col_count = len(df.columns)
            columns = df.columns.tolist()
            
            print(f"✅ SUCCESS with encoding: {encoding}")
            print(f"   Rows: {row_count}, Columns: {col_count}")
            print(f"   Columns: {columns}")
            
            # Check for expected columns for scanner
            if 'YahooTicker' in df.columns:
                print(f"   ✓ Found YahooTicker column")
                print(f"   Sample tickers: {df['YahooTicker'].head(3).tolist()}")
            else:
                print(f"   ❗ WARNING: Missing YahooTicker column")
                
            if 'Tickersymbol' in df.columns:
                print(f"   ✓ Found Tickersymbol column")
                print(f"   Sample symbols: {df['Tickersymbol'].head(3).tolist()}")
            else:
                print(f"   ❗ WARNING: Missing Tickersymbol column")
                
            # Break after first successful encoding
            break
            
        except Exception as e:
            print(f"❌ Failed with encoding {encoding}: {str(e)}")
    
    if not success:
        print("❌ ERROR: Could not load the CSV file with any encoding")
        return False
        
    return True

def main():
    """Test loading all CSV files in the current directory."""
    print("CSV File Loading Test Utility")
    print("=============================")
    
    # Get all CSV files in current directory
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    
    if not csv_files:
        print("No CSV files found in the current directory")
        return
        
    print(f"Found {len(csv_files)} CSV files to test")
    
    results = {}
    for file in csv_files:
        results[file] = test_load_csv(file)
    
    # Summary
    print("\nSummary:")
    print("========")
    success_count = sum(1 for r in results.values() if r)
    print(f"Successfully loaded {success_count} of {len(csv_files)} CSV files")
    
    if success_count < len(csv_files):
        print("\nFailed files:")
        for file, success in results.items():
            if not success:
                print(f"- {file}")

if __name__ == "__main__":
    main()