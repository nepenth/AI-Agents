import asyncio
import unittest
from unittest.mock import patch, AsyncMock
from knowledge_base_agent.playwright_fetcher import fetch_tweet_data_playwright

class TestPlaywrightFetcher(unittest.TestCase):
    @patch("knowledge_base_agent.playwright_fetcher.async_playwright")
    def test_fetch_tweet_data_playwright(self, mock_async_playwright):
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.query_selector_all.return_value = []
        mock_async_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser

        async def run_test():
            result = await fetch_tweet_data_playwright("123")
            self.assertIsInstance(result, dict)
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
