"""
Earnings Analyzer - Composable API

This module provides the main composable API surface for the earnings analyzer package.
These functions can be used independently or chained together in data pipelines.

All functions return pandas-friendly dictionaries and do not perform any database operations.
For high-level orchestration with database caching, use the EarningsAnalyzer class.

Usage Examples:
    # Composable approach (in-memory, no database)
    from earnings_analyzer.api import fetch_transcript, score_sentiment, fetch_company_profile
    
    transcript = fetch_transcript("AAPL")
    sentiment = score_sentiment(transcript['transcript_text'])
    profile = fetch_company_profile("AAPL")
    
    # Database-backed approach
    from earnings_analyzer.api import EarningsAnalyzer
    
    analyzer = EarningsAnalyzer()
    results = analyzer.analyze("AAPL")  # Automatically cached
"""

import logging
from typing import Dict, List, Optional, Union

# Import composable functions from their canonical source modules
from .analysis.fool_scraper import (
    fetch_transcript,
    find_latest_transcript_url,
    find_transcript_url_by_quarter,
    get_transcript_from_fool,
    batch_fetch_transcripts,
    search_transcripts_by_keywords,
    validate_transcript_result,
    get_transcript_metadata_from_url,
    check_transcript_availability
)

from .analysis.sentiment_analyzer import (
    score_sentiment,
    batch_score_sentiment,
    validate_sentiment_result,
    get_sentiment_summary,
    compare_sentiment_trends
)

from .data.financial_data_fetcher import (
    fetch_company_profile,
    get_company_profile,
    get_historical_prices,
    calculate_stock_performance,
    get_financial_statements,
    get_stock_quote,
    batch_fetch_company_profiles,
    batch_fetch_historical_prices,
    get_market_summary,
    get_earnings_calendar,
    validate_financial_data,
    get_price_at_date,
    compare_performance_to_market
)

from .analyzer import EarningsAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Core composable functions - these are the main API surface for in-memory usage
__all__ = [
    # === CORE COMPOSABLE FUNCTIONS ===
    # These are the primary building blocks for custom data pipelines
    'fetch_transcript',           # Get earnings call transcript
    'score_sentiment',           # Analyze transcript sentiment  
    'fetch_company_profile',     # Get company metadata
    'calculate_stock_performance', # Calculate performance metrics
    
    # === TRANSCRIPT FUNCTIONS ===
    'find_latest_transcript_url',
    'find_transcript_url_by_quarter', 
    'get_transcript_from_fool',
    'batch_fetch_transcripts',
    'search_transcripts_by_keywords',
    'get_transcript_metadata_from_url',
    'check_transcript_availability',
    
    # === SENTIMENT ANALYSIS FUNCTIONS ===
    'batch_score_sentiment',
    'get_sentiment_summary',
    'compare_sentiment_trends',
    
    # === FINANCIAL DATA FUNCTIONS ===
    'get_company_profile',       # Alternative name for fetch_company_profile
    'get_historical_prices',
    'get_financial_statements', 
    'get_stock_quote',
    'batch_fetch_company_profiles',
    'batch_fetch_historical_prices',
    'get_market_summary',
    'get_earnings_calendar',
    'get_price_at_date',
    'compare_performance_to_market',
    
    # === VALIDATION FUNCTIONS ===
    'validate_transcript_result',
    'validate_sentiment_result', 
    'validate_financial_data',
    
    # === HIGH-LEVEL ORCHESTRATOR ===
    # Database-backed analysis with automatic caching
    'EarningsAnalyzer',
    
    # === CONVENIENCE FUNCTIONS ===
    'analyze_earnings_call',
    'quick_sentiment_analysis'
]

def _validate_ticker_input(ticker: str, function_name: str) -> Optional[str]:
    """Validate and normalize ticker input."""
    if not ticker or not isinstance(ticker, str):
        logging.error(f"{function_name}: ticker must be a non-empty string")
        return None
    
    ticker = ticker.upper().strip()
    if not ticker:
        logging.error(f"{function_name}: ticker cannot be empty")
        return None
        
    return ticker

