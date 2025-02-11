import re
import shutil
import uuid
import datetime
import logging
from pathlib import Path
from .naming_utils import safe_directory_name
import asyncio
import aiofiles

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
    Generates a README.md in the root of the knowledge base directory that contains:
      - An Overview with total counts.
      - A Knowledge Tree section with a bullet list of items (with links).
      - A Detailed Contents section with tables listing each item.
    """
    readme_path = root_dir / "README.md"
    total_items = 0
    total_categories = 0
    total_subcategories = 0
    knowledge_tree = {}  # { main_category: { sub_category: [ {title, rel_path, description} ] } }

    # Traverse main categories (skip hidden directories)
    for main_cat in sorted(root_dir.iterdir()):
        if not main_cat.is_dir() or main_cat.name.startswith("."):
            continue
        total_categories += 1
        knowledge_tree[main_cat.name] = {}
        # Traverse subcategories
        for sub_cat in sorted(main_cat.iterdir()):
            if not sub_cat.is_dir() or sub_cat.name.startswith("."):
                continue
            total_subcategories += 1
            items = [item for item in sorted(sub_cat.iterdir()) if item.is_dir() and not item.name.startswith(".")]
            knowledge_tree[main_cat.name][sub_cat.name] = []
            for item in items:
                content_md = item / "content.md"
                if content_md.exists():
                    total_items += 1
                    try:
                        with content_md.open('r', encoding='utf-8') as f:
                            lines = f.readlines()
                        title = None
                        description = ""
                        # Extract the title: first header line that starts with "# "
                        for line in lines:
                            if line.startswith("# "):
                                title = line.strip()[2:]
                                break
                        if not title:
                            title = item.name
                        # Extract a description: first non-header, non-empty line.
                        for line in lines:
                            if line.strip() and not line.startswith("#"):
                                description = line.strip()
                                break
                        knowledge_tree[main_cat.name][sub_cat.name].append({
                            "title": title,
                            "rel_path": content_md.relative_to(root_dir).as_posix(),
                            "description": description
                        })
                    except Exception as e:
                        logging.error(f"Error processing {content_md}: {e}")
                else:
                    logging.warning(f"Missing content.md in {item}")

    # Start generating README content.
    lines = []
    lines.append("# Technical Knowledge Base")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- **Total Knowledge Items:** {total_items}")
    lines.append(f"- **Categories:** {total_categories}")
    lines.append(f"- **Subcategories:** {total_subcategories}")
    lines.append("")
    lines.append("## Knowledge Tree")
    lines.append("")
    for main_cat, subcats in knowledge_tree.items():
        main_cat_display = main_cat.replace('_', ' ').title()
        lines.append(f"- **{main_cat_display}**")
        for sub_cat, items in subcats.items():
            sub_cat_display = sub_cat.replace('_', ' ').title()
            lines.append(f"  - **{sub_cat_display}**")
            for item in items:
                # Create a markdown link with title and relative path
                lines.append(f"    - [{item['title']}](./{item['rel_path']}) - {item['description']}")
        lines.append("")
    lines.append("## Detailed Contents")
    lines.append("")
    for main_cat, subcats in knowledge_tree.items():
        main_cat_display = main_cat.replace('_', ' ').title()
        lines.append(f"### {main_cat_display}")
        for sub_cat, items in subcats.items():
            sub_cat_display = sub_cat.replace('_', ' ').title()
            lines.append(f"#### {sub_cat_display}")
            lines.append("")
            lines.append("| Item | Description |")
            lines.append("| --- | --- |")
            for item in items:
                title = sanitize_markdown_cell(item['title'])
                description = sanitize_markdown_cell(item['description'])
                rel_path = item['rel_path']
                lines.append(f"| [{title}](./{rel_path}) | {description} |")
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("_This README is automatically generated by the Knowledge Base Agent._")

    readme_content = "\n".join(lines)
    try:
        readme_path.write_text(readme_content, encoding="utf-8")
        logging.info(f"Generated README at {readme_path}")
    except Exception as e:
        logging.error(f"Failed to write README: {e}")
