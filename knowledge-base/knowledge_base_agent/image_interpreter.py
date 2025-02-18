import base64
import logging
from pathlib import Path
from typing import Optional
from .http_client import HTTPClient

async def interpret_image(http_client: HTTPClient, image_path: Path, vision_model: str) -> str:
    """Interpret image using Ollama vision model."""
    try:
        with image_path.open("rb") as f:
            img_data = f.read()
        encoded_img = base64.b64encode(img_data).decode("utf-8")
        
        payload = {
            "model": vision_model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": "Provide a concise and accurate description of the image.",
                    "images": [encoded_img]
                }
            ]
        }
        
        response = await http_client.post(f"{http_client.config.ollama_url}/api/chat", json=payload)
        data = response.json()
        
        if 'message' in data and 'content' in data['message']:
            return data['message']['content'].strip()
        return data.get("response", "").strip()
        
    except Exception as e:
        logging.error(f"Failed to interpret image {image_path.name}: {e}")
        return "Error in processing image"
