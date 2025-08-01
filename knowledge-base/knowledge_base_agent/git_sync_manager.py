"""
Git Sync Manager - Database-to-Git Synchronization

This module handles the synchronization of Knowledge Base items and Synthesis documents
from the database to a Git repository structure. It replaces the old flat-file based
git_helper.py with a database-first approach.

Key Features:
- Exports KB items and synthesis documents from database to markdown files
- Organizes content into category/subcategory directory structure
- Generates comprehensive README.md with navigation and statistics
- Handles media file synchronization
- Provides clean Git repository management
"""

import asyncio
import logging
import shutil
import subprocess
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import json
import hashlib

from .config import Config
from .models import KnowledgeBaseItem, SubcategorySynthesis, UnifiedTweet, db
from .exceptions import GitSyncError
from .readme_generator import generate_root_readme, write_readme_file
from .category_manager import CategoryManager
from .http_client import HTTPClient


class GitSyncManager:
    """
    Manages synchronization of database content to Git repository.
    
    This class handles the complete pipeline from database export to Git push,
    organizing content into a clean directory structure suitable for GitHub.
    """
    
    def __init__(self, config: Config, task_id: Optional[str] = None):
        """Initialize GitSyncManager with configuration."""
        self.config = config
        self.task_id = task_id
        self.logger = logging.getLogger(__name__)
        
        # Git repository directory (where we'll export content)
        self.repo_dir = Path(config.knowledge_base_dir)
        
        # Content export directory structure
        self.kb_items_dir = self.repo_dir / "knowledge-base"
        self.synthesis_dir = self.repo_dir / "syntheses"
        self.media_dir = self.repo_dir / "media"
        
        # Git configuration
        self.git_executable = None
        self._configure_git_executable()
        
        # Initialize unified logger if available
        if task_id:
            try:
                from .unified_logging import get_unified_logger
                self.unified_logger = get_unified_logger(task_id, config)
            except ImportError:
                self.unified_logger = None
        else:
            self.unified_logger = None

    def _configure_git_executable(self) -> None:
        """Find and configure Git executable."""
        self.git_executable = shutil.which("git")
        if not self.git_executable:
            raise GitSyncError("Git executable not found in PATH")
        
        os.environ['GIT_PYTHON_GIT_EXECUTABLE'] = self.git_executable
        self.logger.info(f"Found Git executable at: {self.git_executable}")

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log message through unified logger if available, otherwise use standard logger."""
        if self.unified_logger:
            self.unified_logger.log(message, level)
        else:
            getattr(self.logger, level.lower())(message)

    async def export_database_to_git(self, commit_message: str = "Update knowledge base content") -> None:
        """
        Main entry point: Export all database content to Git repository.
        
        This method orchestrates the complete export process:
        1. Clean and prepare repository structure
        2. Export KB items to markdown files
        3. Export synthesis documents
        4. Copy media files
        5. Generate comprehensive README
        6. Commit and push to Git
        """
        try:
            self._log("Starting database-to-Git export process")
            
            # Step 1: Prepare repository structure
            await self._prepare_repository_structure()
            
            # Step 2: Export knowledge base items
            kb_stats = await self._export_knowledge_base_items()
            
            # Step 3: Export synthesis documents
            synthesis_stats = await self._export_synthesis_documents()
            
            # Step 4: Copy media files
            media_stats = await self._copy_media_files()
            
            # Step 5: Generate comprehensive README
            await self._generate_comprehensive_readme(kb_stats, synthesis_stats, media_stats)
            
            # Step 6: Commit and push to Git
            await self._commit_and_push(commit_message, kb_stats, synthesis_stats, media_stats)
            
            self._log("✅ Database-to-Git export completed successfully")
            
        except Exception as e:
            self._log(f"❌ Database-to-Git export failed: {e}", "ERROR")
            raise GitSyncError(f"Export failed: {e}") from e

    async def _prepare_repository_structure(self) -> None:
        """Prepare clean repository directory structure."""
        self._log("Preparing repository directory structure")
        
        # Ensure base directories exist
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        self.kb_items_dir.mkdir(parents=True, exist_ok=True)
        self.synthesis_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Git repository if needed
        if not (self.repo_dir / '.git').exists():
            self._log("Initializing Git repository")
            subprocess.run(
                [self.git_executable, "init"],
                cwd=str(self.repo_dir),
                check=True,
                capture_output=True
            )
        
        # Configure Git user if needed
        self._configure_git_user()
        
        # Create/update .gitignore
        await self._create_gitignore()

    def _configure_git_user(self) -> None:
        """Configure Git user credentials."""
        if not self.config.github_user_name or not self.config.github_user_email:
            self._log("Missing Git user configuration", "WARNING")
            return
        
        try:
            subprocess.run(
                [self.git_executable, "config", "user.name", self.config.github_user_name],
                cwd=str(self.repo_dir),
                check=True
            )
            subprocess.run(
                [self.git_executable, "config", "user.email", self.config.github_user_email],
                cwd=str(self.repo_dir),
                check=True
            )
            self._log("Git user configuration updated")
        except subprocess.CalledProcessError as e:
            self._log(f"Failed to configure Git user: {e}", "WARNING")

    async def _create_gitignore(self) -> None:
        """Create or update .gitignore file."""
        gitignore_path = self.repo_dir / ".gitignore"
        gitignore_content = [
            "# Ignore large media files to prevent oversized uploads",
            "# Videos - excluded due to size",
            "*.mp4", "*.avi", "*.mkv", "*.mov", "*.wmv", "*.flv", "*.webm",
            "# Audio files - excluded", 
            "*.mp3", "*.wav", "*.ogg", "*.flac",
            "# Large images - excluded",
            "*.tiff", "*.bmp",
            "# System files",
            ".DS_Store",
            "Thumbs.db",
            "# Temporary files",
            "*.tmp", "*.temp",
            "# Images are included for GitHub sync (PNG, JPG, GIF, WebP)",
            ""
        ]
        
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(gitignore_content))
        
        self._log("Created/updated .gitignore")

    async def _export_knowledge_base_items(self) -> Dict[str, Any]:
        """Export all knowledge base items to markdown files."""
        self._log("Exporting knowledge base items from database")
        
        # Query all KB items from database
        kb_items = KnowledgeBaseItem.query.all()
        
        stats = {
            'total_items': len(kb_items),
            'categories': set(),
            'subcategories': set(),
            'exported_files': 0,
            'failed_exports': 0
        }
        
        for kb_item in kb_items:
            try:
                await self._export_single_kb_item(kb_item, stats)
                stats['exported_files'] += 1
            except Exception as e:
                self._log(f"Failed to export KB item {kb_item.id}: {e}", "ERROR")
                stats['failed_exports'] += 1
        
        self._log(f"Exported {stats['exported_files']} KB items ({stats['failed_exports']} failed)")
        return stats

    async def _export_single_kb_item(self, kb_item: KnowledgeBaseItem, stats: Dict[str, Any]) -> None:
        """Export a single knowledge base item to markdown file."""
        # Determine directory structure
        main_cat = self._sanitize_filename(kb_item.main_category)
        sub_cat = self._sanitize_filename(kb_item.sub_category)
        item_name = self._sanitize_filename(kb_item.item_name or kb_item.title)
        
        stats['categories'].add(main_cat)
        stats['subcategories'].add(f"{main_cat}/{sub_cat}")
        
        # Create directory structure
        item_dir = self.kb_items_dir / main_cat / sub_cat / item_name
        item_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate markdown content
        markdown_content = self._generate_kb_item_markdown(kb_item)
        
        # Write README.md file
        readme_path = item_dir / "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        # Copy associated media files if they exist
        await self._copy_kb_item_media(kb_item, item_dir)

    def _generate_kb_item_markdown(self, kb_item: KnowledgeBaseItem) -> str:
        """Generate markdown content for a knowledge base item."""
        lines = []
        
        # Title
        title = kb_item.display_title or kb_item.title
        lines.append(f"# {title}")
        lines.append("")
        
        # Metadata section
        lines.append("## 📋 Metadata")
        lines.append("")
        lines.append(f"- **Category**: {kb_item.main_category}")
        lines.append(f"- **Subcategory**: {kb_item.sub_category}")
        if kb_item.source_url:
            lines.append(f"- **Source**: [{kb_item.source_url}]({kb_item.source_url})")
        if kb_item.tweet_id:
            lines.append(f"- **Tweet ID**: {kb_item.tweet_id}")
        lines.append(f"- **Created**: {kb_item.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **Last Updated**: {kb_item.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Description if available
        if kb_item.description:
            lines.append("## 📝 Description")
            lines.append("")
            lines.append(kb_item.description)
            lines.append("")
        
        # Main content
        lines.append("## 📄 Content")
        lines.append("")
        lines.append(kb_item.content)
        lines.append("")
        
        # Media section if media exists
        if kb_item.kb_media_paths:
            try:
                media_paths = json.loads(kb_item.kb_media_paths) if isinstance(kb_item.kb_media_paths, str) else kb_item.kb_media_paths
                if media_paths:
                    lines.append("## 🖼️ Media")
                    lines.append("")
                    for media_path in media_paths:
                        media_filename = Path(media_path).name
                        lines.append(f"![{media_filename}](./{media_filename})")
                    lines.append("")
            except (json.JSONDecodeError, TypeError):
                pass
        
        return '\n'.join(lines)

    async def _copy_kb_item_media(self, kb_item: KnowledgeBaseItem, target_dir: Path) -> None:
        """Copy media files associated with a KB item."""
        if not kb_item.kb_media_paths:
            return
        
        try:
            media_paths = json.loads(kb_item.kb_media_paths) if isinstance(kb_item.kb_media_paths, str) else kb_item.kb_media_paths
            
            for media_path in media_paths:
                source_path = Path(media_path)
                if source_path.exists():
                    target_path = target_dir / source_path.name
                    shutil.copy2(source_path, target_path)
                    self._log(f"Copied media file: {source_path.name}")
        except (json.JSONDecodeError, TypeError, OSError) as e:
            self._log(f"Failed to copy media for KB item {kb_item.id}: {e}", "WARNING")

    async def _export_synthesis_documents(self) -> Dict[str, Any]:
        """Export all synthesis documents to markdown files."""
        self._log("Exporting synthesis documents from database")
        
        # Query all synthesis documents from database
        syntheses = SubcategorySynthesis.query.all()
        
        stats = {
            'total_syntheses': len(syntheses),
            'categories': set(),
            'exported_files': 0,
            'failed_exports': 0
        }
        
        for synthesis in syntheses:
            try:
                await self._export_single_synthesis(synthesis, stats)
                stats['exported_files'] += 1
            except Exception as e:
                self._log(f"Failed to export synthesis {synthesis.id}: {e}", "ERROR")
                stats['failed_exports'] += 1
        
        self._log(f"Exported {stats['exported_files']} synthesis documents ({stats['failed_exports']} failed)")
        return stats

    async def _export_single_synthesis(self, synthesis: SubcategorySynthesis, stats: Dict[str, Any]) -> None:
        """Export a single synthesis document to markdown file."""
        # Determine directory structure
        main_cat = self._sanitize_filename(synthesis.main_category)
        sub_cat = self._sanitize_filename(synthesis.sub_category) if synthesis.sub_category else "overview"
        
        stats['categories'].add(main_cat)
        
        # Create directory structure
        synthesis_dir = self.synthesis_dir / main_cat
        synthesis_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        if synthesis.sub_category:
            filename = f"synthesis_{sub_cat}.md"
        else:
            filename = "synthesis_overview.md"
        
        # Generate markdown content
        markdown_content = self._generate_synthesis_markdown(synthesis)
        
        # Write synthesis file
        synthesis_path = synthesis_dir / filename
        with open(synthesis_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

    def _generate_synthesis_markdown(self, synthesis: SubcategorySynthesis) -> str:
        """Generate markdown content for a synthesis document."""
        lines = []
        
        # Title
        lines.append(f"# {synthesis.synthesis_title}")
        lines.append("")
        
        # Metadata section
        lines.append("## 📋 Synthesis Metadata")
        lines.append("")
        lines.append(f"- **Category**: {synthesis.main_category}")
        if synthesis.sub_category:
            lines.append(f"- **Subcategory**: {synthesis.sub_category}")
        lines.append(f"- **Items Analyzed**: {synthesis.item_count}")
        lines.append(f"- **Generated**: {synthesis.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **Last Updated**: {synthesis.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        if synthesis.content_hash:
            lines.append(f"- **Content Hash**: `{synthesis.content_hash[:12]}...`")
        lines.append("")
        
        # Synthesis content
        lines.append("## 🔬 Synthesis")
        lines.append("")
        lines.append(synthesis.synthesis_content)
        lines.append("")
        
        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*This synthesis was automatically generated by analyzing multiple knowledge base items in this category.*")
        lines.append("")
        
        return '\n'.join(lines)

    async def _copy_media_files(self) -> Dict[str, Any]:
        """Copy media files from various sources to centralized media directory."""
        self._log("Copying media files to centralized directory")
        
        stats = {
            'total_files': 0,
            'copied_files': 0,
            'failed_copies': 0,
            'total_size_mb': 0
        }
        
        # Get media paths from UnifiedTweet model
        unified_tweets = UnifiedTweet.query.filter(UnifiedTweet.media_files.isnot(None)).all()
        
        for tweet in unified_tweets:
            try:
                if tweet.media_files:
                    media_files = tweet.media_files if isinstance(tweet.media_files, list) else json.loads(tweet.media_files)
                    for media_path in media_files:
                        await self._copy_single_media_file(media_path, stats)
            except (json.JSONDecodeError, TypeError) as e:
                self._log(f"Failed to process media for tweet {tweet.tweet_id}: {e}", "WARNING")
        
        self._log(f"Copied {stats['copied_files']} media files ({stats['total_size_mb']:.1f} MB total)")
        return stats

    async def _copy_single_media_file(self, media_path: str, stats: Dict[str, Any]) -> None:
        """Copy a single media file to the centralized media directory."""
        try:
            source_path = Path(media_path)
            if not source_path.exists():
                return
            
            # Skip large video files (they should be in .gitignore anyway)
            if source_path.suffix.lower() in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
                return
            
            stats['total_files'] += 1
            
            # Create subdirectory based on file type
            if source_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                target_dir = self.media_dir / "images"
            else:
                target_dir = self.media_dir / "other"
            
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename to avoid conflicts
            target_path = target_dir / source_path.name
            counter = 1
            while target_path.exists():
                stem = source_path.stem
                suffix = source_path.suffix
                target_path = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            
            # Copy file
            shutil.copy2(source_path, target_path)
            
            # Update stats
            file_size_mb = target_path.stat().st_size / (1024 * 1024)
            stats['copied_files'] += 1
            stats['total_size_mb'] += file_size_mb
            
        except (OSError, IOError) as e:
            stats['failed_copies'] += 1
            self._log(f"Failed to copy media file {media_path}: {e}", "WARNING")

    async def _generate_comprehensive_readme(self, kb_stats: Dict[str, Any], synthesis_stats: Dict[str, Any], media_stats: Dict[str, Any]) -> None:
        """Generate comprehensive README.md for the repository."""
        self._log("Generating comprehensive README.md")
        
        try:
            # Use the existing readme generator with database content
            category_manager = CategoryManager(self.config)
            http_client = HTTPClient(self.config)
            
            # Generate README using the existing system but with database content
            await self._generate_database_driven_readme(category_manager, http_client, kb_stats, synthesis_stats, media_stats)
            
        except Exception as e:
            self._log(f"Failed to generate comprehensive README, creating basic version: {e}", "WARNING")
            await self._generate_basic_readme(kb_stats, synthesis_stats, media_stats)

    async def _generate_database_driven_readme(self, category_manager: CategoryManager, http_client: HTTPClient, kb_stats: Dict[str, Any], synthesis_stats: Dict[str, Any], media_stats: Dict[str, Any]) -> None:
        """Generate README using database content instead of file scanning."""
        
        # Collect all items from database
        kb_items = []
        synthesis_items = []
        
        # Get KB items
        db_kb_items = KnowledgeBaseItem.query.all()
        for item in db_kb_items:
            main_cat = self._sanitize_filename(item.main_category)
            sub_cat = self._sanitize_filename(item.sub_category)
            item_name = self._sanitize_filename(item.item_name or item.title)
            
            kb_items.append({
                "main_category": main_cat,
                "sub_category": sub_cat,
                "item_name": item_name,
                "path": f"knowledge-base/{main_cat}/{sub_cat}/{item_name}",
                "description": item.description or "Knowledge base item",
                "last_updated": item.last_updated.timestamp(),
                "tweet_id": item.tweet_id,
                "created_date": item.created_at.strftime('%Y-%m-%d'),
                "source_url": item.source_url or f"https://twitter.com/user/status/{item.tweet_id}" if item.tweet_id else "N/A",
                "type": "kb_item"
            })
        
        # Get synthesis documents
        db_syntheses = SubcategorySynthesis.query.all()
        for synthesis in db_syntheses:
            main_cat = self._sanitize_filename(synthesis.main_category)
            sub_cat = self._sanitize_filename(synthesis.sub_category) if synthesis.sub_category else "overview"
            
            synthesis_items.append({
                "type": "synthesis",
                "main_category": main_cat,
                "sub_category": sub_cat,
                "item_name": synthesis.synthesis_short_name or synthesis.synthesis_title,
                "path": f"syntheses/{main_cat}/synthesis_{sub_cat}.md" if synthesis.sub_category else f"syntheses/{main_cat}/synthesis_overview.md",
                "description": f"Synthesis document analyzing {synthesis.item_count} items. {synthesis.synthesis_content[:200]}..." if synthesis.synthesis_content else "Comprehensive synthesis document.",
                "last_updated": synthesis.last_updated.timestamp(),
                "created_date": synthesis.created_at.strftime('%Y-%m-%d'),
                "source_url": f"/synthesis/{synthesis.id}",
                "item_count": synthesis.item_count,
                "synthesis_id": synthesis.id
            })
        
        # Generate README content
        all_items = kb_items + synthesis_items
        content = await self._build_readme_content(all_items, kb_stats, synthesis_stats, media_stats)
        
        # Write README
        readme_path = self.repo_dir / "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)

    async def _build_readme_content(self, all_items: List[Dict[str, Any]], kb_stats: Dict[str, Any], synthesis_stats: Dict[str, Any], media_stats: Dict[str, Any]) -> str:
        """Build comprehensive README content."""
        lines = []
        
        # Header
        lines.extend([
            "# 📚 Technical Knowledge Base",
            "",
            "Welcome to our comprehensive technical knowledge base! This repository contains curated articles, guides, and AI-generated synthesis documents organized for easy exploration and learning.",
            "",
            "---",
            "## 📊 Repository Overview",
            "",
            f"- **Knowledge Base Items**: {kb_stats['total_items']}",
            f"- **Synthesis Documents**: {synthesis_stats['total_syntheses']}",
            f"- **Total Content Pieces**: {kb_stats['total_items'] + synthesis_stats['total_syntheses']}",
            f"- **Categories**: {len(kb_stats['categories'])}",
            f"- **Media Files**: {media_stats['copied_files']} ({media_stats['total_size_mb']:.1f} MB)",
            f"- **Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "## 🗂️ Repository Structure",
            "",
            "```",
            "📁 knowledge-base/          # Individual knowledge base items",
            "   └── 📁 [category]/",
            "       └── 📁 [subcategory]/",
            "           └── 📁 [item-name]/",
            "               └── 📄 README.md",
            "",
            "📁 syntheses/               # AI-generated synthesis documents", 
            "   └── 📁 [category]/",
            "       └── 📄 synthesis_[subcategory].md",
            "",
            "📁 media/                   # Centralized media files",
            "   ├── 📁 images/",
            "   └── 📁 other/",
            "```",
            "",
        ])
        
        # Group items by category
        categories = {}
        for item in all_items:
            main_cat = item["main_category"]
            sub_cat = item["sub_category"]
            if main_cat not in categories:
                categories[main_cat] = {"subcategories": {}}
            if sub_cat not in categories[main_cat]["subcategories"]:
                categories[main_cat]["subcategories"][sub_cat] = []
            categories[main_cat]["subcategories"][sub_cat].append(item)
        
        # Quick navigation
        lines.extend([
            "## 🧭 Quick Navigation",
            ""
        ])
        
        for main_cat in sorted(categories.keys()):
            main_display = main_cat.replace("_", " ").replace("-", " ").title()
            anchor = main_cat.lower().replace("_", "-")
            lines.append(f"- **[{main_display}](#{anchor})**")
            
            for sub_cat in sorted(categories[main_cat]["subcategories"].keys()):
                sub_display = sub_cat.replace("_", " ").replace("-", " ").title()
                sub_anchor = f"{anchor}-{sub_cat.lower().replace('_', '-')}"
                lines.append(f"  - [{sub_display}](#{sub_anchor})")
        
        # Recent updates
        recent_items = sorted(all_items, key=lambda x: x["last_updated"], reverse=True)[:10]
        if recent_items:
            lines.extend([
                "",
                "---",
                "## 🔔 Recent Updates",
                "",
                "| **Item** | **Type** | **Category** | **Last Updated** |",
                "|----------|----------|--------------|------------------|"
            ])
            
            for item in recent_items:
                name = item["item_name"].replace("-", " ").replace("_", " ").title()
                item_type = "🔬 Synthesis" if item.get("type") == "synthesis" else "📄 KB Item"
                category = f"{item['main_category'].title()}/{item['sub_category'].title()}"
                updated = datetime.fromtimestamp(item["last_updated"]).strftime("%Y-%m-%d")
                path = item["path"]
                
                lines.append(f"| [{name}]({path}) | {item_type} | {category} | {updated} |")
        
        # Categories section
        lines.extend([
            "",
            "---", 
            "## 📋 Categories & Content",
            ""
        ])
        
        for main_cat in sorted(categories.keys()):
            main_display = main_cat.replace("_", " ").replace("-", " ").title()
            anchor = main_cat.lower().replace("_", "-")
            
            total_items = sum(len(items) for items in categories[main_cat]["subcategories"].values())
            kb_count = sum(1 for subcat_items in categories[main_cat]["subcategories"].values() 
                          for item in subcat_items if item.get("type") != "synthesis")
            synthesis_count = sum(1 for subcat_items in categories[main_cat]["subcategories"].values() 
                                for item in subcat_items if item.get("type") == "synthesis")
            
            lines.extend([
                f'### {main_display} <a name="{anchor}"></a>',
                "",
                f"📊 **{total_items} items** ({kb_count} KB items, {synthesis_count} syntheses)",
                ""
            ])
            
            # Add subcategories
            for sub_cat in sorted(categories[main_cat]["subcategories"].keys()):
                sub_display = sub_cat.replace("_", " ").replace("-", " ").title()
                sub_anchor = f"{anchor}-{sub_cat.lower().replace('_', '-')}"
                items = categories[main_cat]["subcategories"][sub_cat]
                
                lines.extend([
                    f'#### {sub_display} <a name="{sub_anchor}"></a>',
                    "",
                    "| **Item** | **Type** | **Description** |",
                    "|----------|----------|-----------------|"
                ])
                
                for item in sorted(items, key=lambda x: x["item_name"]):
                    name = item["item_name"].replace("-", " ").replace("_", " ").title()
                    item_type = "🔬 Synthesis" if item.get("type") == "synthesis" else "📄 KB Item"
                    description = item["description"][:100] + "..." if len(item["description"]) > 100 else item["description"]
                    path = item["path"]
                    
                    lines.append(f"| [{name}]({path}) | {item_type} | {description} |")
                
                lines.append("")
        
        # Footer
        lines.extend([
            "---",
            "## 🚀 Getting Started",
            "",
            "1. **Browse by Category**: Use the navigation above to explore content by topic",
            "2. **Search**: Use GitHub's search functionality to find specific content",
            "3. **Synthesis Documents**: Check out AI-generated syntheses for comprehensive overviews",
            "4. **Media Content**: Visual content is organized in the `media/` directory",
            "",
            "## 🤝 Contributing",
            "",
            "This knowledge base is automatically generated and maintained. Content is sourced from curated social media posts and processed through AI analysis.",
            "",
            "---",
            "",
            f"*Last generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total content pieces: {len(all_items)}*",
            ""
        ])
        
        return '\n'.join(lines)

    async def _generate_basic_readme(self, kb_stats: Dict[str, Any], synthesis_stats: Dict[str, Any], media_stats: Dict[str, Any]) -> None:
        """Generate a basic README as fallback."""
        content = f"""# 📚 Technical Knowledge Base

