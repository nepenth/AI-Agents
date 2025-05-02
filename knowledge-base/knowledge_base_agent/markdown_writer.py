from datetime import datetime
import re
import shutil
import uuid
import logging
from pathlib import Path
from .naming_utils import safe_directory_name
import asyncio
import aiofiles
from typing import Dict, List, Optional, Any, AsyncGenerator

from knowledge_base_agent.exceptions import MarkdownGenerationError
from knowledge_base_agent.config import Config
from knowledge_base_agent.path_utils import PathNormalizer, DirectoryManager, create_kb_path
from knowledge_base_agent.types import KnowledgeBaseItem

_folder_creation_lock = asyncio.Lock()

def format_links_in_text(text: str) -> str:
    """Format URLs in text as markdown links."""
    url_pattern = re.compile(r'(https?://\S+)')
    return url_pattern.sub(r'[\1](\1)', text)

def generate_tweet_markdown_content(
    item_name: str,
    tweet_url: str,
    tweet_text: str,
    image_descriptions: List[str],
    image_filenames: List[str] # Expect filenames like image_1.jpg, video_1.mp4
) -> str:
    """Generate markdown content for a tweet with correct image references."""
    formatted_tweet_text = format_links_in_text(tweet_text)
    lines = [
        f"# {item_name}",
        "",
        f"**Tweet URL:** [{tweet_url}]({tweet_url})",
        "",
        f"**Tweet Text:** {formatted_tweet_text}",
        ""
    ]

    # Iterate through the actual filenames that were copied.
    if image_filenames:
        logging.info(f"Generating markdown for {len(image_filenames)} media files: {image_filenames}")
        for i, filename in enumerate(image_filenames):
            # Safely get the corresponding description, providing a default if index is out of bounds
            desc = image_descriptions[i] if i < len(image_descriptions) else "No description available"
            if not desc: # Handle empty string descriptions
                desc = "No description available"

            # Add description header
            file_type = "Image" if filename.startswith("image_") else "Video" if filename.startswith("video_") else "Media"
            lines.append(f"**{file_type} {i+1} Description:** {desc}")

            # Generate the relative markdown link
            # Ensure filename does not contain problematic characters (should be handled by copy logic, but double-check)
            clean_filename = filename.replace("(", "%28").replace(")", "%29") # Basic URL encoding for parens
            image_link = f"![{file_type} {i+1}](./{clean_filename})"
            logging.debug(f"Adding markdown media link: {image_link}")
            lines.append(image_link)
            lines.append("")
    else:
        logging.info("No image filenames provided, skipping media embedding in markdown.")

    return "\\n".join(lines)

