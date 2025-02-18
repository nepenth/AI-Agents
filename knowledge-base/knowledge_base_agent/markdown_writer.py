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
        """Generate README files for all knowledge base items."""
        try:
            kb_root = Path(self.config.knowledge_base_dir)
            processed_tweets_path = Path(self.config.processed_tweets_file)
            
            # Load processed tweets data
            try:
                processed_tweets = await async_json_load(processed_tweets_path)
            except Exception as e:
                logging.error(f"Failed to load processed tweets: {e}")
                raise MarkdownGenerationError(f"Failed to load processed tweets: {e}")

            # Iterate through all categories and subcategories
            for main_cat in kb_root.iterdir():
                if not main_cat.is_dir() or main_cat.name.startswith('.'):
                    continue
                    
                for sub_cat in main_cat.iterdir():
                    if not sub_cat.is_dir() or sub_cat.name.startswith('.'):
                        continue
                        
                    # Process each knowledge base item
                    for item_dir in sub_cat.iterdir():
                        if not item_dir.is_dir() or item_dir.name.startswith('.'):
                            continue
                            
                        try:
                            # Find corresponding tweet data from processed_tweets.json
                            item_name = item_dir.name
                            tweet_data = next(
                                (tweet for tweet in processed_tweets 
                                 if safe_directory_name(tweet.get('item_name', '')) == item_name),
                                None
                            )
                            
                            if not tweet_data:
                                logging.warning(f"No processed tweet data found for {item_name}")
                                continue

                            # Get media files and descriptions
                            media_files = sorted(
                                [f for f in item_dir.glob("image_*.jpg")],
                                key=lambda x: int(x.stem.split('_')[1])
                            )
                            media_descriptions = tweet_data.get('image_descriptions', [])
                            
                            # Create knowledge base item from tweet data
                            kb_item = {
                                'title': tweet_data.get('item_name', ''),
                                'description': tweet_data.get('description', ''),
                                'content': tweet_data.get('tweet_text', ''),
                                'source_tweet': {
                                    'url': tweet_data.get('tweet_url', ''),
                                    'author': tweet_data.get('author', ''),
                                    'created_at': datetime.datetime.fromisoformat(
                                        tweet_data.get('created_at', datetime.datetime.now().isoformat())
                                    )
                                }
                            }
                            
                            # Generate content using existing method
                            content = self._generate_content(
                                item=kb_item,
                                media_files=media_files,
                                media_descriptions=media_descriptions
                            )
                            
                            # Write README.md
                            readme_path = item_dir / "README.md"
                            await async_write_text(content, readme_path)
                            
                        except Exception as e:
                            logging.error(f"Failed to generate README for {item_dir}: {e}")
                            continue
                            
            logging.info("Successfully generated README files for knowledge base items")
            
        except Exception as e:
            logging.error(f"Failed to generate READMEs: {str(e)}")
            raise MarkdownGenerationError(f"Failed to generate READMEs: {str(e)}")

async def write_markdown_content(
    content_dir: Path,
    main_category: str,
    sub_category: str,
    item_name: str,
    tweet_text: str,
    tweet_url: str,
    image_files: List[Path],
    image_descriptions: List[str]
) -> None:
    """Write markdown content for a knowledge base item."""
    try:
        # Ensure directory exists
        content_dir.mkdir(parents=True, exist_ok=True)
        
        # Create content.md
        content_file = content_dir / "content.md"
        
        # Build markdown content
        content = [
            f"# {item_name}\n",
            f"\n## Source\n",
            f"[Original Tweet]({tweet_url})\n",
            f"\n## Content\n",
            f"{tweet_text}\n"
        ]
        
        # Add images section if there are images
        if image_files:
            content.append("\n## Images\n")
            for i, (img_file, description) in enumerate(zip(image_files, image_descriptions)):
                rel_path = img_file.relative_to(content_dir)
                content.append(f"\n![{description}]({rel_path})\n")
                if description:
                    content.append(f"\n*{description}*\n")
        
        # Write content
        async with aiofiles.open(content_file, 'w', encoding='utf-8') as f:
            await f.write(''.join(content))
            
        logging.info(f"Created markdown content at {content_file}")
        
    except Exception as e:
        logging.error(f"Failed to write markdown content: {e}")
        raise MarkdownGenerationError(f"Failed to write markdown content: {e}")

async def generate_root_readme(kb_dir: Path, category_manager: CategoryManager) -> None:
    """Generate root README.md with category structure."""
    try:
        content = [
            "# Knowledge Base\n",
            "\nAutomatically generated knowledge base from curated tweets.\n",
            "\n## Categories\n"
        ]
        
        # Add category structure
        for main_cat, details in category_manager.categories.items():
            content.append(f"\n### {main_cat}\n")
            if 'description' in details:
                content.append(f"\n{details['description']}\n")
            if 'subcategories' in details:
                for sub_cat in sorted(details['subcategories']):
                    content.append(f"\n- {sub_cat}\n")
        
        # Write README
        readme_path = kb_dir / "README.md"
        async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
            await f.write(''.join(content))
            
        logging.info("Generated root README.md")
        
    except Exception as e:
        logging.error(f"Failed to generate root README: {e}")
        raise MarkdownGenerationError(f"Failed to generate root README: {e}")