This repository contains {kb_stats['total_items']} knowledge base items and {synthesis_stats['total_syntheses']} synthesis documents.

## Structure

- `knowledge-base/` - Individual knowledge base items organized by category
- `syntheses/` - AI-generated synthesis documents  
- `media/` - Associated media files

## Statistics

- **Knowledge Base Items**: {kb_stats['total_items']}
- **Synthesis Documents**: {synthesis_stats['total_syntheses']}
- **Categories**: {len(kb_stats['categories'])}
- **Media Files**: {media_stats['copied_files']}
- **Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

*This knowledge base is automatically generated and maintained.*
"""
        
        readme_path = self.repo_dir / "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)

    async def _commit_and_push(self, commit_message: str, kb_stats: Dict[str, Any], synthesis_stats: Dict[str, Any], media_stats: Dict[str, Any]) -> None:
        """Commit changes and push to remote repository."""
        self._log("Committing and pushing changes to Git repository")
        
        try:
            # Configure remote if needed
            await self._configure_remote()
            
            # Add all changes
            subprocess.run(
                [self.git_executable, "add", "."],
                cwd=str(self.repo_dir),
                check=True,
                capture_output=True
            )
            
            # Check if there are changes to commit
            status_result = subprocess.run(
                [self.git_executable, "status", "--porcelain"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                check=False
            )
            
            if not status_result.stdout.strip():
                self._log("No changes to commit")
                return
            
            # Create detailed commit message
            detailed_message = f"""{commit_message}

