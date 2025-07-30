import argparse
import os
from dotenv import load_dotenv
from earnings_analyzer.analyzer import EarningsAnalyzer
from earnings_analyzer.display import display_snapshot

# Explicitly load .env file from the current working directory
load_dotenv(os.path.join(os.getcwd(), '.env'))

def main():
    """
    Main entry point for the Earnings Analyzer CLI.
    This function handles command-line argument parsing and orchestrates
    the analysis by using the EarningsAnalyzer class.
    """
    parser = argparse.ArgumentParser(
        description="A tool to fetch, scrape, and analyze earnings call transcripts."
    )
    parser.add_argument(
        "--ticker", 
        required=True, 
        help="The stock ticker symbol of the company to analyze (e.g., AAPL, MSFT)."
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="The Gemini model to use for sentiment analysis (e.g., gemini-2.5-flash, gemini-1.5-pro)."
    )
    args = parser.parse_args()

    # 1. Create an instance of our analyzer
    analyzer = EarningsAnalyzer()

    # 2. Call its method to get the results
    results = analyzer.analyze(args.ticker, model_name=args.model)

    # 3. Display the results if the analysis was successful
    if results:
        print("\n--- Analysis Complete ---")
        display_snapshot(results)
    else:
        print("\n--- Analysis Failed ---")

if __name__ == "__main__":
    main()