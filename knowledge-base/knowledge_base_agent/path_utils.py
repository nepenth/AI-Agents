import re
import unicodedata
from pathlib import Path
from typing import Union, List
import os
import platform
from .exceptions import PathValidationError
import shutil
import asyncio
import logging

class PathValidator:
    # Maximum length for different OS
    MAX_PATH_LENGTH = 260 if platform.system() == "Windows" else 4096
    MAX_FILENAME_LENGTH = 255
    
    # Characters not allowed in file names (Windows + Unix)
    INVALID_CHARS = r'[<>:"/\\|?*\x00-\x1F]'
    
    # Reserved names on Windows
    RESERVED_NAMES = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4',
        'LPT1', 'LPT2', 'LPT3', 'LPT4'
    }

class PathNormalizer:
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize a string for use in file/directory names."""
        # Convert to lowercase and normalize unicode characters
        name = unicodedata.normalize('NFKD', name.lower())
        
        # Replace invalid characters with hyphens
        name = re.sub(PathValidator.INVALID_CHARS, '-', name)
        
        # Replace spaces with hyphens
        name = re.sub(r'\s+', '-', name)
        
        # Remove multiple consecutive hyphens
        name = re.sub(r'-+', '-', name)
        
        # Remove leading/trailing hyphens
        name = name.strip('-')
        
        # Ensure name isn't empty or just dots
        if not name or name.strip('.') == '':
            raise PathValidationError("Invalid name: empty or just dots")
            
        # Check reserved names
        if name.upper() in PathValidator.RESERVED_NAMES:
            name = f"kb-{name}"
            
        # Truncate if too long
        if len(name) > PathValidator.MAX_FILENAME_LENGTH:
            name = name[:PathValidator.MAX_FILENAME_LENGTH-4]
            
        return name

    @staticmethod
    def normalize_path(path_components: List[str]) -> Path:
        """Create a normalized path from components."""
        normalized = [PathNormalizer.normalize_name(comp) for comp in path_components]
        path = Path(*normalized)
        
        # Validate full path length
        if len(str(path)) > PathValidator.MAX_PATH_LENGTH:
            raise PathValidationError(f"Path too long: {path}")
            
        return path

class DirectoryManager:
    @staticmethod
    async def ensure_directory(path: Union[str, Path]) -> Path:
        """Ensure directory exists and is valid."""
        path = Path(path)
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except Exception as e:
            raise PathValidationError(f"Failed to create directory: {path}") from e

    @staticmethod
    def is_valid_directory(path: Union[str, Path]) -> bool:
        """Check if directory path is valid."""
        try:
            path = Path(path)
            return (
                len(str(path)) <= PathValidator.MAX_PATH_LENGTH and
                all(
                    len(part) <= PathValidator.MAX_FILENAME_LENGTH and
                    part.upper() not in PathValidator.RESERVED_NAMES
                    for part in path.parts
                )
            )
        except Exception:
            return False

    async def copy_file(self, source: Path, destination: Path) -> None:
        """
        Asynchronously copy a file from source to destination.
        
        Args:
            source (Path): Source file path
            destination (Path): Destination file path
        """
        try:
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Use asyncio to run shutil.copy2 in a thread pool
            await asyncio.get_event_loop().run_in_executor(
                None, shutil.copy2, str(source), str(destination)
            )
            
            logging.debug(f"Copied file from {source} to {destination}")
            
        except Exception as e:
            logging.error(f"Failed to copy file from {source} to {destination}: {e}")
            raise

def create_kb_path(category: str, subcategory: str, name: str) -> Path:
    """Create a knowledge base item path."""
    normalizer = PathNormalizer()
    try:
        return normalizer.normalize_path([category, subcategory, f"{name}.md"])
    except Exception as e:
        raise PathValidationError(f"Failed to create KB path: {e}") from e 