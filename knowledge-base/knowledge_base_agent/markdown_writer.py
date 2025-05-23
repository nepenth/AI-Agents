from datetime import datetime
import re
import shutil
import uuid
import logging
from pathlib import Path
# from .naming_utils import safe_directory_name # safe_directory_name is used in create_kb_path
import asyncio
import aiofiles
from typing import Dict, List, Optional, Any, AsyncGenerator, Tuple # Added Tuple

from knowledge_base_agent.exceptions import MarkdownGenerationError
from knowledge_base_agent.config import Config
from knowledge_base_agent.path_utils import PathNormalizer, DirectoryManager, create_kb_path # create_kb_path uses safe_directory_name
from knowledge_base_agent.types import KnowledgeBaseItem

_folder_creation_lock = asyncio.Lock()

# format_links_in_text can be kept if item.content doesn't already have this
def format_links_in_text(text: str) -> str:
    """Format URLs in text as markdown links."""
    url_pattern = re.compile(r'(https?://\S+)')
    # Avoid double-linking if already in markdown format [text](url)
    # This regex looks for URLs not already part of a markdown link
    def replace_if_not_linked(match):
        url = match.group(1)
        # Check if the URL is preceded by '](' or followed by ')' which are parts of a markdown link
        # This is a simplified check; a full parser would be more robust.
        if text[max(0, match.start()-2):match.start()] == '](' or (match.end() < len(text) and text[match.end()] == ')'):
            return url # Already linked or part of a link structure
        return f'[{url}]({url})'
    return url_pattern.sub(replace_if_not_linked, text)


