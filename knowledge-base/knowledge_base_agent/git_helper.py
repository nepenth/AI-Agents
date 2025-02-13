import subprocess
import datetime
import logging
from pathlib import Path
from .exceptions import KnowledgeBaseError
from typing import List, Optional
import git

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
        """
        Initialize or open the Git repository.
        
        Raises:
            GitError: If initialization fails
        """
        try:
            if not (self.repo_path / '.git').exists():
                self.repo = git.Repo.init(self.repo_path)
                self._setup_remote()
            else:
                self.repo = git.Repo(self.repo_path)
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
