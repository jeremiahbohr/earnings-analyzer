import requests
import logging
import pandas as pd
import datetime
from urllib.parse import urlparse, parse_qs
import time
from earnings_analyzer.config import get_fmp_api_key

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

BASE_URL = "https://financialmodelingprep.com/api/v3"

# Cache API key validation result to avoid repeated checks
_api_key_validated = None
_last_rate_limit_time = {}

def _check_fmp_api_key():
    """Internal helper to check if FMP API key is configured."""
    global _api_key_validated
    
    if _api_key_validated is None:
        api_key = get_fmp_api_key()
        if not api_key:
            logging.error("FMP_API_KEY is not set in the environment variables. Please set it to use Financial Modeling Prep API.")
            _api_key_validated = False
        else:
            _api_key_validated = True
            
    return _api_key_validated

def _sanitize_url_for_logging(url):
    """Remove API key from URL for safe logging."""
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if 'apikey' in query_params:
            query_params['apikey'] = ['***REDACTED***']
        safe_query = '&'.join([f"{k}={v[0]}" for k, v in query_params.items()])
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{safe_query}"
    except Exception:
        return "URL_PARSE_ERROR"

def _handle_rate_limiting(response, ticker=None):
    """Handle rate limiting with exponential backoff."""
    global _last_rate_limit_time
    
    if response.status_code == 429:  # Too Many Requests
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            wait_time = int(retry_after)
        else:
            # Exponential backoff based on ticker
            key = ticker or 'global'
            last_time = _last_rate_limit_time.get(key, 0)
            current_time = time.time()
            if current_time - last_time < 60:  # Less than 1 minute since last rate limit
                wait_time = min(120, 30 * (2 ** len(_last_rate_limit_time)))  # Max 2 minutes
            else:
                wait_time = 30
            _last_rate_limit_time[key] = current_time
            
        logging.warning(f"Rate limited. Waiting {wait_time} seconds before retry...")
        time.sleep(wait_time)
        return True
    return False

