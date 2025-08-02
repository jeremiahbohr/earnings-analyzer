from bs4 import BeautifulSoup
import requests
from googlesearch import search
import logging
import re
import datetime
import time
import random
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# User agent rotation for web scraping
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def _get_random_headers():
    """Get randomized headers for web scraping."""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

def _validate_ticker(ticker):
    """Validate ticker symbol format."""
    if not ticker or not isinstance(ticker, str):
        return None
    
    ticker = ticker.upper().strip()
    
    # Basic ticker validation (1-5 alphanumeric characters)
    if not re.match(r'^[A-Z0-9]{1,5}$', ticker):
        logging.warning(f"Invalid ticker format: {ticker}")
        return None
        
    return ticker

def _validate_quarter(quarter):
    """Validate quarter format."""
    if not quarter:
        return None
        
    if not isinstance(quarter, str):
        logging.error(f"Quarter must be string, got {type(quarter)}")
        return None
        
    quarter = quarter.upper().strip()
    
    if quarter not in ['Q1', 'Q2', 'Q3', 'Q4']:
        logging.error(f"Invalid quarter: {quarter}. Must be Q1, Q2, Q3, or Q4")
        return None
        
    return quarter

def _validate_year(year):
    """Validate year format."""
    if not year:
        return None
        
    if isinstance(year, str):
        try:
            year = int(year)
        except ValueError:
            logging.error(f"Invalid year format: {year}")
            return None
    
    if not isinstance(year, int):
        logging.error(f"Year must be integer, got {type(year)}")
        return None
        
    current_year = datetime.datetime.now().year
    if year < 2000 or year > current_year:
        logging.error(f"Year {year} out of reasonable range (2000-{current_year})")
        return None
        
    return year

def _validate_date_components(year, month, day):
    """Safely validate date components before creating datetime object."""
    try:
        # Check basic ranges
        if not (1 <= month <= 12):
            return False
        if not (1 <= day <= 31):
            return False
            
        # Try to create the date
        datetime.date(year, month, day)
        return True
    except (ValueError, TypeError):
        return False

def _is_valid_transcript_url(url):
    """Validate that URL appears to be a Motley Fool transcript."""
    if not url or not isinstance(url, str):
        return False
        
    try:
        parsed = urlparse(url)
        if 'fool.com' not in parsed.netloc:
            return False
            
        # Check for transcript-specific patterns
        transcript_patterns = [
            'earnings-call-transcript',
            'earnings/call-transcripts',
            '/transcripts/'
        ]
        
        return any(pattern in url.lower() for pattern in transcript_patterns)
    except Exception:
        return False

