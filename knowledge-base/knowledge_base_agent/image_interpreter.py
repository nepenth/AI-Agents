import base64
import logging
import requests
from pathlib import Path
from typing import Optional

def interpret_image(ollama_url: str, image_path: Path, vision_model: str, http_client: Optional[requests.Session] = None) -> str:
    client = http_client or requests
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
        resp = client.post(f"{ollama_url}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        if 'message' in data and 'content' in data['message']:
            description = data['message']['content'].strip()
            return description
        else:
            description = data.get("response", "").strip()
            return description
    except requests.RequestException as e:
        logging.error(f"HTTP Error during image interpretation for {image_path.name}: {e}")
        return "Error in processing image"
