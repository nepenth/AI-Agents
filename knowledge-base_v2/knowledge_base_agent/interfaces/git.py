import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

# Import GitPython carefully, handle ImportError if not installed
try:
    import git
    from git import Repo, Actor, GitCommandError
except ImportError:
    Repo = None # Placeholder if GitPython is not installed
    Actor = None
    GitCommandError = None
    git = None
    print("WARNING: GitPython library not found. Git functionality will be disabled.")
    print("Install it using: pip install GitPython")

# Use TYPE_CHECKING to guard the imports specifically for type hints
if TYPE_CHECKING:
    # These type hints are only needed for static analysis
    from git import Repo as GitRepoType # Use an alias to avoid potential name clash if needed
    from git import Actor as GitActorType

from ..config import Config
from ..exceptions import GitError, ConfigurationError

logger = logging.getLogger(__name__)

class GitClient:
    """Handles Git operations like staging, committing, and pushing."""

    def __init__(self, config: Config):
        if Repo is None:
            raise ConfigurationError("GitPython library is required but not installed.")

        self.config = config
        self.repo_path = config.knowledge_base_dir.resolve() # Use resolved absolute path
        self.repo: Optional["GitRepoType"] = None
        self.remote_name = "origin" # Standard remote name

        if not config.git_enabled:
            logger.warning("Git synchronization is disabled in the configuration.")
            return # Don't try to initialize if disabled

        # Validate required Git config if enabled
        if not (config.github_repo_url and config.github_user_name and config.github_user_email):
             raise ConfigurationError("Git is enabled, but GITHUB_REPO_URL, GITHUB_USER_NAME, or GITHUB_USER_EMAIL is missing.")
        # Token might be optional if using SSH keys configured globally, but needed for HTTPS push usually
        if "https://" in config.github_repo_url and not config.github_token:
             logger.warning("Git is enabled with an HTTPS URL, but GITHUB_TOKEN is missing. Pushing may fail without credentials.")


        logger.info(f"GitClient initialized for repository path: {self.repo_path}")
        self._initialize_repo()


    def _initialize_repo(self):
        """Initializes the GitPython Repo object, cloning if necessary."""
        if not self.config.git_enabled: return

        try:
            if not self.repo_path.exists():
                 logger.info(f"Knowledge base directory '{self.repo_path}' does not exist. Cloning from {self.config.github_repo_url}...")
                 # Clone the repository
                 # TODO: Handle authentication for cloning (SSH keys or token for HTTPS)
                 # For now, assumes SSH key auth is set up globally if needed
                 self.repo = Repo.clone_from(self.config.github_repo_url, self.repo_path)
                 logger.info(f"Repository cloned successfully to {self.repo_path}")
            elif not (self.repo_path / ".git").exists():
                 logger.info(f"Directory '{self.repo_path}' exists but is not a Git repository. Initializing...")
                 self.repo = Repo.init(self.repo_path)
                 # Add remote if not present
                 if self.remote_name not in [r.name for r in self.repo.remotes]:
                     self.repo.create_remote(self.remote_name, self.config.github_repo_url)
                     logger.info(f"Initialized Git repo and added remote '{self.remote_name}' -> {self.config.github_repo_url}")
                 else:
                      logger.info(f"Initialized Git repo. Remote '{self.remote_name}' already exists.")
            else:
                 logger.debug(f"Opening existing Git repository at {self.repo_path}")
                 self.repo = Repo(self.repo_path)
                 # Ensure remote URL matches config?
                 if self.remote_name in [r.name for r in self.repo.remotes]:
                     if self.repo.remotes[self.remote_name].url != self.config.github_repo_url:
                         logger.warning(f"Remote '{self.remote_name}' URL ({self.repo.remotes[self.remote_name].url}) does not match config ({self.config.github_repo_url}). Updating remote URL.")
                         self.repo.delete_remote(self.remote_name)
                         self.repo.create_remote(self.remote_name, self.config.github_repo_url)
                 elif self.config.github_repo_url:
                      logger.warning(f"Remote '{self.remote_name}' not found in existing repo. Adding remote...")
                      self.repo.create_remote(self.remote_name, self.config.github_repo_url)


            # Configure user name and email for commits
            with self.repo.config_writer() as cw:
                 cw.set_value("user", "name", self.config.github_user_name)
                 cw.set_value("user", "email", self.config.github_user_email)
            logger.debug(f"Git user configured as: {self.config.github_user_name} <{self.config.github_user_email}>")

        except GitCommandError as e:
            logger.error(f"Git command failed during repository initialization: {e.stderr}")
            raise GitError(f"Failed to initialize/open repository at {self.repo_path}: {e.stderr}", original_exception=e) from e
        except Exception as e:
            logger.error(f"Unexpected error initializing repository: {e}", exc_info=True)
            raise GitError(f"Unexpected error initializing repository: {e}", original_exception=e) from e

    def _check_enabled_and_repo(self) -> "GitRepoType":
        """Checks if Git is enabled and repo is initialized."""
        if not self.config.git_enabled:
            raise GitError("Git operations called but Git is disabled in config.")
        if self.repo is None:
            # Attempt re-initialization? Or just raise.
            logger.error("Git repository object is not initialized.")
            raise GitError("Git repository not initialized. Check previous logs for errors.")
        return self.repo

    async def commit_and_push_changes(self, commit_message: str = "Automated knowledge base update") -> bool:
        """
        Stages all changes, commits them, and pushes to the remote repository.

        Uses asyncio.to_thread to run blocking GitPython calls.

        Args:
            commit_message: The message for the Git commit.

        Returns:
            True if changes were committed and pushed successfully, False otherwise.
        """
        try:
            repo_obj = await asyncio.to_thread(self._check_enabled_and_repo)

            # Run Git operations in a separate thread
            success = await asyncio.to_thread(
                self._sync_git_operations, repo_obj, commit_message
            )
            return success

        except GitError as e:
             # Catch errors raised by _check_enabled_and_repo or _sync_git_operations
             logger.error(f"Git commit/push failed: {e}")
             return False
        except Exception as e:
             logger.error(f"Unexpected error during Git commit/push: {e}", exc_info=True)
             return False # Or raise a GitError

    def _sync_git_operations(self, repo: "GitRepoType", commit_message: str) -> bool:
        """Synchronous helper function containing the actual GitPython calls."""
        try:
            repo.git.update_environment(
                GIT_SSH_COMMAND=f"ssh -o StrictHostKeyChecking=no -i {os.path.expanduser('~/.ssh/id_rsa')}"
            )

            # Check for changes (staged or unstaged)
            if not repo.is_dirty(untracked_files=True):
                logger.info("No changes detected in the repository. Nothing to commit or push.")
                return True # No changes is considered success

            logger.info("Staging all changes...")
            repo.git.add(A=True) # Stage all changes (git add -A)

            # Check if there's anything actually staged to commit
            staged_diff = repo.index.diff("HEAD")
            unstaged_diff_after_add = repo.index.diff(None) # Compare index to working tree
            is_newly_initialized = not repo.head.is_valid() # Check if repo has any commits yet

            # Only commit if there are staged changes or if it's the very first commit in an initialized repo
            if staged_diff or unstaged_diff_after_add or is_newly_initialized:
                 logger.info(f"Committing changes with message: '{commit_message}'")
                 committer = Actor(self.config.github_user_name, self.config.github_user_email)
                 repo.index.commit(commit_message, author=committer, committer=committer)
                 logger.info("Changes committed successfully.")
            else:
                 logger.info("No staged changes found after 'git add'. Skipping commit.")
                 # If repo wasn't dirty initially but nothing got staged, maybe clean up state?
                 # repo.git.reset('--hard') #? Risky?

            # Push to remote
            if self.remote_name in [r.name for r in repo.remotes]:
                remote = repo.remotes[self.remote_name]
                logger.info(f"Pushing changes to remote '{self.remote_name}' ({remote.url})...")

                # --- Handle Authentication for Push ---
                push_info_list = []
                if "https://" in remote.url and self.config.github_token:
                    # Construct URL with token for HTTPS push
                    # Be cautious about logging the tokenized URL
                    token = self.config.github_token.get_secret_value()
                    push_url = remote.url.replace("https://", f"https://oauth2:{token}@")
                    logger.debug(f"Attempting push via HTTPS with token to {remote.url}") # Log original URL
                    # Pushing to a potentially modified URL might require finding the right refspec
                    current_branch = repo.active_branch.name
                    push_info_list = remote.push(refspec=f"{current_branch}:{current_branch}", push_url=push_url)

                else:
                    # Assume SSH key authentication is configured globally
                    logger.debug("Attempting push via configured remote URL (likely SSH)")
                    current_branch = repo.active_branch.name
                    push_info_list = remote.push(refspec=f"{current_branch}:{current_branch}")

                # Check push results
                push_failed = False
                for push_info in push_info_list:
                     if push_info.flags & (push_info.ERROR | push_info.REJECTED):
                         logger.error(f"Failed to push to remote '{self.remote_name}': {push_info.summary}")
                         push_failed = True
                if not push_failed:
                     logger.info("Changes pushed successfully.")
                     return True
                else:
                     raise GitError(f"Push to remote '{self.remote_name}' failed. Check logs for details.")

            else:
                logger.warning(f"Remote '{self.remote_name}' not configured. Cannot push.")
                # Consider this a success if commit worked but push wasn't possible? Or failure?
                # Let's treat it as a warning but overall success for the commit part.
                return True # Or False if push is mandatory

        except GitCommandError as e:
            # Catch errors from git add, commit, push
            logger.error(f"Git command failed: {e.command} - {e.stderr}")
            raise GitError(f"Git operation failed: {e.stderr}", original_exception=e) from e
        except Exception as e:
             # Catch other unexpected errors
             logger.error(f"Unexpected error during Git operations: {e}", exc_info=True)
             raise GitError(f"Unexpected Git error: {e}", original_exception=e) from e

    async def check_repo_status(self) -> dict:
        """Gets the status of the repository (async wrapper)."""
        try:
            repo_obj = await asyncio.to_thread(self._check_enabled_and_repo)
            status_info = await asyncio.to_thread(self._sync_get_status, repo_obj)
            return status_info
        except GitError as e:
            logger.error(f"Failed to get repo status: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error getting repo status: {e}", exc_info=True)
            return {"error": f"Unexpected error: {e}"}

    def _sync_get_status(self, repo: "GitRepoType") -> dict:
        """Synchronous helper to get repo status."""
        status = {
            "is_dirty": repo.is_dirty(untracked_files=True),
            "untracked_files": list(repo.untracked_files),
            "staged_changes": [item.a_path for item in repo.index.diff("HEAD")],
            "unstaged_changes": [item.a_path for item in repo.index.diff(None)],
            "active_branch": None,
            "last_commit": None,
            "remote_url": None,
        }
        try:
            status["active_branch"] = repo.active_branch.name
            last_commit = repo.head.commit
            status["last_commit"] = {
                "hexsha": last_commit.hexsha[:8],
                "author": str(last_commit.author),
                "date": last_commit.authored_datetime.isoformat(),
                "message": last_commit.message.strip().split('\n')[0], # First line
            }
        except TypeError: # Handle detached HEAD state
            status["active_branch"] = "DETACHED HEAD"
            # Might need specific handling to get last commit SHA if detached
        except Exception as e:
             logger.warning(f"Could not determine branch or last commit: {e}")

        if self.remote_name in [r.name for r in repo.remotes]:
             status["remote_url"] = repo.remotes[self.remote_name].url

        return status
