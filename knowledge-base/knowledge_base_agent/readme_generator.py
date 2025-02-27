from pathlib import Path
from typing import Dict, Any, List
import logging
import aiofiles
import re
from datetime import datetime
from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.exceptions import MarkdownGenerationError
from knowledge_base_agent.config import Config
import json
import os
import shutil

async def generate_root_readme(kb_dir: Path, category_manager: CategoryManager, http_client: HTTPClient, config: Config) -> None:
    """Generate an intelligent root README.md using an LLM based on knowledge base content."""
    try:
        # Get valid paths from cache
        kb_items = []
        
        if config.tweet_cache_file.exists():
            async with aiofiles.open(config.tweet_cache_file, 'r', encoding='utf-8') as f:
                tweet_cache = json.loads(await f.read())
            
            # Debug the kb_dir
            logging.info(f"Knowledge base directory: {kb_dir}")
            
            # First, let's list some files in the kb_dir to verify it exists and has content
            if kb_dir.exists():
                logging.info(f"KB directory exists. Listing first 5 items:")
                for i, (root, dirs, files) in enumerate(os.walk(kb_dir)):
                    if i >= 5:
                        break
                    logging.info(f"Directory: {root}")
                    for file in files[:3]:  # List up to 3 files per directory
                        logging.info(f"  - File: {file}")
            else:
                logging.error(f"KB directory does not exist: {kb_dir}")
            
            # Process each tweet to find KB items
            for tweet_id, tweet_data in tweet_cache.items():
                if not tweet_data.get('kb_item_created', False):
                    continue
                    
                kb_path_str = tweet_data.get('kb_item_path')
                if not kb_path_str:
                    continue
                
                # Try multiple path variations to find the actual file
                kb_path = Path(kb_path_str)
                
                # List of possible paths to check
                paths_to_check = [
                    kb_dir / kb_path,  # Direct path
                    kb_dir / kb_path.relative_to('kb-generated') if kb_path_str.startswith('kb-generated/') else kb_dir / kb_path,
                    kb_dir.parent / kb_path,  # Try from parent directory
                    Path(kb_path_str)  # Try absolute path
                ]
                
                # Check if any of the paths exist
                readme_path = None
                for path in paths_to_check:
                    logging.debug(f"Checking path: {path}")
                    if path.exists() and path.is_file():
                        readme_path = path
                        logging.debug(f"Found KB item at: {readme_path}")
                        break
                    elif path.is_dir() and (path / "README.md").exists():
                        readme_path = path / "README.md"
                        logging.debug(f"Found KB item as README.md in directory: {readme_path}")
                        break
                
                if not readme_path:
                    # Try one more approach - check if removing README.md from the path works
                    if kb_path_str.endswith('/README.md') or kb_path_str.endswith('\\README.md'):
                        dir_path = kb_dir / kb_path.parent
                        if dir_path.exists() and dir_path.is_dir():
                            readme_path = dir_path / "README.md"
                            if readme_path.exists():
                                logging.debug(f"Found KB item by checking directory: {readme_path}")
                
                if not readme_path:
                    logging.warning(f"KB item path {kb_path_str} does not exist")
                    continue
                
                # Extract path components for categorization
                try:
                    rel_path = readme_path.relative_to(kb_dir)
                    path_parts = list(rel_path.parts)
                    
                    if len(path_parts) < 2:  # Need at least main_category/item_name
                        logging.warning(f"Invalid path structure for {kb_path_str}: {path_parts}")
                        continue
                    
                    # Parse path components
                    main_cat = path_parts[0]
                    if len(path_parts) >= 3:
                        sub_cat = path_parts[1]
                        item_name = path_parts[-2] if path_parts[-1] == "README.md" else path_parts[-1].replace('.md', '')
                        # Use directory path for linking
                        item_path = str(rel_path.parent if rel_path.name == "README.md" else rel_path.with_suffix(''))
                    elif len(path_parts) == 2:
                        sub_cat = main_cat
                        item_name = path_parts[1].replace('.md', '')
                        item_path = str(rel_path.parent if rel_path.name == "README.md" else rel_path.with_suffix(''))
                    else:
                        continue
                    
                    logging.debug(f"Found item: {readme_path} -> {item_path}")
                    
                    kb_items.append({
                        'main_category': main_cat,
                        'sub_category': sub_cat,
                        'item_name': item_name,
                        'path': item_path,
                        'description': await get_item_description(readme_path),
                        'last_updated': readme_path.stat().st_mtime,
                        'tweet_id': tweet_id,
                        'created_date': tweet_data.get('processed_date'),
                        'source_url': f"https://twitter.com/user/status/{tweet_id}"
                    })
                except Exception as e:
                    logging.error(f"Error processing KB item {kb_path_str}: {e}")
                    continue

        logging.info(f"Validated KB items: {len(kb_items)} (from cache: {len([t for t in tweet_cache.values() if t.get('kb_item_created', False)])})")
        
        # Calculate stats
        total_items = len(kb_items)
        total_main_cats = len(set(item['main_category'] for item in kb_items))
        total_subcats = len(set(f"{item['main_category']}/{item['sub_category']}" for item in kb_items))
        total_media = sum(1 for root, _, files in os.walk(kb_dir)
                         for file in files if file.startswith('image_') or file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')))

        logging.info(f"Collected {total_items} items, {total_main_cats} main categories, {total_subcats} subcategories")

        # Debug logging for first few items
        logging.info("First 5 KB items paths:")
        for item in kb_items[:5]:
            logging.info(f"- {item['path']}")

        # Prepare context for LLM
        context = [
            f"Total Items: {total_items}",
            f"Main Categories: {total_main_cats}",
            f"Subcategories: {total_subcats}",
            f"Media Files: {total_media}",
            "Knowledge Base Items:"
        ]
        
        # Sort items for consistent output
        sorted_items = sorted(kb_items, key=lambda x: (x['main_category'], x['sub_category'], x['item_name']))
        
        for item in sorted_items:
            context.append(
                f"- {item['item_name'].replace('-', ' ').title()} "
                f"({item['main_category']}/{item['sub_category']}): {item['description']} "
                f"[Source: {item.get('source_url', 'N/A')}]"
            )

        prompt = (
            "Generate a polished root README.md for a technical knowledge base using this data:\n\n"
            f"{'\n'.join(context)}\n\n"
            "Include:\n"
            "1. A welcoming introduction with an emoji (📚) and a brief description\n"
            "2. An overview section (📊) with stats (total items, categories, subcategories, media files)\n"
            "3. A quick navigation section (🧭) with ALL categories and subcategories nested under main categories\n"
            "4. A recent updates section (🔔) as a table with the 5 most recently updated items, including links and source URLs\n"
            "5. A detailed categories section (📋) with collapsible subcategories (<details><summary>) listing ALL items in tables with ONLY two columns: Item and Description (no Source column)\n"
            "6. A footer (🌟) encouraging exploration\n"
            "Format in Markdown with:\n"
            "- Emojis in headers (e.g., ## 📊 Overview)\n"
            "- Horizontal rules (---) between major sections\n"
            "- Bold table headers with separators (e.g., | **Item** | **Description** |)\n"
            "- Anchor tags (e.g., <a name=\"category\"></a>) matching navigation links\n"
            "- All links to items should point to the item directory, not README.md (e.g., path/to/item/)\n"
            "Ensure it's concise, professional, readable, and includes EVERY SINGLE ITEM and category without truncation or omission."
        )

        # Generate with LLM only
        content = await http_client.ollama_generate(
            model=config.text_model,
            prompt=prompt,
            temperature=0.7
        )
        
        if not content:
            raise MarkdownGenerationError("LLM returned empty content")
            
        logging.info(f"LLM generated content length: {len(content.strip())} characters")
        
        # Validate LLM output contains all items
        all_items_included = True
        for item in kb_items:
            item_name = item['item_name'].replace('-', ' ').title()
            if item_name not in content:
                logging.warning(f"Item missing from LLM output: {item_name}")
                all_items_included = False
                break
                
        if not content or len(content.strip()) < 500 or not all_items_included:
            logging.warning("LLM generated insufficient or incomplete content; falling back to static generation")
            content = await generate_static_root_readme(kb_dir, category_manager)
        else:
            logging.info("Using LLM-generated README content")

        # Write README
        readme_path = kb_dir / "README.md"
        async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        logging.info("Generated intelligent root README.md with LLM")

        # Verify the README
        if not verify_readme_links(content, kb_dir):
            logging.warning("README contains invalid links")

        logging.info(f"Raw count of README.md files: {len(kb_items)}")
        
        # Verify against tweet cache
        if config.tweet_cache_file.exists():
            async with aiofiles.open(config.tweet_cache_file, 'r', encoding='utf-8') as f:
                tweet_cache = json.loads(await f.read())
            valid_entries = sum(1 for t in tweet_cache.values() if t.get('kb_item_created', False))
            logging.info(f"Tweet cache entries with KB paths: {valid_entries}/{len(tweet_cache)}")

    except Exception as e:
        logging.error(f"Failed to generate root README: {e}")
        raise MarkdownGenerationError(f"Failed to generate root README: {e}")

async def generate_static_root_readme(kb_dir: Path, category_manager: CategoryManager) -> str:
    """Fallback method to generate a static root README.md with enhanced styling."""
    # Find all KB items by walking the directory
    kb_items = []
    
    # First, try to find all README.md files
    for root, dirs, files in os.walk(kb_dir):
        root_path = Path(root)
        
        # Skip hidden directories and files
        if any(part.startswith('.') for part in root_path.parts):
            continue
            
        # Skip the root directory's README
        if root_path == kb_dir:
            continue
            
        for file in files:
            if file.lower() == "readme.md":
                readme_path = root_path / file
                
                # Get relative path from KB dir
                rel_path = readme_path.relative_to(kb_dir)
                path_parts = list(rel_path.parts)
                
                if len(path_parts) < 2:  # Need at least main_category/item_name
                    continue
                    
                # Parse path components
                main_cat = path_parts[0]
                
                # Handle different directory structures
                if len(path_parts) >= 3:  # main_cat/sub_cat/item/README.md
                    sub_cat = path_parts[1]
                    item_name = path_parts[-2]  # Use directory name as item name
                    item_path = str(rel_path.parent)  # Link to directory
                elif len(path_parts) == 2:  # main_cat/README.md
                    sub_cat = main_cat
                    item_name = path_parts[0]  # Use main category as item name
                    item_path = str(rel_path.parent)  # Link to directory
                else:
                    continue
                
                logging.debug(f"Found README: {readme_path} -> {item_path}")
                
                kb_items.append({
                    'main_category': main_cat,
                    'sub_category': sub_cat,
                    'item_name': item_name,
                    'path': item_path,
                    'description': await get_item_description(readme_path),
                    'last_updated': readme_path.stat().st_mtime
                })
    
    # If we didn't find any README.md files, look for .md files
    if not kb_items:
        for root, dirs, files in os.walk(kb_dir):
            root_path = Path(root)
            
            # Skip hidden directories and files
            if any(part.startswith('.') for part in root_path.parts):
                continue
                
            for file in files:
                if file.lower().endswith('.md') and file.lower() != "readme.md":
                    md_path = root_path / file
                    
                    # Get relative path from KB dir
                    rel_path = md_path.relative_to(kb_dir)
                    path_parts = list(rel_path.parts)
                    
                    if len(path_parts) < 2:  # Skip root level .md files
                        continue
                        
                    # Parse path components
                    main_cat = path_parts[0]
                    
                    if len(path_parts) >= 3:  # main_cat/sub_cat/item.md
                        sub_cat = path_parts[1]
                        item_name = path_parts[-1].replace('.md', '')
                        item_path = str(rel_path.with_suffix(''))  # Link without .md extension
                    elif len(path_parts) == 2:  # main_cat/item.md
                        sub_cat = main_cat
                        item_name = path_parts[1].replace('.md', '')
                        item_path = str(rel_path.with_suffix(''))  # Link without .md extension
                    else:
                        continue
                    
                    logging.debug(f"Found MD file: {md_path} -> {item_path}")
                    
                    kb_items.append({
                        'main_category': main_cat,
                        'sub_category': sub_cat,
                        'item_name': item_name,
                        'path': item_path,
                        'description': await get_item_description(md_path),
                        'last_updated': md_path.stat().st_mtime
                    })
    
    logging.info(f"Found {len(kb_items)} KB items")
    
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
    total_subcats = len(set(f"{item['main_category']}/{item['sub_category']}" for item in kb_items))
    total_media = sum(1 for root, _, files in os.walk(kb_dir)
                     for file in files if file.startswith('image_') or file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')))

    content = [
        "# 📚 Technical Knowledge Base",
        "Welcome to our curated technical knowledge base! Dive into a rich collection of articles, guides, and resources organized for easy exploration.\n",
        "---",
        "## 📊 Overview",
        f"- **Total Items**: {total_items}",
        f"- **Main Categories**: {total_main_cats}",
        f"- **Subcategories**: {total_subcats}",
        f"- **Media Files**: {total_media}",
        f"- **Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "---",
        "## 🧭 Quick Navigation"
    ]

    for main_cat in sorted(categories.keys()):
        main_display = main_cat.replace('_', ' ').title()
        anchor = main_cat.lower().replace('_', '-')
        content.append(f"- **[{main_display}](#{anchor})**")
        for sub_cat in sorted(categories[main_cat]['subcategories'].keys()):
            sub_display = sub_cat.replace('_', ' ').title()
            sub_anchor = f"{anchor}-{sub_cat.lower().replace('_', '-')}"
            content.append(f"  - [{sub_display}](#{sub_anchor})")

    recent_items = sorted(kb_items, key=lambda x: x['last_updated'], reverse=True)[:5]
    if recent_items:
        content.extend([
            "\n---",
            "## 🔔 Recent Updates",
            "| **Item** | **Category** | **Last Updated** | **Source** |",
            "|----------|--------------|------------------|------------|"
        ])
        for item in recent_items:
            name = item['item_name'].replace('-', ' ').title()
            path = f"{item['path']}"
            cat = f"{item['main_category'].title()}/{item['sub_category'].title()}"
            updated = datetime.fromtimestamp(item['last_updated']).strftime('%Y-%m-%d')
            source = item.get('source_url', 'N/A')
            content.append(f"| [{name}]({path}) | {cat} | {updated} | [{source}]({source}) |")

    content.extend([
        "\n---",
        "## 📋 Categories"
    ])
    for main_cat in sorted(categories.keys()):
        main_display = main_cat.replace('_', ' ').title()
        anchor = main_cat.lower().replace('_', '-')
        active_subcats = sorted(categories[main_cat]['subcategories'].keys())
        total_cat_items = sum(len(items) for items in categories[main_cat]['subcategories'].values())
        
        content.extend([
            f"\n### {main_display} <a name=\"{anchor}\"></a>",
            f"*Subcategories: {', '.join(sub.replace('_', ' ') for sub in active_subcats)}*",
            f"*Items: {total_cat_items}*\n"
        ])

        for sub_cat in active_subcats:
            sub_display = sub_cat.replace('_', ' ').title()
            sub_anchor = f"{anchor}-{sub_cat.lower().replace('_', '-')}"
            content.extend([
                f"<details><summary>{sub_display}</summary>\n\n#### {sub_display} <a name=\"{sub_anchor}\"></a>",
                "\n| **Item** | **Description** |",
                "|----------|-----------------|"
            ])
            for item in sorted(categories[main_cat]['subcategories'][sub_cat], key=lambda x: x['item_name']):
                name = item['item_name'].replace('-', ' ').title()
                desc = sanitize_markdown_cell(item['description'])
                path = f"{item['path']}"
                content.append(f"| [{name}]({path}) | {desc} |")
            content.append("</details>\n")

    content.extend([
        "\n---",
        "## 🌟 Explore More",
        "Discover the full depth of our knowledge base in the repository. Happy learning!\n"
    ])

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

        if len(desc) > 250:
            truncated = desc[:250].rsplit(' ', 1)[0] + "..."
            return truncated if len(truncated) > 50 else desc[:250] + "..."
        return desc if desc else "No description available"
        
    except Exception as e:
        logging.warning(f"Failed to get description from {readme_path}: {e}")
        return "Description unavailable"

def sanitize_markdown_cell(text: str) -> str:
    """Escape special characters for markdown tables."""
    if not text:
        return "No description available"
    
    # Replace newlines with spaces
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Escape markdown special characters
    text = text.replace('|', '\\|')
    text = text.replace('[', '\\[').replace(']', '\\]')
    text = text.replace('*', '\\*')
    
    # Truncate long descriptions
    if len(text) > 200:
        text = text[:197] + "..."
        
    return text.strip()

def verify_readme_completeness(readme_content: str, kb_items: list) -> bool:
    """Verify all KB items are included in the README."""
    missing_items = []
    for item in kb_items:
        item_name = item['item_name'].replace('-', ' ').title()
        if item_name not in readme_content:
            missing_items.append(item_name)
    
    if missing_items:
        logging.warning(f"Missing {len(missing_items)} items in README: {missing_items[:5]}...")
        return False
    return True

def verify_readme_links(readme_content: str, kb_dir: Path) -> bool:
    """Verify that links in the README point to existing files."""
    # Extract all markdown links
    link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    links = re.findall(link_pattern, readme_content)
    
    invalid_links = []
    for text, url in links:
        # Skip external links
        if url.startswith('http'):
            continue
            
        # Check if the link points to a file that exists
        if not (kb_dir / url).exists() and not url.startswith('#'):
            invalid_links.append(url)
    
    if invalid_links:
        logging.warning(f"Found {len(invalid_links)} invalid links in README: {invalid_links[:5]}...")
        return False
    return True

def generate_overview_section(kb_items: List[Dict[str, Any]], kb_dir: Path) -> str:
    """Generate the overview section with accurate statistics."""
    # Count unique KB items (not including media files)
    total_items = len(kb_items)
    
    # Count main categories and subcategories
    main_categories = set(item['main_category'] for item in kb_items)
    subcategories = set(f"{item['main_category']}/{item['sub_category']}" for item in kb_items)
    
    # Count media files separately (but don't include in total items)
    media_files = sum(1 for root, _, files in os.walk(kb_dir)
                     for file in files if file.startswith('image_') or file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')))
    
    # Get the current date and time
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # Generate the overview section
    overview = f"""## 📊 Overview
- **Total Items**: {total_items}
- **Main Categories**: {len(main_categories)}
- **Subcategories**: {len(subcategories)}
- **Media Files**: {media_files}
- **Last Updated**: {date_str}
"""
    return overview

def main():
    config = Config()  # Use your actual config import
    kb_dir = Path(config.knowledge_base_dir)
    cache_path = config.tweet_cache_file

    # Get valid paths from cache
    valid_paths = set()
    if cache_path.exists():
        with open(cache_path, 'r') as f:
            tweet_cache = json.load(f)
        valid_paths = {Path(t['kb_item_path']).parent for t in tweet_cache.values() if t.get('kb_item_path')}

    # Find all KB item directories
    orphan_count = 0
    for path in kb_dir.glob('*/*/*'):  # main/sub/item format
        if path.is_dir():
            if path not in valid_paths:
                print(f"Removing orphan: {path}")
                shutil.rmtree(path)
                orphan_count += 1

    print(f"Cleaned {orphan_count} orphaned KB items")

async def validate_readme_links(content: str) -> bool:
    """Check for malformed links before writing"""
    invalid_chars = ['(', ')', "'", '&']
    return all(char not in link for link in re.findall(r'\(([^)]+)', content) for char in invalid_chars)

if __name__ == "__main__":
    main()