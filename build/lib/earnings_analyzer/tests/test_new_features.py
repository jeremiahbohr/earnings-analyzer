import unittest
from unittest.mock import patch, MagicMock
import os
import pandas as pd
import importlib

# Import modules to be tested
from earnings_analyzer.analysis.sentiment_analyzer import analyze_sentiment, generate_qualitative_assessment
from earnings_analyzer.analyzer import EarningsAnalyzer
from earnings_analyzer.config import set_gemini_api_key, set_fmp_api_key, get_gemini_api_key, get_fmp_api_key

class TestNewFeatures(unittest.TestCase):

    def setUp(self):
        # Clear environment variables before each test to ensure clean state
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
        if "FMP_API_KEY" in os.environ:
            del os.environ["FMP_API_KEY"]
        
        # Reload config module to ensure API keys are re-evaluated from os.environ
        import earnings_analyzer.config as config_module
        importlib.reload(config_module)
        self.config_module = config_module

    @patch('earnings_analyzer.analysis.sentiment_analyzer.genai.GenerativeModel')
    @patch('earnings_analyzer.analysis.sentiment_analyzer.genai.configure')
    @patch('earnings_analyzer.analysis.sentiment_analyzer.get_gemini_api_key')
    def test_generate_qualitative_assessment_success(self, mock_get_gemini_api_key, mock_genai_configure, MockGenerativeModel):
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content.return_value.text = "This is a positive assessment." # Mock the response

        # Ensure GEMINI_API_KEY is set for this test
        mock_get_gemini_api_key.return_value = "mock_gemini_key"

        sentiment_data = {
            'overall_sentiment_score': 8,
            'confidence_level': 0.9,
            'key_themes': ['growth', 'innovation']
        }
        assessment = generate_qualitative_assessment(sentiment_data)
        self.assertEqual(assessment, "This is a positive assessment.")
        mock_get_gemini_api_key.assert_called_once()
        mock_genai_configure.assert_called_once_with(api_key="mock_gemini_key")

    @patch('earnings_analyzer.analysis.sentiment_analyzer.genai.GenerativeModel')
    @patch('earnings_analyzer.analysis.sentiment_analyzer.genai.configure')
    @patch('earnings_analyzer.analysis.sentiment_analyzer.get_gemini_api_key')
    def test_generate_qualitative_assessment_no_api_key(self, mock_get_gemini_api_key, mock_genai_configure, MockGenerativeModel):
        # Ensure GEMINI_API_KEY is not set for this test
        mock_get_gemini_api_key.return_value = None

        sentiment_data = {
            'overall_sentiment_score': 8,
            'confidence_level': 0.9,
            'key_themes': ['growth', 'innovation']
        }
        assessment = generate_qualitative_assessment(sentiment_data)
        self.assertIsNone(assessment)
        mock_get_gemini_api_key.assert_called_once()
        mock_genai_configure.assert_not_called()

    @patch('earnings_analyzer.analyzer.EarningsAnalyzer.analyze')
    @patch('earnings_analyzer.analysis.sentiment_analyzer.generate_qualitative_assessment')
    def test_analyze_to_dataframe_success(self, mock_generate_qualitative_assessment, mock_analyze):
        # Mock the analyze method's return value
        mock_analyze.return_value = {
            'profile': {'symbol': 'TEST', 'companyName': 'Test Co', 'sector': 'Tech', 'industry': 'Software'},
            'sentiment': {'overall_sentiment_score': 7, 'confidence_level': 0.8, 'key_themes': ['theme1']},
            'stock_performance': {'price_at_call': 100, 'performance_1_week': 0.01, 'performance_1_month': 0.05, 'performance_3_month': 0.10},
            'correlation': 0.75
        }
        # Mock the qualitative assessment
        mock_generate_qualitative_assessment.return_value = "This is a test assessment."

        analyzer = EarningsAnalyzer()
        df = analyzer.analyze_to_dataframe("TEST")

        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(df['Ticker'].iloc[0], 'TEST')
        self.assertEqual(df['Qualitative Assessment'].iloc[0], "This is a test assessment.")
        self.assertEqual(df['Overall Sentiment Score'].iloc[0], 7)
        self.assertEqual(df['3 Month Performance'].iloc[0], 0.10)

    @patch.dict(os.environ, {'GEMINI_API_KEY': 'initial_gemini_key'}, clear=True)
    def test_set_gemini_api_key(self):
        test_key = "new_gemini_key"
        set_gemini_api_key(test_key)
        self.assertEqual(os.environ.get("GEMINI_API_KEY"), test_key)
        self.assertEqual(self.config_module.get_gemini_api_key(), test_key)

    @patch.dict(os.environ, {'FMP_API_KEY': 'initial_fmp_key'}, clear=True)
    def test_set_fmp_api_key(self):
        test_key = "new_fmp_key"
        set_fmp_api_key(test_key)
        self.assertEqual(os.environ.get("FMP_API_KEY"), test_key)
        self.assertEqual(self.config_module.get_fmp_api_key(), test_key)

if __name__ == '__main__':
    unittest.main()