import requests
import logging
import pandas as pd
import datetime
from earnings_analyzer.config import get_fmp_api_key

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

BASE_URL = "https://financialmodelingprep.com/api/v3"

def _check_fmp_api_key():
    """Internal helper to check if FMP API key is configured."""
    if not get_fmp_api_key():
        logging.error("FMP_API_KEY is not set in the environment variables. Please set it to use Financial Modeling Prep API.")
        return False
    return True


def fetch_company_profile(ticker):
    """
    Main composable function to fetch company profile information.
    
    This is the primary function for getting company metadata in data pipelines.
    
    Args:
        ticker (str): Stock ticker symbol
        
    Returns:
        dict: Company profile data including symbol, companyName, sector, industry, etc.
        None: If profile could not be fetched
    """
    return get_company_profile(ticker)


def get_company_profile(ticker):
    """
    Fetches the company profile for a given ticker from the FMP API.
    
    Args:
        ticker (str): Stock ticker symbol
        
    Returns:
        dict: Company profile data with keys like:
            - symbol, companyName, sector, industry
            - marketCap, price, beta, volAvg
            - description, ceo, fullTimeEmployees
            - website, address, phone
        None: If profile could not be fetched
    """
    if not _check_fmp_api_key():
        return None

    url = f"{BASE_URL}/profile/{ticker}?apikey={get_fmp_api_key()}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data and len(data) > 0:
            profile = data[0]
            logging.info(f"Successfully fetched profile for {ticker}: {profile.get('companyName', 'N/A')}")
            return profile
        else:
            logging.warning(f"No profile data found for {ticker}.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching company profile from FMP API: {e}")
        return None


def get_historical_prices(ticker, limit=None):
    """
    Fetches historical daily stock prices for a given ticker from the FMP API.
    
    Args:
        ticker (str): Stock ticker symbol
        limit (int, optional): Maximum number of historical records to return
        
    Returns:
        list: List of daily price records with keys:
            - date, open, high, low, close, adjClose, volume, change, changePercent
        None: If historical prices could not be fetched
    """
    if not _check_fmp_api_key():
        return None

    url = f"{BASE_URL}/historical-price-full/{ticker}?apikey={get_fmp_api_key()}"
    if limit:
        url += f"&limit={limit}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'historical' in data:
            historical_data = data['historical']
            logging.info(f"Successfully fetched {len(historical_data)} historical price records for {ticker}")
            return historical_data
        else:
            logging.warning(f"No historical price data found for {ticker}.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching historical prices from FMP API: {e}")
        return None


