import os
import re # Import regex for parsing
from .image_processor import ImageProcessor
from .text_analyzer import TextAnalyzer
from .data_manager import DataManager
from .ebay_searcher import eBaySearcher
from .vivino_searcher import VivinoSearcher
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Controller:
    """Orchestrates image processing, text analysis, eBay/Vivino search, and data storage workflows."""

    def __init__(self):
        self.image_processor = ImageProcessor()
        self.text_analyzer = TextAnalyzer()
        self.data_manager = DataManager()
        self.ebay_searcher = eBaySearcher()
        self.vivino_searcher = VivinoSearcher()

    def _parse_card_text_blocks(self, raw_text):
        """Parses the vision model OCR output into text blocks for each card."""
        # Split based on the '--- Card [Number] ---' separator (flexible regex)
        # Regex looks for --- Card, optional space, digits, optional space ---, allowing for variations
        separator_pattern = r"-+\s*Card\s*\d+\s*-+"
        blocks = re.split(separator_pattern, raw_text, flags=re.IGNORECASE)
        
        # Filter out empty strings resulting from splits and strip whitespace
        card_texts = [block.strip() for block in blocks if block and block.strip()]
        
        if not card_texts and raw_text.strip():
             # Fallback if separator wasn't found but text exists
             logger.warning("Card separator '--- Card [Number] ---' not found. Treating entire text as one block.")
             return [raw_text.strip()]
             
        return card_texts

    def _parse_structured_insights(self, insights_text):
        """Parses the structured insights string into a dictionary."""
        details = {}
        # Updated regex to handle potential missing fields or variations
        matches = re.findall(r"^(Player|Year|Brand|Value):\s*(.+?)\s*$", insights_text, re.MULTILINE | re.IGNORECASE)
        details = {key.lower(): value.strip() for key, value in matches}
        
        # Standardize keys and handle potential missing keys
        parsed = {
            'player': details.get('player', 'Unknown'),
            'year': details.get('year', 'Unknown'),
            'brand': details.get('brand', 'Unknown'),
            'value': details.get('value', 'Unknown') 
        }
        # Clean up 'Unknown' values explicitly if needed
        for key in parsed:
             if parsed[key].lower() == 'unknown':
                  parsed[key] = None # Store None instead of "Unknown" string

        return parsed

    def process_item(self, image_path, item_type="baseball card", task_id=None, task_status=None):
        """Process an image: detect/crop items, OCR, analyze, search, save, update status."""
        
        def update_status(message):
            if task_id and task_status and task_id in task_status:
                task_status[task_id]["message"] = message
                logger.info(f"Task {task_id} status update: {message}")

        results_list = [] 
        original_filename = os.path.basename(image_path)

        try:
            # Step 1: Preprocess image for detection
            update_status("Preprocessing image...")
            pil_image_resized = self.image_processor.preprocess_image_for_detection(image_path)

            # Step 2: Detect and Crop items (cards)
            update_status("Detecting items in image...")
            # This returns list of {"image": PIL.Image, "path": str}
            cropped_items_info = self.image_processor.detect_and_crop_cards(pil_image_resized, original_filename) 
            num_items = len(cropped_items_info)

            if num_items == 0:
                logger.warning(f"No items detected in image {image_path}. Aborting further processing for this image.")
                update_status("No items detected in image.")
                 # Consider how to handle this - maybe save a placeholder result?
                 # For now, just return empty list, background thread will mark complete.
                return results_list

            logger.info(f"Detected {num_items} item(s). Starting individual processing...")

            # Process each cropped item
            for i, item_info in enumerate(cropped_items_info):
                cropped_pil_image = item_info["image"]
                cropped_image_path = item_info["path"] # Relative path for saving/display
                current_item_label = f"item {i+1}/{num_items}"

                # Step 3: OCR on the cropped image
                update_status(f"Extracting text from {current_item_label}...")
                cropped_base64 = self.image_processor._image_to_base64(cropped_pil_image) # Use helper
                ocr_prompt = "Extract all visible text from this image accurately."
                # Use the refactored method for Ollama vision call
                raw_text_from_item = self.image_processor.get_ollama_vision_response(cropped_base64, ocr_prompt) 
                
                if not raw_text_from_item:
                     logger.warning(f"OCR failed or returned empty text for {current_item_label}. Skipping analysis.")
                     # Optionally save a result indicating OCR failure
                     continue # Skip to next item

                logger.info(f"Raw text for {current_item_label}: {raw_text_from_item}")


                # Step 4: Generate insights (Interpret OCR text)
                update_status(f"Interpreting text for {current_item_label}...")
                # Insights should be structured string like "Player: X\nYear: Y\nBrand: Z\nValue: $A-$B"
                structured_insights_text = self.text_analyzer.generate_insights(raw_text_from_item, item_type)
                logger.info(f"Interpreted Insights for {current_item_label}: {structured_insights_text}")

                # --- Parse the structured insights ---
                parsed_details = {}
                if item_type.lower() == 'baseball card' and structured_insights_text:
                     parsed_details = self._parse_structured_insights(structured_insights_text)
                     logger.info(f"Parsed details: {parsed_details}")
                
                card_player = parsed_details.get('player')
                card_year = parsed_details.get('year')
                card_brand = parsed_details.get('brand')
                card_value_insight = parsed_details.get('value')

                # Step 5: Search eBay/Vivino for this item
                ebay_value = None
                vivino_value = None
                drink_window = None
                ebay_search_url = None

                search_query = raw_text_from_item # Default
                if item_type.lower() == "baseball card":
                     # Use parsed details for a better search query if available
                     if card_player or card_year or card_brand:
                          search_query = f"{card_year or ''} {card_brand or ''} {card_player or ''}".strip()
                          logger.info(f"Using search query for eBay: '{search_query}'")
                     
                     update_status(f"Searching eBay for {current_item_label}...")
                     try:
                        # *** Ensure ebay_searcher.search_card_value handles the query and returns (value, url) ***
                        ebay_result = self.ebay_searcher.search_card_value(search_query) 
                        if ebay_result and isinstance(ebay_result, (list, tuple)) and len(ebay_result) == 2:
                            ebay_value = str(ebay_result[0])
                            ebay_search_url = str(ebay_result[1])
                            logger.info(f"eBay result for {current_item_label}: Value='{ebay_value}', URL='{ebay_search_url}'")
                        else:
                            logger.warning(f"Invalid eBay result format or no result for {current_item_label}: {ebay_result}")
                            ebay_value = "Search Error or No Result"
                     except Exception as search_e:
                         logger.error(f"Error during eBay search for {current_item_label}: {search_e}")
                         ebay_value = "Search Error"

                elif item_type.lower() == "wine bottle":
                     # Wine logic - needs review if it should operate on cropped image text
                     update_status("Searching Vivino for value...")
                     vivino_value = self.vivino_searcher.search_wine_value(raw_text_from_item) # Try with item text
                     update_status("Determining drink window...")
                     drink_window = self.text_analyzer.get_drink_window(raw_text_from_item, item_type) # Try with item text
                     logger.info(f"Vivino value: {vivino_value}")
                     logger.info(f"Drink window: {drink_window}")


                # Step 6: Save individual result to database with structured fields
                update_status(f"Saving result for {current_item_label}...")
                result_id = self.data_manager.save_result(
                    image_path=image_path, 
                    item_type=item_type, 
                    description=raw_text_from_item,          # Raw OCR
                    insights=structured_insights_text,       # Full insight string
                    ebay_value=ebay_value, 
                    vivino_value=vivino_value, 
                    drink_window=drink_window, 
                    ebay_search_url=ebay_search_url,
                    cropped_image_path=cropped_image_path,   # Cropped image path
                    # --- Pass parsed structured data ---
                    card_player=card_player,
                    card_year=card_year,
                    card_brand=card_brand,
                    card_value_insight=card_value_insight
                )
                logger.info(f"Saved result ID {result_id} for {current_item_label}")

                # Append result to list (include new fields if needed downstream)
                results_list.append({
                    "image_path": image_path, # Original image
                    "cropped_image_path": cropped_image_path, # Path to cropped image
                    "item_type": item_type,
                    "description": raw_text_from_item, 
                    "insights": structured_insights_text, 
                    "ebay_value": ebay_value,
                    "vivino_value": vivino_value,
                    "drink_window": drink_window,
                    "ebay_search_url": ebay_search_url,
                    "result_id": result_id,
                    "card_player": card_player,
                    "card_year": card_year,
                    "card_brand": card_brand,
                    "card_value_insight": card_value_insight,
                    "status": "success"
                })

            # Overall task considered successful if we got here
            update_status("Processing complete.")
            return results_list

        except Exception as e:
            logger.error(f"Error processing items from image {image_path}: {str(e)}")
            update_status(f"Error: {str(e)}")
            raise e 