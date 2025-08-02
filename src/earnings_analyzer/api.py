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

# Import composable functions from their canonical source modules
from .analysis.fool_scraper import (
    fetch_transcript,
    find_latest_transcript_url,
    find_transcript_url_by_quarter,
    get_transcript_from_fool,
    batch_fetch_transcripts,
    search_transcripts_by_keywords,
    validate_transcript_result,
    get_transcript_metadata_from_url
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
    'EarningsAnalyzer'
]


def analyze_earnings_call(ticker, quarter=None, year=None, model_name="gemini-2.5-flash", custom_prompt=None):
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
    try:
        # Step 1: Fetch transcript
        transcript = fetch_transcript(ticker, quarter, year)
        if not transcript:
            return None
            
        # Step 2: Analyze sentiment (with optional custom prompt)
        sentiment = score_sentiment(transcript['transcript_text'], model_name, custom_prompt)
        if not sentiment:
            return None
            
        # Step 3: Get company profile
        profile = fetch_company_profile(ticker)
        if not profile:
            return None
            
        # Step 4: Calculate stock performance (optional - may fail without affecting result)
        stock_performance = None
        if transcript.get('call_date'):
            try:
                stock_performance = calculate_stock_performance(ticker, transcript['call_date'])
            except Exception as e:
                # Stock performance is optional - don't fail the entire analysis
                pass
        
        return {
            'transcript': transcript,
            'sentiment': sentiment,
            'profile': profile,
            'stock_performance': stock_performance
        }
        
    except Exception as e:
        return None


def quick_sentiment_analysis(ticker, quarter=None, year=None, model_name="gemini-2.5-flash", custom_prompt=None):
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
    try:
        transcript = fetch_transcript(ticker, quarter, year)
        if not transcript:
            return None
            
        sentiment = score_sentiment(transcript['transcript_text'], model_name, custom_prompt)
        if not sentiment:
            return None
            
        return {
            'transcript': transcript,
            'sentiment': sentiment
        }
        
    except Exception as e:
        return None