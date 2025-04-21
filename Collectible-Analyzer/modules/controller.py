import os
import re 
import logging
import uuid
import time
from PIL import Image

# Import module components
from .image_segmenter import ImageSegmenter
from .image_processor import ImageProcessor
from .text_analyzer import TextAnalyzer
from .ebay_searcher import eBaySearcher 
from .data_manager import DataManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Global Task Status Dictionary ---
# Needs to be global to be accessed by status checking routes across different requests
tasks = {}

# --- Helper Functions for Task Status (Defined Globally) ---
def update_task_status(task_id, status, message):
    """Updates the status of a task in the global dictionary."""
    if task_id in tasks:
        tasks[task_id]["status"] = status
        tasks[task_id]["message"] = message
        tasks[task_id]["timestamp"] = time.time()
        logger.info(f"Task {task_id} status update: {status} - {message}")
    else:
        logger.warning(f"Attempted to update status for unknown task_id: {task_id}")

def get_task_status(task_id):
    """Retrieves the status of a task."""
    return tasks.get(task_id, {"status": "not_found", "message": "Task ID not found."})

class Controller:
    """Orchestrates image segmentation, processing, analysis, search, and data storage."""

    def __init__(self):
        """Initializes all necessary components."""
        self.image_segmenter = ImageSegmenter()
        self.image_processor = ImageProcessor()
        self.text_analyzer = TextAnalyzer()
        self.ebay_searcher = eBaySearcher()
        self.data_manager = DataManager()
        logger.info("Controller initialized with necessary components.")


    def _parse_structured_insights(self, insights_text):
        """Parses the structured insights string from TextAnalyzer into a dictionary."""
        # Handles insights like "Player: X\nYear: Y\nBrand: Z\nValue: V"
        details = {}
        if not insights_text: return details # Handle empty input

        # Regex to capture key-value pairs, ignoring case and handling potential whitespace variations
        pattern = r"^\s*(Player|Year|Brand|Value)\s*[:\-]?\s*(.*?)\s*$"
        matches = re.findall(pattern, insights_text, re.MULTILINE | re.IGNORECASE)
        
        details = {key.lower(): value.strip() for key, value in matches}
        
        # Clean up common 'not found' variations and ensure keys exist
        parsed = {
            'player': details.get('player'),
            'year': details.get('year'),
            'brand': details.get('brand'),
            'value': details.get('value') 
        }

        for key, value in parsed.items():
            if value and value.lower() in ['not found', 'unknown', 'n/a', '']:
                parsed[key] = None # Standardize missing info as None

        logger.debug(f"Parsed insights details: {parsed}")
        return parsed

    def process_image_task(self, task_id, image_path, item_type):
        """
        Background task execution function.
        Processes an uploaded image: segments, interprets, analyzes, searches, saves.
        Uses the globally defined 'update_task_status' function.
        """
        try:
            # Initial status - Store task entry immediately
            tasks[task_id] = {"status": "starting", "message": "Initializing...", "timestamp": time.time()}
            logger.info(f"Starting background task {task_id} for {image_path}")

            # --- Load Image (using PIL) ---
            update_task_status(task_id, "loading", "Loading image...")
            try:
                 pil_image = Image.open(image_path)
                 pil_image = pil_image.convert("RGB") # Ensure RGB format
                 original_filename = os.path.basename(image_path)
                 logger.info(f"Task {task_id}: Loaded image {original_filename} successfully.")
            except Exception as img_load_e:
                 logger.error(f"Task {task_id}: Failed to load image {image_path} - {img_load_e}")
                 update_task_status(task_id, "error", f"Failed to load image: {img_load_e}")
                 tasks[task_id]["error_details"] = str(img_load_e)
                 return # Stop task on load failure

            # --- Step 1: Segment Image ---
            update_task_status(task_id, "segmenting", "Detecting items in image...")
            # segment_image should return list: [{"image": pil_img, "path": rel_path, "source_filename": ...}, ...]
            # Or the original image if segmentation fails/finds nothing: [{"image": pil_img, "path": "", "source_filename": ...}]
            cropped_items = self.image_segmenter.segment_image(pil_image, original_filename) 
            
            if not cropped_items:
                 # This case should ideally be handled by segment_image returning the fallback original
                 logger.error(f"Task {task_id}: Segmentation returned empty list for {original_filename}. Critical error.")
                 update_task_status(task_id, "error", "Image segmentation failed critically (returned empty list).")
                 tasks[task_id]["error_details"] = "Segmentation returned empty list."
                 return 

            num_items = len(cropped_items)
            logger.info(f"Task {task_id}: Segmentation found {num_items} potential item(s).")
            
            # Check if segmentation failed and returned the original image as fallback
            is_fallback = num_items == 1 and not cropped_items[0].get("path")
            if is_fallback:
                 logger.warning(f"Task {task_id}: Segmentation failed or found no distinct items. Processing original image as one item.")
                 update_task_status(task_id, "processing", "Segmentation failed, processing original image...")
            else:
                 update_task_status(task_id, "processing", f"Found {num_items} items. Starting individual processing...")

            results_summary = [] # Store brief info about each processed item
            processed_count = 0
            
            # --- Step 2: Process Each Cropped/Original Item ---
            for i, item_info in enumerate(cropped_items):
                item_index = i + 1
                current_item_label = f"item {item_index}/{num_items}"
                cropped_pil_image = item_info.get("image")
                cropped_image_path = item_info.get("path", "") # Will be empty string for fallback

                if not cropped_pil_image:
                     logger.error(f"Task {task_id}: Missing image data for {current_item_label}. Skipping.")
                     continue # Skip this item if image is missing

                logger.info(f"Task {task_id}: Processing {current_item_label}...")
                
                # --- 2a: Interpret Cropped Image Text ---
                update_task_status(task_id, "processing", f"Extracting text from {current_item_label}...")
                # image_processor.interpret_image takes PIL image, returns text or error string
                raw_description = self.image_processor.interpret_image(cropped_pil_image, item_type)
                
                if raw_description.startswith("Error:"):
                     logger.error(f"Task {task_id}: Interpretation failed for {current_item_label} - {raw_description}")
                     # Decide how to handle - skip item or save partial? For now, skip.
                     # TODO: Could save a result indicating interpretation failure
                     continue 

                logger.info(f"Task {task_id}: Raw description for {current_item_label}: '{raw_description[:100]}...'") # Log snippet
                
                # --- 2b: Analyze Text (Generate Structured Insights) ---
                update_task_status(task_id, "processing", f"Analyzing text for {current_item_label}...")
                # text_analyzer.generate_insights takes raw text, returns structured string
                structured_insights_text = self.text_analyzer.generate_insights(raw_description, item_type)
                logger.info(f"Task {task_id}: Structured insights for {current_item_label}: '{structured_insights_text[:100]}...'")

                # --- 2c: Parse Structured Insights ---
                # Use the internal helper method to parse the string into a dict
                parsed_details = self._parse_structured_insights(structured_insights_text)
                card_player = parsed_details.get('player')
                card_year = parsed_details.get('year')
                card_brand = parsed_details.get('brand')
                # Value insight from the text model interpretation
                card_value_insight = parsed_details.get('value') 
                
                # --- 2d: External Search (eBay/Vivino) ---
                ebay_value = None
                ebay_url = None
                # vivino_value = None # Add back if VivinoSearcher is used
                # drink_window = None # Add back if TextAnalyzer provides this

                if item_type.lower() == "baseball card":
                    # Construct a search query using parsed details if available
                    query_parts = [card_year, card_brand, card_player]
                    search_query = " ".join(filter(None, query_parts)).strip()
                    if not search_query:
                        # Fallback query if no details were parsed
                        search_query = raw_description[:100].strip() # Use beginning of raw text? Risky.
                        logger.warning(f"Task {task_id}: No structured details for {current_item_label}, using raw text snippet for eBay query: '{search_query}'")
                    
                    if search_query: # Proceed only if we have some query
                        update_task_status(task_id, "processing", f"Searching eBay for {current_item_label}...")
                        logger.info(f"Task {task_id}: Using eBay query for {current_item_label}: '{search_query}'")
                        try:
                            # ebay_searcher.search_card_value should return a single value or a tuple
                            result = self.ebay_searcher.search_card_value(search_query)
                            if isinstance(result, tuple):
                                ebay_value = str(result[0]) if result[0] is not None else None
                                ebay_url = str(result[1]) if len(result) > 1 and result[1] is not None else None
                            else:
                                ebay_value = str(result) if result is not None else None
                                ebay_url = None
                            logger.info(f"Task {task_id}: eBay result for {current_item_label}: Value='{ebay_value}', URL='{ebay_url}'")
                        except Exception as search_e:
                            logger.error(f"Task {task_id}: eBay search failed for {current_item_label} ({search_query}): {search_e}")
                            ebay_value = "Search Error" # Indicate error state
                    else:
                        logger.warning(f"Task {task_id}: Skipping eBay search for {current_item_label} due to empty search query.")

                # Add elif item_type == "wine bottle": block here if needed

                # --- 2e: Save Result to Database ---
                update_task_status(task_id, "saving", f"Saving result for {current_item_label}...")
                try:
                    result_id = self.data_manager.save_result(
                        item_type=item_type,
                        description=raw_description,          # Raw text from vision interpretation
                        insights=structured_insights_text,    # Save the raw insight string
                        card_player=card_player,              # Parsed details
                        card_year=card_year,
                        card_brand=card_brand,
                        card_value_insight=card_value_insight,# Parsed value insight from text model
                        ebay_value=ebay_value,                # Value range from eBay search
                        ebay_search_url=ebay_url,
                        image_path=image_path,                # Path to original uploaded image
                        cropped_image_path=cropped_image_path # Path to the specific cropped image
                    )
                    logger.info(f"Task {task_id}: Saved result ID {result_id} for {current_item_label}")
                    results_summary.append({"id": result_id, "player": card_player, "status": "saved"})
                    processed_count += 1
                except Exception as db_e:
                     logger.error(f"Task {task_id}: Failed to save result for {current_item_label} to database: {db_e}")
                     # Optionally update task status with DB error
                     results_summary.append({"item": item_index, "status": "db_error", "error": str(db_e)})
                     # Continue processing other items even if one fails to save

            # --- Final Task Status ---
            total_items = num_items
            failed_count = total_items - processed_count
            if processed_count == total_items:
                final_message = f"Processing complete. Found and processed {processed_count} item(s)."
                final_status = "complete"
            elif processed_count > 0:
                 final_message = f"Processing partially complete. Processed {processed_count}/{total_items} item(s). {failed_count} item(s) failed."
                 final_status = "complete_with_errors"
                 tasks[task_id]["error_details"] = f"{failed_count} items failed processing or saving."
            else:
                 final_message = "Processing failed. No items were successfully processed."
                 final_status = "error"
                 if "error_details" not in tasks[task_id]:
                     tasks[task_id]["error_details"] = "All items failed during processing or saving phase."

            update_task_status(task_id, final_status, final_message)
            tasks[task_id]["results_summary"] = results_summary # Store brief summary
            logger.info(f"Task {task_id} finished with status: {final_status}")

        except Exception as e:
            # Catch-all for unexpected errors during the task execution
            logger.error(f"Critical error in background task {task_id} for image {image_path}: {str(e)}")
            import traceback
            error_trace = traceback.format_exc()
            logger.error(error_trace) # Log full traceback
            # Update status if task_id exists, otherwise log failure
            if task_id in tasks:
                 update_task_status(task_id, "error", f"An unexpected critical error occurred.")
                 tasks[task_id]["error_details"] = str(e)
                 tasks[task_id]["traceback"] = error_trace # Optionally store traceback
            else:
                 logger.error(f"Task {task_id} failed critically before status could be initialized properly.")

    # --- Method to Initiate the Task ---
    # This would likely be called from your Flask route handler
    def start_image_processing(self, image_path, item_type):
        """Creates a new task ID and starts the background processing."""
        task_id = str(uuid.uuid4())
        logger.info(f"Generated task ID {task_id} for processing {image_path}")
        
        # Here you would typically start the background thread/task runner
        # For example, using threading:
        import threading
        thread = threading.Thread(target=self.process_image_task, args=(task_id, image_path, item_type))
        thread.start()
        
        # Or using Celery:
        # process_image_task.delay(task_id, image_path, item_type) # Assuming process_image_task is a Celery task

        return task_id # Return the task ID to the caller 