import os
import base64
from PIL import Image
import requests
import json
from io import BytesIO
import logging
import cv2 # OpenCV
import numpy as np 
from .text_analyzer import TextAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration variables
OLLAMA_URL = "http://whyland-ai.nakedsun.xyz:11434"
VISION_MODEL = "llava-llama3"
TEXT_MODEL = "llama3.3:70b-instruct-q4_0"
FALLBACK_MODEL = "cogito:70b"

class ImageProcessor:
    """Handles image preprocessing, card detection/cropping, and vision model interaction."""

    def __init__(self, ollama_url=OLLAMA_URL, vision_model=VISION_MODEL, fallback_model=FALLBACK_MODEL):
        self.ollama_url = ollama_url
        self.vision_model = vision_model
        self.fallback_model = fallback_model
        # Create directory for cropped images if it doesn't exist
        self.cropped_dir = "static/uploads/cropped"
        os.makedirs(self.cropped_dir, exist_ok=True)

    def _pil_to_cv2(self, pil_image):
        """Convert PIL Image to OpenCV format (NumPy array)."""
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def _cv2_to_pil(self, cv2_image):
        """Convert OpenCV format (NumPy array) to PIL Image."""
        return Image.fromarray(cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB))

    def _image_to_base64(self, image, format="JPEG", quality=90):
        """Convert PIL Image or CV2 image (NumPy array) to base64 string."""
        if isinstance(image, np.ndarray): # If it's a CV2 image
             image = self._cv2_to_pil(image) # Convert to PIL first
        elif not isinstance(image, Image.Image):
             raise TypeError("Input must be a PIL Image or OpenCV NumPy array")
             
        buffered = BytesIO()
        image.save(buffered, format=format, quality=quality)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def preprocess_image_for_detection(self, image_path, max_dim=2048):
        """Load and resize image using PIL for detection steps."""
        try:
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                # Resize while maintaining aspect ratio
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS) 
                logger.info(f"Preprocessed image {image_path} for detection with max dimensions {max_dim}x{max_dim}")
                return img # Return PIL Image
        except Exception as e:
            logger.error(f"Error during initial preprocessing of {image_path}: {str(e)}")
            raise ValueError(f"Failed initial preprocessing: {str(e)}")

    def detect_and_crop_cards(self, pil_image, original_filename):
        """Detect card-like rectangles using improved OpenCV techniques."""
        cropped_images_info = []
        try:
            img_cv = self._pil_to_cv2(pil_image)
            img_gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # --- Improved Preprocessing ---
            # Gaussian Blur
            img_blur = cv2.GaussianBlur(img_gray, (7, 7), 0) 
            
            # Adaptive Thresholding (Better for varying light)
            img_thresh = cv2.adaptiveThreshold(img_blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                               cv2.THRESH_BINARY_INV, 11, 2) # Block size 11, C=2

            # Morphological Operations (Optional: can help close gaps/remove noise)
            # kernel = np.ones((3,3), np.uint8)
            # img_morph = cv2.morphologyEx(img_thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
            # Use img_thresh or img_morph below based on testing
            target_img_for_contours = img_thresh # Change to img_morph if using morphology

            # Find Contours
            contours, hierarchy = cv2.findContours(target_img_for_contours, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            logger.info(f"Found {len(contours)} potential contours after preprocessing.")
            
            detected_card_count = 0
            # Adjust area filters based on image size and expected card size
            img_area = pil_image.width * pil_image.height
            min_area = img_area * 0.005 # Example: Min 0.5% area - TUNE THIS
            max_area = img_area * 0.50  # Example: Max 50% area - TUNE THIS

            # --- Improved Contour Filtering ---
            possible_cards = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < min_area or area > max_area:
                    continue

                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.02 * peri, True) # Adjust epsilon (0.01-0.04) if needed

                # Check if it's roughly rectangular
                if len(approx) == 4:
                    x, y, w, h = cv2.boundingRect(approx)
                    if h == 0 or w == 0: continue # Avoid division by zero

                    aspect_ratio = float(w) / h
                    # Card aspect ratio is ~2.5 / 3.5 = 0.714 or 1/0.714 = 1.4
                    # Allow some tolerance
                    if (0.65 < aspect_ratio < 0.78) or (1.3 < aspect_ratio < 1.55):
                        # Check extent (ratio of contour area to bounding box area) - helps filter noise
                        rect_area = w*h
                        extent = float(area) / rect_area
                        if extent > 0.85: # Expect card to fill most of its bounding box
                             possible_cards.append({'contour': cnt, 'bounds': (x, y, w, h)})
            
            logger.info(f"Filtered down to {len(possible_cards)} potential card shapes.")

            # Optional: Add Non-Maximum Suppression (NMS) here if detecting overlapping boxes

            # Crop based on filtered contours
            for card_data in possible_cards:
                x, y, w, h = card_data['bounds']
                 # Add small padding, ensuring bounds are valid
                padding = 5 
                y1 = max(0, y - padding)
                y2 = min(img_cv.shape[0], y + h + padding)
                x1 = max(0, x - padding)
                x2 = min(img_cv.shape[1], x + w + padding)
                
                cropped_cv_img = img_cv[y1:y2, x1:x2]

                if cropped_cv_img.size == 0: continue # Skip empty crops
                    
                cropped_pil_img = self._cv2_to_pil(cropped_cv_img)
                detected_card_count += 1

                # Save cropped image
                base_name, ext = os.path.splitext(original_filename)
                # Ensure filename is filesystem-safe (though should be okay here)
                cropped_filename = f"{base_name}_card_{detected_card_count}{ext}" 
                cropped_save_path = os.path.join(self.cropped_dir, cropped_filename)
                try:
                    cropped_pil_img.save(cropped_save_path)
                    logger.info(f"Saved cropped card {detected_card_count} to {cropped_save_path}")
                    
                    # Store relative path from project root for DB/display
                    # Assuming cropped_dir is relative to project root (e.g., "static/...")
                    relative_cropped_path = cropped_save_path 

                    cropped_images_info.append({
                        "image": cropped_pil_img, 
                        "path": relative_cropped_path 
                    })
                except Exception as save_e:
                     logger.error(f"Failed to save cropped image {cropped_save_path}: {save_e}")

            logger.info(f"Detected and successfully cropped {len(cropped_images_info)} card(s).")
            return cropped_images_info

        except Exception as e:
            logger.error(f"Error during card detection/cropping: {str(e)}")
            import traceback
            traceback.print_exc() # Print detailed traceback for debugging
            return []

    def get_ollama_vision_response(self, base64_image, prompt):
        """Sends a base64 image and prompt to the Ollama vision model."""
        try:
            payload = {
                "model": self.vision_model,
                "prompt": prompt,
                "images": [base64_image],
                "stream": False
            }
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=300) # Keep increased timeout
            response.raise_for_status()
            result = response.json()

            if "response" in result:
                return result["response"].strip()
            else:
                logger.error(f"No 'response' in Ollama vision result.")
                return "" # Return empty string on missing response

        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with Ollama vision model: {str(e)}")
            # Try fallback model
            try:
                logger.info(f"Attempting fallback vision model: {self.fallback_model}")
                payload["model"] = self.fallback_model
                response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=300)
                response.raise_for_status()
                result = response.json()
                return result["response"].strip() if "response" in result else ""
            except Exception as fallback_e:
                logger.error(f"Fallback vision model failed: {str(fallback_e)}")
                # Return empty string or raise specific error
                return "" 
        except Exception as e:
             logger.error(f"Unexpected error calling Ollama vision: {str(e)}")
             return ""

# Example usage (for testing)
if __name__ == "__main__":
    # Test image processor
    image_processor = ImageProcessor()
    test_image_path = "sample_card.jpg"  # Replace with actual image path
    if os.path.exists(test_image_path):
        description = image_processor.analyze_image(test_image_path)
        print("Image Description:", description)

        # Test text analyzer
        text_analyzer = TextAnalyzer()
        insights = text_analyzer.generate_insights(description, item_type="baseball card")
        print("Insights:", insights)
    else:
        print(f"Test image {test_image_path} not found")