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
    the analysis using either the composable API or EarningsAnalyzer class.
    """
    parser = argparse.ArgumentParser(
        description="A tool to fetch, scrape, and analyze earnings call transcripts."
    )
    parser.add_argument(
        "--ticker",
        help="The stock ticker symbol of the company to analyze (e.g., AAPL, MSFT)."
    )
    parser.add_argument(
        "--quarter",
        help="The quarter to analyze (e.g., Q1, Q2, Q3, Q4)."
    )
    parser.add_argument(
        "--year", 
        type=int,
        help="The year to analyze (e.g., 2024, 2023)."
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
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Use composable API without database caching (in-memory analysis only)."
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Perform quick sentiment analysis only (transcript + sentiment, no profile or performance data)."
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

    # Use composable API if --no-db flag is set
    if args.no_db:
        if args.quick:
            # Quick sentiment analysis only
            from earnings_analyzer.api import quick_sentiment_analysis
            print(f"\n--- Starting quick sentiment analysis for {args.ticker} (no database caching) ---")
            results = quick_sentiment_analysis(args.ticker, args.quarter, args.year, args.model)
            if results:
                # Format for display_snapshot
                formatted_results = {
                    'profile': {'symbol': args.ticker, 'companyName': f"{args.ticker} (Quick Analysis)"},
                    'sentiment': results['sentiment'],
                    'stock_performance': None,
                    'call_date': results['transcript'].get('call_date'),
                    'quarter': results['transcript'].get('quarter'),
                    'year': results['transcript'].get('year')
                }
                print("\n--- Quick Analysis Complete ---")
                display_snapshot(formatted_results)
            else:
                print("\n--- Quick Analysis Failed ---")
        else:
            # Full composable analysis
            from earnings_analyzer.api import analyze_earnings_call
            print(f"\n--- Starting composable analysis for {args.ticker} (no database caching) ---")
            results = analyze_earnings_call(args.ticker, args.quarter, args.year, args.model)
            if results:
                # Convert to the format expected by display_snapshot
                formatted_results = {
                    'profile': results['profile'],
                    'sentiment': results['sentiment'],
                    'stock_performance': results.get('stock_performance'),
                    'call_date': results['transcript'].get('call_date'),
                    'quarter': results['transcript'].get('quarter'),
                    'year': results['transcript'].get('year'),
                    'filing_url': results['transcript'].get('transcript_url')
                }
                print("\n--- Analysis Complete ---")
                display_snapshot(formatted_results)
            else:
                print("\n--- Analysis Failed ---")
        return

    # Use traditional EarningsAnalyzer class with database
    analyzer = EarningsAnalyzer()

    if args.list_calls:
        if not args.ticker:
            parser.error("--list-calls requires --ticker.")
        existing_calls = analyzer.get_existing_calls(args.ticker)
        if existing_calls:
            print(f"\nExisting earnings calls for {args.ticker}:")
            for call in existing_calls:
                sentiment_score = call.get('overall_sentiment_score')
                score_text = f"(sentiment: {sentiment_score:.1f})" if sentiment_score else "(no sentiment data)"
                print(f"  - {call['call_date']} ({call['quarter']} {call['year']}) {score_text}")
        else:
            print(f"\nNo earnings calls found for {args.ticker} in the database.")
            
    elif args.ticker:
        if args.quick:
            print(f"\n--- Note: --quick flag ignored when using database mode ---")
            
        results = analyzer.analyze(args.ticker, quarter=args.quarter, year=args.year, model_name=args.model)
        if results:
            print("\n--- Analysis Complete ---")
            display_snapshot(results)
        else:
            print("\n--- Analysis Failed ---")


if __name__ == "__main__":
    main()