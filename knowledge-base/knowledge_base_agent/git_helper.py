import asyncio
import logging
from typing import Optional
from pathlib import Path
from git import Repo, GitCommandError
from .config import Config
from .exceptions import GitSyncError

class GitSyncHandler:
    """Handles Git operations for syncing knowledge base changes."""
    
    def __init__(self, config: Config):
        """Initialize GitSyncHandler with config, targeting kb-generated."""
        self.config = config
        self.repo_dir = Path(config.knowledge_base_dir)  # ~/knowledge-base/kb-generated
        self.repo = None
        self.logger = logging.getLogger(__name__)

    async def _configure_git(self) -> None:
        """Configure git with user credentials and initialize if needed."""
        try:
            # Validate GitHub configuration
            if not self.config.github_token:
                raise GitSyncError("GitHub token (GITHUB_TOKEN) is not configured")
            if not self.config.github_user_name:
                raise GitSyncError("GitHub user name (GITHUB_USER_NAME) is not configured")
            if not self.config.github_user_email:
                raise GitSyncError("GitHub user email (GITHUB_USER_EMAIL) is not configured")
            if not self.config.github_repo_url:
                raise GitSyncError("GitHub repository URL (GITHUB_REPO_URL) is not configured")
            
            if not (self.repo_dir / '.git').exists():
                self.logger.info(f"No .git directory found at {self.repo_dir}, initializing repository...")
                self.repo = Repo.init(str(self.repo_dir))
            else:
                self.repo = Repo(str(self.repo_dir))
                self.logger.debug(f"Git repository loaded at {self.repo_dir}")
            
            # Ensure origin remote exists
            remote_url = str(self.config.github_repo_url).replace('https://', f'https://{self.config.github_token}@')
            if 'origin' not in [r.name for r in self.repo.remotes]:
                self.repo.create_remote('origin', remote_url)
                self.logger.debug(f"Created origin remote with URL: {remote_url}")
            else:
                self.repo.remote('origin').set_url(remote_url)
                self.logger.debug(f"Updated origin remote URL to: {remote_url}")
            
            with self.repo.config_writer() as git_config:
                git_config.set_value('user', 'name', self.config.github_user_name)
                git_config.set_value('user', 'email', self.config.github_user_email)
            
            # Ensure main branch exists
            if 'main' not in self.repo.heads:
                self.repo.git.checkout('-B', 'main')
                self.logger.debug("Created main branch")
        except Exception as e:
            self.logger.error(f"Failed to initialize Git repo at {self.repo_dir}: {e}")
            raise GitSyncError(f"Failed to initialize Git repo: {e}")

    async def sync_to_github(self, commit_message: str = "Update knowledge base content") -> None:
        """Sync changes in kb-generated to GitHub repository, overwriting remote state."""
        try:
            await self._configure_git()
            repo = self.repo
            
            repo.git.add(A=True)
            if repo.is_dirty(untracked_files=True):
                repo.index.commit(commit_message)
                self.logger.debug(f"Committed changes with message: {commit_message}")
            else:
                self.logger.info("No changes to commit")
            
            # Force push to overwrite remote state
            repo.git.push('origin', 'main', '--force')
            self.logger.debug("Force-pushed changes to remote repository")
            self.logger.info("Successfully synced to GitHub")
                
        except Exception as e:
            self.logger.error(f"GitHub sync failed: {e}")
            raise GitSyncError(f"Git sync failed: {e}")

    async def run_command(self, cmd: str, cwd: Path) -> None:
        """Run a git command asynchronously."""
        process = await asyncio.create_subprocess_exec(
            *cmd.split(),
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise GitCommandError(f"Command failed: {stderr.decode()}", process.returncode)
        self.logger.debug(f"Ran command '{cmd}': {stdout.decode().strip()}")