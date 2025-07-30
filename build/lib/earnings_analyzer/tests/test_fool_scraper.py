import unittest
from unittest.mock import patch, MagicMock
import requests

from earnings_analyzer.analysis.fool_scraper import find_latest_transcript_url, get_transcript_from_fool

class TestFoolScraper(unittest.TestCase):

    @patch('earnings_analyzer.analysis.fool_scraper.search')
    def test_find_latest_transcript_url_success(self, mock_search):
        mock_search.return_value = iter(['https://www.fool.com/earnings/call-transcripts/2024/01/30/apple-aapl-q1-2025-earnings-call-transcript/'])
        url = find_latest_transcript_url("AAPL")
        self.assertIsNotNone(url)
        self.assertIn("fool.com", url)

    @patch('earnings_analyzer.analysis.fool_scraper.search')
    def test_find_latest_transcript_url_not_found(self, mock_search):
        mock_search.return_value = iter([])
        url = find_latest_transcript_url("NONEXISTENT")
        self.assertIsNone(url)

    @patch('requests.get')
    def test_get_transcript_from_fool_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<html><body><div class='article-body'><p>This is the transcript.</p></div></body></html>"
        mock_get.return_value = mock_response

        transcript = get_transcript_from_fool("http://example.com/transcript")
        self.assertIsNotNone(transcript)
        self.assertIn("This is the transcript.", transcript)

    @patch('requests.get')
    def test_get_transcript_from_fool_no_article_body(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<html><body><div>No transcript here.</div></body></html>"
        mock_get.return_value = mock_response

        transcript = get_transcript_from_fool("http://example.com/no-transcript")
        self.assertIsNone(transcript)

    @patch('requests.get')
    def test_get_transcript_from_fool_http_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("HTTP Error")
        transcript = get_transcript_from_fool("http://example.com/error")
        self.assertIsNone(transcript)

if __name__ == '__main__':
    unittest.main()