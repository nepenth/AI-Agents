import re
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_drink_window(description, item_type):
    """Determine the drink window based on wine description and item type."""
    if item_type.lower() != "wine bottle":
        return None

    try:
        # Extract vintage (e.g., "2015 Napa Valley Cabernet Sauvignon" -> 2015)
        vintage_match = re.search(r'\b(19\d{2}|20\d{2})\b', description)
        vintage = int(vintage_match.group(1)) if vintage_match else None
        current_year = datetime.now().year

        # Define aging potential by varietal/region (based on web search results)
        aging_rules = {
            'cabernet sauvignon': {'years': (10, 15), 'oak': True},
            'merlot': {'years': (5, 7), 'oak': True},
            'pinot noir': {'years': (5, 7), 'oak': False},
            'syrah': {'years': (7, 10), 'oak': True},
            'chardonnay': {'years': (3, 5), 'oak': True},
            'white bordeaux': {'years': (3, 5), 'oak': True},
            'chenin blanc': {'years': (5, 7), 'oak': False},
            'white rioja': {'years': (10, 15), 'oak': True},
            'semillon': {'years': (10, 15), 'oak': False},
            'sauvignon blanc': {'years': (1, 2), 'oak': False},
            'vinho verde': {'years': (1, 2), 'oak': False}
        }

        # Check for varietal/region in description (case-insensitive)
        description_lower = description.lower()
        for varietal, rules in aging_rules.items():
            if varietal in description_lower:
                if not vintage:
                    return "Drink now (vintage unknown)"
                
                min_years, max_years = rules['years']
                age = current_year - vintage
                max_drink_year = vintage + max_years

                if age < min_years:
                    return f"Age until {vintage + min_years}-{max_drink_year}"
                elif min_years <= age <= max_years:
                    return "Drink now"
                else:
                    return "Past-prime"
        
        # Default for unknown varietals
        return "Drink now (unknown varietal)" if not vintage else f"Drink now (age {age} years)"

    except Exception as e:
        logger.error(f"Error determining drink window for {description}: {str(e)}")
        return None