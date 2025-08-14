"""
Media processing service for analyzing images and videos using AI.
"""

import asyncio
import logging
import os
import uuid
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import aiofiles
import aiohttp

from app.services.ai_service import get_ai_service
from app.ai.base import GenerationConfig, ModelType
from app.config import get_settings

logger = logging.getLogger(__name__)


class MediaProcessor:
    """Service for processing media files with AI analysis."""
    
    def __init__(self):
        self.settings = get_settings()
        self.media_dir = Path(self.settings.MEDIA_DIR)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        
        # Supported media types
        self.supported_image_types = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        self.supported_video_types = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
    
    async def process_media_files(
        self, 
        media_files: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process a list of media files and return enhanced metadata."""
        processed_files = []
        
        for media_file in media_files:
            try:
                processed_file = await self._process_single_media(media_file)
                processed_files.append(processed_file)
            except Exception as e:
                logger.error(f"Failed to process media file {media_file.get('url', 'unknown')}: {e}")
                # Add original file info with error
                processed_file = media_file.copy()
                processed_file.update({
                    "processing_error": str(e),
                    "ai_description": None,
                    "local_path": None
                })
                processed_files.append(processed_file)
        
        return processed_files
    
    async def _process_single_media(self, media_file: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single media file."""
        media_url = media_file.get("url")
        media_type = media_file.get("type", "unknown")
        
        if not media_url:
            raise ValueError("Media file missing URL")
        
        # Download media file
        local_path = await self._download_media(media_url, media_type)
        
        # Analyze with AI
        ai_description = await self._analyze_media_with_ai(local_path, media_type)
        
        # Extract metadata
        metadata = await self._extract_media_metadata(local_path, media_type)
        
        # Create processed file info
        processed_file = media_file.copy()
        processed_file.update({
            "local_path": str(local_path),
            "ai_description": ai_description,
            "metadata": metadata,
            "processed_at": asyncio.get_event_loop().time()
        })
        
        return processed_file
    
    async def _download_media(self, media_url: str, media_type: str) -> Path:
        """Download media file to local storage."""
        # Generate unique filename
        file_extension = self._get_file_extension(media_url, media_type)
        filename = f"{uuid.uuid4()}{file_extension}"
        local_path = self.media_dir / filename
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(media_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status} downloading {media_url}")
                    
                    async with aiofiles.open(local_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
            
            logger.info(f"Downloaded media file: {media_url} -> {local_path}")
            return local_path
            
        except Exception as e:
            # Clean up partial download
            if local_path.exists():
                local_path.unlink()
            raise Exception(f"Failed to download media: {e}")
    
    def _get_file_extension(self, media_url: str, media_type: str) -> str:
        """Determine file extension from URL or media type."""
        # Try to get extension from URL
        from urllib.parse import urlparse
        parsed_url = urlparse(media_url)
        path = Path(parsed_url.path)
        
        if path.suffix:
            return path.suffix.lower()
        
        # Fallback to media type mapping
        type_mapping = {
            "image": ".jpg",
            "video": ".mp4",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "video/mp4": ".mp4",
            "video/webm": ".webm"
        }
        
        return type_mapping.get(media_type.lower(), ".bin")
    
    async def _analyze_media_with_ai(self, local_path: Path, media_type: str) -> Optional[str]:
        """Analyze media file using AI vision models."""
        try:
            ai_service = get_ai_service()
            
            # Check if we have vision-capable models
            models = await ai_service.list_models()
            vision_models = [m for m in models if m.get("supports_vision", False)]
            
            if not vision_models:
                logger.warning("No vision-capable AI models available for media analysis")
                return None
            
            # Use the first available vision model
            model_name = vision_models[0]["name"]
            
            # For now, we'll use text generation with a description of what we would do
            # In a real implementation, you'd pass the image to a vision model
            if self._is_image(local_path):
                prompt = f"""Analyze this image file: {local_path.name}
                
Please provide a detailed description of what you see in this image, including:
- Main subjects or objects
- Setting or environment
- Colors and composition
- Any text visible in the image
- Overall mood or atmosphere

Keep the description concise but informative."""
            
            elif self._is_video(local_path):
                prompt = f"""Analyze this video file: {local_path.name}
                
Please provide a description of this video, including:
- Main content or subject matter
- Duration and key scenes
- Visual style and quality
- Any notable audio elements
- Overall purpose or message

Keep the description concise but informative."""
            
            else:
                return f"Media file: {local_path.name} (type: {media_type})"
            
            # Generate description using AI
            config = GenerationConfig(temperature=0.3, max_tokens=200)
            description = await ai_service.generate_text(prompt, model_name, config=config)
            
            return description
            
        except Exception as e:
            logger.error(f"AI analysis failed for {local_path}: {e}")
            return f"Media file: {local_path.name} (AI analysis failed: {str(e)})"
    
    async def _extract_media_metadata(self, local_path: Path, media_type: str) -> Dict[str, Any]:
        """Extract metadata from media file."""
        metadata = {
            "filename": local_path.name,
            "file_size": local_path.stat().st_size,
            "media_type": media_type
        }
        
        try:
            if self._is_image(local_path):
                metadata.update(await self._extract_image_metadata(local_path))
            elif self._is_video(local_path):
                metadata.update(await self._extract_video_metadata(local_path))
        except Exception as e:
            logger.warning(f"Failed to extract metadata from {local_path}: {e}")
            metadata["metadata_error"] = str(e)
        
        return metadata
    
    async def _extract_image_metadata(self, local_path: Path) -> Dict[str, Any]:
        """Extract metadata from image file."""
        try:
            # This would use PIL/Pillow in a real implementation
            # For now, return basic info
            return {
                "type": "image",
                "format": local_path.suffix.upper().lstrip('.'),
            }
        except Exception as e:
            logger.warning(f"Failed to extract image metadata: {e}")
            return {"type": "image", "error": str(e)}
    
    async def _extract_video_metadata(self, local_path: Path) -> Dict[str, Any]:
        """Extract metadata from video file."""
        try:
            # This would use ffmpeg-python or similar in a real implementation
            # For now, return basic info
            return {
                "type": "video",
                "format": local_path.suffix.upper().lstrip('.'),
            }
        except Exception as e:
            logger.warning(f"Failed to extract video metadata: {e}")
            return {"type": "video", "error": str(e)}
    
    def _is_image(self, file_path: Path) -> bool:
        """Check if file is an image."""
        return file_path.suffix.lower() in self.supported_image_types
    
    def _is_video(self, file_path: Path) -> bool:
        """Check if file is a video."""
        return file_path.suffix.lower() in self.supported_video_types
    
    async def cleanup_media_file(self, local_path: str) -> bool:
        """Clean up a downloaded media file."""
        try:
            path = Path(local_path)
            if path.exists() and path.parent == self.media_dir:
                path.unlink()
                logger.info(f"Cleaned up media file: {local_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to cleanup media file {local_path}: {e}")
        
        return False
    
    async def get_media_info(self, local_path: str) -> Optional[Dict[str, Any]]:
        """Get information about a media file."""
        try:
            path = Path(local_path)
            if not path.exists():
                return None
            
            return {
                "filename": path.name,
                "file_size": path.stat().st_size,
                "is_image": self._is_image(path),
                "is_video": self._is_video(path),
                "extension": path.suffix.lower()
            }
        except Exception as e:
            logger.error(f"Failed to get media info for {local_path}: {e}")
            return None


# Global service instance
_media_processor: Optional[MediaProcessor] = None


def get_media_processor() -> MediaProcessor:
    """Get the global media processor instance."""
    global _media_processor
    if _media_processor is None:
        _media_processor = MediaProcessor()
    return _media_processor