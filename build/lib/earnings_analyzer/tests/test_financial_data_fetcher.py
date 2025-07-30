import unittest
from unittest.mock import patch
import json

from earnings_analyzer.data.financial_data_fetcher import get_company_profile, get_historical_prices

class TestFinancialDataFetcher(unittest.TestCase):

    @patch('requests.get')
    def test_get_company_profile_success(self, mock_get):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            "symbol": "AAPL",
            "companyName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics"
        }]
        mock_get.return_value = mock_response

        profile = get_company_profile("AAPL")
        self.assertIsNotNone(profile)
        self.assertEqual(profile['symbol'], "AAPL")
        self.assertEqual(profile['companyName'], "Apple Inc.")

    @patch('requests.get')
    def test_get_company_profile_not_found(self, mock_get):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        profile = get_company_profile("NONEXISTENT")
        self.assertIsNone(profile)

    @patch('requests.get')
    def test_get_historical_prices_success(self, mock_get):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "historical": [
                {"date": "2024-07-29", "close": 213.00},
                {"date": "2024-07-28", "close": 212.00}
            ]
        }
        mock_get.return_value = mock_response

        prices = get_historical_prices("AAPL")
        self.assertIsNotNone(prices)
        self.assertEqual(len(prices), 2)
        self.assertEqual(prices[0]['close'], 213.00)

    @patch('requests.get')
    def test_get_historical_prices_not_found(self, mock_get):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        prices = get_historical_prices("NONEXISTENT")
        self.assertIsNone(prices)

if __name__ == '__main__':
    unittest.main()
