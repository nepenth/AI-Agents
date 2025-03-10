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
from knowledge_base_agent.pages_generator import generate_github_pages

async def generate_root_readme(kb_dir: Path, category_manager: CategoryManager, http_client: HTTPClient, config: Config) -> None:
    """Generate a hybrid README.md using both static generation and LLM enhancement."""
    logging.info(f"Generating root README for knowledge base at {kb_dir}...")
    try:
        kb_items = []
        
        if config.tweet_cache_file.exists():
            async with aiofiles.open(config.tweet_cache_file, 'r', encoding='utf-8') as f:
                tweet_cache = json.loads(await f.read())
            
            logging.debug(f"Knowledge base directory: {kb_dir}")
            if kb_dir.exists():
                logging.debug("KB directory exists. Listing first 5 items:")
                for i, (root, dirs, files) in enumerate(os.walk(kb_dir)):
                    if i >= 5:
                        break
                    logging.debug(f"Directory: {root}")
                    for file in files[:3]:
                        logging.debug(f"  - File: {file}")
            else:
                logging.error(f"KB directory does not exist: {kb_dir}")
                raise MarkdownGenerationError(f"KB directory does not exist: {kb_dir}")
            
            for tweet_id, tweet_data in tweet_cache.items():
                if not tweet_data.get('kb_item_created', False):
                    logging.debug(f"Skipping tweet {tweet_id}: kb_item_created is False")
                    continue
                    
                kb_path_str = tweet_data.get('kb_item_path')
                if not kb_path_str:
                    logging.debug(f"Skipping tweet {tweet_id}: no kb_item_path")
                    continue
                
                kb_path = Path(kb_path_str)
                paths_to_check = [
                    kb_dir / kb_path,
                    kb_dir / kb_path.relative_to('kb-generated') if kb_path_str.startswith('kb-generated/') else kb_dir / kb_path,
                    kb_dir.parent / kb_path,
                    Path(kb_path_str)
                ]
                
                readme_path = None
                for path in paths_to_check:
                    logging.debug(f"Checking path for tweet {tweet_id}: {path}")
                    if path.exists() and path.is_file():
                        readme_path = path
                        logging.debug(f"Found KB item at: {readme_path}")
                        break
                    elif path.is_dir() and (path / "README.md").exists():
                        readme_path = path / "README.md"
                        logging.debug(f"Found KB item as README.md in directory: {readme_path}")
                        break
                
                if not readme_path and kb_path_str.endswith(('/README.md', '\\README.md')):
                    dir_path = kb_dir / kb_path.parent
                    if dir_path.exists() and dir_path.is_dir():
                        readme_path = dir_path / "README.md"
                        if readme_path.exists():
                            logging.debug(f"Found KB item by checking directory: {readme_path}")
                
                if not readme_path:
                    logging.warning(f"KB item path {kb_path_str} does not exist for tweet {tweet_id}")
                    continue
                
                try:
                    rel_path = readme_path.relative_to(kb_dir)
                    path_parts = list(rel_path.parts)
                    
                    if len(path_parts) < 2:
                        logging.warning(f"Invalid path structure for {kb_path_str}: {path_parts}")
                        continue
                    
                    main_cat = path_parts[0]
                    if len(path_parts) >= 3:
                        sub_cat = path_parts[1]
                        item_name = path_parts[-2] if path_parts[-1] == "README.md" else path_parts[-1].replace('.md', '')
                        item_path = str(rel_path.parent if rel_path.name == "README.md" else rel_path.with_suffix(''))
                    elif len(path_parts) == 2:
                        sub_cat = main_cat
                        item_name = path_parts[1].replace('.md', '')
                        item_path = str(rel_path.parent if rel_path.name == "README.md" else rel_path.with_suffix(''))
                    else:
                        continue
                    
                    logging.debug(f"Found item for tweet {tweet_id}: {readme_path} -> {item_path}")
                    
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
                    logging.error(f"Error processing KB item {kb_path_str} for tweet {tweet_id}: {e}")
                    continue

        logging.info(f"Validated {len(kb_items)} KB items (from cache: {len([t for t in tweet_cache.values() if t.get('kb_item_created', False)])})")
        
        # Log item names for debugging
        logging.debug("KB item names for validation:")
        for item in kb_items:
            logging.debug(f"- {item['item_name'].replace('-', ' ').title()}")
        
        total_items = len(kb_items)
        total_main_cats = len(set(item['main_category'] for item in kb_items))
        total_subcats = len(set(f"{item['main_category']}/{item['sub_category']}" for item in kb_items))
        total_media = sum(1 for root, _, files in os.walk(kb_dir)
                         for file in files if file.startswith('image_') or file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')))
        logging.debug(f"Collected {total_items} items, {total_main_cats} main categories, {total_subcats} subcategories, {total_media} media files")
        logging.debug("First 5 KB items paths:")
        for item in kb_items[:5]:
            logging.debug(f"- {item['path']}")

        # Group items by category
        categories = {}
        for item in kb_items:
            main_cat = item['main_category']
            sub_cat = item['sub_category']
            if main_cat not in categories:
                categories[main_cat] = {'subcategories': {}}
            if sub_cat not in categories[main_cat]['subcategories']:
                categories[main_cat]['subcategories'][sub_cat] = []
            categories[main_cat]['subcategories'][sub_cat].append(item)
        
        # Calculate statistics
        total_items = len(kb_items)
        total_main_cats = len(set(item['main_category'] for item in kb_items))
        total_subcats = len(set(f"{item['main_category']}/{item['sub_category']}" for item in kb_items))
        total_media = sum(1 for root, _, files in os.walk(kb_dir)
                         for file in files if file.startswith('image_') or file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')))
        
        # Generate the static structure first (reliable)
        static_content = [
            "# 📚 Technical Knowledge Base",
            "",
            "---",
            "## 📊 Overview",
            f"- **Total Items**: {total_items}",
            f"- **Main Categories**: {total_main_cats}",
            f"- **Subcategories**: {total_subcats}",
            f"- **Media Files**: {total_media}",
            f"- **Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "## 🧭 Quick Navigation"
        ]

        # Add navigation links
        for main_cat in sorted(categories.keys()):
            main_display = main_cat.replace('_', ' ').title()
            anchor = main_cat.lower().replace('_', '-')
            static_content.append(f"- **[{main_display}](#{anchor})**")
            for sub_cat in sorted(categories[main_cat]['subcategories'].keys()):
                sub_display = sub_cat.replace('_', ' ').title()
                sub_anchor = f"{anchor}-{sub_cat.lower().replace('_', '-')}"
                static_content.append(f"  - [{sub_display}](#{sub_anchor})")

        # Add recent updates section
        recent_items = sorted(kb_items, key=lambda x: x['last_updated'], reverse=True)[:5]
        if recent_items:
            static_content.extend([
                "",
                "---",
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
                static_content.append(f"| [{name}]({path}) | {cat} | {updated} | [{source}]({source}) |")

        # Now use the LLM to generate just the introduction
        intro_prompt = f"""Write a welcoming introduction for a technical knowledge base with {total_items} items across {total_main_cats} categories.
The introduction should be 2-3 paragraphs that:
1. Welcomes users to the knowledge base
2. Explains that it contains curated technical content from tweets
3. Encourages exploration of the different categories
4. Mentions that items are organized by category and subcategory

Keep it concise, professional, and engaging. Use markdown formatting.
"""
        
        try:
            intro_content = await http_client.ollama_generate(
                model=config.text_model,
                prompt=intro_prompt,
                temperature=0.7,
                max_tokens=500,
                timeout=250  # Short timeout since this is just the intro
            )
            
            # Insert the LLM-generated intro after the title
            if intro_content and len(intro_content.strip()) > 100:
                static_content[1] = intro_content.strip()
                logging.info("Added LLM-generated introduction")
            else:
                static_content[1] = "Welcome to our curated technical knowledge base! Dive into a rich collection of articles, guides, and resources organized for easy exploration."
                logging.warning("Using default introduction due to insufficient LLM output")
        except Exception as e:
            logging.warning(f"Failed to generate introduction with LLM: {e}")
            static_content[1] = "Welcome to our curated technical knowledge base! Dive into a rich collection of articles, guides, and resources organized for easy exploration."
        
        # Add categories section
        static_content.extend([
            "",
            "---",
            "## 📋 Categories"
        ])
        
        # Add each category and its items
        for main_cat in sorted(categories.keys()):
            main_display = main_cat.replace('_', ' ').title()
            anchor = main_cat.lower().replace('_', '-')
            active_subcats = sorted(categories[main_cat]['subcategories'].keys())
            total_cat_items = sum(len(items) for items in categories[main_cat]['subcategories'].values())
            
            # Try to get a category description from LLM
            try:
                cat_prompt = f"""Write a brief 1-2 sentence description for the '{main_display}' category in a technical knowledge base.
This category contains {total_cat_items} items across {len(active_subcats)} subcategories: {', '.join(sub.replace('_', ' ').title() for sub in active_subcats)}.
Keep it concise and informative."""
                
                cat_desc = await http_client.ollama_generate(
                    model=config.text_model,
                    prompt=cat_prompt,
                    temperature=0.7,
                    max_tokens=200,
                    timeout=30  # Short timeout for category descriptions
                )
                
                if cat_desc and len(cat_desc.strip()) > 20:
                    cat_description = cat_desc.strip()
                else:
                    cat_description = f"A collection of {total_cat_items} items across {len(active_subcats)} subcategories."
            except Exception as e:
                logging.warning(f"Failed to generate category description for {main_display}: {e}")
                cat_description = f"A collection of {total_cat_items} items across {len(active_subcats)} subcategories."
            
            static_content.extend([
                f"\n### {main_display} <a name=\"{anchor}\"></a>",
                f"{cat_description}",
                f"*Subcategories: {', '.join(sub.replace('_', ' ').title() for sub in active_subcats)}*",
                f"*Items: {total_cat_items}*\n"
            ])

            # Add subcategories with collapsible sections
            for sub_cat in active_subcats:
                sub_display = sub_cat.replace('_', ' ').title()
                sub_anchor = f"{anchor}-{sub_cat.lower().replace('_', '-')}"
                static_content.extend([
                    f"<details><summary>{sub_display}</summary>\n\n#### {sub_display} <a name=\"{sub_anchor}\"></a>",
                    "\n| **Item** | **Description** |",
                    "|----------|-----------------|"
                ])
                for item in sorted(categories[main_cat]['subcategories'][sub_cat], key=lambda x: x['item_name']):
                    name = item['item_name'].replace('-', ' ').title()
                    desc = sanitize_markdown_cell(item['description'])
                    path = f"{item['path']}"
                    static_content.append(f"| [{name}]({path}) | {desc} |")
                static_content.append("</details>\n")

        # Add footer
        static_content.extend([
            "",
            "---",
            "## 🌟 Explore More",
            "Discover the full depth of our knowledge base in the repository. Happy learning!",
            ""
        ])

        # Combine all sections
        final_content = "\n".join(static_content)
        
        # Write to file
        readme_path = kb_dir / "README.md"
        async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
            await f.write(final_content)
        
        logging.info("Generated hybrid root README.md")
        
        # Verify links
        if not verify_readme_links(final_content, kb_dir):
            logging.warning("README contains invalid links")
        
        # Generate GitHub Pages
        try:
            await generate_github_pages(kb_dir, http_client, config)
        except Exception as pages_error:
            logging.error(f"Failed to generate GitHub Pages: {pages_error}")
            # Continue with README generation even if Pages generation fails
            
    except Exception as e:
        logging.error(f"Failed to generate root README: {e}")
        # Fall back to fully static generation if anything fails
        try:
            content = await generate_static_root_readme(kb_dir, category_manager)
            readme_path = kb_dir / "README.md"
            async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            logging.info("Generated static README as fallback")
        except Exception as fallback_error:
            logging.error(f"Failed to generate static README: {fallback_error}")
            raise MarkdownGenerationError(f"Failed to generate any README: {e}, fallback error: {fallback_error}")

async def generate_static_root_readme(kb_dir: Path, category_manager: CategoryManager) -> str:
    """Fallback method to generate a static root README.md with enhanced styling."""
    logging.info(f"Generating static root README for {kb_dir}...")
    kb_items = []
    
    for root, dirs, files in os.walk(kb_dir):
        root_path = Path(root)
        if any(part.startswith('.') for part in root_path.parts):
            continue
        if root_path == kb_dir:
            continue
            
        for file in files:
            if file.lower() == "readme.md":
                readme_path = root_path / file
                rel_path = readme_path.relative_to(kb_dir)
                path_parts = list(rel_path.parts)
                
                if len(path_parts) < 2:
                    logging.debug(f"Skipping invalid path structure: {rel_path}")
                    continue
                    
                main_cat = path_parts[0]
                if len(path_parts) >= 3:
                    sub_cat = path_parts[1]
                    item_name = path_parts[-2]
                    item_path = str(rel_path.parent)
                elif len(path_parts) == 2:
                    sub_cat = main_cat
                    item_name = path_parts[0]
                    item_path = str(rel_path.parent)
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
    
    if not kb_items:
        for root, dirs, files in os.walk(kb_dir):
            root_path = Path(root)
            if any(part.startswith('.') for part in root_path.parts):
                continue
                
            for file in files:
                if file.lower().endswith('.md') and file.lower() != "readme.md":
                    md_path = root_path / file
                    rel_path = md_path.relative_to(kb_dir)
                    path_parts = list(rel_path.parts)
                    
                    if len(path_parts) < 2:
                        logging.debug(f"Skipping invalid path structure: {rel_path}")
                        continue
                        
                    main_cat = path_parts[0]
                    if len(path_parts) >= 3:
                        sub_cat = path_parts[1]
                        item_name = path_parts[-1].replace('.md', '')
                        item_path = str(rel_path.with_suffix(''))
                    elif len(path_parts) == 2:
                        sub_cat = main_cat
                        item_name = path_parts[1].replace('.md', '')
                        item_path = str(rel_path.with_suffix(''))
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
    
    logging.info(f"Found {len(kb_items)} KB items for static README")
    
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
    logging.debug(f"Static README stats: {total_items} items, {total_main_cats} main categories, {total_subcats} subcategories, {total_media} media files")

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
            logging.debug(f"Added recent item to static README: {name}")

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
                logging.debug(f"Added item to static README: {name}")
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
            desc = truncated if len(truncated) > 50 else desc[:250] + "..."
        logging.debug(f"Extracted description from {readme_path}: {desc[:50]}...")
        return desc if desc else "No description available"
    except Exception as e:
        logging.warning(f"Failed to get description from {readme_path}: {e}")
        return "Description unavailable"

def sanitize_markdown_cell(text: str) -> str:
    """Escape special characters for markdown tables."""
    if not text:
        logging.debug("Sanitizing empty text; returning default")
        return "No description available"
    
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = text.replace('|', '\\|')
    text = text.replace('[', '\\[').replace(']', '\\]')
    text = text.replace('*', '\\*')
    if len(text) > 200:
        text = text[:197] + "..."
    logging.debug(f"Sanitized markdown cell: {text[:50]}...")
    return text.strip()

def sanitize_link(path: str) -> str:
    """Sanitize links for README markdown."""
    if path == 'N/A':
        logging.debug("Sanitizing N/A link; returning '#'")
        return '#'
    
    sanitized = (path.lower()
                .replace('(', '')
                .replace(')', '')
                .replace(' ', '-')
                .replace(',', '')
                .strip('-'))
    logging.debug(f"Sanitized link: {path} -> {sanitized}")
    return sanitized

def verify_readme_links(content: str, kb_dir: Path) -> bool:
    """Verify that links in the README point to existing files."""
    link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    links = re.findall(link_pattern, content)
    
    invalid_links = []
    for text, url in links:
        if url.startswith(('#', 'http')):
            continue
        
        clean_url = sanitize_link(url)
        if not (kb_dir / clean_url).exists():
            invalid_links.append(url)
            logging.debug(f"Invalid link found: {url}")
    
    if invalid_links:
        logging.warning(f"Found {len(invalid_links)} invalid links in README: {invalid_links[:5]}...")
        return False
    logging.debug("All README links verified as valid")
    return True

def generate_overview_section(kb_items: List[Dict[str, Any]], kb_dir: Path) -> str:
    """Generate the overview section with accurate statistics."""
    total_items = len(kb_items)
    main_categories = set(item['main_category'] for item in kb_items)
    subcategories = set(f"{item['main_category']}/{item['sub_category']}" for item in kb_items)
    media_files = sum(1 for root, _, files in os.walk(kb_dir)
                     for file in files if file.startswith('image_') or file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')))
    
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    overview = f"""## 📊 Overview
- **Total Items**: {total_items}
- **Main Categories**: {len(main_categories)}
- **Subcategories**: {len(subcategories)}
- **Media Files**: {media_files}
- **Last Updated**: {date_str}
"""
    logging.debug(f"Generated overview section: {total_items} items, {len(main_categories)} categories")
    return overview

def main():
    """Main function for manual KB cleanup (used standalone)."""
    config = Config()
    kb_dir = Path(config.knowledge_base_dir)
    cache_path = config.tweet_cache_file

    valid_paths = set()
    if cache_path.exists():
        with open(cache_path, 'r') as f:
            tweet_cache = json.load(f)
        valid_paths = {Path(t['kb_item_path']).parent for t in tweet_cache.values() if t.get('kb_item_path')}

    orphan_count = 0
    for path in kb_dir.glob('*/*/*'):
        if path.is_dir():
            if path not in valid_paths:
                logging.info(f"Removing orphan: {path}")
                shutil.rmtree(path)
                orphan_count += 1

    logging.info(f"Cleaned {orphan_count} orphaned KB items")

async def validate_readme_links(content: str) -> bool:
    """Check for malformed links before writing."""
    invalid_chars = ['(', ')', "'", '&']
    result = all(char not in link for link in re.findall(r'\(([^)]+)', content) for char in invalid_chars)
    logging.debug(f"Validated README links: {'valid' if result else 'invalid characters found'}")
    return result

async def enhance_readme_with_complete_listing(content: str, kb_items: List[Dict[str, Any]], categories: Dict[str, Any]) -> str:
    """Enhance the LLM-generated README with a complete listing of all items."""
    # Find where to insert the complete listing
    if "## 📋 Categories" in content:
        # Split at the categories section
        parts = content.split("## 📋 Categories", 1)
        header = parts[0] + "## 📋 Categories\n\n"
        
        # Generate a complete listing of all categories and items
        listing = []
        for main_cat, data in sorted(categories.items()):
            main_display = main_cat.replace('_', ' ').title()
            anchor = main_cat.lower().replace('_', '-')
            listing.append(f"\n### {main_display} <a name=\"{anchor}\"></a>")
            
            for sub_cat, items in sorted(data['subcategories'].items()):
                sub_display = sub_cat.replace('_', ' ').title()
                sub_anchor = f"{anchor}-{sub_cat.lower().replace('_', '-')}"
                listing.append(f"\n<details><summary>{sub_display}</summary>\n\n#### {sub_display} <a name=\"{sub_anchor}\"></a>")
                listing.append("\n| **Item** | **Description** |")
                listing.append("|----------|-----------------|")
                
                for item in sorted(items, key=lambda x: x['item_name']):
                    name = item['item_name'].replace('-', ' ').title()
                    desc = sanitize_markdown_cell(item['description'])
                    path = f"{item['path']}"
                    listing.append(f"| [{name}]({path}) | {desc} |")
                
                listing.append("</details>\n")
            
        # Combine with the original content
        if len(parts) > 1 and len(parts[1].strip()) > 0:
            # The LLM already generated some category content, append our complete listing
            footer = "\n\n## 🔍 Complete Item Listing\n\n" + "\n".join(listing)
            return header + parts[1] + footer
        else:
            # The LLM didn't generate category content, use our listing
            return header + "\n".join(listing)
    else:
        # No categories section found, append to the end
        return content + "\n\n## 🔍 Complete Item Listing\n\n" + "\n".join([
            f"### {main_cat.replace('_', ' ').title()}\n" +
            "\n".join([
                f"#### {sub_cat.replace('_', ' ').title()}\n" +
                "| **Item** | **Description** |\n" +
                "|----------|------------------|\n" +
                "\n".join([
                    f"| [{item['item_name'].replace('-', ' ').title()}]({item['path']}) | {sanitize_markdown_cell(item['description'])} |"
                    for item in sorted(items, key=lambda x: x['item_name'])
                ])
                for sub_cat, items in sorted(data['subcategories'].items())
            ])
            for main_cat, data in sorted(categories.items())
        ])

if __name__ == "__main__":
    main()