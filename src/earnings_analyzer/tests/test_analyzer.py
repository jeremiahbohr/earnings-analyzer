import pytest
from earnings_analyzer.analyzer import EarningsAnalyzer
from earnings_analyzer.analysis import fool_scraper, sentiment_analyzer
from earnings_analyzer.data import financial_data_fetcher, database

@pytest.fixture
def analyzer():
    """
    Fixture to provide an EarningsAnalyzer instance.
    """
    return EarningsAnalyzer()

def test_analyze_latest_transcript(analyzer, mocker):
    """
    Tests that analyze() correctly calls find_latest_transcript_url when no quarter/year is specified.
    """
    mocker.patch.object(fool_scraper, 'find_latest_transcript_url', return_value="http://www.fool.com/earnings/call-transcripts/2023/01/25/test-q1-2023-earnings-call-transcript/")
    mocker.patch.object(fool_scraper, 'get_transcript_from_fool', return_value="mock transcript")
    mocker.patch.object(financial_data_fetcher, 'get_company_profile', return_value={'symbol': 'TEST', 'companyName': 'Test Co'})
    mocker.patch.object(sentiment_analyzer, 'analyze_sentiment', return_value={'overall_sentiment_score': 8, 'confidence_level': 0.9, 'key_themes': ['growth']})
    mocker.patch.object(financial_data_fetcher, 'get_historical_prices', return_value=[
        {'date': '2023-01-01', 'close': 100.0},
        {'date': '2023-01-25', 'close': 102.0},
        {'date': '2023-02-01', 'close': 105.0},
        {'date': '2023-03-01', 'close': 110.0},
        {'date': '2023-04-01', 'close': 115.0},
        {'date': '2023-05-01', 'close': 120.0},
        {'date': '2024-01-01', 'close': 130.0},
        {'date': '2024-02-01', 'close': 135.0},
        {'date': '2024-03-01', 'close': 140.0},
        {'date': '2024-04-01', 'close': 145.0},
        {'date': '2024-05-01', 'close': 150.0},
        {'date': '2025-01-01', 'close': 160.0},
        {'date': '2025-02-26', 'close': 165.0},
        {'date': '2025-03-05', 'close': 170.0},
        {'date': '2025-04-01', 'close': 175.0},
        {'date': '2025-05-01', 'close': 180.0},
    ])
    mocker.patch.object(database, 'select_company_by_ticker', return_value=None)
    mocker.patch.object(database, 'insert_company')
    mocker.patch.object(database, 'insert_earnings_call', return_value=1)
    mocker.patch.object(database, 'insert_sentiment_analysis')
    mocker.patch.object(database, 'insert_stock_performance')

    results = analyzer.analyze('TEST')

    fool_scraper.find_latest_transcript_url.assert_called_once_with('TEST')
    assert results is not None
    assert results['profile']['symbol'] == 'TEST'
    assert results['quarter'] == 'Q1'  # Should be extracted from URL
    assert results['call_date'] == '2023-01-25'  # Should be extracted from URL

