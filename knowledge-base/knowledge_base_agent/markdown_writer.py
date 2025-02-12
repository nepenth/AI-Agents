import re
import shutil
import uuid
import datetime
import logging
from pathlib import Path
from .naming_utils import safe_directory_name
import asyncio
import aiofiles
from typing import Dict

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

def generate_root_readme(root_dir: Path, category_manager) -> None:
    """
    Generates an enhanced README.md in the root directory with:
    - Overview statistics
    - Clear hierarchical knowledge tree
    - Detailed category summaries with item descriptions
    """
    readme_path = root_dir / "README.md"
    knowledge_tree = {}
    stats = {
        'total_items': 0,
        'total_categories': 0,
        'total_subcategories': 0
    }
    
    # Build knowledge tree structure
    for main_cat in sorted(root_dir.iterdir()):
        if not main_cat.is_dir() or main_cat.name.startswith("."):
            continue
        stats['total_categories'] += 1
        knowledge_tree[main_cat.name] = {
            'description': category_manager.get_category_info(main_cat.name).description,
            'subcategories': {}
        }
        
        for sub_cat in sorted(main_cat.iterdir()):
            if not sub_cat.is_dir() or sub_cat.name.startswith("."):
                continue
            stats['total_subcategories'] += 1
            knowledge_tree[main_cat.name]['subcategories'][sub_cat.name] = []
            
            for item in sorted(sub_cat.iterdir()):
                if not item.is_dir() or item.name.startswith("."):
                    continue
                readme_md = item / "README.md"
                if readme_md.exists():
                    stats['total_items'] += 1
                    try:
                        with readme_md.open('r', encoding='utf-8') as f:
                            content = f.read()
                            title = next((line.strip('# \n') for line in content.split('\n') if line.startswith('# ')), item.name)
                            description = next((line for line in content.split('\n') if line and not line.startswith('#')), '')
                            
                            knowledge_tree[main_cat.name]['subcategories'][sub_cat.name].append({
                                'name': item.name,
                                'title': title,
                                'description': description[:200] + '...' if len(description) > 200 else description,
                                'path': readme_md.relative_to(root_dir).parent.as_posix()
                            })
                    except Exception as e:
                        logging.error(f"Error processing {readme_md}: {e}")

    # Generate README content
    lines = [
        "# Technical Knowledge Base",
        "",
        "## Overview",
        "",
        f"📚 **Total Knowledge Items:** {stats['total_items']}",
        f"📂 **Main Categories:** {stats['total_categories']}",
        f"📁 **Subcategories:** {stats['total_subcategories']}",
        "",
        "## Knowledge Tree",
        "",
    ]

    # Generate hierarchical tree view
    for main_cat, main_data in knowledge_tree.items():
        main_cat_display = main_cat.replace('_', ' ').title()
        lines.append(f"### 📚 {main_cat_display}")
        lines.append(f"_{main_data['description']}_")
        lines.append("")
        
        for sub_cat, items in main_data['subcategories'].items():
            sub_cat_display = sub_cat.replace('_', ' ').title()
            lines.append(f"#### 📁 {sub_cat_display}")
            if items:
                lines.append("")
                lines.append("| Title | Description |")
                lines.append("|-------|-------------|")
                for item in items:
                    title = sanitize_markdown_cell(item['title'])
                    desc = sanitize_markdown_cell(item['description'])
                    lines.append(f"| [`{title}`]({item['path']}) | {desc} |")
            lines.append("")

    lines.extend([
        "---",
        "",
        f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "_This README is automatically generated by the Knowledge Base Agent._"
    ])

    try:
        readme_path.write_text('\n'.join(lines), encoding='utf-8')
        logging.info(f"Generated enhanced README at {readme_path}")
    except Exception as e:
        logging.error(f"Failed to write README: {e}")

class MarkdownWriter:
    def generate_filename(self, tweet) -> str:
        """Generate a filename for the knowledge base entry"""
        # Implementation details
        pass

    def generate_content(self, tweet) -> str:
        """Generate markdown content for the knowledge base entry"""
        # Implementation details
        pass

    def generate_root_readme(self, root_dir: Path, category_manager) -> None:
        """Generate the root README.md file"""
        # Implementation as discussed in previous response
        pass
