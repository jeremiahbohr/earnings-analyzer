# Earnings Call Sentiment Analyzer

A Python package for analyzing earnings call transcripts with AI-powered sentiment analysis and stock performance correlation. Designed for researchers, analysts, and data scientists who need systematic access to earnings sentiment data.

## Features

- **Custom Prompt Analysis:** Define specialized research questions with custom AI prompts
- **Dual Analysis Architecture:** Composable functions for custom pipelines or complete database-backed solution
- **Automated Transcript Retrieval:** Scrapes earnings call transcripts from The Motley Fool for any quarter and year
- **AI Sentiment Analysis:** Uses Google Gemini to extract sentiment scores, confidence levels, and key themes
- **Stock Performance Analysis:** Calculates price movements 1 week, 1 month, and 3 months post-earnings
- **Data Persistence:** Optional SQLite database storage for historical analysis and caching
- **Modular Design:** Use individual functions or the complete orchestrator based on requirements
- **Batch Processing:** Efficient analysis of multiple companies
- **Error Handling:** Comprehensive logging and graceful failure management

## Installation

```bash
pip install earnings-analyzer
```

## Prerequisites

Two API keys are required:

### Financial Modeling Prep (FMP) API
Provides company data and stock prices. Obtain a free API key at [financialmodelingprep.com](https://financialmodelingprep.com/developer/docs/)

### Google Gemini API  
Powers AI sentiment analysis. Obtain a free API key at [Google AI Studio](https://aistudio.google.com/app/apikey)

### Environment Configuration

Create a `.env` file in your project directory:

```
GEMINI_API_KEY=your_gemini_api_key_here
FMP_API_KEY=your_financial_modeling_prep_api_key_here
```

## Quick Start

### Basic Sentiment Analysis

Extract sentiment from the latest earnings call in three lines:

```python
from earnings_analyzer.api import fetch_transcript, score_sentiment

# Retrieve Apple's latest earnings call transcript
transcript = fetch_transcript("AAPL")

# Perform AI sentiment analysis
sentiment = score_sentiment(transcript['transcript_text'])

print(f"Sentiment Score: {sentiment['overall_sentiment_score']}/10")
print(f"Confidence: {sentiment['confidence_level']:.0%}")
print("Key Themes:", sentiment['key_themes'])
```

**Example Output:**
```
Sentiment Score: 7.8/10
Confidence: 85%
Key Themes: ['iPhone 15 strong demand', 'Services revenue growth', 'China market recovery', 'AI integration plans']
```

### Complete Analysis

Obtain transcript, sentiment, company data, and stock performance in a single function call:

```python
from earnings_analyzer.api import analyze_earnings_call

# Comprehensive analysis for Apple's latest earnings
results = analyze_earnings_call("AAPL")

print(f"Company: {results['profile']['companyName']}")
print(f"Sentiment: {results['sentiment']['overall_sentiment_score']}/10")
if results['stock_performance']:
    print(f"1-Week Stock Performance: {results['stock_performance']['performance_1_week']:.1%}")
```

### Specific Quarter Analysis

```python
# Analyze Microsoft Q3 2024 earnings
transcript = fetch_transcript("MSFT", quarter="Q3", year=2024)
sentiment = score_sentiment(transcript['transcript_text'])
```

### Custom Prompt Analysis

Create specialized analyses with custom prompts for research purposes:

```python
# Define a custom research prompt
ai_prompt = """
Analyze this earnings call for AI-related developments.
Return JSON: {"ai_confidence": [1-10], "ai_announcements": [list]}
"""

# Apply to any transcript
sentiment = score_sentiment(transcript['transcript_text'], custom_prompt=ai_prompt)
print(f"AI Confidence: {sentiment['ai_confidence']}/10")
print("AI Announcements:", sentiment['ai_announcements'])
```

### Batch Processing

**Method 1: Using convenience function (recommended)**
```python
from earnings_analyzer.api import batch_analyze_earnings_calls

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
results = batch_analyze_earnings_calls(tickers)

for ticker, result in zip(tickers, results):
    if result:
        sentiment = result['sentiment']
        print(f"{ticker}: {sentiment['overall_sentiment_score']}/10")
```

**Method 2: Manual pipeline for custom processing**
```python
from earnings_analyzer.api import batch_fetch_transcripts, batch_score_sentiment

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]

# Fetch all transcripts
transcripts = batch_fetch_transcripts(tickers)

# Extract transcript text and analyze sentiment
transcript_texts = [t['transcript_text'] for t in transcripts if t and t.get('transcript_text')]
sentiments = batch_score_sentiment(transcript_texts)

# Match results back to tickers
for i, ticker in enumerate(tickers):
    if i < len(sentiments) and sentiments[i]:
        print(f"{ticker}: {sentiments[i]['overall_sentiment_score']}/10")
```

**Method 3: Quick sentiment-only batch analysis**
```python
from earnings_analyzer.api import quick_sentiment_analysis

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
for ticker in tickers:
    result = quick_sentiment_analysis(ticker)
    if result:
        sentiment = result['sentiment']
        print(f"{ticker}: {sentiment['overall_sentiment_score']}/10")
```

## Architecture: Two Analysis Approaches

### Composable Functions (In-Memory)
Designed for custom analysis pipelines, data science workflows, and scenarios where persistence is not required:

```python
from earnings_analyzer.api import (
    fetch_transcript, 
    score_sentiment, 
    fetch_company_profile,
    calculate_stock_performance
)

# Build custom analysis pipeline
transcript = fetch_transcript("NVDA")
sentiment = score_sentiment(transcript['transcript_text'])
profile = fetch_company_profile("NVDA")
performance = calculate_stock_performance("NVDA", transcript['call_date'])
```

### Database-Backed Analysis (Persistent)
Optimal for building historical datasets, tracking trends over time, and repeated analysis:

```python
from earnings_analyzer.api import EarningsAnalyzer

analyzer = EarningsAnalyzer()

# Results automatically cached for subsequent queries
results = analyzer.analyze("TSLA")

# Access historical analysis data
historical_calls = analyzer.get_existing_calls("TSLA")
print(f"Database contains {len(historical_calls)} previous analyses")

# Batch analysis with automatic caching
tech_stocks = ["AAPL", "MSFT", "GOOGL", "META", "AMZN"]
all_results = analyzer.batch_analyze(tech_stocks)
```

## Usage Guidelines

**Composable Functions Are Appropriate When:**
- Building custom data pipelines
- Performing one-off analysis or research
- Integrating with existing pandas/numpy workflows
- Data persistence is not required
- Maximum flexibility is essential

**Database-Backed Analysis Is Appropriate When:**
- Tracking companies across multiple quarters
- Building historical sentiment datasets
- Analyzing longitudinal trends and patterns
- Working repeatedly with the same companies
- Automatic result caching is beneficial

## Configuration and Setup Validation

Check your configuration before starting analysis:

```python
from earnings_analyzer.api import validate_api_configuration, check_data_availability

# Validate API keys and dependencies
config = validate_api_configuration()
if config['fully_configured']:
    print("✓ Ready for analysis")
else:
    print("Configuration issues:", config['errors'])

# Check data availability for specific ticker
availability = check_data_availability("AAPL")
if availability['analysis_feasible']:
    print("✓ Data available for AAPL")
else:
    print("Issues:", availability['errors'])
```

## Command Line Interface

```bash
# Analyze latest earnings call
earnings-analyzer --ticker AAPL

# Analyze specific quarter
earnings-analyzer --ticker MSFT --quarter Q2 --year 2024

# In-memory analysis without database storage
earnings-analyzer --ticker GOOGL --no-db --quick

# List historical analyses in database
earnings-analyzer --ticker TSLA --list-calls
```

## API Reference

| Function | Purpose | Returns |
|----------|---------|---------|
| `fetch_transcript(ticker, quarter, year)` | Retrieve earnings transcript | Dict with transcript text, URL, date |
| `score_sentiment(text, model, custom_prompt)` | Perform AI sentiment analysis | Dict with score, confidence, themes |
| `fetch_company_profile(ticker)` | Obtain company metadata | Dict with sector, industry, financials |
| `calculate_stock_performance(ticker, date)` | Analyze post-earnings price movements | Dict with performance metrics |
| `analyze_earnings_call(ticker, ...)` | Complete in-memory analysis | Dict with all analysis components |
| `quick_sentiment_analysis(ticker, ...)` | Fast transcript + sentiment only | Dict with transcript and sentiment |
| `batch_analyze_earnings_calls(tickers, ...)` | Batch complete analysis | List of analysis results |
| `check_data_availability(ticker, ...)` | Check data availability | Dict with availability status |
| `validate_api_configuration()` | Validate setup | Dict with configuration status |
| `EarningsAnalyzer().analyze(ticker, ...)` | Complete analysis with database caching | Dict with all analysis components |

## Advanced Use Cases

### Sentiment Trend Analysis
```python
analyzer = EarningsAnalyzer()

# Analyze sentiment evolution over time
calls = analyzer.get_existing_calls("AAPL")
scores = [call['overall_sentiment_score'] for call in calls]
dates = [call['call_date'] for call in calls]

# Visualize sentiment trends (requires matplotlib)
import matplotlib.pyplot as plt
plt.plot(dates, scores)
plt.title("Apple Earnings Sentiment Trend")
```

### Research-Focused Analysis
```python
# Risk assessment prompt
risk_prompt = """
Analyze this earnings call for risk factors and management concerns.
Return JSON: {"risk_level": [1-10], "risks": [list], "management_anxiety": "assessment"}
"""

risk_analysis = score_sentiment(transcript['transcript_text'], custom_prompt=risk_prompt)

# Growth strategy prompt  
growth_prompt = """
Examine growth strategies and expansion plans discussed.
Return JSON: {"growth_optimism": [1-10], "expansion_plans": [list]}
"""

growth_analysis = score_sentiment(transcript['transcript_text'], custom_prompt=growth_prompt)
```

### Portfolio-Level Analysis
```python
# Analyze complete portfolio
portfolio = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]
results = analyzer.batch_analyze(portfolio)

# Identify highest sentiment score
best_sentiment = max(results, key=lambda x: x['sentiment']['overall_sentiment_score'] if x else 0)
print(f"Highest sentiment: {best_sentiment['profile']['symbol']}")
```

### Data Pipeline Integration
```python
import pandas as pd
from earnings_analyzer.api import batch_analyze_earnings_calls

# Analyze portfolio and create DataFrame
portfolio = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]
results = batch_analyze_earnings_calls(portfolio)

# Convert to DataFrame for analysis
data = []
for result in results:
    if result:
        data.append({
            'ticker': result['analysis_metadata']['ticker'],
            'sentiment_score': result['sentiment']['overall_sentiment_score'],
            'confidence': result['sentiment']['confidence_level'],
            'sector': result['profile'].get('sector'),
            '1w_performance': result['stock_performance']['performance_1_week'] if result['stock_performance'] else None
        })

df = pd.DataFrame(data)
print(df.describe())
```

## Complete Documentation

**[View Complete Tutorial](vignette.ipynb)** - Comprehensive documentation with advanced examples

This detailed Jupyter notebook provides:
- Complete API key setup and troubleshooting procedures
- Detailed examples of both analysis approaches
- Custom prompt design for specialized research questions
- Advanced use cases and batch processing techniques
- Methods for building sentiment trends and correlations
- Integration patterns for data science workflows
- Performance optimization strategies

## Important Considerations

**Sentiment Analysis Limitations**

The sentiment scores generated by this package are experimental and require validation. Earnings call sentiment may already be incorporated into stock prices by the time transcripts become publicly available. This package provides a framework for testing sentiment-performance correlations, but users should:

- Validate sentiment scores against manual analysis of sample transcripts
- Test correlations across different time windows and market conditions  
- Consider that institutional traders access earnings information in real-time during calls

This is designed as a research tool, not a trading signal generator.

**Data Usage Compliance**

This package is intended for educational and research purposes. Users are responsible for:
- Obtaining proper API keys and respecting rate limits
- Complying with data provider terms of service  
- Ensuring usage aligns with institutional and regulatory requirements

## Troubleshooting

**API Key Configuration:**
```python
from earnings_analyzer.config import set_gemini_api_key, set_fmp_api_key

# Configure keys programmatically (useful in notebooks)
set_gemini_api_key("your_key_here")
set_fmp_api_key("your_key_here")
```

**Database Location:**
```python
import os
# Specify custom database location
os.environ["EARNINGS_ANALYZER_DB"] = "/path/to/your/database.db"
```

**Batch Processing Issues:**
```python
# If batch functions aren't working as expected, try the convenience function
from earnings_analyzer.api import batch_analyze_earnings_calls

# This handles all the data structure matching automatically
results = batch_analyze_earnings_calls(["AAPL", "MSFT"])
```

**Configuration Validation:**
```python
from earnings_analyzer.api import validate_api_configuration

config = validate_api_configuration()
if not config['fully_configured']:
    print("Issues found:")
    for error in config['errors']:
        print(f"  - {error}")
```

**Common Issues:**
- **403 Errors**: Verify API keys and check rate limits
- **Transcript Not Found**: Verify ticker symbol and try alternative quarter/year
- **Import Errors**: Confirm installation with `pip install earnings-analyzer`
- **Batch Processing Errors**: Use `batch_analyze_earnings_calls()` for simplest batch processing
- **Memory Issues**: For large batches, process in smaller chunks or use `quick_sentiment_analysis()`

## Performance Tips

**For Large-Scale Analysis:**
```python
# Process in chunks to manage memory and API rate limits
def analyze_large_portfolio(tickers, chunk_size=5):
    results = []
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i+chunk_size]
        chunk_results = batch_analyze_earnings_calls(chunk)
        results.extend(chunk_results)
        time.sleep(10)  # Respect rate limits
    return results

# Use database-backed analysis for repeated queries
analyzer = EarningsAnalyzer()
for ticker in large_portfolio:
    result = analyzer.analyze(ticker)  # Automatically cached
```

## Contributing

Contributions are welcome. This package is designed for extensibility and community development.

## License

MIT License - see LICENSE file for details.