import re
import uuid
import json
import shutil
from pathlib import Path
import base64
import requests
from config import config

def validate_directory_name(name: str) -> bool:
    MAX_LENGTH = 50
    return len(name) <= MAX_LENGTH and not re.search(r'[<>:"/\\|?*]', name)

def normalize_name_for_filesystem(name: str, max_length: int = 30) -> str:
    name = re.sub(r'\W+', '_', name.lower()).strip('_')[:max_length]
    return name if name else f"unnamed_{uuid.uuid4().hex[:8]}"

def load_json_file(file_path: Path) -> dict:
    if file_path.exists():
        try:
            with file_path.open('r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_json_file(file_path: Path, data: dict):
    with file_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def delete_directory(dir_path: Path):
    if dir_path.exists() and dir_path.is_dir():
        shutil.rmtree(dir_path)

def interpret_image(image_path: Path) -> str:
    """ Uses AI model to interpret an image. """
    try:
        with image_path.open("rb") as f:
            img_data = f.read()
        encoded_img = base64.b64encode(img_data).decode("utf-8")
        payload = {
            "model": config.vision_model,
            "stream": False,
            "messages": [
                {"role": "user", "content": "Describe this image.", "images": [encoded_img]}
            ]
        }
        resp = requests.post(f"{config.ollama_url}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "No response").strip()
    except Exception as e:
        return f"Error interpreting image: {e}"
    
def safe_directory_name(name: str) -> str:
    """ Converts any string into a safe directory name. """
    safe_name = re.sub(r'[^\w-]', '_', name.lower()).strip('_')
    if not safe_name:
        return f"unnamed_{uuid.uuid4().hex[:8]}"
    return safe_name

def format_links_in_text(text: str) -> str:
    url_pattern = re.compile(r'(https?://\S+)')
    return url_pattern.sub(r'[\1](\1)', text)