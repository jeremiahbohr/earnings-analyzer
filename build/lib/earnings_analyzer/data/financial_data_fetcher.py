import requests
import logging
from earnings_analyzer.config import get_fmp_api_key, get_sec_api_key

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

BASE_URL = "https://financialmodelingprep.com/api/v3"

def _check_fmp_api_key():
    if not get_fmp_api_key():
        logging.error("FMP_API_KEY is not set in the environment variables. Please set it to use Financial Modeling Prep API.")
        return False
    return True

def get_historical_prices(ticker):
    """
    Fetches historical daily stock prices for a given ticker from the FMP API.
    """
    if not _check_fmp_api_key():
        return None

    url = f"{BASE_URL}/historical-price-full/{ticker}?apikey={get_fmp_api_key()}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if 'historical' in data:
            return data['historical']
        else:
            logging.warning(f"No historical price data found for {ticker}.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching historical prices from FMP API: {e}")
        return None

def get_company_profile(ticker):
    """
    Fetches the company profile for a given ticker from the FMP API.
    """
    if not _check_fmp_api_key():
        return None

    url = f"{BASE_URL}/profile/{ticker}?apikey={get_fmp_api_key()}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data and len(data) > 0:
            return data[0]
        else:
            logging.warning(f"No profile data found for {ticker}.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching company profile from FMP API: {e}")
        return None

def get_financial_statements(ticker):
    """
    Fetches the quarterly financial statements for a given ticker from the FMP API.
    """
    if not _check_fmp_api_key():
        return None

    # Corrected endpoint for quarterly income statements
    income_url = f"{BASE_URL}/income-statement/{ticker}?period=quarter&limit=1&apikey={get_fmp_api_key()}"
    # Corrected endpoint for quarterly balance sheets
    balance_url = f"{BASE_URL}/balance-sheet-statement/{ticker}?period=quarter&limit=1&apikey={get_fmp_api_key()}"
    
    try:
        income_response = requests.get(income_url)
        income_response.raise_for_status()
        income_statement = income_response.json()

        balance_response = requests.get(balance_url)
        balance_response.raise_for_status()
        balance_sheet = balance_response.json()

        if income_statement and balance_sheet:
            return {
                "income_statement": income_statement[0], # Most recent quarter
                "balance_sheet": balance_sheet[0] # Most recent quarter
            }
        else:
            logging.warning(f"No financial statements found for {ticker}.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching financial statements from FMP API for {ticker}: {e}")
        return None

if __name__ == '__main__':
    # Example usage:
    ticker_symbol = "AAPL"
    print(f"Fetching data for {ticker_symbol}...")

    profile = get_company_profile(ticker_symbol)
    if profile:
        print("\n--- Company Profile ---")
        print(f"Sector: {profile.get('sector')}")
        print(f"Industry: {profile.get('industry')}")

    financials = get_financial_statements(ticker_symbol)
    if financials:
        print("\n--- Key Financials ---")
        print(f"Revenue: {financials['income_statement'].get('revenue')}")
        print(f"Net Income: {financials['income_statement'].get('netIncome')}")
        print(f"Total Debt: {financials['balance_sheet'].get('totalDebt')}")

    historical_data = get_historical_prices(ticker_symbol)
    if historical_data:
        print("\n--- Historical Prices (Last 5 Days) ---")
        for day in historical_data[:5]:
            print(f"{day['date']}: Close = {day['close']}")