class MarkdownWriter:
    """Handles writing content to markdown files in the knowledge base."""

    def __init__(self, config: Config):
        self.config = config
        self.path_normalizer = PathNormalizer()
        self.dir_manager = DirectoryManager()
        # Define allowed extensions (lowercase)
        self.allowed_media_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.mp4', '.mov', '.avi', '.mkv', '.webm') # Added video

    async def _validate_and_copy_media(self, media_files: List[Path], target_dir: Path) -> AsyncGenerator[tuple, None]:
        """Validate and copy media files, yielding valid files copied and their new names."""
        valid_files = []
        invalid_files = []
        for img in media_files:
            # Check extension against allowed list (case-insensitive)
            if img.suffix.lower() in self.allowed_media_extensions:
                valid_files.append(img)
            else:
                invalid_files.append(img.name)

        if invalid_files:
            logging.warning(f"Invalid or unsupported media types skipped: {invalid_files}")

        for i, media_path in enumerate(valid_files):
            if media_path.exists():
                # Determine the new name based on type for clarity, using a consistent index
                file_suffix = media_path.suffix.lower()
                if file_suffix in ('.mp4', '.mov', '.avi', '.mkv', '.webm'):
                    media_name = f"video_{i+1}{file_suffix}"
                else: # Assume image
                    media_name = f"image_{i+1}{file_suffix}"

                new_path = target_dir / media_name
                try:
                    await self.dir_manager.copy_file(media_path, new_path)
                    # Add explicit log after successful copy
                    logging.info(f"Successfully copied {media_path} to {new_path}")
                    yield (media_path, media_name)

                except Exception as e:
                     # Ensure errors are logged clearly
                     logging.error(f"Failed to copy media file {media_path} to {new_path}: {e}", exc_info=True)
            else:
                logging.warning(f"Media file not found, skipping: {media_path}")

    async def write_tweet_markdown(
        self,
        root_dir: Path,
        tweet_id: str,
        tweet_data: Dict[str, Any],
        image_files: List[Path],
        image_descriptions: List[str],
        main_category: str = None,
        sub_category: str = None,
        item_name: str = None,
        tweet_text: str = None,
        tweet_url: str = None
    ) -> tuple[str, List[str]]:
        """Write tweet markdown using cached tweet data, returning the content file path and copied media paths."""
        categories = tweet_data.get('categories')
        if not categories:
            raise MarkdownGenerationError(f"No category data found for tweet {tweet_id}")
            
        main_category = main_category or categories['main_category']
        sub_category = sub_category or categories['sub_category']
        item_name = item_name or categories['item_name']
        tweet_text = tweet_text or tweet_data.get('full_text', '')
        tweet_url = tweet_url or tweet_data.get('tweet_url', '')
        safe_item_name = safe_directory_name(item_name)
        tweet_folder = root_dir / main_category / sub_category / safe_item_name

        async with _folder_creation_lock:
            if tweet_folder.exists():
                unique_suffix = uuid.uuid4().hex[:6]
                safe_item_name = f"{safe_item_name}_{unique_suffix}"
                tweet_folder = root_dir / main_category / sub_category / safe_item_name

        temp_folder = tweet_folder.with_suffix('.temp')
        # Ensure target directory exists before copying
        await self.dir_manager.ensure_dir_exists(temp_folder)

        try:
            if not tweet_text.strip():
                logging.warning(f"Empty tweet text for tweet {tweet_id}")

            # Copy valid media files and track new filenames
            copied_media_info = [] # Store tuples of (original_path, new_filename)
            async for img_path, new_filename in self._validate_and_copy_media(image_files, temp_folder):
                # Log the details being collected
                logging.info(f"Collected media for markdown: Original={img_path}, New={new_filename}")
                copied_media_info.append((img_path, new_filename))

            # Extract just the filenames for markdown generation
            image_filenames = [info[1] for info in copied_media_info]
            copied_media_paths = [str(temp_folder / fname) for fname in image_filenames] # Use temp_folder path initially

            # Log before generating content
            logging.info(f"Generating markdown with image filenames: {image_filenames}")
            logging.info(f"Corresponding descriptions count: {len(image_descriptions)}")
            if len(image_filenames) != len(image_descriptions):
                logging.warning("Mismatch between number of copied images and descriptions!")
                # Adjust descriptions list to match filenames to avoid errors, though this might lose data
                image_descriptions = image_descriptions[:len(image_filenames)]

            # Generate content with correct filenames
            content_md = generate_tweet_markdown_content(
                item_name,
                tweet_url,
                tweet_text,
                image_descriptions,
                image_filenames=image_filenames
            )
            logging.debug(f"Generated markdown content for tweet {tweet_id}: {content_md[:500]}...")  # Log first 500 chars for debugging
            
            content_md_path = temp_folder / "README.md"
            logging.info(f"Writing markdown content to {content_md_path}")
            async with aiofiles.open(content_md_path, 'w', encoding="utf-8") as f:
                await f.write(content_md)
            logging.info(f"Successfully wrote markdown content to {content_md_path}")

            # Rename the folder *after* all writes are complete
            async with _folder_creation_lock:
                if tweet_folder.exists():
                    logging.warning(f"Destination folder {tweet_folder} exists, removing before rename.")
                    # Use async removal if possible, or sync if needed
                    shutil.rmtree(tweet_folder) # Consider adding async equivalent if needed
                temp_folder.rename(tweet_folder)
                logging.info(f"Renamed {temp_folder} to {tweet_folder}")

            # Return the *final* correct path and the final copied media paths
            final_readme_path = tweet_folder / "README.md"
            final_copied_media_paths = [str(tweet_folder / fname) for fname in image_filenames]

            # Validate media references in the final README
            async with aiofiles.open(final_readme_path, 'r', encoding="utf-8") as f:
                final_content = await f.read()
            if not validate_media_references(final_content, tweet_folder):
                logging.error(f"Media references validation failed for {final_readme_path}. Media links may be broken.")
                # Force rewrite with correct content if validation fails
                logging.info(f"Rewriting README for tweet {tweet_id} to ensure media links.")
                content_md = generate_tweet_markdown_content(
                    item_name,
                    tweet_url,
                    tweet_text,
                    image_descriptions,
                    image_filenames=image_filenames
                )
                async with aiofiles.open(final_readme_path, 'w', encoding="utf-8") as f:
                    await f.write(content_md)
                logging.info(f"Rewrote markdown content to {final_readme_path}")

            return str(final_readme_path), final_copied_media_paths

        except Exception as e:
            logging.error(f"Failed to write tweet markdown for {tweet_id}: {str(e)}")
            if temp_folder.exists():
                shutil.rmtree(temp_folder)
            raise MarkdownGenerationError(f"Failed to write tweet markdown: {str(e)}")

    async def write_kb_item(
        self,
        item: KnowledgeBaseItem,
        media_files: List[Path],
        media_descriptions: List[str],
        root_dir: Path
    ) -> tuple[Path, List[str]]:
        """Write knowledge base item to markdown with media, returning the README path and copied media paths."""
        try:
            kb_path = create_kb_path(
                item.category_info.main_category,
                item.category_info.sub_category,
                item.title
            )
            if root_dir:
                kb_path = root_dir / kb_path

            temp_dir = kb_path.with_suffix('.temp')
            temp_dir.mkdir(parents=True, exist_ok=True)

            try:
                # Ensure tweet URL is included
                content = f"{item.content}\n\n---\n**Source**: [Original Tweet]({item.source_tweet['url']})"
                
                # Append media links if media files are provided and not already in content
                if media_files and not any(f"![Image" in content or f"![Video" in content for content in content.split('\n')):
                    logging.info(f"Appending media links to content for KB item {item.title}")
                    content += "\n\n## Media Content\n"
                    for i, media_path in enumerate(media_files):
                        file_suffix = media_path.suffix.lower()
                        file_type = "Video" if file_suffix in ('.mp4', '.mov', '.avi', '.mkv', '.webm') else "Image"
                        media_name = f"{file_type.lower()}_{i+1}{file_suffix}"
                        desc = media_descriptions[i] if i < len(media_descriptions) else "No description available"
                        content += f"**{file_type} {i+1} Description:** {desc}\n"
                        content += f"![{file_type} {i+1}](./{media_name})\n\n"
                
                readme_path = temp_dir / "README.md"
                async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
                    await f.write(content)
                logging.info(f"Wrote content to {readme_path} with media links appended if necessary")

                cleanup_files = []
                copied_media_paths = []
                if media_files:
                    async for img_path, img_name in self._validate_and_copy_media(media_files, temp_dir):
                        cleanup_files.append(img_path)
                        copied_media_paths.append(str(temp_dir / img_name))

                if kb_path.exists():
                    shutil.rmtree(kb_path)
                temp_dir.rename(kb_path)

                # Cleanup original files (optional)
                if media_files:
                    for img_path in media_files:
                        if img_path.exists() and img_path in cleanup_files:
                            # Optionally uncomment to delete originals from cache
                            # img_path.unlink()
                            pass

                return kb_path, copied_media_paths

            except Exception as e:
                logging.error(f"Failed to write KB item content: {str(e)}")
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                raise

        except Exception as e:
            logging.error(f"Failed to create KB item directory: {str(e)}")
            raise MarkdownGenerationError(f"Failed to write KB item: {str(e)}")

def validate_media_references(content: str, directory: Path) -> bool:
    """Validate that all media references in the content exist in the directory."""
    # Extract all image references
    image_pattern = r'!\[.*?\]\(\./(.*?)\)'
    referenced_images = re.findall(image_pattern, content)
    
    missing_images = []
    for img in referenced_images:
        if not (directory / img).exists():
            missing_images.append(img)
    
    if missing_images:
        logging.warning(f"Missing referenced images: {missing_images}")
        return False
    return True