def _handle_request_with_retry(url, max_retries=3, base_delay=1):
    """Make HTTP request with retry logic and rate limiting."""
    for attempt in range(max_retries):
        try:
            # Random delay between requests to avoid rate limiting
            if attempt > 0:
                delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0.5, 1.5)
                logging.info(f"Retry attempt {attempt + 1}, waiting {delay:.1f} seconds...")
                time.sleep(delay)
            
            headers = _get_random_headers()
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 403:
                logging.warning(f"Access forbidden (403) for {url}. May be blocked or rate limited.")
                if attempt < max_retries - 1:
                    continue
                else:
                    return None
                    
            elif response.status_code == 429:
                retry_after = response.headers.get('Retry-After', '60')
                try:
                    wait_time = int(retry_after)
                except ValueError:
                    wait_time = 60
                logging.warning(f"Rate limited (429). Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
                
            response.raise_for_status()
            return response
            
        except requests.exceptions.Timeout:
            logging.warning(f"Request timeout (attempt {attempt + 1}/{max_retries}) for {url}")
            if attempt == max_retries - 1:
                logging.error(f"Final timeout after {max_retries} attempts")
                return None
                
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                logging.error(f"Final connection error after {max_retries} attempts")
                return None
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [403, 429]:
                continue  # These are handled above
            else:
                logging.error(f"HTTP Error {e.response.status_code}: {e}")
                return None
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error: {e}")
            return None
            
    return None

def fetch_transcript(ticker, quarter=None, year=None):
    """
    Main composable function to fetch earnings call transcript for a given ticker.
    
    This combines URL finding and transcript scraping into a single convenient function
    that's perfect for use in data pipelines.
    
    Args:
        ticker (str): The stock ticker symbol.
        quarter (str, optional): Quarter like "Q1", "Q2", "Q3", "Q4"
        year (int, optional): Year like 2024, 2023
        
    Returns:
        dict: Contains transcript_text, transcript_url, call_date, quarter, year, ticker
        None: If transcript could not be fetched
    """
    # Validate inputs
    ticker = _validate_ticker(ticker)
    if not ticker:
        logging.error("Invalid ticker provided to fetch_transcript")
        return None
        
    if quarter:
        quarter = _validate_quarter(quarter)
        if not quarter:
            return None
            
    if year:
        year = _validate_year(year)
        if not year:
            return None
    
    try:
        # Find the transcript URL
        if quarter and year:
            logging.info(f"Finding {quarter} {year} transcript for {ticker}...")
            transcript_url = find_transcript_url_by_quarter(ticker, quarter, year)
        else:
            logging.info(f"Finding latest transcript for {ticker}...")
            transcript_url = find_latest_transcript_url(ticker)
            
        if not transcript_url:
            logging.error(f"Could not find transcript URL for {ticker}")
            return None
            
        # Validate the URL
        if not _is_valid_transcript_url(transcript_url):
            logging.error(f"Found URL does not appear to be a valid transcript: {transcript_url}")
            return None
            
        # Scrape the transcript content
        logging.info(f"Scraping transcript from {transcript_url}...")
        transcript_text = get_transcript_from_fool(transcript_url)
        
        if not transcript_text:
            logging.error(f"Could not scrape transcript content from {transcript_url}")
            return None
            
        # Validate transcript content
        if len(transcript_text.strip()) < 500:  # Minimum reasonable transcript length
            logging.warning(f"Transcript seems unusually short ({len(transcript_text)} chars) for {ticker}")
            
        # Parse call details from URL or use provided parameters
        call_date, parsed_quarter, parsed_year = _parse_call_details_from_url(transcript_url)
        
        # Use provided parameters if available, otherwise use parsed values
        final_quarter = quarter if quarter else parsed_quarter
        final_year = year if year else parsed_year
        
        # If we still don't have quarter/year and user provided them, construct date
        if quarter and year and not call_date:
            try:
                month_map = {"Q1": 3, "Q2": 6, "Q3": 9, "Q4": 12}  # End of quarter months
                month = month_map.get(quarter)
                if month and _validate_date_components(year, month, 1):
                    call_date = datetime.date(year, month, 1)
            except Exception as e:
                logging.warning(f"Could not construct date from quarter {quarter} and year {year}: {e}")
            
        return {
            'ticker': ticker,
            'transcript_text': transcript_text,
            'transcript_url': transcript_url,
            'call_date': call_date.strftime('%Y-%m-%d') if call_date else None,
            'quarter': final_quarter,
            'year': final_year
        }
        
    except Exception as e:
        logging.error(f"Error fetching transcript for {ticker}: {e}")
        return None

def find_latest_transcript_url(ticker):
    """
    Finds the URL of the most recent earnings call transcript for a given ticker on fool.com.
    
    Args:
        ticker (str): The stock ticker symbol.
        
    Returns:
        str: URL of the most recent transcript
        None: If no transcript URL could be found
    """
    ticker = _validate_ticker(ticker)
    if not ticker:
        return None
        
    query = f"site:fool.com {ticker} earnings call transcript"
    
    try:
        # Add small random delay to avoid being too aggressive
        time.sleep(random.uniform(1, 3))
        
        search_results = search(query, num_results=10, sleep_interval=2)
        
        for result in search_results:
            if _is_valid_transcript_url(result):
                logging.info(f"Found latest transcript URL for {ticker}: {result}")
                return result
                
        logging.warning(f"Could not find a valid transcript URL for {ticker} on fool.com.")
        return None
        
    except Exception as e:
        logging.error(f"Error finding transcript URL for {ticker}: {e}")
        return None

def find_transcript_url_by_quarter(ticker, quarter, year):
    """
    Finds the URL of a specific quarter's earnings call transcript for a given ticker on fool.com.
    
    Args:
        ticker (str): The stock ticker symbol.
        quarter (str): Quarter like "Q1", "Q2", "Q3", "Q4"
        year (int): Year like 2024, 2023
        
    Returns:
        str: URL of the specified quarter's transcript
        None: If no transcript URL could be found
    """
    ticker = _validate_ticker(ticker)
    quarter = _validate_quarter(quarter)
    year = _validate_year(year)
    
    if not all([ticker, quarter, year]):
        return None
        
    query = f"site:fool.com {ticker} {quarter} {year} earnings call transcript"
    
    try:
        # Add small random delay to avoid being too aggressive
        time.sleep(random.uniform(1, 3))
        
        search_results = search(query, num_results=10, sleep_interval=2)
        
        for result in search_results:
            if not _is_valid_transcript_url(result):
                continue
                
            # More flexible pattern matching for quarter and year
            patterns = [
                rf'-{re.escape(ticker.lower())}-{quarter.lower()}-{year}-earnings',
                rf'{quarter.lower()}-{year}.*{ticker.lower()}.*earnings',
                rf'{ticker.lower()}.*{quarter.lower()}.*{year}.*earnings'
            ]
            
            if any(re.search(pattern, result.lower()) for pattern in patterns):
                logging.info(f"Found {quarter} {year} transcript URL for {ticker}: {result}")
                return result
                
        logging.warning(f"Could not find {quarter} {year} transcript URL for {ticker} on fool.com.")
        return None
        
    except Exception as e:
        logging.error(f"Error finding {quarter} {year} transcript URL for {ticker}: {e}")
        return None

def get_transcript_from_fool(url):
    """
    Scrapes the earnings call transcript from a Motley Fool URL.
    
    Args:
        url (str): The Motley Fool transcript URL
        
    Returns:
        str: The transcript text content
        None: If scraping failed
    """
    if not url or not isinstance(url, str):
        logging.error("Invalid URL provided to get_transcript_from_fool")
        return None
        
    if not _is_valid_transcript_url(url):
        logging.error(f"URL does not appear to be a valid Motley Fool transcript: {url}")
        return None
    
    try:
        response = _handle_request_with_retry(url)
        if not response:
            return None
            
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type:
            logging.error(f"Expected HTML content, got {content_type}")
            return None
            
        # Handle encoding properly
        response.encoding = response.apparent_encoding or 'utf-8'
        
        soup = BeautifulSoup(response.content, 'html.parser')

        # Try multiple selectors for article content
        content_selectors = [
            'div.article-body',
            'div.content-body',
            'div.article-content',
            'article',
            'div.post-content',
            'div.entry-content'
        ]
        
        transcript_text = None
        
        for selector in content_selectors:
            article_body = soup.select_one(selector)
            if article_body:
                transcript_text = article_body.get_text(separator='\n', strip=True)
                break
                
        if not transcript_text:
            # Fallback: try to extract any substantial text content
            logging.warning(f"Could not find article body with standard selectors, trying fallback extraction")
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
                
            # Get text from body
            body = soup.find('body')
            if body:
                transcript_text = body.get_text(separator='\n', strip=True)
            else:
                transcript_text = soup.get_text(separator='\n', strip=True)
        
        if transcript_text:
            # Clean up the text
            lines = transcript_text.split('\n')
            # Remove very short lines that are likely navigation/ads
            cleaned_lines = [line.strip() for line in lines if len(line.strip()) > 20]
            transcript_text = '\n'.join(cleaned_lines)
            
            if len(transcript_text.strip()) < 500:
                logging.warning(f"Extracted transcript seems very short: {len(transcript_text)} characters")
                return None
                
            logging.info(f"Successfully scraped transcript from {url} ({len(transcript_text)} characters)")
            return transcript_text
        else:
            logging.warning(f"Could not find any substantial text content in the transcript at {url}")
            return None

    except UnicodeDecodeError as e:
        logging.error(f"Encoding error while scraping transcript from {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error scraping transcript from {url}: {e}")
        return None

def batch_fetch_transcripts(tickers, quarter=None, year=None):
    """
    Fetches transcripts for multiple tickers in batch.
    
    Useful for processing multiple companies efficiently in data pipeline scenarios.
    
    Args:
        tickers (list): List of stock ticker symbols
        quarter (str, optional): Quarter like "Q1", "Q2", "Q3", "Q4"
        year (int, optional): Year like 2024, 2023
        
    Returns:
        list: List of transcript result dictionaries in the same order as input tickers.
              Failed fetches will be None in the corresponding position.
    """
    if not tickers or not isinstance(tickers, list):
        logging.error("Invalid tickers list provided to batch_fetch_transcripts")
        return []
        
    # Validate quarter and year once
    if quarter:
        quarter = _validate_quarter(quarter)
        if not quarter:
            return [None] * len(tickers)
            
    if year:
        year = _validate_year(year)
        if not year:
            return [None] * len(tickers)
    
    results = []
    
    for i, ticker in enumerate(tickers):
        if not ticker or not isinstance(ticker, str):
            logging.warning(f"Skipping invalid ticker at position {i}: {ticker}")
            results.append(None)
            continue
            
        logging.info(f"Processing ticker {i+1}/{len(tickers)}: {ticker}")
        
        try:
            result = fetch_transcript(ticker, quarter, year)
            results.append(result)
        except Exception as e:
            logging.error(f"Error processing ticker {ticker}: {e}")
            results.append(None)
        
        # Rate limiting: wait between requests
        if i < len(tickers) - 1:  # Don't sleep after last request
            delay = random.uniform(3, 7)  # Random delay to appear more human-like
            logging.debug(f"Waiting {delay:.1f} seconds before next request...")
            time.sleep(delay)
        
    return results

def search_transcripts_by_keywords(ticker, keywords, max_results=5):
    """
    Searches for transcripts containing specific keywords.
    
    Args:
        ticker (str): Stock ticker symbol
        keywords (list): List of keywords to search for
        max_results (int): Maximum number of results to return
        
    Returns:
        list: List of transcript URLs that match the search criteria
    """
    ticker = _validate_ticker(ticker)
    if not ticker:
        return []
        
    if not keywords or not isinstance(keywords, list):
        logging.error("Keywords must be a non-empty list")
        return []
        
    if not isinstance(max_results, int) or max_results < 1:
        logging.error("max_results must be a positive integer")
        return []
    
    keywords_str = " ".join(str(kw) for kw in keywords)
    query = f"site:fool.com {ticker} earnings call transcript {keywords_str}"
    
    try:
        urls = []
        search_results = search(query, num_results=max_results * 2, sleep_interval=2)  # Get more to filter
        
        for result in search_results:
            if len(urls) >= max_results:
                break
                
            if _is_valid_transcript_url(result):
                urls.append(result)
                
        logging.info(f"Found {len(urls)} transcript URLs for {ticker} with keywords: {keywords}")
        return urls
        
    except Exception as e:
        logging.error(f"Error searching for transcripts with keywords {keywords} for {ticker}: {e}")
        return []

def validate_transcript_result(transcript_result):
    """
    Validates that a transcript fetch result has the expected structure.
    
    Args:
        transcript_result (dict): The result from fetch_transcript()
        
    Returns:
        bool: True if the result is valid, False otherwise
    """
    if not isinstance(transcript_result, dict):
        return False
        
    required_fields = ['ticker', 'transcript_text', 'transcript_url']
    
    for field in required_fields:
        if field not in transcript_result:
            return False
        if not transcript_result[field]:  # Check for None or empty string
            return False
            
    # Additional validation
    transcript_text = transcript_result.get('transcript_text')
    if not isinstance(transcript_text, str):
        return False
    if len(transcript_text.strip()) < 100:  # Minimum reasonable length
        return False
        
    # Validate URL format
    transcript_url = transcript_result.get('transcript_url')
    if not _is_valid_transcript_url(transcript_url):
        return False
        
    return True

def get_transcript_metadata_from_url(url):
    """
    Extracts metadata (quarter, year, ticker) from a Motley Fool transcript URL.
    
    Args:
        url (str): The Motley Fool transcript URL
        
    Returns:
        dict: Contains extracted metadata like quarter, year, ticker
        None: If metadata could not be extracted
    """
    if not url or not isinstance(url, str):
        return None
        
    if not _is_valid_transcript_url(url):
        return None
    
    try:
        # Multiple patterns to handle different URL formats
        patterns = [
            # Pattern: /earnings/call-transcripts/YYYY/MM/DD/company-ticker-q#-YYYY-earnings-call-transcript/
            r'/earnings/call-transcripts/(\d{4})/(\d{2})/(\d{2})/.*-([a-zA-Z]+)-q(\d)-(\d{4})-earnings-call-transcript',
            # Alternative pattern: /transcripts/YYYY/MM/DD/ticker-q#-YYYY/
            r'/transcripts/(\d{4})/(\d{2})/(\d{2})/([a-zA-Z]+)-q(\d)-(\d{4})',
            # More flexible pattern
            r'(\d{4})/(\d{2})/(\d{2}).*([a-zA-Z]{2,5}).*q(\d).*(\d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if len(groups) >= 6:
                    year_url, month, day, ticker, quarter_num, year_quarter = groups[:6]
                    
                    # Validate extracted data
                    if not _validate_date_components(int(year_url), int(month), int(day)):
                        continue
                        
                    if not _validate_ticker(ticker):
                        continue
                        
                    if quarter_num not in ['1', '2', '3', '4']:
                        continue
                        
                    return {
                        'url_date': f"{year_url}-{month}-{day}",
                        'ticker': ticker.upper(),
                        'quarter': f"Q{quarter_num}",
                        'year': int(year_quarter),
                        'month': int(month),
                        'day': int(day)
                    }
        
        logging.warning(f"Could not extract metadata from URL: {url}")
        return None
            
    except Exception as e:
        logging.error(f"Error extracting metadata from URL {url}: {e}")
        return None

def _parse_call_details_from_url(transcript_url):
    """
    Helper function to parse call date, quarter, and year from transcript URL.
    
    Args:
        transcript_url (str): The Motley Fool transcript URL
        
    Returns:
        tuple: (call_date, quarter, year)
    """
    call_date = None
    quarter = None
    year = None
    
    try:
        metadata = get_transcript_metadata_from_url(transcript_url)
        if metadata:
            quarter = metadata.get('quarter')
            year = metadata.get('year')
            
            # Construct call date from metadata
            url_year = metadata.get('year')
            url_month = metadata.get('month')
            url_day = metadata.get('day')
            
            if all([url_year, url_month, url_day]):
                if _validate_date_components(url_year, url_month, url_day):
                    call_date = datetime.date(url_year, url_month, url_day)
    except Exception as e:
        logging.warning(f"Could not parse date/quarter/year from URL: {e}")
    
    return call_date, quarter, year

def check_transcript_availability(ticker, quarter=None, year=None):
    """
    Check if a transcript is available without downloading it.
    
    Args:
        ticker (str): Stock ticker symbol
        quarter (str, optional): Quarter like "Q1", "Q2", "Q3", "Q4"
        year (int, optional): Year like 2024, 2023
        
    Returns:
        dict: Contains availability status and URL if found
    """
    ticker = _validate_ticker(ticker)
    if not ticker:
        return {'available': False, 'error': 'Invalid ticker'}
    
    try:
        if quarter and year:
            quarter = _validate_quarter(quarter)
            year = _validate_year(year)
            if not quarter or not year:
                return {'available': False, 'error': 'Invalid quarter or year'}
            url = find_transcript_url_by_quarter(ticker, quarter, year)
        else:
            url = find_latest_transcript_url(ticker)
            
        if url:
            return {
                'available': True,
                'url': url,
                'ticker': ticker,
                'quarter': quarter,
                'year': year
            }
        else:
            return {
                'available': False,
                'ticker': ticker,
                'quarter': quarter,
                'year': year,
                'error': 'No transcript URL found'
            }
            
    except Exception as e:
        return {
            'available': False,
            'ticker': ticker,
            'error': str(e)
        }