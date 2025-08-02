import datetime
import json
import pandas as pd
import logging
from typing import Dict, List, Optional, Union
import contextlib
import atexit

# Import the canonical composable functions from their source modules
from .analysis.fool_scraper import fetch_transcript
from .analysis.sentiment_analyzer import score_sentiment
from .data.financial_data_fetcher import fetch_company_profile, calculate_stock_performance, get_historical_prices
from .data import database

# Configure logging for analyzer
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


class EarningsAnalyzer:
    """
    High-level orchestrator class that uses the composable functions
    and provides database persistence and caching.
    
    This class provides the "database-backed" path for earnings analysis,
    automatically caching results and providing historical data retrieval.
    """
    
    def __init__(self):
        """Initializes the EarningsAnalyzer and sets up the database."""
        self.conn = None
        self._setup_database_connection()
        
        # Register cleanup on exit
        atexit.register(self._cleanup)

    def _setup_database_connection(self):
        """Set up database connection with proper error handling."""
        try:
            if not database.setup_database():
                logging.error("Failed to setup database during initialization")
                return
                
            self.conn = database.create_connection(database.DATABASE_FILE)
            if self.conn is None:
                logging.error("Error: Could not establish a database connection.")
            else:
                logging.info("Database connection established successfully")
                
        except Exception as e:
            logging.error(f"Error during database setup or connection: {e}")
            self.conn = None

    def _ensure_connection(self):
        """Ensure database connection is active, reconnect if necessary."""
        if self.conn is None:
            logging.warning("Database connection is None, attempting to reconnect...")
            self._setup_database_connection()
            return self.conn is not None
            
        try:
            # Test connection with a simple query
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception as e:
            logging.warning(f"Database connection test failed: {e}. Attempting to reconnect...")
            self._cleanup()
            self._setup_database_connection()
            return self.conn is not None

    def _cleanup(self):
        """Clean up database connection."""
        if self.conn:
            try:
                database.close_connection(self.conn)
                logging.debug("Database connection closed")
            except Exception as e:
                logging.error(f"Error closing database connection: {e}")
            finally:
                self.conn = None

    def _safe_json_loads(self, json_string):
        """Safely parse JSON string with error handling."""
        if not json_string:
            return []
            
        if isinstance(json_string, list):
            return json_string
            
        try:
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError) as e:
            logging.warning(f"Failed to parse JSON string: {e}. Raw value: {json_string}")
            return []

    def _safe_date_conversion(self, date_input):
        """Safely convert various date formats to datetime.date object."""
        if not date_input:
            return None
            
        if isinstance(date_input, datetime.date):
            return date_input
        elif isinstance(date_input, datetime.datetime):
            return date_input.date()
        elif isinstance(date_input, str):
            try:
                # Try common date formats
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y']:
                    try:
                        return datetime.datetime.strptime(date_input, fmt).date()
                    except ValueError:
                        continue
                logging.warning(f"Could not parse date string: {date_input}")
                return None
            except Exception as e:
                logging.error(f"Error parsing date {date_input}: {e}")
                return None
        else:
            logging.warning(f"Unsupported date type: {type(date_input)}")
            return None

    def analyze(self, ticker: str, quarter: Optional[str] = None, year: Optional[int] = None, 
                model_name: str = "gemini-2.5-flash", custom_prompt: Optional[str] = None) -> Optional[Dict]:
        """
        Performs a full analysis for a given stock ticker with database caching.
        
        Uses the composable functions but adds database persistence and caching.
        If analysis already exists in database, returns cached data.
        
        Args:
            ticker (str): Stock ticker symbol
            quarter (str, optional): Quarter like "Q1", "Q2", "Q3", "Q4"
            year (int, optional): Year like 2024, 2023
            model_name (str): Gemini model to use for sentiment analysis
            custom_prompt (str, optional): Complete custom prompt for sentiment analysis. Overrides default prompt.
            
        Returns:
            dict: Complete analysis results including profile, sentiment, stock_performance
            None: If analysis failed
        """
        if not ticker or not isinstance(ticker, str):
            logging.error("Invalid ticker provided to analyze()")
            return None
            
        ticker = ticker.upper().strip()
        
        # Validate inputs
        if quarter and quarter.upper() not in ['Q1', 'Q2', 'Q3', 'Q4']:
            logging.error(f"Invalid quarter: {quarter}. Must be Q1, Q2, Q3, or Q4")
            return None
            
        if year and (not isinstance(year, int) or year < 2000 or year > datetime.datetime.now().year):
            logging.error(f"Invalid year: {year}")
            return None

        try:
            # First, try to determine the call identity to check for existing data
            transcript_data = fetch_transcript(ticker, quarter, year)
            if not transcript_data:
                logging.error(f"Could not fetch transcript for {ticker}. Aborting.")
                return None

            final_quarter = transcript_data.get('quarter')
            final_year = transcript_data.get('year')

            # Check for existing cached data (only if using default prompt and we have database connection)
            if not custom_prompt and final_quarter and final_year and self._ensure_connection():
                existing_call = database.select_earnings_call_by_ticker_quarter_year(
                    self.conn, ticker, final_quarter, final_year
                )
                if existing_call:
                    logging.info(f"Found existing analysis for {ticker} {final_quarter} {final_year}. Returning cached data.")
                    return self._format_existing_call_data(existing_call)

            if custom_prompt:
                logging.info(f"--- Using custom prompt for {ticker} {final_quarter} {final_year} (no caching) ---")
            else:
                logging.info(f"--- No cached data found. Starting full analysis for {ticker} {final_quarter} {final_year} ---")

            # Fetch all components using composable functions
            profile = fetch_company_profile(ticker)
            if not profile:
                logging.error(f"Could not fetch profile for {ticker}. Aborting.")
                return None

            sentiment = score_sentiment(transcript_data['transcript_text'], model_name, custom_prompt)
            if not sentiment:
                logging.error("Could not analyze sentiment. Aborting.")
                return None

            # For stock performance, we need historical prices
            stock_performance = None
            call_date = transcript_data.get('call_date')
            
            if call_date:
                try:
                    historical_prices = get_historical_prices(ticker)
                    if historical_prices:
                        stock_performance = calculate_stock_performance(ticker, call_date, historical_prices)
                    else:
                        logging.warning(f"Could not fetch historical prices for {ticker}")
                except Exception as e:
                    logging.warning(f"Error calculating stock performance for {ticker}: {e}")

            # Store in database (only if using default prompt and we have database connection)
            if not custom_prompt and self._ensure_connection():
                try:
                    self._store_analysis_in_database(profile, transcript_data, sentiment, stock_performance, model_name)
                except Exception as e:
                    logging.warning(f"Failed to store analysis in database: {e}")

            # Consolidate and return results
            return {
                "profile": profile,
                "sentiment": sentiment,
                "stock_performance": stock_performance,
                "model_name": model_name,
                "call_date": transcript_data.get('call_date'),
                "quarter": transcript_data.get('quarter'),
                "year": transcript_data.get('year'),
                "filing_url": transcript_data.get('transcript_url')
            }

        except Exception as e:
            logging.error(f"Unexpected error during analysis for {ticker}: {e}")
            return None

    def _format_existing_call_data(self, existing_call) -> Dict:
        """Format existing database record into the expected return format."""
        try:
            return {
                "profile": {
                    "symbol": existing_call[0],
                    "companyName": existing_call[1],
                    "sector": existing_call[2]
                },
                "call_date": existing_call[3],
                "quarter": existing_call[4],
                "year": existing_call[5],
                "filing_url": existing_call[6],
                "sentiment": {
                    "overall_sentiment_score": existing_call[7],
                    "confidence_level": existing_call[8],
                    "key_themes": self._safe_json_loads(existing_call[9]),
                    "model_name": existing_call[10],
                    "qualitative_assessment": existing_call[11] or ""
                },
                "stock_performance": {
                    "price_at_call": existing_call[12],
                    "price_1_week": existing_call[13],
                    "price_1_month": existing_call[14],
                    "price_3_month": existing_call[15],
                    "performance_1_week": existing_call[16],
                    "performance_1_month": existing_call[17],
                    "performance_3_month": existing_call[18]
                } if existing_call[12] is not None else None
            }
        except Exception as e:
            logging.error(f"Error formatting existing call data: {e}")
            return {}

    def _store_analysis_in_database(self, profile: Dict, transcript_data: Dict, 
                                   sentiment: Dict, stock_performance: Optional[Dict], model_name: str):
        """Store analysis results in database with comprehensive error handling."""
        if not self.conn:
            logging.warning("No database connection available for storing analysis")
            return

        try:
            # Store company info
            company_data = (
                profile.get('symbol'),
                profile.get('companyName'),
                profile.get('sector')
            )
            
            # Check if company already exists
            existing_company = database.select_company_by_ticker(self.conn, profile.get('symbol'))
            if not existing_company:
                database.insert_company(self.conn, company_data)

            # Store earnings call
            call_date = self._safe_date_conversion(transcript_data.get('call_date'))
                
            earnings_call_data = (
                profile.get('symbol'),
                call_date,
                transcript_data.get('quarter'),
                transcript_data.get('year'),
                transcript_data.get('transcript_text'),
                transcript_data.get('transcript_url')
            )
            
            earnings_call_id = database.insert_earnings_call(self.conn, earnings_call_data)
            if not earnings_call_id:
                logging.warning("Failed to insert earnings call, skipping sentiment and performance storage")
                return

            # Store sentiment analysis
            if sentiment:
                try:
                    key_themes = sentiment.get('key_themes', [])
                    if isinstance(key_themes, list):
                        key_themes_json = json.dumps(key_themes)
                    else:
                        key_themes_json = json.dumps([])
                        
                    sentiment_data = (
                        earnings_call_id,
                        sentiment.get('overall_sentiment_score'),
                        sentiment.get('confidence_level'),
                        key_themes_json,
                        model_name,
                        sentiment.get('qualitative_assessment', '')
                    )
                    database.insert_sentiment_analysis(self.conn, sentiment_data)
                except Exception as e:
                    logging.warning(f"Failed to store sentiment analysis: {e}")

            # Store stock performance
            if earnings_call_id and stock_performance:
                try:
                    stock_performance_data = (
                        earnings_call_id,
                        stock_performance.get('price_at_call'),
                        stock_performance.get('price_1_week'),
                        stock_performance.get('price_1_month'),
                        stock_performance.get('price_3_month'),
                        stock_performance.get('performance_1_week'),
                        stock_performance.get('performance_1_month'),
                        stock_performance.get('performance_3_month')
                    )
                    database.insert_stock_performance(self.conn, stock_performance_data)
                except Exception as e:
                    logging.warning(f"Failed to store stock performance: {e}")

        except Exception as e:
            logging.error(f"Error storing analysis in database: {e}")

    def get_existing_calls(self, ticker: str) -> List[Dict]:
        """
        Retrieves a list of existing earnings calls for a given ticker from the database.
        
        Args:
            ticker (str): Stock ticker symbol
            
        Returns:
            list: List of existing call dictionaries with metadata and analysis results
        """
        if not ticker or not isinstance(ticker, str):
            logging.error("Invalid ticker provided to get_existing_calls()")
            return []
            
        ticker = ticker.upper().strip()
        
        if not self._ensure_connection():
            logging.error("Database connection not established. Cannot retrieve existing calls.")
            return []
        
        try:
            records = database.select_earnings_calls_by_ticker(self.conn, ticker)
            if records:
                return [{
                    'ticker': r[0],
                    'call_date': r[1],
                    'quarter': r[2],
                    'year': r[3],
                    'filing_url': r[4],
                    'transcript_text': r[5],
                    'overall_sentiment_score': r[6],
                    'confidence_level': r[7],
                    'model_name': r[8],
                    'qualitative_assessment': r[9],
                    'key_themes': self._safe_json_loads(r[10])
                } for r in records]
            else:
                return []
        except Exception as e:
            logging.error(f"Error retrieving existing calls for {ticker}: {e}")
            return []

    def get_all_calls(self) -> List[Dict]:
        """
        Retrieves all earnings calls from the database.
        
        Returns:
            list: List of all call dictionaries with metadata and analysis results
        """
        if not self._ensure_connection():
            logging.error("Database connection not established. Cannot retrieve calls.")
            return []
        
        try:
            records = database.select_all_earnings_calls(self.conn)
            if records:
                return [{
                    'ticker': r[0],
                    'call_date': r[1],
                    'quarter': r[2],
                    'year': r[3],
                    'filing_url': r[4],
                    'transcript_text': r[5],
                    'overall_sentiment_score': r[6],
                    'confidence_level': r[7],
                    'model_name': r[8],
                    'qualitative_assessment': r[9],
                    'key_themes': self._safe_json_loads(r[10])
                } for r in records]
            else:
                return []
        except Exception as e:
            logging.error(f"Error retrieving all calls: {e}")
            return []

    def analyze_to_dataframe(self, ticker: str, quarter: Optional[str] = None, year: Optional[int] = None, 
                            model_name: str = "gemini-2.5-flash", custom_prompt: Optional[str] = None) -> pd.DataFrame:
        """
        Performs a full analysis for a given stock ticker and returns the results
        as a pandas DataFrame row, including a qualitative assessment.
        
        Args:
            ticker (str): Stock ticker symbol
            quarter (str, optional): Quarter like "Q1", "Q2", "Q3", "Q4"
            year (int, optional): Year like 2024, 2023
            model_name (str): Gemini model to use for sentiment analysis
            custom_prompt (str, optional): Complete custom prompt for sentiment analysis. Overrides default prompt.
            
        Returns:
            pandas.DataFrame: Single-row DataFrame with flattened analysis results
        """
        try:
            analysis_results = self.analyze(ticker, quarter=quarter, year=year, 
                                          model_name=model_name, custom_prompt=custom_prompt)

            if not analysis_results:
                return pd.DataFrame()

            profile_data = analysis_results.get('profile', {})
            sentiment_data = analysis_results.get('sentiment', {})
            stock_performance_data = analysis_results.get('stock_performance', {})

            # Handle both default and custom prompt results
            if custom_prompt:
                # For custom prompts, we can't predict the structure, so create a flexible representation
                df_row = {
                    'Ticker': profile_data.get('symbol'),
                    'Company Name': profile_data.get('companyName'),
                    'Sector': profile_data.get('sector'),
                    'Industry': profile_data.get('industry'),
                    'Sentiment Model': sentiment_data.get('model_name'),
                    'Custom Prompt Used': True,
                    'Sentiment Results': str(sentiment_data),  # Convert to string for DataFrame compatibility
                    'Price at Call': stock_performance_data.get('price_at_call') if stock_performance_data else None,
                    '1 Week Performance': stock_performance_data.get('performance_1_week') if stock_performance_data else None,
                    '1 Month Performance': stock_performance_data.get('performance_1_month') if stock_performance_data else None,
                    '3 Month Performance': stock_performance_data.get('performance_3_month') if stock_performance_data else None,
                    'Call Date': analysis_results.get('call_date'),
                    'Quarter': analysis_results.get('quarter')
                }
            else:
                # Default prompt structure
                key_themes = sentiment_data.get('key_themes', [])
                themes_str = ", ".join(key_themes) if isinstance(key_themes, list) else str(key_themes)
                
                df_row = {
                    'Ticker': profile_data.get('symbol'),
                    'Company Name': profile_data.get('companyName'),
                    'Sector': profile_data.get('sector'),
                    'Industry': profile_data.get('industry'),
                    'Sentiment Model': sentiment_data.get('model_name'),
                    'Custom Prompt Used': False,
                    'Overall Sentiment Score': sentiment_data.get('overall_sentiment_score'),
                    'Sentiment Confidence': sentiment_data.get('confidence_level'),
                    'Key Themes': themes_str,
                    'Qualitative Assessment': sentiment_data.get('qualitative_assessment'),
                    'Price at Call': stock_performance_data.get('price_at_call') if stock_performance_data else None,
                    '1 Week Performance': stock_performance_data.get('performance_1_week') if stock_performance_data else None,
                    '1 Month Performance': stock_performance_data.get('performance_1_month') if stock_performance_data else None,
                    '3 Month Performance': stock_performance_data.get('performance_3_month') if stock_performance_data else None,
                    'Call Date': analysis_results.get('call_date'),
                    'Quarter': analysis_results.get('quarter')
                }

            return pd.DataFrame([df_row])
            
        except Exception as e:
            logging.error(f"Error creating DataFrame for {ticker}: {e}")
            return pd.DataFrame()

    def batch_analyze(self, tickers: List[str], quarter: Optional[str] = None, year: Optional[int] = None, 
                     model_name: str = "gemini-2.5-flash", custom_prompt: Optional[str] = None) -> List[Optional[Dict]]:
        """
        Performs analysis for multiple tickers and returns combined results.
        
        Args:
            tickers (list): List of stock ticker symbols
            quarter (str, optional): Quarter like "Q1", "Q2", "Q3", "Q4"
            year (int, optional): Year like 2024, 2023
            model_name (str): Gemini model to use for sentiment analysis
            custom_prompt (str, optional): Complete custom prompt for sentiment analysis. Overrides default prompt.
            
        Returns:
            list: List of analysis results in the same order as input tickers
        """
        if not tickers or not isinstance(tickers, list):
            logging.error("tickers must be a non-empty list")
            return []
        
        results = []
        
        for i, ticker in enumerate(tickers):
            if not ticker or not isinstance(ticker, str):
                logging.warning(f"Skipping invalid ticker at position {i}: {ticker}")
                results.append(None)
                continue
                
            logging.info(f"Analyzing ticker {i+1}/{len(tickers)}: {ticker}")
            
            try:
                result = self.analyze(ticker, quarter, year, model_name, custom_prompt)
                results.append(result)
            except Exception as e:
                logging.error(f"Error analyzing ticker {ticker}: {e}")
                results.append(None)
            
        return results

    def get_portfolio_summary(self, tickers: List[str]) -> Optional[Dict]:
        """
        Gets a summary of sentiment and performance across multiple tickers.
        
        Args:
            tickers (list): List of stock ticker symbols
            
        Returns:
            dict: Portfolio-level summary statistics
        """
        if not tickers or not isinstance(tickers, list):
            logging.error("tickers must be a non-empty list")
            return None
        
        all_results = []
        
        for ticker in tickers:
            if not ticker or not isinstance(ticker, str):
                continue
                
            try:
                calls = self.get_existing_calls(ticker.upper().strip())
                all_results.extend(calls)
            except Exception as e:
                logging.warning(f"Error getting calls for {ticker}: {e}")
                continue
            
        if not all_results:
            return {
                'total_calls': 0,
                'unique_tickers': len([t for t in tickers if t and isinstance(t, str)]),
                'error': 'No analysis data found for any tickers'
            }
            
        # Calculate portfolio statistics
        sentiment_scores = [call['overall_sentiment_score'] for call in all_results 
                          if call.get('overall_sentiment_score') is not None]
        
        unique_tickers = set(call['ticker'] for call in all_results if call.get('ticker'))
        
        call_dates = [call['call_date'] for call in all_results if call.get('call_date')]
        
        summary = {
            'total_calls': len(all_results),
            'unique_tickers': len(unique_tickers),
            'tickers_analyzed': list(unique_tickers)
        }
        
        if sentiment_scores:
            summary.update({
                'average_sentiment': sum(sentiment_scores) / len(sentiment_scores),
                'sentiment_range': [min(sentiment_scores), max(sentiment_scores)],
                'sentiment_std_dev': (sum((x - sum(sentiment_scores)/len(sentiment_scores))**2 for x in sentiment_scores) / len(sentiment_scores))**0.5
            })
        
        if call_dates:
            summary['latest_analysis_date'] = max(call_dates)
            summary['earliest_analysis_date'] = min(call_dates)
        
        return summary

    def get_database_stats(self) -> Optional[Dict]:
        """
        Get statistics about the database contents.
        
        Returns:
            dict: Database statistics including record counts
        """
        if not self._ensure_connection():
            return None
            
        try:
            return database.get_database_stats(self.conn)
        except Exception as e:
            logging.error(f"Error getting database stats: {e}")
            return None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self._cleanup()

    def __del__(self):
        """Destructor to ensure cleanup."""
        self._cleanup()