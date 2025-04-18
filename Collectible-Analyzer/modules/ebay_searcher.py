import requests
from bs4 import BeautifulSoup
import logging
import re
from statistics import mean

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class eBaySearcher:
    """Handles searching eBay for sold baseball card listings to estimate value."""

    def __init__(self):
        self.base_url = "https://www.ebay.com/sch/i.html"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def search_card_value(self, description):
        """Search eBay for sold listings of a baseball card and estimate its value."""
        try:
            # Clean description for search query
            query = description.replace(" rookie card", "").replace(" card", "").strip()
            params = {
                "_nkw": query,
                "_sacat": 0,
                "LH_Sold": 1,  # Only sold items
                "LH_Complete": 1,  # Completed listings
                "_ipg": 25,  # Items per page
                "_fosrp": 1  # Sort by relevance
            }

            # Send request to eBay
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find sold item prices
            prices = []
            price_elements = soup.select(".s-item__price")
            for elem in price_elements:
                price_text = elem.text.strip()
                # Extract numeric value (e.g., "$123.45" or "US $123.45")
                match = re.search(r'[\$US\s]*([\d,.]+)', price_text)
                if match:
                    try:
                        price = float(match.group(1).replace(",", ""))
                        prices.append(price)
                    except ValueError:
                        continue

            if not prices:
                logger.info(f"No sold listings found for: {query}")
                return None

            # Calculate average price (or range for more granularity)
            avg_price = mean(prices)
            price_range = f"${min(prices):.2f}-${max(prices):.2f}" if len(prices) > 1 else f"${avg_price:.2f}"
            logger.info(f"eBay value for {query}: {price_range} (based on {len(prices)} listings)")
            return price_range

        except Exception as e:
            logger.error(f"Error searching eBay for {description}: {str(e)}")
            return None