from typing import Dict, Any, Tuple, Optional
import logging
from datetime import datetime
from knowledge_base_agent.exceptions import CategoryGenerationError
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.types import CategoryInfo
import json
import re

async def categorize_and_name_content(
    ollama_url: str,
    text: str,
    text_model: str,
    tweet_id: str,
    category_manager: CategoryManager,
    http_client: HTTPClient
) -> Tuple[str, str, str]:
    """Categorize content and generate item name."""
    try:
        # Get categories using the category manager
        main_cat, sub_cat = await category_manager.classify_content(
            text=text,
            tweet_id=tweet_id
        )

        # Normalize categories
        main_cat = main_cat.lower().replace(' ', '_')
        sub_cat = sub_cat.lower().replace(' ', '_')
        
        # Generate item name
        item_name = await category_manager.generate_item_name(
            text=text,
            main_category=main_cat,
            sub_category=sub_cat,
            tweet_id=tweet_id
        )
        
        # Ensure category exists
        if not category_manager.category_exists(main_cat, sub_cat):
            category_manager.add_category(main_cat, sub_cat)
            
        return main_cat, sub_cat, item_name
        
    except Exception as e:
        logging.error(f"Failed to categorize content for tweet {tweet_id}: {e}")
        raise CategoryGenerationError(f"Failed to categorize content for tweet {tweet_id}: {e}")

async def process_categories(
    tweet_id: str,
    tweet_data: Dict[str, Any],
    config: Config,
    http_client: HTTPClient,
    state_manager: Optional[StateManager] = None
) -> Dict[str, Any]:
    """Process and assign categories to a tweet."""
    from .media_processor import process_media_content  # Import here to avoid circular dependency
    
    try:
        # Skip if already categorized
        if tweet_data.get('categories_processed', False):
            logging.info(f"Categories already processed for tweet {tweet_id}, skipping...")
            return tweet_data

        # Ensure media is processed first
        if not tweet_data.get('media_processed', False):
            logging.info(f"Media not yet processed for tweet {tweet_id}, processing now...")
            tweet_data = await process_media_content(tweet_data, http_client, config)

        # Generate categories
        tweet_text = tweet_data.get('full_text', '')
        image_descriptions = tweet_data.get('image_descriptions', [])
        combined_text = f"{tweet_text}\n\nImage Descriptions:\n" + "\n".join(image_descriptions)

        category_manager = CategoryManager(config, http_client=http_client)
        main_cat, sub_cat, item_name = await categorize_and_name_content(
            ollama_url=config.ollama_url,
            text=combined_text,
            text_model=config.text_model,
            tweet_id=tweet_id,
            category_manager=category_manager,
            http_client=http_client
        )
        
        # Save categories
        tweet_data['categories'] = {
            'main_category': main_cat,
            'sub_category': sub_cat,
            'item_name': item_name,
            'model_used': config.text_model,
            'categorized_at': datetime.now().isoformat()
        }
        tweet_data['categories_processed'] = True

        # Update state if manager provided
        if state_manager:
            await state_manager.update_tweet_data(tweet_id, tweet_data)

        return tweet_data

    except Exception as e:
        logging.error(f"Failed to process categories for tweet {tweet_id}: {str(e)}")
        raise CategoryGenerationError(f"Failed to process categories: {str(e)}")

async def generate_categories(tweet_text: str, tweet_id: str, http_client: HTTPClient, text_model: str) -> CategoryInfo:
    """Generate category information from tweet text."""
    try:
        prompt = (
            "Analyze this tweet and provide category information in JSON format:\n\n"
            f"Tweet: {tweet_text}\n\n"
            "Required format:\n"
            "{\n"
            '  "category": "main technical category",\n'
            '  "subcategory": "specific technical subcategory",\n'
            '  "name": "concise_technical_name",\n'
            '  "description": "brief technical description"\n'
            "}\n\n"
            "Rules:\n"
            "- Categories should be technical and specific\n"
            "- Name should be 2-4 words, lowercase with underscores\n"
            "- Description should be 1-2 sentences\n"
        )
        logging.debug(f"Sending category generation prompt for tweet text: {tweet_text[:100]}...")
        # Use the rate-limited http_client
        response_text = await http_client.ollama_generate(
            model=text_model,
            prompt=prompt,
            temperature=0.7  # More deterministic for categories
        )
        
        if not response_text:
            raise CategoryGenerationError("Empty response from Ollama")
        
        try:
            # Try to parse the JSON response
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract JSON from the response
            # Sometimes the model might include additional text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse extracted JSON: {e}")
                    logging.error(f"Raw response: {response_text}")
                    raise CategoryGenerationError("Invalid JSON format in response")
            else:
                logging.error(f"No JSON found in response: {response_text}")
                raise CategoryGenerationError("No valid JSON found in response")
        
        # Validate required fields
        required_fields = ["category", "subcategory", "name", "description"]
        if not all(field in result for field in required_fields):
            missing_fields = [field for field in required_fields if field not in result]
            raise CategoryGenerationError(f"Missing required fields: {missing_fields}")
        
        # Normalize field values
        result["category"] = result["category"].lower().replace(" ", "_")
        result["subcategory"] = result["subcategory"].lower().replace(" ", "_")
        result["name"] = result["name"].lower().replace(" ", "_")
        
        logging.info(f"Successfully generated categories: {result}")
        return CategoryInfo(**result)
        
    except Exception as e:
        logging.error(f"Category generation failed: {str(e)}")
        logging.error(f"Tweet text: {tweet_text[:100]}...")
        raise CategoryGenerationError(f"Failed to generate categories: {str(e)}")