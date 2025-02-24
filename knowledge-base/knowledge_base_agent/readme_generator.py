from pathlib import Path
from typing import Dict, Any
import logging
import aiofiles
import re
from datetime import datetime
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.exceptions import MarkdownGenerationError
from knowledge_base_agent.config import Config

async def generate_root_readme(kb_dir: Path, category_manager: CategoryManager, http_client: HTTPClient, config: Config) -> None:
    """Generate an intelligent root README.md using an LLM based on knowledge base content."""
    try:
        # Collect knowledge base items
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
                            'description': await get_item_description(readme_path),
                            'last_updated': readme_path.stat().st_mtime
                        })

        # Calculate basic stats
        total_items = len(kb_items)
        total_main_cats = len(set(item['main_category'] for item in kb_items))
        total_subcats = len(set(f"{item['main_category']}/{item['sub_category']}" for item in kb_items))
        total_media = sum(len(list(item_dir.glob("image_*.*"))) 
                         for main_cat in kb_dir.iterdir() if main_cat.is_dir()
                         for sub_cat in main_cat.iterdir() if sub_cat.is_dir()
                         for item_dir in sub_cat.iterdir() if item_dir.is_dir())

        # Prepare context for LLM
        context = [
            f"Total Items: {total_items}",
            f"Main Categories: {total_main_cats}",
            f"Subcategories: {total_subcats}",
            f"Media Files: {total_media}",
            "Knowledge Base Items:"
        ]
        for item in kb_items:
            context.append(
                f"- {item['item_name'].replace('-', ' ').title()} "
                f"({item['main_category']}/{item['sub_category']}): {item['description']}"
            )

        prompt = (
            "Generate a polished root README.md for a technical knowledge base using this data:\n\n"
            f"{'\n'.join(context)}\n\n"
            "Include:\n"
            "1. A welcoming introduction\n"
            "2. An overview section with stats (total items, categories, etc.)\n"
            "3. A quick navigation section with links to categories and subcategories\n"
            "4. A recent updates section highlighting the 5 most recently updated items\n"
            "5. A detailed categories section with item tables\n"
            "Format in Markdown with proper headers, links (e.g., [Item](path)), and tables."
            "Use anchor tags (e.g., <a name=\"category\"></a>) for navigation."
            "Make it concise, professional, and readable."
        )

        # Generate content with LLM
        content = await http_client.ollama_generate(
            model=config.text_model,
            prompt=prompt,
            temperature=0.7
        )

        if not content or len(content.strip()) < 100:
            logging.warning("LLM generated insufficient content; falling back to static generation")
            content = await generate_static_root_readme(kb_dir, category_manager)

        # Write README
        readme_path = kb_dir / "README.md"
        async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        logging.info("Generated intelligent root README.md with LLM")

    except Exception as e:
        logging.error(f"Failed to generate root README: {e}")
        raise MarkdownGenerationError(f"Failed to generate root README: {e}")

