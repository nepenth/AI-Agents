import base64
import logging
from pathlib import Path
from typing import Optional
from knowledge_base_agent.exceptions import VisionModelError
from knowledge_base_agent.http_client import HTTPClient

async def interpret_image(http_client: HTTPClient, image_path: Path, vision_model: str) -> str:
    """Interpret image content using vision model."""
    try:
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Prepare prompt for vision model
        prompt = "Describe this image in detail, focusing on the main subject and any relevant technical details."

        # Use /api/generate endpoint with image
        response = await http_client.post(
            f"{http_client.base_url}/api/generate",
            json={
                "model": vision_model,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False
            }
        )

        if isinstance(response, dict) and "response" in response:
            return response["response"].strip()
        else:
            raise VisionModelError("Invalid response format from vision model")

    except Exception as e:
        logging.error(f"Failed to interpret image {image_path}: {e}")
        raise VisionModelError(f"Failed to interpret image {image_path}: {e}")