def _validate_quarter_year(quarter: Optional[str], year: Optional[int], function_name: str) -> tuple:
    """Validate quarter and year inputs."""
    if quarter:
        if not isinstance(quarter, str):
            logging.error(f"{function_name}: quarter must be a string")
            return None, None
        quarter = quarter.upper().strip()
        if quarter not in ['Q1', 'Q2', 'Q3', 'Q4']:
            logging.error(f"{function_name}: quarter must be Q1, Q2, Q3, or Q4")
            return None, None
    
    if year:
        if not isinstance(year, int):
            logging.error(f"{function_name}: year must be an integer")
            return None, None
        if year < 2000 or year > 2030:
            logging.error(f"{function_name}: year must be between 2000 and 2030")
            return None, None
    
    return quarter, year

def analyze_earnings_call(ticker: str, quarter: Optional[str] = None, year: Optional[int] = None, 
                         model_name: str = "gemini-2.5-flash", custom_prompt: Optional[str] = None) -> Optional[Dict]:
    """
    Convenience function that performs a complete earnings call analysis using composable functions.
    
    This provides a middle ground between individual composable functions and the full
    EarningsAnalyzer class. Results are returned in-memory without database storage.
    
    Args:
        ticker (str): Stock ticker symbol
        quarter (str, optional): Quarter like "Q1", "Q2", "Q3", "Q4"  
        year (int, optional): Year like 2024, 2023
        model_name (str): Gemini model to use for sentiment analysis
        custom_prompt (str, optional): Complete custom prompt for sentiment analysis. Overrides default prompt.
        
    Returns:
        dict: Complete analysis results with keys:
            - transcript: Full transcript data
            - sentiment: Sentiment analysis results  
            - profile: Company profile data
            - stock_performance: Performance metrics (if historical data available)
        None: If any critical component fails
    """
    # Validate inputs
    ticker = _validate_ticker_input(ticker, "analyze_earnings_call")
    if not ticker:
        return None
    
    quarter, year = _validate_quarter_year(quarter, year, "analyze_earnings_call")
    if quarter is None and quarter is not None:  # Validation failed
        return None
    if year is None and year is not None:  # Validation failed
        return None
    
    if not isinstance(model_name, str) or not model_name.strip():
        logging.error("analyze_earnings_call: model_name must be a non-empty string")
        return None
    
    if custom_prompt is not None and not isinstance(custom_prompt, str):
        logging.error("analyze_earnings_call: custom_prompt must be a string")
        return None
    
    try:
        logging.info(f"Starting complete analysis for {ticker}" + 
                    (f" {quarter} {year}" if quarter and year else ""))
        
        # Step 1: Fetch transcript
        logging.info(f"Step 1/4: Fetching transcript for {ticker}...")
        transcript = fetch_transcript(ticker, quarter, year)
        if not transcript:
            logging.error(f"Failed to fetch transcript for {ticker}")
            return None
        
        # Validate transcript
        if not validate_transcript_result(transcript):
            logging.error(f"Invalid transcript result for {ticker}")
            return None
            
        logging.info(f"✓ Successfully fetched transcript ({len(transcript['transcript_text'])} characters)")
            
        # Step 2: Analyze sentiment (with optional custom prompt)
        logging.info(f"Step 2/4: Analyzing sentiment for {ticker}...")
        sentiment = score_sentiment(transcript['transcript_text'], model_name, custom_prompt)
        if not sentiment:
            logging.error(f"Failed to analyze sentiment for {ticker}")
            return None
        
        # Validate sentiment (only for default prompts)
        if not custom_prompt and not validate_sentiment_result(sentiment):
            logging.error(f"Invalid sentiment result for {ticker}")
            return None
            
        logging.info(f"✓ Successfully analyzed sentiment" + 
                    (f" (score: {sentiment.get('overall_sentiment_score', 'N/A')})" if not custom_prompt else ""))
            
        # Step 3: Get company profile
        logging.info(f"Step 3/4: Fetching company profile for {ticker}...")
        profile = fetch_company_profile(ticker)
        if not profile:
            logging.error(f"Failed to fetch company profile for {ticker}")
            return None
        
        # Validate profile
        if not validate_financial_data(profile, "profile"):
            logging.error(f"Invalid company profile for {ticker}")
            return None
            
        logging.info(f"✓ Successfully fetched profile for {profile.get('companyName', ticker)}")
            
        # Step 4: Calculate stock performance (optional - may fail without affecting result)
        stock_performance = None
        call_date = transcript.get('call_date')
        
        if call_date:
            logging.info(f"Step 4/4: Calculating stock performance for {ticker}...")
            try:
                stock_performance = calculate_stock_performance(ticker, call_date)
                if stock_performance and validate_financial_data(stock_performance, "stock_performance"):
                    logging.info(f"✓ Successfully calculated stock performance")
                else:
                    logging.warning(f"Could not calculate valid stock performance for {ticker}")
                    stock_performance = None
            except Exception as e:
                logging.warning(f"Error calculating stock performance for {ticker}: {e}")
                stock_performance = None
        else:
            logging.warning(f"No call date available, skipping stock performance calculation")
        
        result = {
            'transcript': transcript,
            'sentiment': sentiment,
            'profile': profile,
            'stock_performance': stock_performance,
            'analysis_metadata': {
                'ticker': ticker,
                'quarter': quarter,
                'year': year,
                'model_name': model_name,
                'custom_prompt_used': custom_prompt is not None,
                'analysis_complete': True
            }
        }
        
        logging.info(f"✓ Complete analysis finished successfully for {ticker}")
        return result
        
    except Exception as e:
        logging.error(f"Unexpected error during complete analysis for {ticker}: {e}")
        return None

