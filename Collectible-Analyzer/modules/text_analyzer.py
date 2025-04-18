import requests
import logging
from .drink_window import get_drink_window

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration variables
OLLAMA_URL = "http://whyland-ai.nakedsun.xyz:11434"
VISION_MODEL = "llava-llama3"
TEXT_MODEL = "llama3.3:70b-instruct-q4_0"
FALLBACK_MODEL = "cogito:70b"

class TextAnalyzer:
    """Handles text processing using Ollama text model."""

    def __init__(self, ollama_url=OLLAMA_URL, text_model=TEXT_MODEL, fallback_model=FALLBACK_MODEL):
        self.ollama_url = ollama_url
        self.text_model = text_model
        self.fallback_model = fallback_model

    def generate_insights(self, text, item_type="baseball card"):
        """Interpret extracted text to identify item details and generate valuation insights."""
        try:
            # Customize prompt based on item type
            if item_type.lower() == "baseball card":
                # New prompt to INTERPRET raw OCR text and provide structured details + value
                prompt = (
                    f"The following text was extracted from a single baseball card: '{text}'. "
                    "Analyze this text to identify the card's key details. "
                    "Provide ONLY the following information in this exact format:\n"
                    "Player: [Identified Player Name]\n"
                    "Year: [Identified Year]\n"
                    "Brand: [Identified Brand/Set]\n"
                    "Value: [Estimated Value Range, e.g., $10-$20]"
                    "\nIf a detail cannot be determined from the text, state 'Unknown'."
                )
            elif item_type.lower() == "wine bottle":
                # Keep wine prompt focused
                drink_window = get_drink_window(text, item_type) or "Unknown drink window"
                prompt = (
                    f"Analyze the wine label description: '{text}'. "
                    "Provide ONLY an estimated value range (e.g., $20-$50) and the drink window. "
                    f"Format: Value: [range], Drink Window: {drink_window}"
                )
            else:
                # Generic fallback
                prompt = f"Provide key insights for: '{text}'"

            # Prepare payload for Ollama API
            payload = {
                "model": self.text_model,
                "prompt": prompt,
                "stream": False
            }

            # Send request to Ollama with increased timeout
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=300)  # 5 minutes
            response.raise_for_status()
            result = response.json()

            # Extract the insights
            if "response" in result:
                insights = result["response"].strip()
                return insights
            else:
                logger.error(f"No response from text model for text: {text}")
                raise ValueError("Text model returned no response")

        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with Ollama for text model: {str(e)}")
            # Try fallback model
            try:
                logger.info(f"Attempting fallback model: {self.fallback_model}")
                payload["model"] = self.fallback_model
                response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=300)  # 5 minutes
                response.raise_for_status()
                result = response.json()
                insights = result["response"].strip() if "response" in result else ""
                return insights
            except Exception as fallback_e:
                logger.error(f"Fallback model failed: {str(fallback_e)}")
                raise ValueError(f"Failed to generate insights with both primary and fallback models: {str(fallback_e)}")

    def get_drink_window(self, text, item_type):
        """Get the drink window for a wine bottle."""
        return get_drink_window(text, item_type)