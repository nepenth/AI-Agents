from pathlib import Path
from typing import Dict, Any, List
import logging
import aiofiles
import yaml
from datetime import datetime
import shutil
import os
import json

from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.config import Config
from knowledge_base_agent.exceptions import PagesGenerationError

async def generate_github_pages(kb_dir: Path, http_client: HTTPClient, config: Config) -> None:
    """Generate GitHub Pages for the knowledge base."""
    logging.info(f"Generating GitHub Pages for knowledge base at {kb_dir}...")
    try:
        # Create necessary directories - use 'docs' folder for GitHub Pages
        docs_dir = kb_dir / "docs"
        docs_dir.mkdir(exist_ok=True)
        
        # Load tweet cache to get KB items
        kb_items = []
        if config.tweet_cache_file.exists():
            async with aiofiles.open(config.tweet_cache_file, 'r', encoding='utf-8') as f:
                tweet_cache = json.loads(await f.read())
            
            # Process tweet cache to get KB items
            kb_items = await collect_kb_items(kb_dir, tweet_cache)
        
        if not kb_items:
            logging.warning("No KB items found for GitHub Pages generation")
            return
            
        # Organize items by category
        categories = organize_by_category(kb_items)
        
        # Skip workflow file generation - not needed for basic GitHub Pages
        # await generate_github_workflow(kb_dir)
        
        # Generate index.html instead of MkDocs config
        await generate_index_html(kb_dir, kb_items, categories)
        
        # Generate category pages
        for main_cat, data in categories.items():
            await generate_category_html(kb_dir, main_cat, data)
            
            # Generate subcategory pages
            for sub_cat, items in data['subcategories'].items():
                await generate_subcategory_html(kb_dir, main_cat, sub_cat, items)
                
                # Copy KB item content to docs directory
                for item in items:
                    await copy_kb_item_html(kb_dir, item, docs_dir, main_cat, sub_cat)
        
        logging.info("GitHub Pages generation completed successfully")
        
    except Exception as e:
        logging.error(f"Failed to generate GitHub Pages: {e}")
        raise PagesGenerationError(f"Failed to generate GitHub Pages: {e}")

async def collect_kb_items(kb_dir: Path, tweet_cache: Dict) -> List[Dict[str, Any]]:
    """Collect knowledge base items from tweet cache."""
    kb_items = []
    
    for tweet_id, tweet_data in tweet_cache.items():
        if not tweet_data.get('kb_item_created', False):
            continue
            
        kb_path_str = tweet_data.get('kb_item_path')
        if not kb_path_str:
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
            if path.exists() and path.is_file():
                readme_path = path
                break
            elif path.is_dir() and (path / "README.md").exists():
                readme_path = path / "README.md"
                break
        
        if not readme_path and kb_path_str.endswith(('/README.md', '\\README.md')):
            dir_path = kb_dir / kb_path.parent
            if dir_path.exists() and dir_path.is_dir():
                readme_path = dir_path / "README.md"
                if readme_path.exists():
                    readme_path = dir_path / "README.md"
        
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
            
            kb_items.append({
                'main_category': main_cat,
                'sub_category': sub_cat,
                'item_name': item_name,
                'path': item_path,
                'file_path': str(readme_path),
                'description': await get_item_description(readme_path),
                'last_updated': readme_path.stat().st_mtime,
                'tweet_id': tweet_id,
                'created_date': tweet_data.get('processed_date'),
                'source_url': f"https://twitter.com/user/status/{tweet_id}"
            })
        except Exception as e:
            logging.error(f"Error processing KB item {kb_path_str} for tweet {tweet_id}: {e}")
            continue
    
    return kb_items

def organize_by_category(kb_items: List[Dict[str, Any]]) -> Dict:
    """Organize KB items by category and subcategory."""
    categories = {}
    for item in kb_items:
        main_cat = item['main_category']
        sub_cat = item['sub_category']
        if main_cat not in categories:
            categories[main_cat] = {'subcategories': {}}
        if sub_cat not in categories[main_cat]['subcategories']:
            categories[main_cat]['subcategories'][sub_cat] = []
        categories[main_cat]['subcategories'][sub_cat].append(item)
    return categories

