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
        Fetches company profile, scrapes the latest earnings transcript,
        performs sentiment analysis, calculates stock performance,
        and stores the results in the database.

        Args:
            ticker: The stock ticker symbol to analyze.
            quarter: Optional. The quarter of the earnings call (e.g., "Q1", "Q2").
            year: Optional. The year of the earnings call (e.g., 2024).
            model_name: The name of the Gemini model to use.

        Returns:
            A dictionary containing the analysis results, or None on failure.
        """
        logging.info(f"--- Analyzing {ticker} using {model_name} ---")

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
                    sentiment_data = (earnings_call_id, sentiment.get('overall_sentiment_score'), sentiment.get('confidence_level'), key_themes_json)
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

    def analyze_to_dataframe(self, ticker, quarter=None, year=None, model_name="gemini-2.5-flash"):
        """
        Performs a full analysis for a given stock ticker and returns the results
        as a pandas DataFrame row, including a qualitative assessment.

        Args:
            ticker: The stock ticker symbol to analyze.
            quarter: Optional. The quarter of the earnings call (e.g., "Q1", "Q2").
            year: Optional. The year of the earnings call (e.g., 2024).
            model_name: The name of the Gemini model to use.

        Returns:
            pandas.DataFrame: A DataFrame containing the analysis results, or an empty DataFrame on failure.
        """
        analysis_results = self.analyze(ticker, quarter=quarter, year=year, model_name=model_name)

        if not analysis_results:
            return pd.DataFrame()

        profile_data = analysis_results.get('profile', {})
        sentiment_data = analysis_results.get('sentiment', {})
        stock_performance_data = analysis_results.get('stock_performance', {})

        # Generate qualitative assessment
        qualitative_assessment = sentiment_analyzer.generate_qualitative_assessment(sentiment_data, model_name=model_name)

        # Flatten the data into a single dictionary for DataFrame row
        df_row = {
            'Ticker': profile_data.get('symbol'),
            'Company Name': profile_data.get('companyName'),
            'Sector': profile_data.get('sector'),
            'Industry': profile_data.get('industry'),
            'Sentiment Model': analysis_results.get('model_name'),
            'Overall Sentiment Score': sentiment_data.get('overall_sentiment_score'),
            'Sentiment Confidence': sentiment_data.get('confidence_level'),
            'Key Themes': ", ".join(sentiment_data.get('key_themes', [])),
            'Qualitative Assessment': qualitative_assessment,
            'Price at Call': stock_performance_data.get('price_at_call'),
            '1 Week Performance': stock_performance_data.get('performance_1_week'),
            '1 Month Performance': stock_performance_data.get('performance_1_month'),
            '3 Month Performance': stock_performance_data.get('performance_3_month'),
            'Call Date': analysis_results.get('call_date'),
            'Quarter': analysis_results.get('quarter')
        }

        return pd.DataFrame([df_row])