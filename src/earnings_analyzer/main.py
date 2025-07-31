import argparse
import os
from dotenv import load_dotenv
from earnings_analyzer.analyzer import EarningsAnalyzer
from earnings_analyzer.config import validate_api_keys
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
        help="The stock ticker symbol of the company to analyze (e.g., AAPL, MSFT)."
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="The Gemini model to use for sentiment analysis (e.g., gemini-2.5-flash)."
    )
    parser.add_argument(
        "--db-path",
        help="Optional: Path to the SQLite database file. Defaults to ~/.earnings_analyzer/earnings_analyzer.db."
    )
    parser.add_argument(
        "--list-calls",
        action="store_true",
        help="List all existing earnings calls for a given ticker stored in the database."
    )
    args = parser.parse_args()

    # Show help and exit without validating API keys
    if not args.ticker and not args.list_calls:
        parser.print_help()
        return

    # Only validate API keys when actually needed
    validate_api_keys()
    
    if args.db_path:
        os.environ["EARNINGS_ANALYZER_DB"] = args.db_path

    analyzer = EarningsAnalyzer()

    if args.list_calls:
        if not args.ticker:
            parser.error("--list-calls requires --ticker.")
        existing_calls = analyzer.get_existing_calls(args.ticker)
        if existing_calls:
            print(f"Existing earnings calls for {args.ticker}:")
            for call in existing_calls:
                print(f"- {call['call_date']} ({call['quarter']} {call['year']})")
        else:
            print(f"No earnings calls found for {args.ticker} in the database.")
    elif args.ticker:
        results = analyzer.analyze(args.ticker, model_name=args.model)
        if results:
            print("\n--- Analysis Complete ---")
            display_snapshot(results)
        else:
            print("\n--- Analysis Failed ---")

if __name__ == "__main__":
    main()