from datetime import datetime
import re
import shutil
import uuid
import logging
from pathlib import Path
from .naming_utils import safe_directory_name
import asyncio
import aiofiles
from typing import Dict, List, Optional, Any

from knowledge_base_agent.exceptions import StorageError
from knowledge_base_agent.config import Config
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.exceptions import KnowledgeBaseError, MarkdownGenerationError
from knowledge_base_agent.file_utils import async_json_load, async_write_text
from knowledge_base_agent.path_utils import PathNormalizer, DirectoryManager, create_kb_path
from knowledge_base_agent.types import KnowledgeBaseItem, CategoryInfo

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

class MarkdownWriter:
    """Handles writing content to markdown files in the knowledge base."""

    def __init__(self, config: Config):
        self.config = config
        self.path_normalizer = PathNormalizer()
        self.dir_manager = DirectoryManager()

    async def write_tweet_markdown(
        self,
        root_dir: Path,
        tweet_id: str,
        tweet_data: Dict[str, Any],
        image_files: list,
        image_descriptions: list,
        main_category: str = None,
        sub_category: str = None,
        item_name: str = None,
        tweet_text: str = None,
        tweet_url: str = None
    ):
        """Write tweet markdown using cached tweet data."""
        # Get categories from tweet data
        categories = tweet_data.get('categories')
        if not categories:
            raise MarkdownGenerationError(f"No category data found for tweet {tweet_id}")
            
        # Use provided values or fall back to tweet_data
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

    async def write_kb_item(
        self,
        item: KnowledgeBaseItem,
        media_files: List[Path] = None,
        media_descriptions: List[str] = None,
        root_dir: Path = None
    ) -> None:
        """Write knowledge base item to markdown with media."""
        try:
            # Create KB path using existing utility
            kb_path = create_kb_path(
                item.category_info.main_category,
                item.category_info.sub_category,
                item.title
            )
            if root_dir:
                kb_path = root_dir / kb_path

            # Create temp directory for atomic operations
            temp_dir = kb_path.with_suffix('.temp')
            temp_dir.mkdir(parents=True, exist_ok=True)

            try:
                # Generate content using existing method
                content = self._generate_content(
                    item=item,
                    media_files=media_files,
                    media_descriptions=media_descriptions
                )

                # Write markdown file
                readme_path = temp_dir / "README.md"
                async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
                    await f.write(content)

                # Copy media files if they exist
                if media_files:
                    await self._copy_media_files(media_files, temp_dir)

                # Atomic directory rename
                if kb_path.exists():
                    shutil.rmtree(kb_path)
                temp_dir.rename(kb_path)

                return str(kb_path / "README.md")

            except Exception as e:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                raise

        except Exception as e:
            logging.error(f"Failed to write KB item: {e}")
            raise MarkdownGenerationError(f"Failed to write KB item: {e}")

    def _generate_content(
        self,
        item: KnowledgeBaseItem,
        media_files: List[Path] = None,
        media_descriptions: List[str] = None
    ) -> str:
        """Generate markdown content with proper formatting."""
        # The content is already in markdown format from the LLM
        content = item.content

        # Add source information
        source_section = [
            "\n## Source\n",
            f"- Original Tweet: [{item.source_tweet['url']}]({item.source_tweet['url']})",
            f"- Date: {item.source_tweet['created_at'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        ]
        
        # Add media section if present
        media_section = []
        if media_files and media_descriptions:
            media_section.append("\n## Media\n")
            for idx, (media, desc) in enumerate(zip(media_files, media_descriptions), 1):
                media_section.extend([
                    f"### Media {idx}",
                    f"![{media.stem}](./{media.name})",
                    f"**Description:** {desc}\n"
                ])
        
        # Add last updated timestamp
        timestamp = f"\n*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        
        # Combine all sections
        return content + '\n'.join(source_section + media_section) + timestamp

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
    """Generate comprehensive root README.md with knowledge base structure."""
    try:
        # Get all knowledge base items
        kb_items = []
        for main_cat in kb_dir.iterdir():
            if not main_cat.is_dir() or main_cat.name.startswith('.'):
                continue
                
            for sub_cat in main_cat.iterdir():
                if not sub_cat.is_dir() or sub_cat.name.startswith('.'):
                    continue
                    
                for item_dir in sub_cat.iterdir():
                    if not item_dir.is_dir() or item_dir.name.startswith('.'):
                        continue
                    
                    readme_path = item_dir / "README.md"
                    if readme_path.exists():
                        kb_items.append({
                            'main_category': main_cat.name,
                            'sub_category': sub_cat.name,
                            'item_name': item_dir.name,
                            'path': readme_path.relative_to(kb_dir),
                            'description': await get_item_description(readme_path)
                        })

        # Organize items by category
        categories = {}
        for item in kb_items:
            main_cat = item['main_category']
            sub_cat = item['sub_category']
            
            if main_cat not in categories:
                categories[main_cat] = {'description': category_manager.get_category_description(main_cat), 'subcategories': {}}
            
            if sub_cat not in categories[main_cat]['subcategories']:
                categories[main_cat]['subcategories'][sub_cat] = []
                
            categories[main_cat]['subcategories'][sub_cat].append(item)

        # Generate markdown content
        content = [
            "# Technical Knowledge Base\n",
            "Welcome to our curated technical knowledge base! This repository contains a collection of technical articles, guides, and resources organized by category.\n",
            f"\n## Overview\n",
            f"- Total Knowledge Base Items: {len(kb_items)}",
            f"- Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Categories: {len(categories)}",
            f"- Subcategories: {sum(len(cat['subcategories']) for cat in categories.values())}\n",
            "\n## Quick Links\n"
        ]

        # Add table of contents
        for main_cat in sorted(categories.keys()):
            content.append(f"- [{main_cat.replace('_', ' ').title()}](#{main_cat})")
            for sub_cat in sorted(categories[main_cat]['subcategories'].keys()):
                content.append(f"  - [{sub_cat.replace('_', ' ').title()}](#{main_cat}-{sub_cat})")

        # Add detailed category sections
        content.append("\n## Categories\n")
        for main_cat in sorted(categories.keys()):
            cat_data = categories[main_cat]
            content.extend([
                f"\n### {main_cat.replace('_', ' ').title()} {{{main_cat}}}\n",
                f"{cat_data['description']}\n" if cat_data['description'] else "",
                f"*Number of items: {sum(len(items) for items in cat_data['subcategories'].values())}*\n"
            ])

            # Add subcategories
            for sub_cat in sorted(cat_data['subcategories'].keys()):
                items = cat_data['subcategories'][sub_cat]
                content.extend([
                    f"\n#### {sub_cat.replace('_', ' ').title()} {{{main_cat}-{sub_cat}}}\n",
                    "*Items in this category:*\n"
                ])

                # Add items table
                content.extend([
                    "| Item | Description |",
                    "|------|-------------|"
                ])
                
                for item in sorted(items, key=lambda x: x['item_name']):
                    name = item['item_name'].replace('-', ' ').title()
                    desc = item['description'].replace('\n', ' ').strip()
                    path = item['path']
                    content.append(f"| [{name}]({path}) | {desc} |")
                content.append("")

        # Write README
        readme_path = kb_dir / "README.md"
        async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
            await f.write('\n'.join(content))
            
        logging.info("Generated comprehensive root README.md")
        
    except Exception as e:
        logging.error(f"Failed to generate root README: {e}")
        raise MarkdownGenerationError(f"Failed to generate root README: {e}")

async def get_item_description(readme_path: Path) -> str:
    """Extract description from a knowledge base item's README."""
    try:
        async with aiofiles.open(readme_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            
        # Look for description section
        desc_match = re.search(r'^## Description\s*\n(.*?)(?=\n#|$)', content, re.MULTILINE | re.DOTALL)
        if desc_match:
            return desc_match.group(1).strip()[:200] + "..."  # Truncate long descriptions
        
        # Fallback to first non-empty paragraph after title
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        if len(paragraphs) > 1:
            return paragraphs[1][:200] + "..."
            
        return "No description available"
        
    except Exception as e:
        logging.warning(f"Failed to get description from {readme_path}: {e}")
        return "Description unavailable"