def quick_sentiment_analysis(ticker: str, quarter: Optional[str] = None, year: Optional[int] = None, 
                            model_name: str = "gemini-2.5-flash", custom_prompt: Optional[str] = None) -> Optional[Dict]:
    """
    Quick sentiment analysis without company profile or stock performance data.
    
    Useful when you only need sentiment scores and want maximum speed.
    
    Args:
        ticker (str): Stock ticker symbol
        quarter (str, optional): Quarter like "Q1", "Q2", "Q3", "Q4"
        year (int, optional): Year like 2024, 2023  
        model_name (str): Gemini model to use for sentiment analysis
        custom_prompt (str, optional): Complete custom prompt for sentiment analysis. Overrides default prompt.
        
    Returns:
        dict: Contains transcript and sentiment data only
        None: If transcript fetch or sentiment analysis fails
    """
    # Validate inputs
    ticker = _validate_ticker_input(ticker, "quick_sentiment_analysis")
    if not ticker:
        return None
    
    quarter, year = _validate_quarter_year(quarter, year, "quick_sentiment_analysis")
    if quarter is None and quarter is not None:  # Validation failed
        return None
    if year is None and year is not None:  # Validation failed
        return None
    
    if not isinstance(model_name, str) or not model_name.strip():
        logging.error("quick_sentiment_analysis: model_name must be a non-empty string")
        return None
    
    if custom_prompt is not None and not isinstance(custom_prompt, str):
        logging.error("quick_sentiment_analysis: custom_prompt must be a string")
        return None
    
    try:
        logging.info(f"Starting quick sentiment analysis for {ticker}" + 
                    (f" {quarter} {year}" if quarter and year else ""))
        
        # Step 1: Fetch transcript
        logging.info(f"Step 1/2: Fetching transcript for {ticker}...")
        transcript = fetch_transcript(ticker, quarter, year)
        if not transcript:
            logging.error(f"Failed to fetch transcript for {ticker}")
            return None
        
        # Validate transcript
        if not validate_transcript_result(transcript):
            logging.error(f"Invalid transcript result for {ticker}")
            return None
            
        logging.info(f"✓ Successfully fetched transcript ({len(transcript['transcript_text'])} characters)")
            
        # Step 2: Analyze sentiment
        logging.info(f"Step 2/2: Analyzing sentiment for {ticker}...")
        sentiment = score_sentiment(transcript['transcript_text'], model_name, custom_prompt)
        if not sentiment:
            logging.error(f"Failed to analyze sentiment for {ticker}")
            return None
        
        # Validate sentiment (only for default prompts)
        if not custom_prompt and not validate_sentiment_result(sentiment):
            logging.error(f"Invalid sentiment result for {ticker}")
            return None
            
        logging.info(f"✓ Successfully analyzed sentiment" + 
                    (f" (score: {sentiment.get('overall_sentiment_score', 'N/A')})" if not custom_prompt else ""))
        
        result = {
            'transcript': transcript,
            'sentiment': sentiment,
            'analysis_metadata': {
                'ticker': ticker,
                'quarter': quarter,
                'year': year,
                'model_name': model_name,
                'custom_prompt_used': custom_prompt is not None,
                'quick_analysis': True
            }
        }
        
        logging.info(f"✓ Quick sentiment analysis finished successfully for {ticker}")
        return result
        
    except Exception as e:
        logging.error(f"Unexpected error during quick sentiment analysis for {ticker}: {e}")
        return None