📊 Export Summary:
- Knowledge Base Items: {kb_stats['total_items']} ({kb_stats['exported_files']} exported)
- Synthesis Documents: {synthesis_stats['total_syntheses']} ({synthesis_stats['exported_files']} exported)
- Media Files: {media_stats['copied_files']} ({media_stats['total_size_mb']:.1f} MB)
- Categories: {len(kb_stats['categories'])}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            # Commit changes
            subprocess.run(
                [self.git_executable, "commit", "-m", detailed_message],
                cwd=str(self.repo_dir),
                check=True,
                capture_output=True
            )
            
            # Push to remote
            await self._push_to_remote()
            
            self._log("✅ Successfully committed and pushed changes to Git repository")
            
        except subprocess.CalledProcessError as e:
            self._log(f"Git operation failed: {e}", "ERROR")
            raise GitSyncError(f"Git operation failed: {e}") from e

    async def _configure_remote(self) -> None:
        """Configure Git remote origin."""
        if not self.config.github_repo_url or not self.config.github_token:
            self._log("Missing GitHub configuration", "WARNING")
            return
        
        # Create authenticated URL
        remote_url = str(self.config.github_repo_url).replace(
            'https://', f'https://{self.config.github_token}@'
        )
        
        try:
            # Check if remote exists
            remotes_result = subprocess.run(
                [self.git_executable, "remote"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                check=False
            )
            
            remotes = remotes_result.stdout.splitlines() if remotes_result.returncode == 0 else []
            
            if 'origin' not in remotes:
                # Add remote
                subprocess.run(
                    [self.git_executable, "remote", "add", "origin", remote_url],
                    cwd=str(self.repo_dir),
                    check=True
                )
                self._log("Added Git remote origin")
            else:
                # Update remote URL
                subprocess.run(
                    [self.git_executable, "remote", "set-url", "origin", remote_url],
                    cwd=str(self.repo_dir),
                    check=True
                )
                self._log("Updated Git remote origin URL")
                
        except subprocess.CalledProcessError as e:
            self._log(f"Failed to configure Git remote: {e}", "WARNING")

    async def _push_to_remote(self) -> None:
        """Push changes to remote repository with retry logic."""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Get current branch
                branch_result = subprocess.run(
                    [self.git_executable, "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(self.repo_dir),
                    capture_output=True,
                    text=True,
                    check=True
                )
                current_branch = branch_result.stdout.strip()
                
                # Push with force to overwrite remote
                subprocess.run(
                    [self.git_executable, "push", "origin", current_branch, "--force"],
                    cwd=str(self.repo_dir),
                    check=True,
                    capture_output=True,
                    timeout=300  # 5 minute timeout
                )
                
                self._log(f"Successfully pushed to remote branch: {current_branch}")
                return
                
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                self._log(f"Push attempt {attempt + 1}/{max_retries} failed: {e}", "WARNING")
                
                if attempt == max_retries - 1:
                    raise GitSyncError(f"Failed to push after {max_retries} attempts: {e}") from e
                
                # Wait before retry
                await asyncio.sleep(10)

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as a filename or directory name."""
        if not name:
            return "unknown"
        
        # Replace problematic characters
        sanitized = name.lower()
        sanitized = sanitized.replace(" ", "-")
        sanitized = sanitized.replace("_", "-")
        
        # Remove or replace other problematic characters
        import re
        sanitized = re.sub(r'[^\w\-.]', '', sanitized)
        sanitized = re.sub(r'-+', '-', sanitized)  # Collapse multiple dashes
        sanitized = sanitized.strip('-')  # Remove leading/trailing dashes
        
        return sanitized or "unknown"


# Convenience function for backward compatibility
async def sync_database_to_git(config: Config, task_id: Optional[str] = None, commit_message: str = "Update knowledge base content") -> None:
    """
    Convenience function to sync database content to Git repository.
    
    This function provides a simple interface for the complete database-to-Git
    synchronization process.
    """
    git_sync_manager = GitSyncManager(config, task_id)
    await git_sync_manager.export_database_to_git(commit_message)