class MarkdownWriter:
    """Handles writing content to markdown files in the knowledge base."""

    def __init__(self, config: Config):
        self.config = config
        self.path_normalizer = PathNormalizer() # Potentially used by create_kb_path
        self.dir_manager = DirectoryManager()
        self.allowed_media_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.mp4', '.mov', '.avi', '.mkv', '.webm')

    async def _copy_media_to_kb_item_dir(
        self,
        source_media_paths_relative: List[str], # List of paths to cached media, relative to project_root
        kb_item_temp_dir: Path # Absolute path to KB item's temporary directory
    ) -> Tuple[List[str], List[str]]:
        """
        Copies media from cache to the KB item's temporary directory's 'media' subfolder.
        Renames media to a consistent format (e.g., image_1.jpg, video_1.mp4).

        Args:
            source_media_paths_relative: List of paths to cached media, relative to project_root.
            kb_item_temp_dir: The temporary directory (absolute path) for the new KB item.

        Returns:
            A tuple containing:
            - List of new media filenames (e.g., ["image_1.jpg", "video_1.mp4"]) created in kb_item_temp_dir.
            - List of full paths to the copied media in kb_item_temp_dir.
        """
        new_media_filenames = []
        copied_media_full_paths = []
        image_count = 0
        video_count = 0

        media_subdir_abs = kb_item_temp_dir / "media"
        await self.dir_manager.ensure_directory(media_subdir_abs)

        for i, media_path_rel_str in enumerate(source_media_paths_relative):
            # Resolve relative path from project root to absolute path
            media_file_abs = self.config.resolve_path_from_project_root(media_path_rel_str)
            
            if not media_file_abs.exists():
                logging.warning(f"Source media file not found (after resolving {media_path_rel_str} to {media_file_abs}), skipping: {media_path_rel_str}")
                continue

            if media_file_abs.suffix.lower() not in self.allowed_media_extensions:
                logging.warning(f"Unsupported media type skipped: {media_file_abs}")
                continue

            file_suffix = media_file_abs.suffix.lower()
            new_filename = ""
            if file_suffix in ('.mp4', '.mov', '.avi', '.mkv', '.webm'):
                video_count += 1
                new_filename = f"video_{video_count}{file_suffix}"
            else: # Assume image
                image_count += 1
                new_filename = f"image_{image_count}{file_suffix}"

            destination_path = media_subdir_abs / new_filename
            try:
                await self.dir_manager.copy_file(media_file_abs, destination_path)
                logging.info(f"Successfully copied {media_file_abs} to {destination_path}")
                new_media_filenames.append(new_filename)
                copied_media_full_paths.append(str(destination_path))
            except Exception as e:
                logging.error(f"Failed to copy media file {media_file_abs} to {destination_path}: {e}", exc_info=True)
        
        return new_media_filenames, copied_media_full_paths

    async def write_kb_item(
        self,
        item: KnowledgeBaseItem, 
        # root_dir: Path # This is self.config.knowledge_base_dir (absolute)
        # root_dir is no longer needed as an argument, self.config.knowledge_base_dir is used
    ) -> Tuple[Path, List[str]]:
        """
        Writes a KnowledgeBaseItem to markdown, copies associated media,
        and returns the path to the item's directory (relative to project_root)
        and a list of copied media paths (relative to the knowledge_base_dir, e.g. kb-generated).

        Args:
            item: The KnowledgeBaseItem object containing content and metadata.

        Returns:
            A tuple containing:
            - Path to the KB item's directory (relative to project_root, e.g., "kb-generated/main_cat/sub_cat/item_title").
            - List of relative paths of copied media (relative to knowledge_base_dir, e.g. "main_cat/sub_cat/item_title/image_1.jpg").
        """
        # self.config.knowledge_base_dir is the absolute path to the KB root (e.g., /path/to/project/kb-generated)
        kb_root_abs = self.config.knowledge_base_dir
        try:
            # 1. Determine KB item path (directory)
            # create_kb_path returns a path relative to the KB root (e.g., main_cat/sub_cat/item_title)
            kb_item_rel_to_kb_root_path = create_kb_path(
                item.category_info.main_category,
                item.category_info.sub_category,
                item.display_title # Changed from item.title
            )
            # Full absolute path to the KB item directory
            kb_item_full_dir_path_abs = kb_root_abs / kb_item_rel_to_kb_root_path

            unique_temp_suffix = uuid.uuid4().hex[:8]
            temp_kb_item_dir_abs = kb_item_full_dir_path_abs.parent / f"{kb_item_full_dir_path_abs.name}_{unique_temp_suffix}.temp"
            
            await self.dir_manager.ensure_directory(temp_kb_item_dir_abs)
            logging.debug(f"Using temporary directory: {temp_kb_item_dir_abs}")

            # 2. Copy media files 
            # item.source_media_cache_paths are paths to cached media, relative to project_root
            new_media_filenames_in_item_dir, _ = await self._copy_media_to_kb_item_dir(
                item.source_media_cache_paths, # Changed from item.media_urls
                temp_kb_item_dir_abs # Absolute path to temp dir for copying
            )

            # 3. Prepare a metadata and media header.
            # item.markdown_content (from kb_item_generator) will provide the main H1 title and article body.
            header_lines = []
            
            # Add source, author, and date information
            header_lines.append(f"**Source:** [{item.source_tweet.get('url', 'N/A')}]({item.source_tweet.get('url', '#')})")
            if item.source_tweet.get('author'):
                header_lines.append(f"**Author:** {item.source_tweet.get('author')}")
            if item.source_tweet.get('created_at'):
                 try:
                    dt_obj = datetime.fromisoformat(item.source_tweet['created_at']) if isinstance(item.source_tweet['created_at'], str) else item.source_tweet['created_at']
                    header_lines.append(f"**Original Post Date:** {dt_obj.strftime('%Y-%m-%d %H:%M:%S')}")
                 except ValueError:
                    header_lines.append(f"**Original Post Date:** {item.source_tweet.get('created_at')}")
            
            # Add a separator if source/author/date info was added.
            if header_lines: # Check if any of the above lines were added
                header_lines.append("") 
            
            # Add media embeds section if media exists
            if new_media_filenames_in_item_dir: # Check if media was successfully copied
                header_lines.append("## Media")
                header_lines.append("")
                current_media_idx = 0
                for i, original_media_path_str in enumerate(item.source_media_cache_paths):
                    if current_media_idx < len(new_media_filenames_in_item_dir):
                        media_filename_in_item_dir = new_media_filenames_in_item_dir[current_media_idx]
                        description = item.image_descriptions[i] if i < len(item.image_descriptions) else "Media"
                        file_type = "Image" if media_filename_in_item_dir.startswith("image_") else "Video" if media_filename_in_item_dir.startswith("video_") else "Media"
                        
                        header_lines.append(f"**{file_type} Description:** {format_links_in_text(description if description else 'N/A')}")
                        header_lines.append(f"![{description if description else file_type}]({Path('./media', media_filename_in_item_dir)})") 
                        header_lines.append("")
                        current_media_idx +=1
                    else:
                        # This case should ideally not be hit if logic is correct, but good for logging.
                        logging.warning(f"Media file {original_media_path_str} mentioned in source_media_cache_paths but not found in new_media_filenames_in_item_dir during Markdown header generation.")
                
                # Add a blank line after the media section if it was added and had content.
                if current_media_idx > 0: # Check if any media items were actually processed and added
                    header_lines.append("")

            # Construct the header string.
            metadata_and_media_header = "\n".join(header_lines)

            # The item.markdown_content already contains the H1 title and the full article body.
            # Prepend the metadata_and_media_header.
            if metadata_and_media_header.strip(): # If there's actual content in the header
                final_markdown_content = metadata_and_media_header.strip() + "\n\n" + item.markdown_content.strip()
            else: # No metadata or media, just use the item's markdown content
                final_markdown_content = item.markdown_content.strip()

            # 4. Write README.md
            readme_path_in_temp_abs = temp_kb_item_dir_abs / "README.md"
            async with aiofiles.open(readme_path_in_temp_abs, 'w', encoding="utf-8") as f:
                await f.write(final_markdown_content)
            logging.info(f"Successfully wrote KB item to temporary file: {readme_path_in_temp_abs}")

            # 5. Atomically move temp directory to final location
            async with _folder_creation_lock:
                if kb_item_full_dir_path_abs.exists():
                    logging.warning(f"Destination folder {kb_item_full_dir_path_abs} exists. Removing before rename.")
                    try:
                        shutil.rmtree(kb_item_full_dir_path_abs) 
                    except OSError as e:
                        logging.error(f"Error removing existing directory {kb_item_full_dir_path_abs}: {e}")
                        fallback_temp_name = temp_kb_item_dir_abs.parent / f"{kb_item_full_dir_path_abs.name}_fallback_{uuid.uuid4().hex[:4]}"
                        temp_kb_item_dir_abs.rename(fallback_temp_name)
                        raise MarkdownGenerationError(f"Failed to remove existing directory {kb_item_full_dir_path_abs}, temp data saved to {fallback_temp_name}") from e

                temp_kb_item_dir_abs.rename(kb_item_full_dir_path_abs)
                logging.info(f"Atomically moved {temp_kb_item_dir_abs} to {kb_item_full_dir_path_abs}")

            # 6. Prepare list of copied media paths *relative to kb_root_abs (e.g. kb-generated)*
            # kb_item_rel_to_kb_root_path is like "main_cat/sub_cat/item_title"
            # new_media_filenames_in_item_dir is like ["image_1.jpg", "video_1.mp4"]
            final_copied_media_rel_to_kb_root_paths = [
                str(kb_item_rel_to_kb_root_path / "media" / fname) for fname in new_media_filenames_in_item_dir
            ]
            
            # Return path to KB item's directory, relative to project_root
            kb_item_dir_rel_to_project_root = self.config.get_relative_path(kb_item_full_dir_path_abs)
            
            return kb_item_dir_rel_to_project_root, final_copied_media_rel_to_kb_root_paths

        except Exception as e:
            logging.error(f"Failed to write knowledge base item for '{item.display_title}': {e}", exc_info=True) # Changed from item.title
            if 'temp_kb_item_dir_abs' in locals() and temp_kb_item_dir_abs.exists():
                try:
                    shutil.rmtree(temp_kb_item_dir_abs)
                    logging.info(f"Cleaned up temporary directory {temp_kb_item_dir_abs} after error.")
                except Exception as cleanup_e:
                    logging.error(f"Failed to cleanup temporary directory {temp_kb_item_dir_abs}: {cleanup_e}")
            raise MarkdownGenerationError(f"Failed to write KB item '{item.display_title}': {str(e)}") from e # Changed from item.title


# Keep validate_media_references if it's still valuable for debugging or a final check,
# though the new relative linking should be more robust.
# For now, assuming it might be useful.
def validate_media_references(content: str, directory: Path) -> bool: # directory is absolute
    """Validate that media references in markdown content exist in the directory."""
    media_link_pattern = re.compile(r"!\[.*?\]\(\.?/([^)]+)\)")
    found_links = media_link_pattern.findall(content)
    
    if not found_links:
        logging.debug(f"No relative media links found (like './media.ext') in content for validation in {directory}")
        return True 

    all_found = True
    for media_filename in found_links:
        media_file_path = directory / media_filename # directory is absolute, media_filename is relative to it
        if not media_file_path.exists():
            logging.warning(f"Validation failed: Media file '{media_filename}' referenced in markdown not found in directory '{directory}'. Full path checked: {media_file_path}")
            all_found = False
        else:
            logging.debug(f"Validation success: Media file '{media_filename}' found at '{media_file_path}'.")
            
    return all_found