def calculate_stock_performance(ticker, call_date, historical_prices=None):
    """
    Calculates stock performance metrics relative to earnings call date.
    
    This function is unique to the financial data fetcher and provides
    performance analysis capabilities for earnings call analysis.
    
    Args:
        ticker (str): Stock ticker symbol
        call_date (str or datetime): Date of the earnings call
        historical_prices (list, optional): Pre-fetched historical price data
        
    Returns:
        dict: Contains price_at_call, price_1_week, price_1_month, price_3_month,
              performance_1_week, performance_1_month, performance_3_month
        None: If calculation failed
    """
    if not call_date:
        logging.warning("Call date is required for stock performance calculation")
        return None
        
    try:
        # Fetch historical prices if not provided
        if historical_prices is None:
            historical_prices = get_historical_prices(ticker)
            
        if not historical_prices:
            logging.warning(f"No historical prices available for {ticker}")
            return None

        # Convert call_date to datetime if it's a string
        if isinstance(call_date, str):
            call_date = datetime.datetime.strptime(call_date, '%Y-%m-%d').date()
        elif isinstance(call_date, datetime.datetime):
            call_date = call_date.date()

        df = pd.DataFrame(historical_prices)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()

        call_date_dt = pd.to_datetime(call_date)

        # Find the price at call date (or closest prior date)
        price_at_call_series = df.loc[df.index <= call_date_dt, 'close']
        if price_at_call_series.empty:
            logging.warning(f"No price data available at or before call date {call_date}")
            return None
        price_at_call = price_at_call_series.iloc[-1]

        # Calculate future dates
        one_week_later = call_date_dt + pd.Timedelta(weeks=1)
        one_month_later = call_date_dt + pd.Timedelta(days=30)
        three_month_later = call_date_dt + pd.Timedelta(days=90)

        # Get prices at future dates (or closest available)
        price_1_week = df.loc[df.index >= one_week_later, 'close'].iloc[0] if not df.loc[df.index >= one_week_later].empty else None
        price_1_month = df.loc[df.index >= one_month_later, 'close'].iloc[0] if not df.loc[df.index >= one_month_later].empty else None
        price_3_month = df.loc[df.index >= three_month_later, 'close'].iloc[0] if not df.loc[df.index >= three_month_later].empty else None

        # Calculate performance percentages
        performance_1_week = (price_1_week - price_at_call) / price_at_call if price_1_week else None
        performance_1_month = (price_1_month - price_at_call) / price_at_call if price_1_month else None
        performance_3_month = (price_3_month - price_at_call) / price_at_call if price_3_month else None

        logging.info(f"Calculated stock performance for {ticker} from {call_date}")
        return {
            'price_at_call': price_at_call,
            'price_1_week': price_1_week,
            'price_1_month': price_1_month,
            'price_3_month': price_3_month,
            'performance_1_week': performance_1_week,
            'performance_1_month': performance_1_month,
            'performance_3_month': performance_3_month
        }
        
    except Exception as e:
        logging.error(f"Error calculating stock performance for {ticker}: {e}")
        return None


def get_financial_statements(ticker, period="quarter", limit=1):
    """
    Fetches financial statements for a given ticker from the FMP API.
    
    Args:
        ticker (str): Stock ticker symbol
        period (str): "quarter" or "annual"
        limit (int): Number of periods to return
        
    Returns:
        dict: Contains income_statement and balance_sheet data
        None: If financial statements could not be fetched
    """
    if not _check_fmp_api_key():
        return None

    income_url = f"{BASE_URL}/income-statement/{ticker}?period={period}&limit={limit}&apikey={get_fmp_api_key()}"
    balance_url = f"{BASE_URL}/balance-sheet-statement/{ticker}?period={period}&limit={limit}&apikey={get_fmp_api_key()}"
    
    try:
        income_response = requests.get(income_url, timeout=10)
        income_response.raise_for_status()
        income_statement = income_response.json()

        balance_response = requests.get(balance_url, timeout=10)
        balance_response.raise_for_status()
        balance_sheet = balance_response.json()

        if income_statement and balance_sheet:
            result = {
                "income_statement": income_statement[0] if limit == 1 else income_statement,
                "balance_sheet": balance_sheet[0] if limit == 1 else balance_sheet
            }
            logging.info(f"Successfully fetched financial statements for {ticker}.")
            return result
        else:
            logging.warning(f"No financial statements found for {ticker}.")
            return None

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP Error fetching financial statements from FMP API (Status: {e.response.status_code}): {e}. Check your API key or ticker symbol.")
        return None
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Connection Error fetching financial statements from FMP API: {e}. Check your internet connection.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"An unexpected Request Error occurred fetching financial statements from FMP API for {ticker}: {e}")
        return None


def get_stock_quote(ticker):
    """
    Fetches real-time stock quote for a given ticker.
    
    Args:
        ticker (str): Stock ticker symbol
        
    Returns:
        dict: Real-time quote data including price, change, volume
        None: If quote could not be fetched
    """
    if not _check_fmp_api_key():
        return None

    url = f"{BASE_URL}/quote/{ticker}?apikey={get_fmp_api_key()}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data and len(data) > 0:
            quote = data[0]
            logging.info(f"Successfully fetched quote for {ticker}: ${quote.get('price', 'N/A')}")
            return quote
        else:
            logging.warning(f"No quote data found for {ticker}.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching stock quote from FMP API: {e}")
        return None


