import requests
import logging
from config import config
from utils import normalize_name_for_filesystem

async def categorize_and_name_content(combined_text: str, tweet_id: str, max_retries=3) -> tuple:
    """ Uses the AI model to categorize and name content, ensuring a valid output. """
    prompt_text = config.agent_prompt_categorization.replace("{content}", combined_text)
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{config.ollama_url}/api/generate",
                json={"prompt": prompt_text, "model": config.text_model, "stream": False},
                timeout=120
            )
            response.raise_for_status()
            raw_response = response.json().get("response", "").strip()

            main_cat, sub_cat, item_name = raw_response.split('|')
            main_cat, sub_cat, item_name = map(normalize_name_for_filesystem, [main_cat, sub_cat, item_name])
            return (main_cat, sub_cat, item_name)

        except Exception as e:
            logging.error(f"Categorization attempt {attempt + 1} failed for tweet {tweet_id}: {e}")

    return ("software_engineering", "best_practices", f"fallback_{tweet_id[:8]}")
