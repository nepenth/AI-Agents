import re
import shutil
import uuid
import datetime
import logging
from pathlib import Path
from .naming_utils import safe_directory_name

def sanitize_markdown_cell(text: str) -> str:
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

def write_tweet_markdown(
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

    if tweet_folder.exists():
        unique_suffix = uuid.uuid4().hex[:6]
        safe_item_name = f"{safe_item_name}_{unique_suffix}"
        tweet_folder = root_dir / main_category / sub_category / safe_item_name

    temp_folder = tweet_folder.with_suffix('.temp')
    temp_folder.mkdir(parents=True, exist_ok=True)

    try:
        content_md = generate_tweet_markdown_content(item_name, tweet_url, tweet_text, image_descriptions)
        content_md_path = temp_folder / "content.md"
        content_md_path.write_text(content_md, encoding="utf-8")

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
    readme_path = root_dir / "README.md"
    total_items = 0
    total_categories = 0
    total_subcategories = 0
    knowledge_tree = {}

    for main_category in sorted(root_dir.iterdir()):
        if not (main_category.is_dir() and not main_category.name.startswith(".")):
            continue
        total_categories += 1
        knowledge_tree[main_category.name] = {}

        for sub_category in sorted(main_category.iterdir()):
            if not (sub_category.is_dir() and not sub_category.name.startswith(".")):
                continue
            total_subcategories += 1
            items = [item for item in sorted(sub_category.iterdir())
                     if item.is_dir() and not item.name.startswith(".")]
            knowledge_tree[main_category.name][sub_category.name] = []

            for it in items:
                content_md = it / "content.md"
                if content_md.exists():
                    total_items += 1
                    try:
                        with content_md.open('r', encoding='utf-8') as f:
                            content_lines = f.readlines()
                        title = next(
                            (line[2:].strip() for line in content_lines if line.startswith("# ")),
                            it.name
                        )
                        knowledge_tree[main_category.name][sub_category.name].append({
                            'title': title,
                            'path': content_md,
                            'item_dir': it
                        })
                    except Exception as e:
                        logging.error(f"Error reading {content_md}: {e}")

    lines = [
        "# Technical Knowledge Base",
        "",
        "## Overview",
        "",
        f"📚 **Total Knowledge Items:** {total_items}",
        f"📂 **Categories:** {total_categories}",
        f"📁 **Subcategories:** {total_subcategories}",
        "",
        "## Quick Navigation",
        "",
        "- [Knowledge Tree](#knowledge-tree)",
        "- [Detailed Contents](#detailed-contents)",
        "",
        "## Knowledge Tree",
        ""
    ]

    for main_cat, subcats in knowledge_tree.items():
        main_cat_display = main_cat.replace('_', ' ').title()
        lines.append(f"- 📂 **{main_cat_display}**")
        for sub_cat, items in subcats.items():
            sub_cat_display = sub_cat.replace('_', ' ').title()
            lines.append(f"  - 📁 {sub_cat_display}")
            for item in items:
                relative_path = item['path'].relative_to(root_dir).as_posix()
                lines.append(f"    - 📄 [{item['title']}](./{relative_path})")
        lines.append("")

    lines.extend([
        "## Detailed Contents",
        "",
        "_Each section below contains detailed descriptions and links to the knowledge base items._",
        ""
    ])

    for main_cat, subcats in knowledge_tree.items():
        main_cat_display = main_cat.replace('_', ' ').title()
        lines.append(f"### 📂 {main_cat_display}")
        lines.append("")
        cat_info = category_manager.get_category_info(main_cat) if category_manager else None
        if cat_info and cat_info.description:
            lines.append(f"_{cat_info.description}_")
            lines.append("")
        for sub_cat, items in subcats.items():
            if not items:
                continue
            sub_cat_display = sub_cat.replace('_', ' ').title()
            lines.append(f"#### 📁 {sub_cat_display}")
            lines.append("")
            lines.extend(["| Item | Description | Keywords |", "|------|-------------|----------|"])
            for item in items:
                content_md = item['path']
                try:
                    content = content_md.read_text(encoding='utf-8')
                    tweet_text = re.search(r'\*\*Tweet Text:\*\* (.*?)(?:\n\n|\Z)', content, re.DOTALL)
                    description = tweet_text.group(1).strip() if tweet_text else "No description available."
                    img_descriptions = re.findall(r'\*\*Image \d+ Description:\*\* (.*?)\n', content)
                    keywords = []
                    if img_descriptions:
                        keywords = [w.strip().lower() for w in img_descriptions[0].split() if len(w) > 3][:5]
                    relative_path = content_md.relative_to(root_dir).as_posix()
                    title_link = f"[{item['title']}](./{relative_path})"
                    desc_truncated = description[:100] + "..." if len(description) > 100 else description
                    desc_truncated = sanitize_markdown_cell(desc_truncated)
                    keyword_text = ", ".join(keywords) if keywords else "N/A"
                    lines.append(f"| {title_link} | {desc_truncated} | {keyword_text} |")
                except Exception as e:
                    lines.append(f"| {item['title']} | Error processing content | N/A |")
                    logging.error(f"Error processing {content_md}: {e}")
            lines.append("")

    lines.extend([
        "---",
        "",
        f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "_This README is automatically generated by the Knowledge Base Agent._"
    ])

    readme_content = "\n".join(lines)
    readme_path.write_text(readme_content, encoding="utf-8")