def batch_fetch_company_profiles(tickers):
    """
    Fetches company profiles for multiple tickers in batch.
    
    Args:
        tickers (list): List of stock ticker symbols
        
    Returns:
        list: List of company profile dictionaries in the same order as input.
              Failed fetches will be None in the corresponding position.
    """
    results = []
    
    for i, ticker in enumerate(tickers):
        logging.info(f"Fetching profile {i+1}/{len(tickers)}: {ticker}")
        result = get_company_profile(ticker)
        results.append(result)
        
    return results


def batch_fetch_historical_prices(tickers, limit=None):
    """
    Fetches historical prices for multiple tickers in batch.
    
    Args:
        tickers (list): List of stock ticker symbols
        limit (int, optional): Maximum number of historical records per ticker
        
    Returns:
        dict: Dictionary mapping ticker -> historical price data
    """
    results = {}
    
    for i, ticker in enumerate(tickers):
        logging.info(f"Fetching historical prices {i+1}/{len(tickers)}: {ticker}")
        historical_data = get_historical_prices(ticker, limit)
        results[ticker] = historical_data
        
    return results


def get_market_summary():
    """
    Fetches overall market summary data.
    
    Returns:
        dict: Market summary data including major indices
        None: If market summary could not be fetched
    """
    if not _check_fmp_api_key():
        return None

    # Get data for major indices
    indices = ["^GSPC", "^DJI", "^IXIC"]  # S&P 500, Dow Jones, NASDAQ
    url = f"{BASE_URL}/quote/{','.join(indices)}?apikey={get_fmp_api_key()}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data:
            market_data = {
                'sp500': next((item for item in data if item['symbol'] == '^GSPC'), None),
                'dow_jones': next((item for item in data if item['symbol'] == '^DJI'), None),
                'nasdaq': next((item for item in data if item['symbol'] == '^IXIC'), None)
            }
            logging.info("Successfully fetched market summary")
            return market_data
        else:
            logging.warning("No market summary data found.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching market summary from FMP API: {e}")
        return None


def get_earnings_calendar(ticker=None):
    """
    Fetches earnings calendar data.
    
    Args:
        ticker (str, optional): Specific ticker to get earnings calendar for
        
    Returns:
        list: Earnings calendar entries
        None: If calendar could not be fetched
    """
    if not _check_fmp_api_key():
        return None

    if ticker:
        url = f"{BASE_URL}/historical/earning_calendar/{ticker}?apikey={get_fmp_api_key()}"
    else:
        url = f"{BASE_URL}/earning_calendar?apikey={get_fmp_api_key()}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data:
            logging.info(f"Successfully fetched earnings calendar{' for ' + ticker if ticker else ''}")
            return data
        else:
            logging.warning(f"No earnings calendar data found{' for ' + ticker if ticker else ''}.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching earnings calendar from FMP API: {e}")
        return None


def validate_financial_data(data, data_type):
    """
    Validates that financial data has the expected structure.
    
    Args:
        data: The financial data to validate
        data_type (str): Type of data ("profile", "historical", "financial_statements", "quote")
        
    Returns:
        bool: True if the data is valid, False otherwise
    """
    if not data:
        return False
        
    try:
        if data_type == "profile":
            required_fields = ['symbol', 'companyName']
            return isinstance(data, dict) and all(field in data for field in required_fields)
            
        elif data_type == "historical":
            if not isinstance(data, list) or len(data) == 0:
                return False
            required_fields = ['date', 'close', 'open', 'high', 'low']
            return all(field in data[0] for field in required_fields)
            
        elif data_type == "financial_statements":
            return (isinstance(data, dict) and 
                   'income_statement' in data and 
                   'balance_sheet' in data)
                   
        elif data_type == "quote":
            required_fields = ['symbol', 'price']
            return isinstance(data, dict) and all(field in data for field in required_fields)
            
        elif data_type == "stock_performance":
            required_fields = ['price_at_call', 'performance_1_week', 'performance_1_month', 'performance_3_month']
            return isinstance(data, dict) and all(field in data for field in required_fields)
            
    except Exception:
        return False
        
    return False


