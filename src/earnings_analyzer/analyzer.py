import datetime
import json
import pandas as pd
import logging

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
        try:
            database.setup_database()
            self.conn = database.create_connection(database.DATABASE_FILE)
            if self.conn is None:
                logging.error("Error: Could not establish a database connection.")
        except Exception as e:
            logging.error(f"Error during database setup or connection: {e}")
            self.conn = None

    def analyze(self, ticker, quarter=None, year=None, model_name="gemini-2.5-flash", custom_prompt=None):
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
        # First, try to determine the call identity to check for existing data
        transcript_data = fetch_transcript(ticker, quarter, year)
        if not transcript_data:
            logging.error(f"Could not fetch transcript for {ticker}. Aborting.")
            return None

        final_quarter = transcript_data['quarter']
        final_year = transcript_data['year']

        # Check for existing cached data (only if using default prompt)
        if not custom_prompt and final_quarter and final_year:
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
        historical_prices = None
        try:
            historical_prices = get_historical_prices(ticker)
        except Exception as e:
            logging.warning(f"Error fetching historical prices for {ticker}: {e}")

        stock_performance = calculate_stock_performance(
            ticker, transcript_data['call_date'], historical_prices
        )

        # Store in database (only if using default prompt)
        if not custom_prompt:
            self._store_analysis_in_database(
                profile, transcript_data, sentiment, stock_performance, model_name
            )

        # Consolidate and return results
        return {
            "profile": profile,
            "sentiment": sentiment,
            "stock_performance": stock_performance,
            "model_name": model_name,
            "call_date": transcript_data['call_date'],
            "quarter": transcript_data['quarter'],
            "year": transcript_data['year'],
            "filing_url": transcript_data['transcript_url']
        }

    def _format_existing_call_data(self, existing_call):
        """Format existing database record into the expected return format."""
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
                "key_themes": json.loads(existing_call[9]) if existing_call[9] else [],
                "model_name": existing_call[10],
                "qualitative_assessment": existing_call[11]
            },
            "stock_performance": {
                "price_at_call": existing_call[12],
                "price_1_week": existing_call[13],
                "price_1_month": existing_call[14],
                "price_3_month": existing_call[15],
                "performance_1_week": existing_call[16],
                "performance_1_month": existing_call[17],
                "performance_3_month": existing_call[18]
            }
        }

    def _store_analysis_in_database(self, profile, transcript_data, sentiment, stock_performance, model_name):
        """Store analysis results in database."""
        if not self.conn:
            return

        try:
            # Store company info
            company_data = (profile.get('symbol'), profile.get('companyName'), profile.get('sector'))
            if not database.select_company_by_ticker(self.conn, profile.get('symbol')):
                database.insert_company(self.conn, company_data)

            # Store earnings call
            call_date = transcript_data['call_date']
            if isinstance(call_date, str):
                call_date = datetime.datetime.strptime(call_date, '%Y-%m-%d').date()
                
            earnings_call_data = (
                profile.get('symbol'),
                call_date,
                transcript_data['quarter'],
                transcript_data['year'],
                transcript_data['transcript_text'],
                transcript_data['transcript_url']
            )
            earnings_call_id = database.insert_earnings_call(self.conn, earnings_call_data)

            # Store sentiment analysis
            if earnings_call_id and sentiment:
                key_themes_json = json.dumps(sentiment.get('key_themes', []))
                sentiment_data = (
                    earnings_call_id,
                    sentiment.get('overall_sentiment_score'),
                    sentiment.get('confidence_level'),
                    key_themes_json,
                    model_name,
                    sentiment.get('qualitative_assessment')
                )
                database.insert_sentiment_analysis(self.conn, sentiment_data)

            # Store stock performance
            if earnings_call_id and stock_performance:
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
            logging.warning(f"Error storing analysis in database: {e}")

    def get_existing_calls(self, ticker):
        """
        Retrieves a list of existing earnings calls for a given ticker from the database.
        
        Args:
            ticker (str): Stock ticker symbol
            
        Returns:
            list: List of existing call dictionaries with metadata and analysis results
        """
        if not self.conn:
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
                    'key_themes': json.loads(r[10]) if r[10] else []
                } for r in records]
            else:
                return []
        except Exception as e:
            logging.error(f"Error retrieving existing calls for {ticker}: {e}")
            return []

    def get_all_calls(self):
        """
        Retrieves all earnings calls from the database.
        
        Returns:
            list: List of all call dictionaries with metadata and analysis results
        """
        if not self.conn:
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
                    'key_themes': json.loads(r[10]) if r[10] and isinstance(r[10], str) else r[10]
                } for r in records]
            else:
                return []
        except Exception as e:
            logging.error(f"Error retrieving all calls: {e}")
            return []

    def analyze_to_dataframe(self, ticker, quarter=None, year=None, model_name="gemini-2.5-flash", custom_prompt=None):
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
        analysis_results = self.analyze(ticker, quarter=quarter, year=year, model_name=model_name, custom_prompt=custom_prompt)

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
                'Price at Call': stock_performance_data.get('price_at_call'),
                '1 Week Performance': stock_performance_data.get('performance_1_week'),
                '1 Month Performance': stock_performance_data.get('performance_1_month'),
                '3 Month Performance': stock_performance_data.get('performance_3_month'),
                'Call Date': analysis_results.get('call_date'),
                'Quarter': analysis_results.get('quarter')
            }
        else:
            # Default prompt structure
            df_row = {
                'Ticker': profile_data.get('symbol'),
                'Company Name': profile_data.get('companyName'),
                'Sector': profile_data.get('sector'),
                'Industry': profile_data.get('industry'),
                'Sentiment Model': sentiment_data.get('model_name'),
                'Custom Prompt Used': False,
                'Overall Sentiment Score': sentiment_data.get('overall_sentiment_score'),
                'Sentiment Confidence': sentiment_data.get('confidence_level'),
                'Key Themes': ", ".join(sentiment_data.get('key_themes', [])),
                'Qualitative Assessment': sentiment_data.get('qualitative_assessment'),
                'Price at Call': stock_performance_data.get('price_at_call'),
                '1 Week Performance': stock_performance_data.get('performance_1_week'),
                '1 Month Performance': stock_performance_data.get('performance_1_month'),
                '3 Month Performance': stock_performance_data.get('performance_3_month'),
                'Call Date': analysis_results.get('call_date'),
                'Quarter': analysis_results.get('quarter')
            }

        return pd.DataFrame([df_row])

    def batch_analyze(self, tickers, quarter=None, year=None, model_name="gemini-2.5-flash", custom_prompt=None):
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
        results = []
        
        for i, ticker in enumerate(tickers):
            logging.info(f"Analyzing ticker {i+1}/{len(tickers)}: {ticker}")
            result = self.analyze(ticker, quarter, year, model_name, custom_prompt)
            results.append(result)
            
        return results

    def get_portfolio_summary(self, tickers):
        """
        Gets a summary of sentiment and performance across multiple tickers.
        
        Args:
            tickers (list): List of stock ticker symbols
            
        Returns:
            dict: Portfolio-level summary statistics
        """
        all_results = []
        
        for ticker in tickers:
            calls = self.get_existing_calls(ticker)
            all_results.extend(calls)
            
        if not all_results:
            return None
            
        # Calculate portfolio statistics
        sentiment_scores = [call['overall_sentiment_score'] for call in all_results if call['overall_sentiment_score']]
        
        return {
            'total_calls': len(all_results),
            'unique_tickers': len(set(call['ticker'] for call in all_results)),
            'average_sentiment': sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else None,
            'sentiment_range': [min(sentiment_scores), max(sentiment_scores)] if sentiment_scores else None,
            'latest_analysis_date': max(call['call_date'] for call in all_results) if all_results else None
        }