def test_analyze_specific_transcript(analyzer, mocker):
    """
    Tests that analyze() correctly calls find_transcript_url_by_quarter when quarter/year are specified.
    """
    mocker.patch.object(fool_scraper, 'find_transcript_url_by_quarter', return_value="http://www.fool.com/earnings/call-transcripts/2023/01/25/TEST-q1-2023-earnings-call-transcript/")
    mocker.patch.object(fool_scraper, 'get_transcript_from_fool', return_value="mock transcript")
    mocker.patch.object(financial_data_fetcher, 'get_company_profile', return_value={'symbol': 'TEST', 'companyName': 'Test Co'})
    mocker.patch.object(sentiment_analyzer, 'analyze_sentiment', return_value={'overall_sentiment_score': 8, 'confidence_level': 0.9, 'key_themes': ['growth']})
    mocker.patch.object(financial_data_fetcher, 'get_historical_prices', return_value=[
        {'date': '2023-01-01', 'close': 100.0},
        {'date': '2023-01-25', 'close': 102.0},
        {'date': '2023-02-01', 'close': 105.0},
        {'date': '2023-03-01', 'close': 110.0},
        {'date': '2023-04-01', 'close': 115.0},
        {'date': '2023-05-01', 'close': 120.0},
        {'date': '2024-01-01', 'close': 130.0},
        {'date': '2024-02-01', 'close': 135.0},
        {'date': '2024-03-01', 'close': 140.0},
        {'date': '2024-04-01', 'close': 145.0},
        {'date': '2024-05-01', 'close': 150.0},
        {'date': '2025-01-01', 'close': 160.0},
        {'date': '2025-02-26', 'close': 165.0},
        {'date': '2025-03-05', 'close': 170.0},
        {'date': '2025-04-01', 'close': 175.0},
        {'date': '2025-05-01', 'close': 180.0},
    ])
    mocker.patch.object(database, 'select_company_by_ticker', return_value=None)
    mocker.patch.object(database, 'insert_company')
    mocker.patch.object(database, 'insert_earnings_call', return_value=1)
    mocker.patch.object(database, 'insert_sentiment_analysis')
    mocker.patch.object(database, 'insert_stock_performance')

    results = analyzer.analyze('TEST', quarter="Q1", year=2023)

    fool_scraper.find_transcript_url_by_quarter.assert_called_once_with('TEST', "Q1", 2023)
    assert results is not None
    assert results['profile']['symbol'] == 'TEST'
    assert results['quarter'] == 'Q1'  # Should use provided quarter
    assert results['call_date'] == '2023-01-01'  # Should use constructed date from quarter/year

def test_analyze_to_dataframe_output(analyzer, mocker):
    """
    Tests that analyze_to_dataframe returns a DataFrame with expected columns.
    """
    mocker.patch.object(fool_scraper, 'find_latest_transcript_url', return_value="http://www.fool.com/earnings/call-transcripts/2023/01/25/test-q1-2023-earnings-call-transcript/")
    mocker.patch.object(fool_scraper, 'get_transcript_from_fool', return_value="mock transcript")
    mocker.patch.object(financial_data_fetcher, 'get_company_profile', return_value={'symbol': 'TEST', 'companyName': 'Test Co', 'sector': 'Tech', 'industry': 'Software'})
    mocker.patch.object(sentiment_analyzer, 'analyze_sentiment', return_value={'overall_sentiment_score': 8, 'confidence_level': 0.9, 'key_themes': ['growth']})
    mocker.patch.object(sentiment_analyzer, 'generate_qualitative_assessment', return_value="Good.")
    mocker.patch.object(financial_data_fetcher, 'get_historical_prices', return_value=[
        {'date': '2023-01-01', 'close': 100.0},
        {'date': '2023-01-25', 'close': 102.0},
        {'date': '2023-02-01', 'close': 105.0},
        {'date': '2023-03-01', 'close': 110.0},
        {'date': '2023-04-01', 'close': 115.0},
        {'date': '2023-05-01', 'close': 120.0},
        {'date': '2024-01-01', 'close': 130.0},
        {'date': '2024-02-01', 'close': 135.0},
        {'date': '2024-03-01', 'close': 140.0},
        {'date': '2024-04-01', 'close': 145.0},
        {'date': '2024-05-01', 'close': 150.0},
        {'date': '2025-01-01', 'close': 160.0},
        {'date': '2025-02-26', 'close': 165.0},
        {'date': '2025-03-05', 'close': 170.0},
        {'date': '2025-04-01', 'close': 175.0},
        {'date': '2025-05-01', 'close': 180.0},
    ])
    mocker.patch.object(database, 'select_company_by_ticker', return_value=None)
    mocker.patch.object(database, 'insert_company')
    mocker.patch.object(database, 'insert_earnings_call', return_value=1)
    mocker.patch.object(database, 'insert_sentiment_analysis')
    mocker.patch.object(database, 'insert_stock_performance')

    df = analyzer.analyze_to_dataframe('TEST')

    assert not df.empty
    expected_columns = [
        'Ticker', 'Company Name', 'Sector', 'Industry', 'Sentiment Model',
        'Overall Sentiment Score', 'Sentiment Confidence', 'Key Themes',
        'Qualitative Assessment', 'Price at Call', '1 Week Performance',
        '1 Month Performance', '3 Month Performance', 'Call Date', 'Quarter'  # Updated to match actual DataFrame
    ]
    assert all(col in df.columns for col in expected_columns)
    assert df['Ticker'].iloc[0] == 'TEST'
    assert df['Quarter'].iloc[0] == 'Q1'  # Should be extracted from URL
    assert df['Call Date'].iloc[0] == '2023-01-25'  # Should be extracted from URL

