import datetime
import json
import re
import pandas as pd
import logging

from .data import financial_data_fetcher as fmp
from .analysis import fool_scraper, sentiment_analyzer
from .data import database

# Configure logging for analyzer
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class EarningsAnalyzer:
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

    def analyze(self, ticker, quarter=None, year=None, model_name="gemini-2.5-flash"):
        """
        Performs a full analysis for a given stock ticker.
        Checks for existing data before fetching and analyzing.
        """
        final_quarter, final_year, transcript_url = self._determine_call_identity(ticker, quarter, year)

        if not all([final_quarter, final_year, transcript_url]):
            logging.error(f"Could not determine the earnings call identity for {ticker}. Aborting.")
            return None

        # Check for an existing record using the determined quarter and year
        existing_call = database.select_earnings_call_by_ticker_quarter_year(self.conn, ticker, final_quarter, final_year)
        if existing_call:
            logging.info(f"Found existing analysis for {ticker} {final_quarter} {final_year}. Returning cached data.")
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

        logging.info(f"--- No cached data found. Starting full analysis for {ticker} {final_quarter} {final_year} ---")

        # 1. Fetch Company Profile
        logging.info("Fetching company profile...")
        try:
            profile = fmp.get_company_profile(ticker)
            if not profile:
                logging.error(f"Error: Could not fetch profile for {ticker}. Aborting.")
                return None
        except Exception as e:
            logging.error(f"Error fetching company profile for {ticker}: {e}. Aborting.")
            return None

        # Store company info in database
        if self.conn:
            try:
                company_data = (profile.get('symbol'), profile.get('companyName'), profile.get('sector'))
                # Check if company already exists to avoid primary key violation
                if not database.select_company_by_ticker(self.conn, profile.get('symbol')):
                    database.insert_company(self.conn, company_data)
            except Exception as e:
                logging.warning(f"Error storing company info in database: {e}")

        # 2. Find and Scrape the Transcript
        logging.info("Finding transcript URL from fool.com...")
        transcript_url = None
        try:
            if quarter and year:
                logging.info(f"Attempting to find {quarter} {year} transcript for {ticker}...")
                transcript_url = fool_scraper.find_transcript_url_by_quarter(ticker, quarter, year)
            else:
                logging.info(f"Attempting to find latest transcript for {ticker}...")
                transcript_url = fool_scraper.find_latest_transcript_url(ticker)

            if not transcript_url:
                logging.error(f"Error: Could not find transcript URL for {ticker}. Aborting.")
                return None
        except Exception as e:
            logging.error(f"Error finding transcript URL for {ticker}: {e}. Aborting.")
            return None
        
        logging.info(f"Scraping transcript from {transcript_url}...")
        transcript = None
        try:
            transcript = fool_scraper.get_transcript_from_fool(transcript_url)
            if not transcript:
                logging.error("Error: Could not scrape transcript. Aborting.")
                return None
        except Exception as e:
            logging.error(f"Error scraping transcript from {transcript_url}: {e}. Aborting.")
            return None

        # Determine call_date and quarter based on provided parameters or URL extraction
        final_call_date = None
        final_quarter = "Unknown"
        final_year = None

        if quarter and year:
            try:
                # Assume first day of the quarter for simplicity if specific date not available
                month_map = {"Q1": 1, "Q2": 4, "Q3": 7, "Q4": 10}
                month = month_map.get(quarter.upper())
                if month:
                    final_call_date = datetime.date(year, month, 1)
                    final_quarter = quarter.upper()
                    final_year = year
                else:
                    logging.warning(f"Invalid quarter format provided: {quarter}. Attempting to parse from URL.")
            except ValueError:
                logging.warning(f"Could not construct date from provided quarter ({quarter}) and year ({year}). Attempting to parse from URL.")

        if not final_call_date: # Fallback to URL extraction if parameters not provided or invalid
            match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/.+-q(\d)-(\d{4})-earnings-call-transcript', transcript_url)
            if match:
                year_str, month_str, day_str, quarter_num_str, year_q_str = match.groups()
                try:
                    final_call_date = datetime.date(int(year_str), int(month_str), int(day_str))
                    final_quarter = f"Q{quarter_num_str}"
                    final_year = int(year_q_str)
                except ValueError:
                    logging.warning("Could not parse date/quarter/year from URL.")

        # 3. Analyze Sentiment
        logging.info("Analyzing transcript sentiment...")
        sentiment = None
        try:
            sentiment = sentiment_analyzer.analyze_sentiment(transcript, model_name=model_name)
            if not sentiment:
                logging.error("Error: Could not analyze sentiment. Aborting.")
                return None
        except Exception as e:
            logging.error(f"Error analyzing sentiment: {e}. Aborting.")
            return None

        # 4. Calculate Stock Performance
        logging.info("Calculating stock performance...")
        historical_prices = None
        try:
            historical_prices = fmp.get_historical_prices(ticker)
        except Exception as e:
            logging.warning(f"Error fetching historical prices for {ticker}: {e}.")
            historical_prices = None

        stock_performance = self._calculate_stock_performance(ticker, final_call_date, historical_prices)

        # Store earnings call info in database
        earnings_call_id = None
        if self.conn:
            try:
                earnings_call_data = (profile.get('symbol'), final_call_date, final_quarter, final_year, transcript, transcript_url)
                earnings_call_id = database.insert_earnings_call(self.conn, earnings_call_data)

                # Store sentiment analysis results
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

                # Store stock performance results
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
                logging.warning(f"Error storing earnings call or related data in database: {e}")

        # 5. Consolidate and return the results
        results = {
            "profile": profile,
            "sentiment": sentiment,
            "stock_performance": stock_performance,
            "model_name": model_name,
            "call_date": final_call_date.strftime('%Y-%m-%d') if final_call_date else None,
            "quarter": final_quarter
        }

        return results

    def _calculate_stock_performance(self, ticker, call_date, historical_prices):
        """
        Calculates stock performance metrics relative to the earnings call date.
        """
        if not historical_prices or not call_date:
            logging.warning("Missing historical prices or call date for stock performance calculation.")
            return None

        try:
            df = pd.DataFrame(historical_prices)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()

            call_date_dt = pd.to_datetime(call_date)

            # Find the price at call date
            price_at_call = df.loc[df.index <= call_date_dt, 'close'].iloc[-1]

            # Calculate future dates
            one_week_later = call_date_dt + pd.Timedelta(weeks=1)
            one_month_later = call_date_dt + pd.Timedelta(days=30) # Approx a month
            three_month_later = call_date_dt + pd.Timedelta(days=90) # Approx three months

            # Get prices at future dates
            price_1_week = df.loc[df.index >= one_week_later, 'close'].iloc[0] if not df.loc[df.index >= one_week_later].empty else None
            price_1_month = df.loc[df.index >= one_month_later, 'close'].iloc[0] if not df.loc[df.index >= one_month_later].empty else None
            price_3_month = df.loc[df.index >= three_month_later, 'close'].iloc[0] if not df.loc[df.index >= three_month_later].empty else None

            # Calculate performance
            performance_1_week = (price_1_week - price_at_call) / price_at_call if price_1_week else None
            performance_1_month = (price_1_month - price_at_call) / price_at_call if price_1_month else None
            performance_3_month = (price_3_month - price_at_call) / price_at_call if price_3_month else None

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
            logging.warning(f"Error calculating stock performance for {ticker}: {e}")
            return None

    def _determine_call_identity(self, ticker, quarter, year):
        """Determines the specific quarter, year, and transcript URL for a request."""
        transcript_url = None
        try:
            if quarter and year:
                logging.info(f"Attempting to find {quarter} {year} transcript for {ticker}...")
                transcript_url = fool_scraper.find_transcript_url_by_quarter(ticker, quarter, year)
            else:
                logging.info(f"Attempting to find latest transcript for {ticker}...")
                transcript_url = fool_scraper.find_latest_transcript_url(ticker)

            if not transcript_url:
                return None, None, None

        except Exception as e:
            logging.error(f"Error finding transcript URL for {ticker}: {e}.")
            return None, None, None

        # Extract quarter and year from URL if not provided
        if not (quarter and year):
            match = re.search(r'-q(\d)-(\d{4})-earnings-call-transcript', transcript_url)
            if match:
                quarter = f"Q{match.group(1)}"
                year = int(match.group(2))

        return quarter, year, transcript_url

    def get_existing_calls(self, ticker):
        """
        Retrieves a list of existing earnings calls for a given ticker from the database.

        Args:
            ticker: The stock ticker symbol.

        Returns:
            A list of dictionaries, each containing 'call_date', 'quarter', and 'year'
            for the existing earnings calls, or an empty list if none found or on error.
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
                    'overall_sentiment_score': r[5],
                    'confidence_level': r[6],
                    'model_name': r[7],
                    'qualitative_assessment': r[8],
                    'key_themes': json.loads(r[9]) if r[9] else [] # Parse JSON string back to list
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
            A list of dictionaries, each representing an earnings call,
            or an empty list if none found or on error.
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
                    'overall_sentiment_score': r[5],
                    'confidence_level': r[6],
                    'model_name': r[7],
                    'qualitative_assessment': r[8],
                    'key_themes': json.loads(r[9]) if r[9] and isinstance(r[9], str) else r[9]
                } for r in records]
            else:
                return []
        except Exception as e:
            logging.error(f"Error retrieving all calls: {e}")
            return []

    def analyze_to_dataframe(self, ticker, quarter=None, year=None, model_name="gemini-2.5-flash"):
        """
        Performs a full analysis for a given stock ticker and returns the results
        as a pandas DataFrame row, including a qualitative assessment.
        """
        analysis_results = self.analyze(ticker, quarter=quarter, year=year, model_name=model_name)

        if not analysis_results:
            return pd.DataFrame()

        profile_data = analysis_results.get('profile', {})
        sentiment_data = analysis_results.get('sentiment', {})
        stock_performance_data = analysis_results.get('stock_performance', {})

        # Flatten the data into a single dictionary for DataFrame row
        df_row = {
            'Ticker': profile_data.get('symbol'),
            'Company Name': profile_data.get('companyName'),
            'Sector': profile_data.get('sector'),
            'Industry': profile_data.get('industry'),
            'Sentiment Model': sentiment_data.get('model_name'),
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