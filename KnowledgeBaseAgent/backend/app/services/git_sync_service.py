"""Git sync and repository management service."""

import os
import asyncio
import logging
import tempfile
import shutil
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
import hashlib

from app.database.connection import get_db_session
from app.repositories.content import get_content_repository
from app.repositories.knowledge import get_knowledge_repository
from app.repositories.synthesis import get_synthesis_repository
from app.repositories.readme import get_readme_repository
from app.models.git_sync import GitSyncOperation

logger = logging.getLogger(__name__)


@dataclass
class GitConfig:
    """Git repository configuration."""
    repo_url: str
    branch: str = "main"
    username: Optional[str] = None
    password: Optional[str] = None
    ssh_key_path: Optional[str] = None
    commit_author_name: str = "AI Agent"
    commit_author_email: str = "ai-agent@example.com"
    auto_push: bool = True
    auto_pull: bool = True


@dataclass
class GitSyncResult:
    """Result of a Git sync operation."""
    success: bool
    message: str
    operation_id: str
    files_exported: int
    files_changed: int
    commit_hash: Optional[str] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class GitOperations:
    """Git operations wrapper with error handling."""
    
    def __init__(self, repo_path: Path, config: GitConfig):
        self.repo_path = repo_path
        self.config = config
    
    async def clone_or_pull(self) -> bool:
        """Clone repository or pull latest changes."""
        try:
            if self.repo_path.exists() and (self.repo_path / ".git").exists():
                # Repository exists, pull latest changes
                if self.config.auto_pull:
                    result = await self._run_git_command(["pull", "origin", self.config.branch])
                    return result.returncode == 0
                return True
            else:
                # Clone repository
                clone_cmd = ["clone", "-b", self.config.branch, self.config.repo_url, str(self.repo_path)]
                result = await self._run_git_command(clone_cmd, cwd=self.repo_path.parent)
                return result.returncode == 0
                
        except Exception as e:
            logger.error(f"Git clone/pull failed: {e}")
            return False
    
    async def add_and_commit(self, message: str, files: List[str] = None) -> Optional[str]:
        """Add files and create commit."""
        try:
            # Add files
            if files:
                for file in files:
                    await self._run_git_command(["add", file])
            else:
                await self._run_git_command(["add", "."])
            
            # Check if there are changes to commit
            status_result = await self._run_git_command(["status", "--porcelain"])
            if not status_result.stdout.strip():
                logger.info("No changes to commit")
                return None
            
            # Set author info
            await self._run_git_command(["config", "user.name", self.config.commit_author_name])
            await self._run_git_command(["config", "user.email", self.config.commit_author_email])
            
            # Commit changes
            commit_result = await self._run_git_command(["commit", "-m", message])
            if commit_result.returncode == 0:
                # Get commit hash
                hash_result = await self._run_git_command(["rev-parse", "HEAD"])
                return hash_result.stdout.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Git commit failed: {e}")
            return None
    
    async def push(self) -> bool:
        """Push changes to remote repository."""
        try:
            if self.config.auto_push:
                result = await self._run_git_command(["push", "origin", self.config.branch])
                return result.returncode == 0
            return True
            
        except Exception as e:
            logger.error(f"Git push failed: {e}")
            return False
    
    async def get_changed_files(self) -> List[str]:
        """Get list of changed files."""
        try:
            result = await self._run_git_command(["diff", "--name-only", "HEAD"])
            if result.returncode == 0:
                return [f.strip() for f in result.stdout.split('\n') if f.strip()]
            return []
            
        except Exception as e:
            logger.error(f"Failed to get changed files: {e}")
            return []
    
    async def _run_git_command(self, args: List[str], cwd: Path = None) -> asyncio.subprocess.Process:
        """Run git command with proper error handling."""
        cmd = ["git"] + args
        work_dir = cwd or self.repo_path
        
        logger.debug(f"Running git command: {' '.join(cmd)} in {work_dir}")
        
        # Set up authentication if needed
        env = os.environ.copy()
        if self.config.username and self.config.password:
            # For HTTPS authentication
            repo_url_with_auth = self.config.repo_url.replace(
                "https://", f"https://{self.config.username}:{self.config.password}@"
            )
            env["GIT_ASKPASS"] = "echo"
            env["GIT_USERNAME"] = self.config.username
            env["GIT_PASSWORD"] = self.config.password
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=work_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await process.communicate()
        
        # Store results for access
        process.stdout = stdout.decode('utf-8') if stdout else ""
        process.stderr = stderr.decode('utf-8') if stderr else ""
        
        if process.returncode != 0:
            logger.error(f"Git command failed: {process.stderr}")
        
        return process


