import requests
from bs4 import BeautifulSoup
import logging
import re
from urllib.parse import quote

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VivinoSearcher:
    """Handles searching Vivino for wine bottle prices and ratings."""

    def __init__(self):
        self.base_url = "https://www.vivino.com/search/wines"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def search_wine_value(self, description):
        """Search Vivino for wine bottle details and return price and rating."""
        try:
            # Clean description for search query
            query = description.strip()
            params = {"q": query}

            # Send request to Vivino
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find wine price and rating
            prices = []
            ratings = []
            wine_cards = soup.select(".wine-card")
            for card in wine_cards[:5]:  # Limit to top 5 results for relevance
                # Extract price
                price_elem = card.select_one(".wine-price-value")
                if price_elem:
                    price_text = price_elem.text.strip()
                    match = re.search(r'[\$]?([\d,.]+)', price_text)
                    if match:
                        try:
                            price = float(match.group(1).replace(",", ""))
                            prices.append(price)
                        except ValueError:
                            continue

                # Extract rating
                rating_elem = card.select_one(".average__number")
                if rating_elem:
                    rating_text = rating_elem.text.strip()
                    try:
                        rating = float(rating_text)
                        if 0 <= rating <= 5:
                            ratings.append(rating)
                    except ValueError:
                        continue

            if not prices or not ratings:
                logger.info(f"No Vivino results found for: {query}")
                return None

            # Calculate average price and rating
            avg_price = sum(prices) / len(prices)
            avg_rating = sum(ratings) / len(ratings)
            result = f"${avg_price:.2f}, {avg_rating:.1f}/5"
            logger.info(f"Vivino value for {query}: {result} (based on {len(prices)} listings)")
            return result

        except Exception as e:
            logger.error(f"Error searching Vivino for {description}: {str(e)}")
            return None