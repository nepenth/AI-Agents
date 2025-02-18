import re
import shutil
import uuid
import datetime
import logging
from pathlib import Path
from .naming_utils import safe_directory_name
import asyncio
import aiofiles
from typing import Dict, List, Optional, Any

from .exceptions import StorageError
from .config import Config
from .category_manager import CategoryManager
from knowledge_base_agent.exceptions import KnowledgeBaseError
from knowledge_base_agent.file_utils import async_json_load, async_write_text
from .path_utils import PathNormalizer, DirectoryManager, create_kb_path
from .types import KnowledgeBaseItem, CategoryInfo
from .exceptions import MarkdownGenerationError

_folder_creation_lock = asyncio.Lock()

def sanitize_markdown_cell(text: str) -> str:
    """Escape vertical bars for markdown tables."""
    return text.replace('|', '&#124;').strip()

def format_links_in_text(text: str) -> str:
    import re
    url_pattern = re.compile(r'(https?://\S+)')
    return url_pattern.sub(r'[\1](\1)', text)

def generate_tweet_markdown_content(
    item_name: str,
    tweet_url: str,
    tweet_text: str,
    image_descriptions: list
) -> str:
    formatted_tweet_text = format_links_in_text(tweet_text)
    lines = [
        f"# {item_name}",
        "",
        f"**Tweet URL:** [{tweet_url}]({tweet_url})",
        "",
        f"**Tweet Text:** {formatted_tweet_text}",
        ""
    ]

    for i, desc in enumerate(image_descriptions):
        img_name = f"image_{i+1}.jpg"
        lines.append(f"**Image {i+1} Description:** {desc}")
        lines.append(f"![Image {i+1}](./{img_name})")
        lines.append("")
    return "\n".join(lines)

async def write_tweet_markdown(
    root_dir: Path,
    tweet_id: str,
    main_category: str,
    sub_category: str,
    item_name: str,
    tweet_text: str,
    image_files: list,
    image_descriptions: list,
    tweet_url: str
):
    safe_item_name = safe_directory_name(item_name)
    tweet_folder = root_dir / main_category / sub_category / safe_item_name

    async with _folder_creation_lock:
        if tweet_folder.exists():
            unique_suffix = uuid.uuid4().hex[:6]
            safe_item_name = f"{safe_item_name}_{unique_suffix}"
            tweet_folder = root_dir / main_category / sub_category / safe_item_name

    temp_folder = tweet_folder.with_suffix('.temp')
    temp_folder.mkdir(parents=True, exist_ok=True)

    try:
        # Add content validation before writing
        if not tweet_text.strip():
            logging.warning(f"Empty tweet text for {tweet_id}")
            
        # Ensure image files exist before copying
        valid_image_files = [img for img in image_files if img.exists()]
        if len(valid_image_files) != len(image_files):
            logging.warning(f"Some image files missing for {tweet_id}")

        content_md = generate_tweet_markdown_content(item_name, tweet_url, tweet_text, image_descriptions)
        content_md_path = temp_folder / "content.md"
        async with aiofiles.open(content_md_path, 'w', encoding="utf-8") as f:
            await f.write(content_md)

        for i, img_path in enumerate(image_files):
            if img_path.exists():
                img_name = f"image_{i+1}.jpg"
                shutil.copy2(img_path, temp_folder / img_name)

        # Atomic rename of temp folder to final folder
        temp_folder.rename(tweet_folder)

        for img_path in image_files:
            if img_path.exists():
                img_path.unlink()
    except Exception as e:
        if temp_folder.exists():
            shutil.rmtree(temp_folder)
        logging.error(f"Failed to write tweet markdown for {tweet_id}: {e}")
        raise

class MarkdownWriter:
    """Handles writing content to markdown files in the knowledge base."""

    def __init__(self, config: Config):
        self.config = config
        self.path_normalizer = PathNormalizer()
        self.dir_manager = DirectoryManager()

    async def write_kb_item(
        self,
        item: KnowledgeBaseItem,
        media_files: List[Path] = None,
        media_descriptions: List[str] = None
    ) -> None:
        """Write knowledge base item to markdown with media."""
        try:
            kb_path = create_kb_path(
                item['category_info']['category'],
                item['category_info']['subcategory'],
                item['title']
            )
            
            # Create temp directory for atomic writes
            temp_dir = kb_path.with_suffix('.temp')
            await self.dir_manager.ensure_directory(temp_dir)

            # Generate and write content
            content = self._generate_content(item, media_files, media_descriptions)
            await async_write_text(content, temp_dir / "README.md")

            # Copy media files if present
            if media_files:
                await self._copy_media_files(media_files, temp_dir)

            # Atomic directory rename
            if kb_path.exists():
                kb_path.unlink()
            temp_dir.rename(kb_path)

        except Exception as e:
            if temp_dir.exists():
                temp_dir.unlink()
            raise MarkdownGenerationError(f"Failed to write KB item: {e}")

    def _generate_content(
        self,
        item: KnowledgeBaseItem,
        media_files: List[Path] = None,
        media_descriptions: List[str] = None
    ) -> str:
        """Generate markdown content with proper formatting."""
        parts = [
            f"# {item['title']}\n",
            f"## Description\n{item['description']}\n",
            f"## Content\n{item['content']}\n",
            "## Source\n",
            f"- Original Tweet: [{item['source_tweet']['url']}]({item['source_tweet']['url']})",
            f"- Author: {item['source_tweet']['author']}",
            f"- Date: {item['source_tweet']['created_at'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        ]

        if media_files and media_descriptions:
            parts.append("## Media\n")
            for idx, (media, desc) in enumerate(zip(media_files, media_descriptions), 1):
                parts.extend([
                    f"### Media {idx}",
                    f"![{media.stem}](./{media.name})",
                    f"**Description:** {desc}\n"
                ])

        parts.append(f"\n*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        return "\n".join(parts)

    async def _copy_media_files(self, media_files: List[Path], target_dir: Path) -> None:
        """Copy media files to target directory."""
        for media_file in media_files:
            if media_file.exists():
                await self.dir_manager.copy_file(media_file, target_dir / media_file.name)

    async def generate_readme(self) -> None:
        """Generate the main README file."""
        try:
            # README generation logic here
            pass
        except Exception as e:
            logging.error(f"Failed to generate README: {str(e)}")
            raise MarkdownGenerationError(f"Failed to generate README: {str(e)}")

async def generate_root_readme(knowledge_base_dir: Path, category_manager: CategoryManager) -> None:
    """Generate the root README.md file."""
    try:
        logging.info(f"Generating root README.md in {knowledge_base_dir}")
        content = ["# Knowledge Base\n"]
        
        for main_cat in sorted(category_manager.get_all_main_categories()):
            content.append(f"## {main_cat}\n")
            for sub_cat in sorted(category_manager.get_subcategories(main_cat)):
                content.append(f"### {sub_cat}\n")
                
                sub_cat_path = knowledge_base_dir / main_cat / sub_cat
                if sub_cat_path.exists():
                    items = [p for p in sub_cat_path.iterdir() if p.is_dir()]
                    for item in sorted(items):
                        content.append(f"- [{item.name}]({main_cat}/{sub_cat}/{item.name})")
                
                content.append("")
        
        readme_path = knowledge_base_dir / "README.md"
        async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
            await f.write("\n".join(content))
            
        logging.info("Root README.md generated successfully")
            
    except Exception as e:
        logging.error(f"Failed to generate root README: {e}")
        raise StorageError(f"Failed to generate root README: {e}")
