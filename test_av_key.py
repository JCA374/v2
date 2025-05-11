import requests
import json

def test_alpha_vantage_key(api_key, symbol="ERIC-B.ST"):
    """Test Alpha Vantage API key with a symbol"""
    print(f"Testing Alpha Vantage API key with symbol: {symbol}")
    
    url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={api_key}"
    response = requests.get(url)
    data = response.json()
    
    # Check if we got valid data (not an error)
    if "Symbol" in data:
        print(f"Success! Got data for {data.get('Name', 'Unknown')}")
        print(f"Symbol: {data.get('Symbol')}")
        print(f"Exchange: {data.get('Exchange')}")
        print(f"Industry: {data.get('Industry', 'Unknown')}")
        return True
    else:
        print(f"Error: {data}")
        return False
        
def test_price_data(api_key, symbol="ERIC-B.ST"):
    """Test fetching price data"""
    print(f"\nFetching price data for {symbol}")
    
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={api_key}"
    response = requests.get(url)
    data = response.json()
    
    # Check if we got valid data (not an error)
    if "Time Series (Daily)" in data:
        time_series = data["Time Series (Daily)"]
        dates = list(time_series.keys())
        print(f"Success! Got price data with {len(dates)} days")
        
        if dates:
            latest_date = dates[0]
            latest_data = time_series[latest_date]
            print(f"Latest date: {latest_date}")
            print(f"Open: {latest_data.get('1. open')}")
            print(f"High: {latest_data.get('2. high')}")
            print(f"Low: {latest_data.get('3. low')}")
            print(f"Close: {latest_data.get('4. close')}")
            print(f"Volume: {latest_data.get('5. volume')}")
        return True
    else:
        print(f"Error: {data}")
        return False

if __name__ == "__main__":
    # The API key from secrets.toml
    api_key = "5LU2EKREIF85DZTC"
    
    # Test with a Swedish stock
    test_alpha_vantage_key(api_key, "ERIC-B.ST")
    test_price_data(api_key, "ERIC-B.ST")
    
    # Also test with a US stock for comparison
    print("\n--- Testing with US stock ---")
    test_alpha_vantage_key(api_key, "AAPL")
    test_price_data(api_key, "AAPL")