import os
import base64
from PIL import Image
import requests
import json
from io import BytesIO
import logging
import cv2
import numpy as np
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration variables
OLLAMA_URL = "http://whyland-ai.nakedsun.xyz:11434"
VISION_MODEL = "llava-llama3"
FALLBACK_MODEL = "cogito:70b"

class ImageSegmenter:
    """Handles detecting and cropping baseball cards from an image."""

    def __init__(self, ollama_url=OLLAMA_URL, vision_model=VISION_MODEL, fallback_model=FALLBACK_MODEL):
        self.ollama_url = ollama_url
        self.vision_model = vision_model
        self.fallback_model = fallback_model
        self.cropped_dir = "static/uploads/cropped"
        os.makedirs(self.cropped_dir, exist_ok=True)

    def _pil_to_cv2(self, pil_image):
        """Convert PIL Image to OpenCV format."""
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def _cv2_to_pil(self, cv2_image):
        """Convert OpenCV format to PIL Image."""
        return Image.fromarray(cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB))

    def _image_to_base64(self, image, format="JPEG", quality=90):
        """Convert PIL Image to base64 string."""
        if not isinstance(image, Image.Image):
            raise TypeError("Input must be a PIL Image")
        buffered = BytesIO()
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(buffered, format=format, quality=quality)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def _call_ollama_vision_for_boxes(self, base64_image, prompt):
        """Sends image and prompt to Ollama for bounding box detection."""
        payload = {
            "model": self.vision_model,
            "prompt": prompt,
            "images": [base64_image],
            "stream": False,
            "temperature": 0.3,  # Lower for more consistent output
            "max_tokens": 1000
        }
        current_model = self.vision_model
        try:
            logger.info(f"Sending request to Ollama ({current_model})...")
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=180)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Ollama ({current_model}) response: {result}")
            return result.get("response", "").strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error with Ollama ({current_model}): {e}")
            if self.fallback_model and current_model != self.fallback_model:
                try:
                    logger.info(f"Trying fallback model: {self.fallback_model}")
                    payload["model"] = self.fallback_model
                    response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=180)
                    response.raise_for_status()
                    result = response.json()
                    return result.get("response", "").strip()
                except Exception as fallback_e:
                    logger.error(f"Fallback model failed: {fallback_e}")
                    return ""
            return ""
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return ""

    def _parse_bounding_boxes(self, response_text, img_width, img_height):
        """Parse bounding box coordinates from Ollama response."""
        bounding_boxes = []
        try:
            # Try JSON parsing first
            data = json.loads(response_text)
            if isinstance(data, list):
                for item in data:
                    x1, y1, x2, y2 = item.get('x1', 0), item.get('y1', 0), item.get('x2', 0), item.get('y2', 0)
                    if x1 < x2 <= img_width and y1 < y2 <= img_height and x1 >= 0 and y1 >= 0:
                        bounding_boxes.append((x1, y1, x2, y2))
                    else:
                        logger.warning(f"Invalid box: ({x1}, {y1}, {x2}, {y2})")
                return bounding_boxes
        except json.JSONDecodeError:
            pass

        # Fallback to regex
        pattern = r"\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)"
        matches = re.findall(pattern, response_text)
        for match in matches:
            try:
                x1, y1, x2, y2 = map(int, match)
                if x1 < x2 <= img_width and y1 < y2 <= img_height and x1 >= 0 and y1 >= 0:
                    # Validate approximate card aspect ratio (2.5:3.5 or vice versa)
                    width, height = x2 - x1, y2 - y1
                    aspect = width / height if height > width else height / width
                    if 0.6 < aspect < 0.8:
                        bounding_boxes.append((x1, y1, x2, y2))
                    else:
                        logger.warning(f"Box rejected due to aspect ratio: ({x1}, {y1}, {x2}, {y2})")
                else:
                    logger.warning(f"Out-of-bounds box: ({x1}, {y1}, {x2}, {y2})")
            except ValueError:
                logger.warning(f"Could not parse: {match}")

        logger.info(f"Parsed {len(bounding_boxes)} boxes")
        return bounding_boxes

    def _grid_fallback(self, pil_image, original_filename):
        """Crop image into a 3x3 grid as a last resort."""
        logger.info("Using 3x3 grid fallback")
        width, height = pil_image.size
        card_width, card_height = width // 3, height // 3
        margin = int(min(card_width, card_height) * 0.05)  # 5% margin
        cropped_images_info = []

        for row in range(3):
            for col in range(3):
                x1 = col * card_width + margin
                y1 = row * card_height + margin
                x2 = x1 + card_width - 2 * margin
                y2 = y1 + card_height - 2 * margin
                cropped_pil = pil_image.crop((x1, y1, x2, y2))

                base_name, ext = os.path.splitext(original_filename)
                safe_base_name = re.sub(r'[^\w\-]+', '_', base_name)
                cropped_filename = f"{safe_base_name}_card_{row*3+col+1}{ext}"
                cropped_save_path = os.path.join(self.cropped_dir, cropped_filename)

                cropped_pil.save(cropped_save_path)
                relative_cropped_path = os.path.relpath(cropped_save_path, start=".")
                cropped_images_info.append({
                    "image": cropped_pil,
                    "path": relative_cropped_path,
                    "source_filename": original_filename
                })

        return cropped_images_info

    def segment_image(self, pil_image, original_filename):
        """Detect and crop baseball cards using Ollama or OpenCV."""
        cropped_images_info = []
        try:
            logger.info(f"Segmenting {original_filename}")
            # Resize image for consistency (optional, adjust based on model performance)
            max_size = 2000
            if max(pil_image.size) > max_size:
                pil_image = pil_image.copy()
                pil_image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            base64_image = self._image_to_base64(pil_image)
            prompt = (
                f"Detect exactly 9 baseball cards in a 3x3 grid. "
                f"Return bounding box coordinates for each card as a JSON array of objects: "
                f"[{{'card': 1, 'x1': int, 'y1': int, 'x2': int, 'y2': int}}, ...]. "
                f"Coordinates are in pixels relative to the top-left corner (0,0). "
                f"Image size: {pil_image.width}x{pil_image.height} pixels. "
                f"Sort cards from top-left to bottom-right. Ensure the bounding boxes are slightly larger to include the full card."
            )

            response_text = self._call_ollama_vision_for_boxes(base64_image, prompt)
            if not response_text:
                logger.warning("Empty Ollama response. Trying OpenCV.")
                return self._fallback_opencv_segmentation(pil_image, original_filename)

            bounding_boxes = self._parse_bounding_boxes(response_text, pil_image.width, pil_image.height)
            if len(bounding_boxes) != 9:
                logger.warning(f"Found {len(bounding_boxes)} boxes, expected 9. Trying OpenCV.")
                return self._fallback_opencv_segmentation(pil_image, original_filename)

            img_cv = self._pil_to_cv2(pil_image)
            detected_card_count = 0
            for box in bounding_boxes:
                x1, y1, x2, y2 = box
                # Expand the bounding box by 5% on each side to ensure full card capture
                width, height = x2 - x1, y2 - y1
                margin_x, margin_y = int(width * 0.05), int(height * 0.05)
                x1 = max(0, x1 - margin_x)
                y1 = max(0, y1 - margin_y)
                x2 = min(pil_image.width, x2 + margin_x)
                y2 = min(pil_image.height, y2 + margin_y)
                
                cropped_cv_img = img_cv[y1:y2, x1:x2]
                if cropped_cv_img.size == 0:
                    logger.warning(f"Empty crop for box {box}")
                    continue

                # Check orientation using edge detection
                edges = cv2.Canny(cropped_cv_img, 100, 200)
                lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=50, maxLineGap=10)
                angle = 0
                if lines is not None:
                    for line in lines:
                        x1_line, y1_line, x2_line, y2_line = line[0]
                        angle += np.arctan2(y2_line - y1_line, x2_line - x1_line) * 180 / np.pi
                    angle /= len(lines)
                    if abs(angle) > 45:
                        cropped_cv_img = cv2.rotate(cropped_cv_img, cv2.ROTATE_90_CLOCKWISE)

                cropped_pil_img = self._cv2_to_pil(cropped_cv_img)
                detected_card_count += 1

                base_name, ext = os.path.splitext(original_filename)
                safe_base_name = re.sub(r'[^\w\-]+', '_', base_name)
                cropped_filename = f"{safe_base_name}_card_{detected_card_count}{ext}"
                cropped_save_path = os.path.join(self.cropped_dir, cropped_filename)

                cropped_pil_img.save(cropped_save_path)
                relative_cropped_path = os.path.relpath(cropped_save_path, start=".")
                cropped_images_info.append({
                    "image": cropped_pil_img,
                    "path": relative_cropped_path,
                    "source_filename": original_filename
                })

            if not cropped_images_info:
                logger.warning("No crops produced. Using grid fallback.")
                return self._grid_fallback(pil_image, original_filename)

            logger.info(f"Cropped {len(cropped_images_info)} cards")
            return cropped_images_info

        except Exception as e:
            logger.error(f"Segmentation error: {e}", exc_info=True)
            return self._fallback_opencv_segmentation(pil_image, original_filename)

    def _fallback_opencv_segmentation(self, pil_image, original_filename):
        """Fallback to OpenCV contour detection."""
        logger.info(f"OpenCV fallback for {original_filename}")
        img_cv = self._pil_to_cv2(pil_image)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(edges, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        bounding_boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect = w / h if h > w else h / w
            area = w * h
            if 0.6 < aspect < 0.8 and 0.05 * pil_image.width * pil_image.height < area < 0.15 * pil_image.width * pil_image.height:
                # Expand the bounding box by 5% on each side
                margin_x, margin_y = int(w * 0.05), int(h * 0.05)
                x1 = max(0, x - margin_x)
                y1 = max(0, y - margin_y)
                x2 = min(pil_image.width, x + w + margin_x)
                y2 = min(pil_image.height, y + h + margin_y)
                bounding_boxes.append((x1, y1, x2, y2))

        # Sort boxes in 3x3 grid order (top-left to bottom-right)
        bounding_boxes.sort(key=lambda box: (box[1] // (pil_image.height // 3), box[0] // (pil_image.width // 3)))

        if len(bounding_boxes) != 9:
            logger.warning(f"OpenCV found {len(bounding_boxes)} boxes. Using grid fallback.")
            return self._grid_fallback(pil_image, original_filename)

        cropped_images_info = []
        img_cv = self._pil_to_cv2(pil_image)  # Reconvert if needed
        for i, box in enumerate(bounding_boxes):
            x1, y1, x2, y2 = box
            cropped_cv_img = img_cv[y1:y2, x1:x2]
            if cropped_cv_img.size == 0:
                continue

            cropped_pil_img = self._cv2_to_pil(cropped_cv_img)
            base_name, ext = os.path.splitext(original_filename)
            safe_base_name = re.sub(r'[^\w\-]+', '_', base_name)
            cropped_filename = f"{safe_base_name}_card_{i+1}{ext}"
            cropped_save_path = os.path.join(self.cropped_dir, cropped_filename)

            cropped_pil_img.save(cropped_save_path)
            relative_cropped_path = os.path.relpath(cropped_save_path, start=".")
            cropped_images_info.append({
                "image": cropped_pil_img,
                "path": relative_cropped_path,
                "source_filename": original_filename
            })

        if not cropped_images_info:
            logger.warning("OpenCV produced no crops. Using grid fallback.")
            return self._grid_fallback(pil_image, original_filename)

        logger.info(f"OpenCV cropped {len(cropped_images_info)} cards")
        return cropped_images_info