from bs4 import BeautifulSoup
import requests
from googlesearch import search
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def find_latest_transcript_url(ticker):
    """
    Finds the URL of the most recent earnings call transcript for a given ticker on fool.com.
    
    Args:
        ticker (str): The stock ticker symbol.
    """
    query = f"site:fool.com {ticker} earnings call transcript"
    try:
        # The search function returns an iterator. Get the first result.
        search_results = search(query)
        first_result = next(search_results, None)
        
        if first_result:
            return first_result
        else:
            logging.warning(f"Could not find a transcript URL for {ticker} on fool.com.")
            return None
    except Exception as e:
        logging.error(f"Error finding transcript URL for {ticker}: {e}")
        return None

def find_transcript_url_by_quarter(ticker, quarter, year):
    """
    Finds a specific earnings call transcript by quarter and year on fool.com.
    
    Args:
        ticker (str): Stock ticker symbol
        quarter (str): Quarter like "Q1", "Q2", "Q3", "Q4" 
        year (int): Year like 2024, 2023
    """
    query = f"site:fool.com {ticker} {quarter} {year} earnings call transcript"
    try:
        for result in search(query):
            # Motley Fool URLs follow a pattern like:
            # /earnings/call-transcripts/2024/01/25/apple-aapl-q1-2024-earnings-call-transcript/
            # We need to be careful with the quarter format in the URL (e.g., q1, q2)
            if f"-{quarter.lower()}-{year}-earnings" in result:
                return result
        logging.warning(f"Could not find {quarter} {year} transcript URL for {ticker} on fool.com.")
        return None
    except Exception as e:
        logging.error(f"Error finding {quarter} {year} transcript URL for {ticker}: {e}")
        return None

def get_transcript_from_fool(url):
    """
    Scrapes the earnings call transcript from a Motley Fool URL.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        article_body = soup.find('div', class_='article-body')

        if article_body:
            return article_body.get_text(separator='\n', strip=True)
        else:
            logging.warning("Could not find the article body in the transcript.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching transcript from Motley Fool: {e}")
        return None
