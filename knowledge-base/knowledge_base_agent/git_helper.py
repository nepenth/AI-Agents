import subprocess
import datetime
import logging
from pathlib import Path
from .exceptions import KnowledgeBaseError
from typing import List, Optional
import git
from knowledge_base_agent.config import Config
from knowledge_base_agent.exceptions import GitSyncError
from git import Repo, GitCommandError
import asyncio
from functools import partial

def run_git_command(cmd: List[str], cwd: Path, capture_output: bool = False) -> Optional[str]:
    logging.debug(f"Running git command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True
        )
        if capture_output:
            logging.debug(f"Command output: {result.stdout}")
            return result.stdout.strip()
        return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Git command failed: {e.stderr}")
        raise KnowledgeBaseError(f"Git command failed: {e.stderr}")

class GitHelper:
    """Handles Git operations for the knowledge base."""
    
    def __init__(
        self,
        repo_path: Path,
        repo_url: str,
        token: str,
        user_name: str,
        user_email: str
    ):
        """
        Initialize GitHelper.
        
        Args:
            repo_path: Path to the repository
            repo_url: URL of the remote repository
            token: GitHub token
            user_name: Git user name
            user_email: Git user email
            
        Raises:
            GitError: If initialization fails
        """
        self.repo_path = repo_path
        self.repo_url = repo_url
        self.token = token
        self.user_name = user_name
        self.user_email = user_email
        self.repo: Optional[git.Repo] = None

    def initialize_repo(self) -> None:
        """Initialize or verify the git repository."""
        try:
            if not (self.repo_path / '.git').exists():
                self.repo = git.Repo.init(self.repo_path)
                self._setup_remote()
                # Set up initial branch and upstream
                self.repo.git.checkout('-B', 'main')  # Create and switch to main branch
                self.repo.git.push('--set-upstream', 'origin', 'main')  # Set upstream branch
            else:
                self.repo = git.Repo(self.repo_path)
                # Ensure remote exists
                if 'origin' not in [r.name for r in self.repo.remotes]:
                    self._setup_remote()
                    self.repo.git.push('--set-upstream', 'origin', 'main')
        except Exception as e:
            raise KnowledgeBaseError(f"Failed to initialize repository: {e}")

    def _setup_remote(self) -> None:
        """
        Set up the remote repository.
        
        Raises:
            GitError: If remote setup fails
        """
        try:
            remote_url = self.repo_url.replace('https://', f'https://{self.token}@')
            self.repo.create_remote('origin', remote_url)
        except Exception as e:
            raise KnowledgeBaseError(f"Failed to setup remote: {e}")

    def commit_and_push(self, commit_message: Optional[str] = None) -> None:
        """
        Commit changes and push to remote.
        
        Args:
            commit_message: Optional custom commit message
            
        Raises:
            GitError: If commit or push fails
        """
        try:
            if not self.repo:
                self.initialize_repo()

            # Configure user
            self.repo.config_writer().set_value("user", "name", self.user_name).release()
            self.repo.config_writer().set_value("user", "email", self.user_email).release()

            # Add all changes
            self.repo.git.add(all=True)

            # Check if there are changes to commit
            if self.repo.is_dirty(untracked_files=True):
                message = commit_message or f"Update knowledge base: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                self.repo.index.commit(message)
                
                # Push changes
                origin = self.repo.remote('origin')
                origin.push()
                
                logging.info("Successfully pushed changes to remote repository")
            else:
                logging.info("No changes to commit")
                
        except Exception as e:
            raise KnowledgeBaseError(f"Failed to commit and push changes: {e}")

def push_to_github(
    knowledge_base_dir: Path,
    github_repo_url: str,
    github_token: str,
    git_user_name: str,
    git_user_email: str,
    commit_message: Optional[str] = None
) -> None:
    """
    Push changes to GitHub.
    
    Raises:
        GitError: If the operation fails
    """
    try:
        helper = GitHelper(
            repo_path=knowledge_base_dir,
            repo_url=github_repo_url,
            token=github_token,
            user_name=git_user_name,
            user_email=git_user_email
        )
        helper.commit_and_push(commit_message)
    except Exception as e:
        raise KnowledgeBaseError(f"Failed to push to GitHub: {e}")

class GitSyncHandler:
    def __init__(self, config: Config):
        self.config = config
        self.repo_path = self.config.knowledge_base_dir
        self._repo: Optional[Repo] = None

    async def sync_to_github(self, message: str) -> None:
        """Main sync operation coordinator."""
        try:
            await self._init_repo()
            await self._configure_repo()
            await self._stage_changes()
            await self._commit_changes()
            await self._push_changes()
            logging.info("Successfully synced knowledge base to GitHub")
        except Exception as e:
            logging.exception("GitHub sync failed")
            raise GitSyncError("Failed to sync with GitHub") from e

    async def _init_repo(self) -> None:
        """Initialize or get existing repo."""
        try:
            # Run in thread pool to avoid blocking
            self._repo = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: Repo(self.repo_path) if Path(self.repo_path / '.git').exists() 
                else Repo.init(self.repo_path)
            )
            logging.info(f"Initialized git repo at {self.repo_path}")
        except Exception as e:
            raise GitSyncError(f"Failed to initialize git repo at {self.repo_path}") from e

    async def _configure_repo(self) -> None:
        """Configure git repository settings."""
        try:
            # Configure user
            await self._git_command('config', 'user.name', self.config.github_user_name)
            await self._git_command('config', 'user.email', self.config.github_user_email)

            # Configure remote
            remote_url = str(self.config.github_repo_url)
            if not remote_url.startswith('https://'):
                remote_url = f"https://{self.config.github_token}@{remote_url.split('://')[-1]}"

            # Check/update remote
            try:
                await self._git_command('remote', 'remove', 'origin')
            except GitCommandError:
                pass  # Ignore if remote doesn't exist
            await self._git_command('remote', 'add', 'origin', remote_url)
            logging.info("Configured git repository settings")
        except Exception as e:
            raise GitSyncError("Failed to configure git repository") from e

    async def _stage_changes(self) -> None:
        """Stage all changes in knowledge base directory."""
        try:
            await self._git_command('add', '-A')
            status = await self._git_command('status', '--porcelain')
            if not status:
                logging.info("No changes to commit")
                return
            logging.info(f"Staged changes: \n{status}")
        except Exception as e:
            raise GitSyncError("Failed to stage changes") from e

    async def _commit_changes(self) -> None:
        """Commit staged changes."""
        try:
            status = await self._git_command('status', '--porcelain')
            if not status:
                return
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            message = f"Update knowledge base - {timestamp}"
            await self._git_command('commit', '-m', message)
            logging.info(f"Committed changes: {message}")
        except Exception as e:
            raise GitSyncError("Failed to commit changes") from e

    async def _push_changes(self) -> None:
        """Push changes to remote repository."""
        try:
            await self._git_command('push', '-u', 'origin', 'main', '--force')
            logging.info("Successfully pushed changes to GitHub")
        except Exception as e:
            raise GitSyncError("Failed to push changes to GitHub") from e

    async def _git_command(self, *args):
        """Execute a git command asynchronously."""
        def func():
            return self._repo.git.execute(['git'] + list(args))
        return await asyncio.to_thread(func)