def _make_api_request(url, timeout=30, max_retries=3, ticker=None):
    """Make API request with proper error handling, rate limiting, and retries."""
    if not _check_fmp_api_key():
        return None
        
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            
            # Handle rate limiting
            if _handle_rate_limiting(response, ticker):
                continue  # Retry after rate limit
                
            response.raise_for_status()
            data = response.json()
            
            if not data:
                logging.warning(f"Empty response from FMP API for {_sanitize_url_for_logging(url)}")
                return None
                
            return data
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logging.error(f"API key invalid or quota exceeded (HTTP 403). Check your FMP API key and subscription limits.")
                return None
            elif e.response.status_code == 404:
                logging.warning(f"Resource not found (HTTP 404) for {ticker or 'request'}")
                return None
            else:
                logging.error(f"HTTP Error {e.response.status_code} from FMP API: {e}")
                if attempt == max_retries - 1:
                    return None
                    
        except requests.exceptions.Timeout:
            logging.warning(f"Request timeout (attempt {attempt + 1}/{max_retries}) for {ticker or 'request'}")
            if attempt == max_retries - 1:
                logging.error(f"Final timeout after {max_retries} attempts")
                return None
                
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                logging.error(f"Final connection error after {max_retries} attempts")
                return None
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error from FMP API: {e}")
            return None
            
        except ValueError as e:  # JSON decode error
            logging.error(f"Invalid JSON response from FMP API: {e}")
            return None
            
        # Wait before retry (except for last attempt)
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            logging.info(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            
    return None

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
    if not ticker or not isinstance(ticker, str):
        logging.error("Invalid ticker provided to fetch_company_profile")
        return None
        
    return get_company_profile(ticker.upper().strip())

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
    if not ticker or not isinstance(ticker, str):
        logging.error("Invalid ticker provided to get_company_profile")
        return None
        
    ticker = ticker.upper().strip()
    url = f"{BASE_URL}/profile/{ticker}?apikey={get_fmp_api_key()}"
    
    data = _make_api_request(url, ticker=ticker)
    if not data:
        return None
        
    if len(data) > 0:
        profile = data[0]
        # Validate essential fields
        if not profile.get('symbol') or not profile.get('companyName'):
            logging.warning(f"Incomplete profile data for {ticker}")
            return None
            
        logging.info(f"Successfully fetched profile for {ticker}: {profile.get('companyName', 'N/A')}")
        return profile
    else:
        logging.warning(f"No profile data found for {ticker}.")
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
    if not ticker or not isinstance(ticker, str):
        logging.error("Invalid ticker provided to get_historical_prices")
        return None
        
    ticker = ticker.upper().strip()
    url = f"{BASE_URL}/historical-price-full/{ticker}?apikey={get_fmp_api_key()}"
    if limit and isinstance(limit, int) and limit > 0:
        url += f"&limit={limit}"
    
    data = _make_api_request(url, ticker=ticker)
    if not data:
        return None
        
    if 'historical' in data and data['historical']:
        historical_data = data['historical']
        
        # Validate data structure
        required_fields = ['date', 'close', 'open', 'high', 'low']
        if historical_data and all(field in historical_data[0] for field in required_fields):
            logging.info(f"Successfully fetched {len(historical_data)} historical price records for {ticker}")
            return historical_data
        else:
            logging.warning(f"Historical price data missing required fields for {ticker}")
            return None
    else:
        logging.warning(f"No historical price data found for {ticker}.")
        return None

def _validate_date_input(date_input, param_name="date"):
    """Validate and convert date input to datetime.date object."""
    if not date_input:
        logging.warning(f"{param_name} is required")
        return None
        
    try:
        if isinstance(date_input, str):
            # Try common date formats
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y']:
                try:
                    return datetime.datetime.strptime(date_input, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Unsupported date format: {date_input}")
        elif isinstance(date_input, datetime.datetime):
            return date_input.date()
        elif isinstance(date_input, datetime.date):
            return date_input
        else:
            raise ValueError(f"Unsupported date type: {type(date_input)}")
    except Exception as e:
        logging.error(f"Error validating {param_name}: {e}")
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
    if not ticker or not isinstance(ticker, str):
        logging.error("Invalid ticker provided to calculate_stock_performance")
        return None
        
    call_date = _validate_date_input(call_date, "call_date")
    if not call_date:
        return None
        
    ticker = ticker.upper().strip()
        
    try:
        # Fetch historical prices if not provided
        if historical_prices is None:
            historical_prices = get_historical_prices(ticker)
            
        if not historical_prices:
            logging.warning(f"No historical prices available for {ticker}")
            return None

        df = pd.DataFrame(historical_prices)
        
        # Validate DataFrame structure
        required_columns = ['date', 'close']
        if not all(col in df.columns for col in required_columns):
            logging.error(f"Historical price data missing required columns for {ticker}")
            return None
            
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date', 'close'])
        
        if df.empty:
            logging.warning(f"No valid price data after cleaning for {ticker}")
            return None
            
        df = df.set_index('date').sort_index()

        call_date_dt = pd.to_datetime(call_date)

        # Find the price at call date (or closest prior date)
        price_at_call_series = df.loc[df.index <= call_date_dt, 'close']
        if price_at_call_series.empty:
            logging.warning(f"No price data available at or before call date {call_date} for {ticker}")
            return None
        price_at_call = float(price_at_call_series.iloc[-1])

        # Calculate future dates
        one_week_later = call_date_dt + pd.Timedelta(weeks=1)
        one_month_later = call_date_dt + pd.Timedelta(days=30)
        three_month_later = call_date_dt + pd.Timedelta(days=90)

        # Get prices at future dates (or closest available)
        def get_next_available_price(target_date):
            future_prices = df.loc[df.index >= target_date, 'close']
            if not future_prices.empty:
                return float(future_prices.iloc[0])
            return None

        price_1_week = get_next_available_price(one_week_later)
        price_1_month = get_next_available_price(one_month_later)
        price_3_month = get_next_available_price(three_month_later)

        # Calculate performance percentages
        def safe_performance_calc(future_price, base_price):
            if future_price is not None and base_price and base_price != 0:
                return (future_price - base_price) / base_price
            return None

        performance_1_week = safe_performance_calc(price_1_week, price_at_call)
        performance_1_month = safe_performance_calc(price_1_month, price_at_call)
        performance_3_month = safe_performance_calc(price_3_month, price_at_call)

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
    if not ticker or not isinstance(ticker, str):
        logging.error("Invalid ticker provided to get_financial_statements")
        return None
        
    if period not in ["quarter", "annual"]:
        logging.error(f"Invalid period '{period}'. Must be 'quarter' or 'annual'")
        return None
        
    if not isinstance(limit, int) or limit < 1:
        logging.error(f"Invalid limit '{limit}'. Must be positive integer")
        return None
        
    ticker = ticker.upper().strip()
    
    income_url = f"{BASE_URL}/income-statement/{ticker}?period={period}&limit={limit}&apikey={get_fmp_api_key()}"
    balance_url = f"{BASE_URL}/balance-sheet-statement/{ticker}?period={period}&limit={limit}&apikey={get_fmp_api_key()}"
    
    income_statement = _make_api_request(income_url, ticker=ticker)
    if not income_statement:
        return None
        
    balance_sheet = _make_api_request(balance_url, ticker=ticker)
    if not balance_sheet:
        return None

    if income_statement and balance_sheet:
        result = {
            "income_statement": income_statement[0] if limit == 1 and income_statement else income_statement,
            "balance_sheet": balance_sheet[0] if limit == 1 and balance_sheet else balance_sheet
        }
        logging.info(f"Successfully fetched financial statements for {ticker}.")
        return result
    else:
        logging.warning(f"Incomplete financial statements found for {ticker}.")
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
    if not ticker or not isinstance(ticker, str):
        logging.error("Invalid ticker provided to get_stock_quote")
        return None
        
    ticker = ticker.upper().strip()
    url = f"{BASE_URL}/quote/{ticker}?apikey={get_fmp_api_key()}"
    
    data = _make_api_request(url, ticker=ticker)
    if not data:
        return None
        
    if len(data) > 0:
        quote = data[0]
        # Validate essential fields
        if 'symbol' not in quote or 'price' not in quote:
            logging.warning(f"Incomplete quote data for {ticker}")
            return None
            
        logging.info(f"Successfully fetched quote for {ticker}: ${quote.get('price', 'N/A')}")
        return quote
    else:
        logging.warning(f"No quote data found for {ticker}.")
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
    if not tickers or not isinstance(tickers, list):
        logging.error("Invalid tickers list provided to batch_fetch_company_profiles")
        return []
        
    results = []
    
    for i, ticker in enumerate(tickers):
        if not ticker or not isinstance(ticker, str):
            logging.warning(f"Skipping invalid ticker at position {i}: {ticker}")
            results.append(None)
            continue
            
        logging.info(f"Fetching profile {i+1}/{len(tickers)}: {ticker}")
        result = get_company_profile(ticker)
        results.append(result)
        
        # Small delay to be respectful to API
        if i < len(tickers) - 1:  # Don't sleep after last request
            time.sleep(0.1)
        
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
    if not tickers or not isinstance(tickers, list):
        logging.error("Invalid tickers list provided to batch_fetch_historical_prices")
        return {}
        
    results = {}
    
    for i, ticker in enumerate(tickers):
        if not ticker or not isinstance(ticker, str):
            logging.warning(f"Skipping invalid ticker at position {i}: {ticker}")
            results[ticker] = None
            continue
            
        logging.info(f"Fetching historical prices {i+1}/{len(tickers)}: {ticker}")
        historical_data = get_historical_prices(ticker, limit)
        results[ticker] = historical_data
        
        # Small delay to be respectful to API
        if i < len(tickers) - 1:  # Don't sleep after last request
            time.sleep(0.1)
        
    return results

def get_market_summary():
    """
    Fetches overall market summary data.
    
    Returns:
        dict: Market summary data including major indices
        None: If market summary could not be fetched
    """
    # Get data for major indices
    indices = ["^GSPC", "^DJI", "^IXIC"]  # S&P 500, Dow Jones, NASDAQ
    url = f"{BASE_URL}/quote/{','.join(indices)}?apikey={get_fmp_api_key()}"
    
    data = _make_api_request(url)
    if not data:
        return None
        
    if data:
        market_data = {
            'sp500': next((item for item in data if item.get('symbol') == '^GSPC'), None),
            'dow_jones': next((item for item in data if item.get('symbol') == '^DJI'), None),
            'nasdaq': next((item for item in data if item.get('symbol') == '^IXIC'), None)
        }
        
        # Verify we got at least some data
        if any(market_data.values()):
            logging.info("Successfully fetched market summary")
            return market_data
        else:
            logging.warning("No market data found in response")
            return None
    else:
        logging.warning("No market summary data found.")
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
    if ticker:
        if not isinstance(ticker, str):
            logging.error("Invalid ticker provided to get_earnings_calendar")
            return None
        ticker = ticker.upper().strip()
        url = f"{BASE_URL}/historical/earning_calendar/{ticker}?apikey={get_fmp_api_key()}"
    else:
        url = f"{BASE_URL}/earning_calendar?apikey={get_fmp_api_key()}"
    
    data = _make_api_request(url, ticker=ticker)
    if data:
        logging.info(f"Successfully fetched earnings calendar{' for ' + ticker if ticker else ''}")
        return data
    else:
        logging.warning(f"No earnings calendar data found{' for ' + ticker if ticker else ''}.")
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
            
    except Exception as e:
        logging.error(f"Error validating {data_type} data: {e}")
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
    if not ticker or not isinstance(ticker, str):
        logging.error("Invalid ticker provided to get_price_at_date")
        return None
        
    target_date = _validate_date_input(target_date, "target_date")
    if not target_date:
        return None
        
    ticker = ticker.upper().strip()
    
    try:
        # Fetch historical prices if not provided
        if historical_prices is None:
            historical_prices = get_historical_prices(ticker)
            
        if not historical_prices:
            return None

        df = pd.DataFrame(historical_prices)
        
        # Validate DataFrame structure
        if 'date' not in df.columns or 'close' not in df.columns:
            logging.error(f"Historical price data missing required columns for {ticker}")
            return None
            
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date', 'close'])
        
        if df.empty:
            logging.warning(f"No valid price data for {ticker}")
            return None
            
        df['date'] = df['date'].dt.date
        df = df.sort_values('date')

        # Find exact match first
        exact_match = df[df['date'] == target_date]
        if not exact_match.empty:
            row = exact_match.iloc[0]
            return {
                'price': float(row['close']),
                'date': row['date'].strftime('%Y-%m-%d'),
                'closest_match': True
            }

        # Find closest available date before target
        before_target = df[df['date'] <= target_date]
        if not before_target.empty:
            row = before_target.iloc[-1]  # Most recent date before target
            return {
                'price': float(row['close']),
                'date': row['date'].strftime('%Y-%m-%d'),
                'closest_match': False
            }

        # If no date before target, get the earliest available
        if not df.empty:
            row = df.iloc[0]
            return {
                'price': float(row['close']),
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
    if not ticker or not isinstance(ticker, str):
        logging.error("Invalid ticker provided to compare_performance_to_market")
        return None
        
    call_date = _validate_date_input(call_date, "call_date")
    if not call_date:
        return None
        
    ticker = ticker.upper().strip()
    
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
        def safe_relative_calc(stock_perf_val, market_perf_val):
            if stock_perf_val is not None and market_perf_val is not None:
                return stock_perf_val - market_perf_val
            return None

        relative_1_week = safe_relative_calc(stock_perf['performance_1_week'], sp500_perf['performance_1_week'])
        relative_1_month = safe_relative_calc(stock_perf['performance_1_month'], sp500_perf['performance_1_month'])
        relative_3_month = safe_relative_calc(stock_perf['performance_3_month'], sp500_perf['performance_3_month'])

        return {
            'stock_performance': stock_perf,
            'sp500_performance': sp500_perf,
            'relative_performance': {
                'vs_sp500_1_week': relative_1_week,
                'vs_sp500_1_month': relative_1_month,
                'vs_sp500_3_month': relative_3_month
            },
            'outperformed_market': {
                '1_week': relative_1_week > 0 if relative_1_week is not None else None,
                '1_month': relative_1_month > 0 if relative_1_month is not None else None,
                '3_month': relative_3_month > 0 if relative_3_month is not None else None
            }
        }
        
    except Exception as e:
        logging.error(f"Error comparing performance to market for {ticker}: {e}")
        return None