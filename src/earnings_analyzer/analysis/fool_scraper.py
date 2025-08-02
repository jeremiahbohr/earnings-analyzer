from bs4 import BeautifulSoup
import requests
from googlesearch import search
import logging
import re
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

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
            
        # Scrape the transcript content
        logging.info(f"Scraping transcript from {transcript_url}...")
        transcript_text = get_transcript_from_fool(transcript_url)
        
        if not transcript_text:
            logging.error(f"Could not scrape transcript content from {transcript_url}")
            return None
            
        # Parse call details from URL or use provided parameters
        call_date, parsed_quarter, parsed_year = _parse_call_details_from_url(transcript_url)
        
        # Use provided parameters if available, otherwise use parsed values
        final_quarter = quarter.upper() if quarter else parsed_quarter
        final_year = year if year else parsed_year
        
        # If we still don't have quarter/year and user provided them, construct date
        if quarter and year and not call_date:
            try:
                month_map = {"Q1": 1, "Q2": 4, "Q3": 7, "Q4": 10}
                month = month_map.get(quarter.upper())
                if month:
                    call_date = datetime.date(year, month, 1)
            except ValueError:
                logging.warning(f"Could not construct date from quarter {quarter} and year {year}")
            
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
    query = f"site:fool.com {ticker} earnings call transcript"
    try:
        # The search function returns an iterator. Get the first result.
        search_results = search(query)
        first_result = next(search_results, None)
        
        if first_result:
            logging.info(f"Found latest transcript URL for {ticker}: {first_result}")
            return first_result
        else:
            logging.warning(f"Could not find a transcript URL for {ticker} on fool.com.")
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
    query = f"site:fool.com {ticker} {quarter} {year} earnings call transcript"
    try:
        for result in search(query):
            pattern = rf'-{re.escape(ticker.lower())}-{quarter.lower()}-{year}-earnings'
            
            if re.search(pattern, result.lower()):
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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        article_body = soup.find('div', class_='article-body')

        if article_body:
            transcript_text = article_body.get_text(separator='\n', strip=True)
            logging.info(f"Successfully scraped transcript from {url} ({len(transcript_text)} characters)")
            return transcript_text
        else:
            logging.warning(f"Could not find the article body in the transcript at {url}")
            return None

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP Error fetching transcript from Motley Fool (Status: {e.response.status_code}): {e}. Check if the URL is correct or if you are blocked (e.g., by a VPN).")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Network Error fetching transcript from Motley Fool: {e}. Check your internet connection.")
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
    results = []
    
    for i, ticker in enumerate(tickers):
        logging.info(f"Processing ticker {i+1}/{len(tickers)}: {ticker}")
        result = fetch_transcript(ticker, quarter, year)
        results.append(result)
        
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
    keywords_str = " ".join(keywords)
    query = f"site:fool.com {ticker} earnings call transcript {keywords_str}"
    
    try:
        urls = []
        search_results = search(query)
        
        for i, result in enumerate(search_results):
            if i >= max_results:
                break
            if "earnings-call-transcript" in result:
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
    if not isinstance(transcript_result['transcript_text'], str):
        return False
    if len(transcript_result['transcript_text'].strip()) == 0:
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
    try:
        # Pattern: /earnings/call-transcripts/YYYY/MM/DD/company-ticker-q#-YYYY-earnings-call-transcript/
        pattern = r'/earnings/call-transcripts/(\d{4})/(\d{2})/(\d{2})/.*-([a-zA-Z]+)-q(\d)-(\d{4})-earnings-call-transcript'
        match = re.search(pattern, url)
        
        if match:
            year_url, month, day, ticker, quarter_num, year_quarter = match.groups()
            return {
                'url_date': f"{year_url}-{month}-{day}",
                'ticker': ticker.upper(),
                'quarter': f"Q{quarter_num}",
                'year': int(year_quarter),
                'month': int(month),
                'day': int(day)
            }
        else:
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
    
    # Pattern: /YYYY/MM/DD/...q#-YYYY-earnings-call-transcript
    match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/.+-q(\d)-(\d{4})-earnings-call-transcript', transcript_url)
    if match:
        year_str, month_str, day_str, quarter_num_str, year_q_str = match.groups()
        try:
            call_date = datetime.date(int(year_str), int(month_str), int(day_str))
            quarter = f"Q{quarter_num_str}"
            year = int(year_q_str)
        except ValueError:
            logging.warning("Could not parse date/quarter/year from URL")
    
    return call_date, quarter, year