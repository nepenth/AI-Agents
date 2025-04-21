import os
import base64
from PIL import Image
import requests
import json
from io import BytesIO
import logging
import numpy as np # Keep numpy if needed for _image_to_base64 check

# Remove cv2 import if not used elsewhere
# import cv2 
# Remove text_analyzer import, it's used in controller
# from .text_analyzer import TextAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration variables (can be passed or defined)
OLLAMA_URL = "http://whyland-ai.nakedsun.xyz:11434"
VISION_MODEL = "llava-llama3" # Model for interpretation
FALLBACK_MODEL = "cogito:70b" # Optional fallback

class ImageProcessor:
    """Handles interpreting the content of a single image using a vision model."""

    def __init__(self, ollama_url=OLLAMA_URL, vision_model=VISION_MODEL, fallback_model=FALLBACK_MODEL):
        self.ollama_url = ollama_url
        self.vision_model = vision_model
        self.fallback_model = fallback_model
        # No longer needs cropped_dir
        # self.cropped_dir = "static/uploads/cropped"
        # os.makedirs(self.cropped_dir, exist_ok=True)

    # Keep utility if needed by interpret_image, otherwise remove
    def _image_to_base64(self, image, format="JPEG", quality=90):
        """Convert PIL Image to base64 string."""
        if not isinstance(image, Image.Image):
            # Allow numpy array check if needed, otherwise remove
            if isinstance(image, np.ndarray):
                 raise TypeError("Input should be PIL Image for interpretation, not CV2 array.")
            raise TypeError("Input must be a PIL Image")
             
        buffered = BytesIO()
        # Ensure image is RGB before saving to JPEG
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(buffered, format=format, quality=quality)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
        
    # Removed _pil_to_cv2, _cv2_to_pil
    # Removed preprocess_image_for_detection (preprocessing happens before segmentation)
    # Removed detect_and_crop_cards and _parse_bounding_boxes

    def interpret_image(self, pil_image, item_type="baseball card"):
        """Sends a single PIL image to Ollama Vision for text interpretation."""
        if not isinstance(pil_image, Image.Image):
            logger.error("interpret_image received non-PIL image.")
            return "Error: Invalid image type provided for interpretation."
            
        try:
            base64_image = self._image_to_base64(pil_image)
            
            # --- Interpretation Prompt ---
            # Focus on extracting specific details from the SINGLE card image
            if item_type == "baseball card":
                 prompt = (
                     "Analyze this image of a single baseball card. "
                     "Extract the player's full name, the card year (often near the copyright or on the back, but look everywhere), and the card brand/set (e.g., Topps, Donruss, Fleer, Bowman, Score, Upper Deck). "
                     "Provide only the extracted text relevant to these details. If a detail is not visible, state 'Not found'."
                 )
            elif item_type == "wine bottle":
                 prompt = (
                      "Analyze this image of a single wine bottle label. "
                      "Extract the Winery Name, Wine Name/Varietal, and Vintage Year. "
                      "Provide only the extracted text relevant to these details. If a detail is not visible, state 'Not found'."
                 )
            else:
                 prompt = "Describe the contents of this image in detail."

            logger.info(f"Sending request to Ollama ({self.vision_model}) for interpretation...")
            payload = {
                "model": self.vision_model,
                "prompt": prompt,
                "images": [base64_image],
                "stream": False
            }
            current_model = self.vision_model
            
            try:
                response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=300) # Keep longer timeout for interpretation
                response.raise_for_status()
                result = response.json()
                logger.info(f"Ollama ({current_model}) raw response for interpretation: {result}")
                extracted_text = result.get("response", "").strip()
                if not extracted_text:
                     logger.warning(f"Ollama ({current_model}) returned empty response for interpretation.")
                     return "Error: AI model returned empty response."
                return extracted_text

            except requests.exceptions.RequestException as e:
                logger.error(f"Error communicating with Ollama ({current_model}) for interpretation: {e}")
                 # Optional: Try fallback model if defined
                if self.fallback_model and current_model != self.fallback_model:
                    try:
                        logger.info(f"Attempting fallback interpretation model: {self.fallback_model}")
                        payload["model"] = self.fallback_model
                        current_model = self.fallback_model # Update for logging
                        response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=300)
                        response.raise_for_status()
                        result = response.json()
                        logger.info(f"Ollama ({current_model}) raw response for interpretation: {result}")
                        extracted_text = result.get("response", "").strip()
                        if not extracted_text:
                            logger.warning(f"Ollama ({current_model}) returned empty response for interpretation.")
                            return "Error: AI model returned empty response."
                        return extracted_text
                    except Exception as fallback_e:
                        logger.error(f"Fallback interpretation model ({self.fallback_model}) failed: {fallback_e}")
                        return "Error: AI analysis failed after fallback."
                return "Error: AI analysis failed." # Return error on primary failure if no fallback
            except Exception as e:
                logger.error(f"Unexpected error during Ollama interpretation call: {e}")
                return "Error: Unexpected error during AI analysis."

        except Exception as e:
            logger.error(f"Error during image interpretation preparation: {e}")
            import traceback
            traceback.print_exc()
            return "Error: Failed to prepare image for AI analysis."
            
    # Removed get_ollama_vision_response (logic integrated into interpret_image)
    # Removed __main__ example block