def batch_analyze_earnings_calls(tickers: List[str], quarter: Optional[str] = None, year: Optional[int] = None,
                                model_name: str = "gemini-2.5-flash", custom_prompt: Optional[str] = None) -> List[Optional[Dict]]:
    """
    Perform complete earnings call analysis for multiple tickers in batch.
    
    Args:
        tickers (list): List of stock ticker symbols
        quarter (str, optional): Quarter like "Q1", "Q2", "Q3", "Q4"
        year (int, optional): Year like 2024, 2023
        model_name (str): Gemini model to use for sentiment analysis
        custom_prompt (str, optional): Complete custom prompt for sentiment analysis
        
    Returns:
        list: List of complete analysis results in same order as input tickers
    """
    if not tickers or not isinstance(tickers, list):
        logging.error("batch_analyze_earnings_calls: tickers must be a non-empty list")
        return []
    
    # Validate quarter and year once
    quarter, year = _validate_quarter_year(quarter, year, "batch_analyze_earnings_calls")
    if quarter is None and quarter is not None:  # Validation failed
        return [None] * len(tickers)
    if year is None and year is not None:  # Validation failed
        return [None] * len(tickers)
    
    results = []
    
    for i, ticker in enumerate(tickers):
        logging.info(f"Processing ticker {i+1}/{len(tickers)}: {ticker}")
        
        try:
            result = analyze_earnings_call(ticker, quarter, year, model_name, custom_prompt)
            results.append(result)
        except Exception as e:
            logging.error(f"Error processing ticker {ticker}: {e}")
            results.append(None)
    
    success_count = len([r for r in results if r is not None])
    logging.info(f"Batch analysis complete: {success_count}/{len(tickers)} successful")
    
    return results

def check_data_availability(ticker: str, quarter: Optional[str] = None, year: Optional[int] = None) -> Dict:
    """
    Check availability of data components without performing full analysis.
    
    Args:
        ticker (str): Stock ticker symbol
        quarter (str, optional): Quarter like "Q1", "Q2", "Q3", "Q4"
        year (int, optional): Year like 2024, 2023
        
    Returns:
        dict: Availability status for each data component
    """
    ticker = _validate_ticker_input(ticker, "check_data_availability")
    if not ticker:
        return {'error': 'Invalid ticker'}
    
    quarter, year = _validate_quarter_year(quarter, year, "check_data_availability")
    if quarter is None and quarter is not None:  # Validation failed
        return {'error': 'Invalid quarter'}
    if year is None and year is not None:  # Validation failed
        return {'error': 'Invalid year'}
    
    result = {
        'ticker': ticker,
        'quarter': quarter,
        'year': year,
        'transcript_available': False,
        'profile_available': False,
        'historical_prices_available': False,
        'transcript_url': None,
        'errors': []
    }
    
    try:
        # Check transcript availability
        transcript_check = check_transcript_availability(ticker, quarter, year)
        result['transcript_available'] = transcript_check.get('available', False)
        result['transcript_url'] = transcript_check.get('url')
        if not result['transcript_available']:
            result['errors'].append(f"Transcript not available: {transcript_check.get('error', 'Unknown error')}")
        
        # Check company profile availability
        try:
            profile = fetch_company_profile(ticker)
            result['profile_available'] = profile is not None
            if not result['profile_available']:
                result['errors'].append("Company profile not available")
        except Exception as e:
            result['errors'].append(f"Error checking profile: {e}")
        
        # Check historical price availability
        try:
            prices = get_historical_prices(ticker, limit=5)  # Just check a few records
            result['historical_prices_available'] = prices is not None and len(prices) > 0
            if not result['historical_prices_available']:
                result['errors'].append("Historical prices not available")
        except Exception as e:
            result['errors'].append(f"Error checking historical prices: {e}")
        
        result['analysis_feasible'] = (result['transcript_available'] and 
                                     result['profile_available'])
        
        return result
        
    except Exception as e:
        result['errors'].append(f"Unexpected error: {e}")
        return result

