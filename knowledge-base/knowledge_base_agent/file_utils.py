import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

def safe_read_json(file_path: Path, default: Any = None) -> Any:
    """Unified JSON file reading with error handling."""
    if not file_path.exists():
        return default or {}
    try:
        with file_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to read JSON from {file_path}: {e}")
        return default or {}

def safe_write_json(file_path: Path, data: Any, indent: int = 4) -> bool:
    """Unified JSON file writing with error handling."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent)
        return True
    except Exception as e:
        logging.error(f"Failed to write JSON to {file_path}: {e}")
        return False 
    