def get_price_at_date(ticker, target_date, historical_prices=None):
    """
    Gets the stock price for a specific date or the closest available date.
    
    Args:
        ticker (str): Stock ticker symbol
        target_date (str or datetime): The target date to find price for
        historical_prices (list, optional): Pre-fetched historical price data
        
    Returns:
        dict: Contains price, date, and closest_match info
        None: If price could not be found
    """
    try:
        # Fetch historical prices if not provided
        if historical_prices is None:
            historical_prices = get_historical_prices(ticker)
            
        if not historical_prices:
            return None

        # Convert target_date to datetime if it's a string
        if isinstance(target_date, str):
            target_date = datetime.datetime.strptime(target_date, '%Y-%m-%d').date()
        elif isinstance(target_date, datetime.datetime):
            target_date = target_date.date()

        df = pd.DataFrame(historical_prices)
        df['date'] = pd.to_datetime(df['date']).dt.date
        df = df.sort_values('date')

        # Find exact match first
        exact_match = df[df['date'] == target_date]
        if not exact_match.empty:
            row = exact_match.iloc[0]
            return {
                'price': row['close'],
                'date': row['date'].strftime('%Y-%m-%d'),
                'closest_match': True
            }

        # Find closest available date before target
        before_target = df[df['date'] <= target_date]
        if not before_target.empty:
            row = before_target.iloc[-1]  # Most recent date before target
            return {
                'price': row['close'],
                'date': row['date'].strftime('%Y-%m-%d'),
                'closest_match': False
            }

        # If no date before target, get the earliest available
        if not df.empty:
            row = df.iloc[0]
            return {
                'price': row['close'],
                'date': row['date'].strftime('%Y-%m-%d'),
                'closest_match': False
            }

        return None
        
    except Exception as e:
        logging.error(f"Error getting price at date for {ticker}: {e}")
        return None


def compare_performance_to_market(ticker, call_date, historical_prices=None):
    """
    Compares a stock's performance to market indices after an earnings call.
    
    Args:
        ticker (str): Stock ticker symbol
        call_date (str or datetime): Date of the earnings call
        historical_prices (list, optional): Pre-fetched historical price data
        
    Returns:
        dict: Contains relative performance vs S&P 500, sector performance, etc.
        None: If comparison could not be performed
    """
    try:
        # Get stock performance
        stock_perf = calculate_stock_performance(ticker, call_date, historical_prices)
        if not stock_perf:
            return None

        # Get S&P 500 performance for comparison
        sp500_perf = calculate_stock_performance("^GSPC", call_date)
        if not sp500_perf:
            logging.warning("Could not fetch S&P 500 data for comparison")
            return {
                'stock_performance': stock_perf,
                'relative_to_sp500': None
            }

        # Calculate relative performance
        relative_1_week = None
        relative_1_month = None  
        relative_3_month = None

        if stock_perf['performance_1_week'] and sp500_perf['performance_1_week']:
            relative_1_week = stock_perf['performance_1_week'] - sp500_perf['performance_1_week']
            
        if stock_perf['performance_1_month'] and sp500_perf['performance_1_month']:
            relative_1_month = stock_perf['performance_1_month'] - sp500_perf['performance_1_month']
            
        if stock_perf['performance_3_month'] and sp500_perf['performance_3_month']:
            relative_3_month = stock_perf['performance_3_month'] - sp500_perf['performance_3_month']

        return {
            'stock_performance': stock_perf,
            'sp500_performance': sp500_perf,
            'relative_performance': {
                'vs_sp500_1_week': relative_1_week,
                'vs_sp500_1_month': relative_1_month,
                'vs_sp500_3_month': relative_3_month
            },
            'outperformed_market': {
                '1_week': relative_1_week > 0 if relative_1_week else None,
                '1_month': relative_1_month > 0 if relative_1_month else None,
                '3_month': relative_3_month > 0 if relative_3_month else None
            }
        }
        
    except Exception as e:
        logging.error(f"Error comparing performance to market for {ticker}: {e}")
        return None