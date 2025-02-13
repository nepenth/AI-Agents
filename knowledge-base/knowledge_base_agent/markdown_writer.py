import re
import shutil
import uuid
import datetime
import logging
from pathlib import Path
from .naming_utils import safe_directory_name
import asyncio
import aiofiles
from typing import Dict, List, Optional

from .exceptions import StorageError
from .config import Config
from .category_manager import CategoryManager

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

    async def write_tweet_markdown(
        self,
        config: Config,
        tweet_id: str,
        main_category: str,
        sub_category: str,
        item_name: str,
        tweet_text: str,
        tweet_url: str,
        image_files: Optional[List[Path]] = None,
        image_descriptions: Optional[List[str]] = None
    ) -> None:
        """Write tweet content to a markdown file."""
        try:
            safe_name = safe_directory_name(item_name)
            item_dir = config.knowledge_base_dir / main_category / sub_category / safe_name
            
            # Create temporary directory for atomic writes
            temp_dir = item_dir.with_suffix('.temp')
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Prepare and write content
            content = self._prepare_markdown_content(
                item_name=item_name,
                tweet_text=tweet_text,
                tweet_url=tweet_url,
                image_files=image_files,
                image_descriptions=image_descriptions
            )
            
            async with aiofiles.open(temp_dir / "README.md", 'w', encoding='utf-8') as f:
                await f.write(content)

            # Copy images if they exist
            if image_files:
                await self._copy_images(image_files, temp_dir)

            # Atomic directory rename
            if item_dir.exists():
                shutil.rmtree(item_dir)
            temp_dir.rename(item_dir)
                
        except Exception as e:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise StorageError(f"Failed to write markdown for tweet {tweet_id}: {e}")

    def _prepare_markdown_content(self, item_name: str, tweet_text: str, tweet_url: str,
                                image_files: Optional[List[Path]] = None,
                                image_descriptions: Optional[List[str]] = None) -> str:
        """Prepare markdown content with proper formatting."""
        content_parts = [
            f"# {item_name}\n",
            f"**Original Tweet:** [{tweet_url}]({tweet_url})\n",
            f"**Content:**\n{tweet_text}\n"
        ]
        
        if image_files and image_descriptions:
            content_parts.append("## Images\n")
            for idx, (image, desc) in enumerate(zip(image_files, image_descriptions), 1):
                content_parts.extend([
                    f"### Image {idx}\n",
                    f"![Image {idx}](./{image.name})\n",
                    f"**AI Interpretation:** {desc}\n"
                ])
                
        content_parts.append(f"\n*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        return "\n".join(content_parts)

    async def _copy_images(self, image_files: List[Path], target_dir: Path) -> None:
        """Copy images to the target directory."""
        try:
            for image_file in image_files:
                if image_file.exists():
                    shutil.copy2(image_file, target_dir / image_file.name)
        except Exception as e:
            raise StorageError(f"Failed to copy images: {e}")

def generate_root_readme(knowledge_base_dir: Path, category_manager: CategoryManager) -> None:
    """
    Generate the root README.md file.
    
    Raises:
        StorageError: If writing fails
    """
    try:
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
        with readme_path.open('w', encoding='utf-8') as f:
            f.write("\n".join(content))
            
    except Exception as e:
        raise StorageError(f"Failed to generate root README: {e}")