def test_analyze_to_dataframe_specific_quarter_output(analyzer, mocker):
    """
    Tests that analyze_to_dataframe returns a DataFrame with expected columns and correct quarter/year.
    """
    mocker.patch.object(fool_scraper, 'find_transcript_url_by_quarter', return_value="http://example.com/2023/01/25/test-q1-2023-earnings-call-transcript")
    mocker.patch.object(fool_scraper, 'get_transcript_from_fool', return_value="mock transcript")
    mocker.patch.object(financial_data_fetcher, 'get_company_profile', return_value={'symbol': 'TEST', 'companyName': 'Test Co', 'sector': 'Tech', 'industry': 'Software'})
    mocker.patch.object(sentiment_analyzer, 'analyze_sentiment', return_value={'overall_sentiment_score': 8, 'confidence_level': 0.9, 'key_themes': ['growth']})
    mocker.patch.object(sentiment_analyzer, 'generate_qualitative_assessment', return_value="Good.")
    mocker.patch.object(financial_data_fetcher, 'get_historical_prices', return_value=[
        {'date': '2023-01-01', 'close': 100.0},
        {'date': '2023-01-25', 'close': 102.0},
        {'date': '2023-02-01', 'close': 105.0},
        {'date': '2023-03-01', 'close': 110.0},
        {'date': '2023-04-01', 'close': 115.0},
        {'date': '2023-05-01', 'close': 120.0},
        {'date': '2024-01-01', 'close': 130.0},
        {'date': '2024-02-01', 'close': 135.0},
        {'date': '2024-03-01', 'close': 140.0},
        {'date': '2024-04-01', 'close': 145.0},
        {'date': '2024-05-01', 'close': 150.0},
        {'date': '2025-01-01', 'close': 160.0},
        {'date': '2025-02-26', 'close': 165.0},
        {'date': '2025-03-05', 'close': 170.0},
        {'date': '2025-04-01', 'close': 175.0},
        {'date': '2025-05-01', 'close': 180.0},
    ])
    mocker.patch.object(database, 'select_company_by_ticker', return_value=None)
    mocker.patch.object(database, 'insert_company')
    mocker.patch.object(database, 'insert_earnings_call', return_value=1)
    mocker.patch.object(database, 'insert_sentiment_analysis')
    mocker.patch.object(database, 'insert_stock_performance')

    df = analyzer.analyze_to_dataframe('TEST', quarter="Q1", year=2023)

    assert not df.empty
    expected_columns = [
        'Ticker', 'Company Name', 'Sector', 'Industry', 'Sentiment Model',
        'Overall Sentiment Score', 'Sentiment Confidence', 'Key Themes',
        'Qualitative Assessment', 'Price at Call', '1 Week Performance',
        '1 Month Performance', '3 Month Performance', 'Call Date', 'Quarter'  # Updated to match actual DataFrame
    ]
    assert all(col in df.columns for col in expected_columns)
    assert df['Ticker'].iloc[0] == 'TEST'
    assert df['Quarter'].iloc[0] == 'Q1'  # Should use provided quarter
    assert df['Call Date'].iloc[0] == '2023-01-01'  # Should use constructed date from quarter/year