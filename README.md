# Earnings Call Sentiment Analyzer

This Python package provides a tool to fetch company profile data, scrape the latest earnings call transcript from The Motley Fool, perform sentiment analysis, and correlate sentiment with stock performance.

## Features

- **Flexible Transcript Scraping:** Automatically finds and scrapes earnings call transcripts for a given stock ticker from `fool.com`, with options to specify a particular quarter and year or default to the latest.
- **Company Data:** Fetches company profile information (sector, industry) from the Financial Modeling Prep API.
- **AI-Powered Sentiment Analysis:** Uses the Google Gemini API to analyze the transcript and provide a sentiment score, confidence level, and key discussion themes.
- **Data Persistence:** Stores company profiles, earnings call details, sentiment analysis results, and stock performance data in a local SQLite database (`earnings_analyzer.db`).
- **Structured Output:** Returns a clean dictionary object containing all the fetched and analyzed data, including the earnings call date and quarter.
- **Robust Error Handling:** Includes comprehensive error handling and logging for API calls, data processing, and database operations.

## Installation

This package is not yet available on PyPI. You can install it directly from the GitHub repository:

```bash
pip install git+https://github.com/jeremiahbohr/earnings-analyzer.git
```

## Prerequisites

Before using the package, you must set up the required API keys. Create a file named `.env` in the directory where you will run the script (or set them as environment variables) and add the following keys:

```
GEMINI_API_KEY=your_gemini_api_key_here
FMP_API_KEY=your_financial_modeling_prep_api_key_here
```

## Usage

The package provides an `EarningsAnalyzer` class that encapsulates the entire workflow. You can use it in your own Python script or via the command-line interface.

## Data Usage Disclaimer
This tool is for educational and research purposes. Users are responsible for:
- Obtaining proper API keys and respecting rate limits
- Complying with data provider terms of service  
- Not using for illegal market manipulation