async def generate_index_html(kb_dir: Path, kb_items: List[Dict[str, Any]], categories: Dict) -> None:
    """Generate the index.html page for GitHub Pages."""
    docs_dir = kb_dir / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    total_items = len(kb_items)
    total_main_cats = len(categories)
    total_subcats = sum(len(data['subcategories']) for data in categories.values())
    
    # Get recent items
    recent_items = sorted(kb_items, key=lambda x: x['last_updated'], reverse=True)[:5]
    
    # Build HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Technical Knowledge Base</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
    <style>
        body {{ padding: 20px; }}
        .container {{ max-width: 1200px; }}
        .recent-item {{ margin-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1 class="mb-4">Technical Knowledge Base</h1>
        
        <p class="lead">
            Welcome to our curated technical knowledge base! Dive into a rich collection of articles, 
            guides, and resources organized for easy exploration.
        </p>
        
        <div class="card mb-4">
            <div class="card-header">
                <h2 class="h5 mb-0">Overview</h2>
            </div>
            <div class="card-body">
                <ul>
                    <li><strong>Total Items:</strong> {total_items}</li>
                    <li><strong>Main Categories:</strong> {total_main_cats}</li>
                    <li><strong>Subcategories:</strong> {total_subcats}</li>
                    <li><strong>Last Updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                </ul>
            </div>
        </div>
        
        <div class="card mb-4">
            <div class="card-header">
                <h2 class="h5 mb-0">Recent Updates</h2>
            </div>
            <div class="card-body">
                <div class="list-group">
"""
    
    for item in recent_items:
        name = item['item_name'].replace('-', ' ').title()
        cat = f"{item['main_category'].replace('_', ' ').title()}/{item['sub_category'].replace('_', ' ').title()}"
        updated = datetime.fromtimestamp(item['last_updated']).strftime('%Y-%m-%d')
        path = f"categories/{item['main_category']}/{item['sub_category']}/{item['item_name']}.html"
        html_content += f"""
                    <a href="{path}" class="list-group-item list-group-item-action">
                        <div class="d-flex w-100 justify-content-between">
                            <h5 class="mb-1">{name}</h5>
                            <small>{updated}</small>
                        </div>
                        <p class="mb-1">{cat}</p>
                    </a>
"""
    
    html_content += """
                </div>
            </div>
        </div>
        
        <h2 class="mb-3">Categories</h2>
        <div class="row">
"""
    
    # Add category cards
    for main_cat, data in sorted(categories.items()):
        main_display = main_cat.replace('_', ' ').title()
        subcats = len(data['subcategories'])
        items = sum(len(items) for items in data['subcategories'].values())
        html_content += f"""
            <div class="col-md-4 mb-4">
                <div class="card h-100">
                    <div class="card-header">
                        <h3 class="h5 mb-0">{main_display}</h3>
                    </div>
                    <div class="card-body">
                        <p>{subcats} subcategories, {items} items</p>
                        <a href="categories/{main_cat}/index.html" class="btn btn-primary">Explore</a>
                    </div>
                </div>
            </div>
"""
    
    html_content += """
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
    
    # Write to file
    async with aiofiles.open(docs_dir / "index.html", 'w', encoding='utf-8') as f:
        await f.write(html_content)
    
    logging.info("Generated index.html for GitHub Pages")

async def generate_category_html(kb_dir: Path, category: str, data: Dict) -> None:
    """Generate a category index HTML page."""
    cat_dir = kb_dir / "docs" / "categories" / category
    cat_dir.mkdir(parents=True, exist_ok=True)
    
    display_name = category.replace('_', ' ').title()
    subcategories = sorted(data['subcategories'].keys())
    total_items = sum(len(items) for items in data['subcategories'].values())
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{display_name} - Technical Knowledge Base</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
    <style>
        body {{ padding: 20px; }}
        .container {{ max-width: 1200px; }}
    </style>
</head>
<body>
    <div class="container">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="../../index.html">Home</a></li>
                <li class="breadcrumb-item active" aria-current="page">{display_name}</li>
            </ol>
        </nav>
        
        <h1 class="mb-4">{display_name}</h1>
        
        <p class="lead">
            A collection of {total_items} items across {len(subcategories)} subcategories.
        </p>
        
        <h2 class="mb-3">Subcategories</h2>
        <div class="row">
"""
    
    for sub_cat in subcategories:
        sub_display = sub_cat.replace('_', ' ').title()
        items_count = len(data['subcategories'][sub_cat])
        html_content += f"""
            <div class="col-md-4 mb-4">
                <div class="card h-100">
                    <div class="card-header">
                        <h3 class="h5 mb-0">{sub_display}</h3>
                    </div>
                    <div class="card-body">
                        <p>{items_count} items</p>
                        <a href="{sub_cat}/index.html" class="btn btn-primary">View Items</a>
                    </div>
                </div>
            </div>
"""
    
    html_content += """
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
    
    # Write to file
    async with aiofiles.open(cat_dir / "index.html", 'w', encoding='utf-8') as f:
        await f.write(html_content)
    
    logging.info(f"Generated category HTML page for {category}")

async def generate_subcategory_html(kb_dir: Path, main_cat: str, sub_cat: str, items: List[Dict[str, Any]]) -> None:
    """Generate a subcategory index HTML page."""
    sub_dir = kb_dir / "docs" / "categories" / main_cat / sub_cat
    sub_dir.mkdir(parents=True, exist_ok=True)
    
    main_display = main_cat.replace('_', ' ').title()
    sub_display = sub_cat.replace('_', ' ').title()
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{sub_display} - {main_display} - Technical Knowledge Base</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
    <style>
        body {{ padding: 20px; }}
        .container {{ max-width: 1200px; }}
    </style>
</head>
<body>
    <div class="container">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="../../../index.html">Home</a></li>
                <li class="breadcrumb-item"><a href="../index.html">{main_display}</a></li>
                <li class="breadcrumb-item active" aria-current="page">{sub_display}</li>
            </ol>
        </nav>
        
        <h1 class="mb-4">{sub_display}</h1>
        
        <p class="lead">
            A collection of {len(items)} items in the {sub_display} subcategory.
        </p>
        
        <div class="list-group mb-4">
"""
    
    for item in sorted(items, key=lambda x: x['item_name']):
        name = item['item_name'].replace('-', ' ').title()
        desc = sanitize_markdown_cell(item['description'])
        updated = datetime.fromtimestamp(item['last_updated']).strftime('%Y-%m-%d')
        html_content += f"""
            <a href="{item['item_name']}.html" class="list-group-item list-group-item-action">
                <div class="d-flex w-100 justify-content-between">
                    <h5 class="mb-1">{name}</h5>
                    <small>Updated: {updated}</small>
                </div>
                <p class="mb-1">{desc}</p>
            </a>
"""
    
    html_content += """
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
    
    # Write to file
    async with aiofiles.open(sub_dir / "index.html", 'w', encoding='utf-8') as f:
        await f.write(html_content)
    
    logging.info(f"Generated subcategory HTML page for {main_cat}/{sub_cat}")

async def copy_kb_item_html(kb_dir: Path, item: Dict[str, Any], docs_dir: Path, main_cat: str, sub_cat: str) -> None:
    """Convert KB item markdown to HTML and save to docs directory."""
    source_path = Path(item['file_path'])
    if not source_path.exists():
        logging.warning(f"Source file not found: {source_path}")
        return
    
    target_dir = docs_dir / "categories" / main_cat / sub_cat
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{item['item_name']}.html"
    
    # Read source content
    async with aiofiles.open(source_path, 'r', encoding='utf-8') as src:
        content = await src.read()
    
    # Convert markdown to HTML (simple conversion)
    import re
    
    # Basic markdown conversion
    html_content = content
    
    # Headers
    html_content = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
    
    # Lists
    html_content = re.sub(r'^- (.*?)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'(<li>.*?</li>\n)+', r'<ul>\n\g<0></ul>', html_content, flags=re.DOTALL)
    
    # Links
    html_content = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', html_content)
    
    # Paragraphs
    html_content = re.sub(r'(?<!\n)\n(?!\n)(?!<[uo]l|<li|<h[1-6])', ' ', html_content)
    html_content = re.sub(r'\n\n(?!<[uo]l|<li|<h[1-6])', '</p>\n\n<p>', html_content)
    html_content = '<p>' + html_content + '</p>'
    
    # Code blocks
    html_content = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', html_content, flags=re.DOTALL)
    
    # Wrap in HTML template
    name = item['item_name'].replace('-', ' ').title()
    html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} - Technical Knowledge Base</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
    <style>
        body {{ padding: 20px; }}
        .container {{ max-width: 1000px; }}
        pre {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; }}
        img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <div class="container">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="../../../index.html">Home</a></li>
                <li class="breadcrumb-item"><a href="../index.html">{main_cat.replace('_', ' ').title()}</a></li>
                <li class="breadcrumb-item"><a href="index.html">{sub_cat.replace('_', ' ').title()}</a></li>
                <li class="breadcrumb-item active" aria-current="page">{name}</li>
            </ol>
        </nav>
        
        <div class="content">
            {html_content}
        </div>
        
        <hr>
        <div class="metadata">
            <p>
                <small>
                    Source: <a href="{item.get('source_url', '#')}">{item.get('source_url', 'N/A')}</a><br>
                    Last Updated: {datetime.fromtimestamp(item['last_updated']).strftime('%Y-%m-%d')}
                </small>
            </p>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
    
    # Write to file
    async with aiofiles.open(target_path, 'w', encoding='utf-8') as dest:
        await dest.write(html_page)
    
    # Copy any associated media files
    await copy_media_files(source_path.parent, target_dir)
    
    logging.debug(f"Converted KB item to HTML: {source_path} -> {target_path}")

async def copy_media_files(source_dir: Path, target_dir: Path) -> None:
    """Copy media files associated with a KB item."""
    if not source_dir.exists() or not source_dir.is_dir():
        return
    
    for file in source_dir.glob('*'):
        if file.is_file() and (file.name.startswith('image_') or file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            shutil.copy2(file, target_dir / file.name)
            logging.debug(f"Copied media file: {file} -> {target_dir / file.name}")

async def get_item_description(readme_path: Path) -> str:
    """Extract a polished description from a knowledge base item's README."""
    try:
        async with aiofiles.open(readme_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        import re
        desc_match = re.search(r'^## Description\s*\n(.*?)(?=\n#|$)', content, re.MULTILINE | re.DOTALL)
        if desc_match:
            desc = desc_match.group(1).strip()
        else:
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            desc = paragraphs[1] if len(paragraphs) > 1 else paragraphs[0] if paragraphs else ""

        if len(desc) > 250:
            truncated = desc[:250].rsplit(' ', 1)[0] + "..."
            desc = truncated if len(truncated) > 50 else desc[:250] + "..."
        return desc if desc else "No description available"
    except Exception as e:
        logging.warning(f"Failed to get description from {readme_path}: {e}")
        return "Description unavailable"

def sanitize_markdown_cell(text: str) -> str:
    """Escape special characters for markdown tables."""
    if not text:
        return "No description available"
    
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = text.replace('|', '\\|')
    text = text.replace('[', '\\[').replace(']', '\\]')
    text = text.replace('*', '\\*')
    if len(text) > 200:
        text = text[:197] + "..."
    return text.strip() 