def get_available_models() -> Dict:
    """
    Get information about available models and their capabilities.
    
    Returns:
        dict: Information about available Gemini models
    """
    return {
        'sentiment_models': {
            'gemini-2.5-flash': {
                'description': 'Latest fast model, good balance of speed and quality',
                'recommended': True,
                'use_case': 'General sentiment analysis'
            },
            'gemini-1.5-pro': {
                'description': 'High-quality model with excellent reasoning',
                'recommended': False,
                'use_case': 'Complex analysis requiring detailed reasoning'
            },
            'gemini-1.5-flash': {
                'description': 'Fast model, good for high-volume processing',
                'recommended': False,
                'use_case': 'Batch processing, speed-critical applications'
            }
        },
        'default_model': 'gemini-2.5-flash',
        'custom_prompts_supported': True,
        'batch_processing_supported': True
    }

def validate_api_configuration() -> Dict:
    """
    Validate that required API keys and dependencies are properly configured.
    
    Returns:
        dict: Configuration validation results
    """
    from .config import get_gemini_api_key, get_fmp_api_key
    
    config_status = {
        'gemini_api_key': False,
        'fmp_api_key': False,
        'dependencies': {
            'requests': False,
            'beautifulsoup4': False,
            'pandas': False,
            'google-generativeai': False
        },
        'errors': [],
        'warnings': []
    }
    
    # Check API keys
    try:
        gemini_key = get_gemini_api_key()
        config_status['gemini_api_key'] = bool(gemini_key)
        if not gemini_key:
            config_status['errors'].append("GEMINI_API_KEY not set")
    except Exception as e:
        config_status['errors'].append(f"Error checking Gemini API key: {e}")
    
    try:
        fmp_key = get_fmp_api_key()
        config_status['fmp_api_key'] = bool(fmp_key)
        if not fmp_key:
            config_status['errors'].append("FMP_API_KEY not set")
    except Exception as e:
        config_status['errors'].append(f"Error checking FMP API key: {e}")
    
    # Check dependencies
    dependencies = ['requests', 'bs4', 'pandas', 'google.generativeai']
    dependency_names = ['requests', 'beautifulsoup4', 'pandas', 'google-generativeai']
    
    for dep, name in zip(dependencies, dependency_names):
        try:
            __import__(dep)
            config_status['dependencies'][name] = True
        except ImportError:
            config_status['dependencies'][name] = False
            config_status['errors'].append(f"Missing dependency: {name}")
    
    # Add warnings for potential issues
    if not all(config_status['dependencies'].values()):
        config_status['warnings'].append("Some dependencies are missing - functionality may be limited")
    
    config_status['fully_configured'] = (config_status['gemini_api_key'] and 
                                       config_status['fmp_api_key'] and 
                                       all(config_status['dependencies'].values()))
    
    return config_status

# Helper function for users to understand the API structure
def get_api_help() -> str:
    """
    Get help text explaining the API structure and usage patterns.
    
    Returns:
        str: Formatted help text
    """
    help_text = """
Earnings Analyzer API Help
=========================

CORE FUNCTIONS (for custom pipelines):
- fetch_transcript(ticker, quarter=None, year=None)
- score_sentiment(transcript_text, model_name="gemini-2.5-flash", custom_prompt=None)
- fetch_company_profile(ticker)
- calculate_stock_performance(ticker, call_date)

CONVENIENCE FUNCTIONS:
- analyze_earnings_call(ticker, ...)  # Complete analysis, no database
- quick_sentiment_analysis(ticker, ...)  # Just transcript + sentiment
- batch_analyze_earnings_calls(tickers, ...)  # Batch processing

DATABASE-BACKED ANALYSIS:
- EarningsAnalyzer()  # Class with automatic caching

VALIDATION & UTILITIES:
- check_data_availability(ticker, ...)  # Check what data is available
- validate_api_configuration()  # Check API keys and dependencies
- get_available_models()  # List supported models

USAGE PATTERNS:

1. Quick sentiment check:
   result = quick_sentiment_analysis("AAPL")
   
2. Complete analysis:
   result = analyze_earnings_call("AAPL")
   
3. Custom pipeline:
   transcript = fetch_transcript("AAPL")
   sentiment = score_sentiment(transcript['transcript_text'])
   
4. Database-backed (with caching):
   analyzer = EarningsAnalyzer()
   result = analyzer.analyze("AAPL")

For detailed documentation, see the README.md file.
"""
    return help_text