class FileExporter:
    """Export database content to temporary files for Git sync."""
    
    def __init__(self, export_dir: Path):
        self.export_dir = export_dir
        self.exported_files = []
    
    async def export_all_content(self) -> Dict[str, int]:
        """Export all content from database to files."""
        stats = {
            'content_items': 0,
            'knowledge_items': 0,
            'synthesis_documents': 0,
            'readme_files': 0
        }
        
        try:
            async with get_db_session() as db:
                # Export content items
                content_repo = get_content_repository()
                content_items = await content_repo.list(db, limit=10000)
                
                for item in content_items:
                    await self._export_content_item(item)
                    stats['content_items'] += 1
                
                # Export knowledge items
                knowledge_repo = get_knowledge_repository()
                knowledge_items = await knowledge_repo.list(db, limit=10000)
                
                for item in knowledge_items:
                    await self._export_knowledge_item(item)
                    stats['knowledge_items'] += 1
                
                # Export synthesis documents
                synthesis_repo = get_synthesis_repository()
                synthesis_docs = await synthesis_repo.list(db, limit=10000)
                
                for doc in synthesis_docs:
                    await self._export_synthesis_document(doc)
                    stats['synthesis_documents'] += 1
                
                # Export README files
                readme_repo = get_readme_repository()
                readme_items = await readme_repo.list(db, limit=1000)
                
                for readme in readme_items:
                    await self._export_readme_content(readme)
                    stats['readme_files'] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Content export failed: {e}")
            raise
    
    async def _export_content_item(self, item):
        """Export a single content item to markdown file."""
        try:
            # Create category directory structure
            category_dir = self.export_dir / "content" / (item.main_category or "uncategorized")
            category_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            safe_title = self._sanitize_filename(item.title)
            filename = f"{safe_title}_{item.id[:8]}.md"
            file_path = category_dir / filename
            
            # Generate markdown content
            markdown_content = self._generate_content_markdown(item)
            
            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            self.exported_files.append(str(file_path.relative_to(self.export_dir)))
            
        except Exception as e:
            logger.error(f"Failed to export content item {item.id}: {e}")
    
    async def _export_knowledge_item(self, item):
        """Export a knowledge item to markdown file."""
        try:
            # Create knowledge directory structure
            knowledge_dir = self.export_dir / "knowledge" / (item.main_category or "general")
            knowledge_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            safe_title = self._sanitize_filename(item.title)
            filename = f"{safe_title}_{item.id[:8]}.md"
            file_path = knowledge_dir / filename
            
            # Generate markdown content
            markdown_content = self._generate_knowledge_markdown(item)
            
            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            self.exported_files.append(str(file_path.relative_to(self.export_dir)))
            
        except Exception as e:
            logger.error(f"Failed to export knowledge item {item.id}: {e}")
    
    async def _export_synthesis_document(self, doc):
        """Export a synthesis document to markdown file."""
        try:
            # Create synthesis directory structure
            synthesis_dir = self.export_dir / "synthesis" / doc.main_category
            synthesis_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            safe_title = self._sanitize_filename(doc.title)
            filename = f"{safe_title}_{doc.id[:8]}.md"
            file_path = synthesis_dir / filename
            
            # Generate markdown content
            markdown_content = self._generate_synthesis_markdown(doc)
            
            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            self.exported_files.append(str(file_path.relative_to(self.export_dir)))
            
        except Exception as e:
            logger.error(f"Failed to export synthesis document {doc.id}: {e}")
    
    async def _export_readme_content(self, readme):
        """Export README content to appropriate location."""
        try:
            # Determine file path based on content type
            if readme.content_type == "main_readme":
                file_path = self.export_dir / "README.md"
            elif readme.content_type == "category_index":
                category_dir = self.export_dir / readme.category
                category_dir.mkdir(parents=True, exist_ok=True)
                file_path = category_dir / "README.md"
            else:
                # Subcategory index
                category_dir = self.export_dir / readme.category / readme.subcategory
                category_dir.mkdir(parents=True, exist_ok=True)
                file_path = category_dir / "README.md"
            
            # Write README content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(readme.content)
            
            self.exported_files.append(str(file_path.relative_to(self.export_dir)))
            
        except Exception as e:
            logger.error(f"Failed to export README {readme.id}: {e}")
    
    def _generate_content_markdown(self, item) -> str:
        """Generate markdown content for a content item."""
        lines = []
        
        # Title
        lines.append(f"# {item.title}")
        lines.append("")
        
        # Metadata
        lines.append("## Metadata")
        lines.append("")
        lines.append(f"- **ID**: {item.id}")
        lines.append(f"- **Source**: {item.source_type}")
        if item.source_url:
            lines.append(f"- **URL**: {item.source_url}")
        lines.append(f"- **Category**: {item.main_category or 'Uncategorized'}")
        if item.sub_category:
            lines.append(f"- **Subcategory**: {item.sub_category}")
        lines.append(f"- **Created**: {item.created_at.isoformat()}")
        lines.append("")
        
        # Content
        lines.append("## Content")
        lines.append("")
        lines.append(item.content)
        lines.append("")
        
        # Tags
        if item.tags:
            lines.append("## Tags")
            lines.append("")
            for tag in item.tags:
                lines.append(f"- {tag}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_knowledge_markdown(self, item) -> str:
        """Generate markdown content for a knowledge item."""
        lines = []
        
        # Title
        lines.append(f"# {item.title}")
        lines.append("")
        
        # Metadata
        lines.append("## Knowledge Item Details")
        lines.append("")
        lines.append(f"- **ID**: {item.id}")
        lines.append(f"- **Category**: {item.main_category}")
        if item.sub_category:
            lines.append(f"- **Subcategory**: {item.sub_category}")
        lines.append(f"- **Created**: {item.created_at.isoformat()}")
        lines.append("")
        
        # Enhanced content
        lines.append("## Enhanced Content")
        lines.append("")
        lines.append(item.enhanced_content or item.content)
        lines.append("")
        
        # Summary if available
        if item.summary:
            lines.append("## Summary")
            lines.append("")
            lines.append(item.summary)
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_synthesis_markdown(self, doc) -> str:
        """Generate markdown content for a synthesis document."""
        lines = []
        
        # Title
        lines.append(f"# {doc.title}")
        lines.append("")
        
        # Metadata
        lines.append("## Synthesis Details")
        lines.append("")
        lines.append(f"- **Category**: {doc.main_category}")
        if doc.sub_category:
            lines.append(f"- **Subcategory**: {doc.sub_category}")
        lines.append(f"- **Sources**: {doc.item_count} items")
        lines.append(f"- **Generated**: {doc.created_at.isoformat()}")
        lines.append("")
        
        # Content
        lines.append("## Analysis")
        lines.append("")
        lines.append(doc.content)
        lines.append("")
        
        return "\n".join(lines)
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > 100:
            filename = filename[:100]
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        
        return filename or "untitled"
    
    def cleanup(self):
        """Clean up exported files."""
        try:
            if self.export_dir.exists():
                shutil.rmtree(self.export_dir)
                logger.info(f"Cleaned up export directory: {self.export_dir}")
        except Exception as e:
            logger.error(f"Failed to cleanup export directory: {e}")


class GitSyncService:
    """Service for Git repository synchronization."""
    
    def __init__(self):
        self.temp_dirs = []
    
    async def sync_to_repository(self, config: GitConfig) -> GitSyncResult:
        """Sync database content to Git repository."""
        operation_id = self._generate_operation_id()
        temp_dir = None
        
        try:
            logger.info(f"Starting Git sync operation {operation_id}")
            
            # Create temporary directory for export
            temp_dir = Path(tempfile.mkdtemp(prefix="git_sync_"))
            self.temp_dirs.append(temp_dir)
            
            # Initialize Git operations
            git_ops = GitOperations(temp_dir, config)
            
            # Clone or pull repository
            if not await git_ops.clone_or_pull():
                raise Exception("Failed to clone or pull repository")
            
            # Export content to temporary files
            exporter = FileExporter(temp_dir)
            export_stats = await exporter.export_all_content()
            
            # Detect changed files
            changed_files = await git_ops.get_changed_files()
            
            # Commit changes if any
            commit_message = self._generate_commit_message(export_stats)
            commit_hash = await git_ops.add_and_commit(commit_message)
            
            # Push changes
            push_success = await git_ops.push()
            
            # Record operation in database
            await self._record_sync_operation(
                operation_id, config, export_stats, commit_hash, push_success
            )
            
            # Cleanup temporary files
            exporter.cleanup()
            
            return GitSyncResult(
                success=push_success,
                message=f"Sync completed successfully. Commit: {commit_hash}" if commit_hash else "No changes to sync",
                operation_id=operation_id,
                files_exported=sum(export_stats.values()),
                files_changed=len(changed_files),
                commit_hash=commit_hash
            )
            
        except Exception as e:
            logger.error(f"Git sync operation {operation_id} failed: {e}")
            
            return GitSyncResult(
                success=False,
                message=f"Sync failed: {str(e)}",
                operation_id=operation_id,
                files_exported=0,
                files_changed=0,
                errors=[str(e)]
            )
        
        finally:
            # Cleanup temporary directory
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    if temp_dir in self.temp_dirs:
                        self.temp_dirs.remove(temp_dir)
                except Exception as e:
                    logger.error(f"Failed to cleanup temp directory {temp_dir}: {e}")
    
    async def get_sync_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get Git sync operation history."""
        try:
            async with get_db_session() as db:
                # Query sync operations from database
                # This would need to be implemented with proper repository
                # For now, return empty list
                return []
                
        except Exception as e:
            logger.error(f"Failed to get sync history: {e}")
            return []
    
    def _generate_operation_id(self) -> str:
        """Generate unique operation ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"sync_{timestamp}"
    
    def _generate_commit_message(self, export_stats: Dict[str, int]) -> str:
        """Generate commit message based on export statistics."""
        total_files = sum(export_stats.values())
        
        if total_files == 0:
            return "Update knowledge base (no changes)"
        
        parts = []
        if export_stats.get('content_items', 0) > 0:
            parts.append(f"{export_stats['content_items']} content items")
        if export_stats.get('knowledge_items', 0) > 0:
            parts.append(f"{export_stats['knowledge_items']} knowledge items")
        if export_stats.get('synthesis_documents', 0) > 0:
            parts.append(f"{export_stats['synthesis_documents']} synthesis docs")
        if export_stats.get('readme_files', 0) > 0:
            parts.append(f"{export_stats['readme_files']} README files")
        
        message = f"Update knowledge base: {', '.join(parts)}"
        message += f"\n\nTotal files: {total_files}"
        message += f"\nGenerated: {datetime.utcnow().isoformat()}"
        
        return message
    
    async def _record_sync_operation(
        self, 
        operation_id: str, 
        config: GitConfig, 
        export_stats: Dict[str, int],
        commit_hash: Optional[str],
        push_success: bool
    ):
        """Record sync operation in database."""
        try:
            async with get_db_session() as db:
                # Create GitSyncOperation record
                sync_op = GitSyncOperation(
                    id=operation_id,
                    repository_url=config.repo_url,
                    branch=config.branch,
                    status="completed" if push_success else "failed",
                    commit_hash=commit_hash,
                    files_exported=sum(export_stats.values()),
                    export_stats=export_stats,
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow()
                )
                
                db.add(sync_op)
                await db.commit()
                
        except Exception as e:
            logger.error(f"Failed to record sync operation: {e}")
    
    def cleanup_all_temp_dirs(self):
        """Cleanup all temporary directories."""
        for temp_dir in self.temp_dirs:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except Exception as e:
                logger.error(f"Failed to cleanup temp directory {temp_dir}: {e}")
        
        self.temp_dirs.clear()


# Global service instance
_git_sync_service: Optional[GitSyncService] = None


def get_git_sync_service() -> GitSyncService:
    """Get the global Git sync service instance."""
    global _git_sync_service
    if _git_sync_service is None:
        _git_sync_service = GitSyncService()
    return _git_sync_service