async def generate_static_root_readme(kb_dir: Path, category_manager: CategoryManager) -> str:
    """Fallback method to generate a static root README.md."""
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
                        'description': await get_item_description(readme_path),
                        'last_updated': readme_path.stat().st_mtime
                    })

    categories = {}
    for item in kb_items:
        main_cat = item['main_category']
        sub_cat = item['sub_category']
        if main_cat not in categories:
            categories[main_cat] = {'subcategories': {}}
        if sub_cat not in categories[main_cat]['subcategories']:
            categories[main_cat]['subcategories'][sub_cat] = []
        categories[main_cat]['subcategories'][sub_cat].append(item)

    total_items = len(kb_items)
    total_main_cats = len(categories)
    total_subcats = sum(len(subcats) for subcats in categories.values())
    total_media = sum(len(list(item_dir.glob("image_*.*"))) 
                     for main_cat in kb_dir.iterdir() if main_cat.is_dir()
                     for sub_cat in main_cat.iterdir() if sub_cat.is_dir()
                     for item_dir in sub_cat.iterdir() if item_dir.is_dir())

    content = [
        "# Technical Knowledge Base\n",
        "Welcome to our curated technical knowledge base! Explore a wealth of technical articles, guides, and resources organized by category.\n",
        "## Overview\n",
        f"- **Total Items**: {total_items}",
        f"- **Main Categories**: {total_main_cats}",
        f"- **Subcategories**: {total_subcats}",
        f"- **Media Files**: {total_media}",
        f"- **Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## Quick Navigation\n"
    ]

    for main_cat in sorted(categories.keys()):
        main_display = main_cat.replace('_', ' ').title()
        content.append(f"- [{main_display}](#{main_cat})")
        for sub_cat in sorted(categories[main_cat]['subcategories'].keys()):
            sub_display = sub_cat.replace('_', ' ').title()
            anchor = f"{main_cat}-{sub_cat}"
            content.append(f"  - [{sub_display}](#{anchor})")

    recent_items = sorted(kb_items, key=lambda x: x['last_updated'], reverse=True)[:5]
    if recent_items:
        content.extend([
            "\n## Recent Updates\n",
            "| Item | Category | Last Updated |",
            "|------|----------|--------------|"
        ])
        for item in recent_items:
            name = item['item_name'].replace('-', ' ').title()
            path = item['path']
            cat = f"{item['main_category'].title()}/{item['sub_category'].title()}"
            updated = datetime.fromtimestamp(item['last_updated']).strftime('%Y-%m-%d')
            content.append(f"| [{name}]({path}) | {cat} | {updated} |")

    content.append("\n## Categories\n")
    for main_cat in sorted(categories.keys()):
        cat_data = categories[main_cat]
        main_display = main_cat.replace('_', ' ').title()
        active_subcats = sorted(cat_data['subcategories'].keys())
        active_subcat_display = ', '.join(sub.replace('_', ' ') for sub in active_subcats)
        total_cat_items = sum(len(items) for items in cat_data['subcategories'].values())

        content.extend([
            f"\n### {main_display} <a name=\"{main_cat}\"></a>\n",
            f"*Subcategories with content: {active_subcat_display}*",
            f"*Items: {total_cat_items}*\n"
        ])

        for sub_cat in active_subcats:
            items = cat_data['subcategories'][sub_cat]
            sub_display = sub_cat.replace('_', ' ').title()
            anchor = f"{main_cat}-{sub_cat}"
            content.extend([
                f"\n#### {sub_display} <a name=\"{anchor}\"></a>\n",
                "| Item | Description |",
                "|------|-------------|"
            ])
            for item in sorted(items, key=lambda x: x['item_name']):
                name = item['item_name'].replace('-', ' ').title()
                desc = sanitize_markdown_cell(item['description'])
                path = item['path']
                content.append(f"| [{name}]({path}) | {desc} |")

    return '\n'.join(content)

async def get_item_description(readme_path: Path) -> str:
    """Extract a polished description from a knowledge base item's README."""
    try:
        async with aiofiles.open(readme_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        desc_match = re.search(r'^## Description\s*\n(.*?)(?=\n#|$)', content, re.MULTILINE | re.DOTALL)
        if desc_match:
            desc = desc_match.group(1).strip()
        else:
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            desc = paragraphs[1] if len(paragraphs) > 1 else paragraphs[0] if paragraphs else ""

        if len(desc) > 200:
            truncated = desc[:200].rsplit(' ', 1)[0] + "..."
            return truncated if len(truncated) > 50 else desc[:200] + "..."
        return desc if desc else "No description available"
        
    except Exception as e:
        logging.warning(f"Failed to get description from {readme_path}: {e}")
        return "Description unavailable"

def sanitize_markdown_cell(text: str) -> str:
    """Escape vertical bars for markdown tables."""
    return text.replace('|', '&#124;').strip()