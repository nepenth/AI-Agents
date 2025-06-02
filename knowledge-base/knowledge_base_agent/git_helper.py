import asyncio
import logging
from typing import Optional
from pathlib import Path
from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError
import shutil
import os # Added for os.environ
import subprocess # Added for direct git operations
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

    def _configure_git(self) -> None:
        """Configure git with user credentials and initialize if needed using direct subprocess calls."""
        print("GIT_HELPER_PRINT: _configure_git called") # Force print
        self.logger.info("GIT_HELPER_LOGGER: _configure_git called - INFO") # Standard logger
        self.logger.debug("GIT_HELPER_LOGGER: _configure_git called - DEBUG") # Standard logger
        
        original_level = self.logger.level
        if self.logger.level == 0 or self.logger.level > logging.DEBUG:
            self.logger.setLevel(logging.DEBUG) 
            self.logger.debug("GIT_HELPER_LOGGER: Temporarily set git_helper logger level to DEBUG for _configure_git")

        try:
            print("GIT_HELPER_PRINT: Checking for git executable...") # Force print
            git_executable = shutil.which("git")
            print(f"GIT_HELPER_PRINT: shutil.which('git') returned: {git_executable}") # Force print
            
            if not git_executable:
                self.logger.error("Git executable not found in PATH. Please ensure Git is installed and accessible by the Python process.")
                print("GIT_HELPER_PRINT: Git executable NOT FOUND in PATH.") # Force print
                raise GitSyncError("Git executable not found in PATH.")
            
            self.logger.info(f"Found Git executable at: {git_executable}. Setting GIT_PYTHON_GIT_EXECUTABLE.")
            print(f"GIT_HELPER_PRINT: Found Git executable at: {git_executable}. Setting GIT_PYTHON_GIT_EXECUTABLE.") # Force print
            os.environ['GIT_PYTHON_GIT_EXECUTABLE'] = git_executable

            # Validate GitHub configuration (logging existing checks)
            if not self.config.github_token: self.logger.warning("Missing GITHUB_TOKEN")
            if not self.config.github_user_name: self.logger.warning("Missing GITHUB_USER_NAME")
            if not self.config.github_user_email: self.logger.warning("Missing GITHUB_USER_EMAIL")
            if not self.config.github_repo_url: self.logger.warning("Missing GITHUB_REPO_URL")
            
            # Ensure repo_dir exists
            self.repo_dir.mkdir(parents=True, exist_ok=True)
            
            # Direct subprocess calls for Git operations
            if not (self.repo_dir / '.git').exists():
                self.logger.info(f"GIT_HELPER_LOGGER: Attempting direct subprocess call for 'git init' in {self.repo_dir}")
                print(f"GIT_HELPER_PRINT: Attempting direct subprocess call for 'git init' in {self.repo_dir}")
                result = subprocess.run(
                    [git_executable, "init"],
                    cwd=str(self.repo_dir),
                    capture_output=True,
                    text=True,
                    check=True,
                    shell=False
                )
                self.logger.info(f"GIT_HELPER_LOGGER: Direct 'git init' successful. Output: {result.stdout}")
                print(f"GIT_HELPER_PRINT: Direct 'git init' successful. Output: {result.stdout}")
            else:
                self.logger.info(f"GIT_HELPER_LOGGER: Found existing .git directory at {self.repo_dir}")
                print(f"GIT_HELPER_PRINT: Found existing .git directory at {self.repo_dir}")
            
            # Configure user name and email
            self.logger.info("GIT_HELPER_LOGGER: Configuring user name and email via direct subprocess")
            print("GIT_HELPER_PRINT: Configuring user name and email via direct subprocess")
            subprocess.run(
                [git_executable, "config", "user.name", self.config.github_user_name],
                cwd=str(self.repo_dir),
                check=True,
                shell=False
            )
            subprocess.run(
                [git_executable, "config", "user.email", self.config.github_user_email],
                cwd=str(self.repo_dir),
                check=True,
                shell=False
            )
            self.logger.info("GIT_HELPER_LOGGER: User name and email configured")
            print("GIT_HELPER_PRINT: User name and email configured")
            
            # Set up remote origin
            remote_url = str(self.config.github_repo_url).replace('https://', f'https://{self.config.github_token}@')
            print(f"GIT_HELPER_PRINT: Configured remote URL (with token): {remote_url[:remote_url.find('@') + 1]}...") # Print part of URL
            self.logger.info("GIT_HELPER_LOGGER: Setting up remote origin via direct subprocess")
            print("GIT_HELPER_PRINT: Setting up remote origin via direct subprocess")
            # First, check if remote exists
            remotes_result = subprocess.run(
                [git_executable, "remote"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                check=False,
                shell=False
            )
            remotes = remotes_result.stdout.splitlines() if remotes_result.returncode == 0 else []
            if 'origin' not in remotes:
                print("GIT_HELPER_PRINT: Creating remote 'origin' via direct subprocess")
                subprocess.run(
                    [git_executable, "remote", "add", "origin", remote_url],
                    cwd=str(self.repo_dir),
                    check=True,
                    shell=False
                )
            else:
                print("GIT_HELPER_PRINT: Remote 'origin' exists. Checking URL via direct subprocess")
                remote_url_result = subprocess.run(
                    [git_executable, "remote", "get-url", "origin"],
                    cwd=str(self.repo_dir),
                    capture_output=True,
                    text=True,
                    check=False,
                    shell=False
                )
                if remote_url_result.returncode == 0 and remote_url_result.stdout.strip() != remote_url:
                    print("GIT_HELPER_PRINT: Updating remote 'origin' URL via direct subprocess")
                    subprocess.run(
                        [git_executable, "remote", "set-url", "origin", remote_url],
                        cwd=str(self.repo_dir),
                        check=True,
                        shell=False
                    )
                else:
                    print("GIT_HELPER_PRINT: Remote 'origin' URL is correct or get-url failed")
            self.logger.info("GIT_HELPER_LOGGER: Remote origin configured")
            print("GIT_HELPER_PRINT: Remote origin configured")
            
            # Check and configure 'main' branch
            print("GIT_HELPER_PRINT: Checking 'main' branch via direct subprocess")
            branches_result = subprocess.run(
                [git_executable, "branch", "--list"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                check=False,
                shell=False
            )
            branches = [b.strip('* ').strip() for b in branches_result.stdout.splitlines()] if branches_result.returncode == 0 else []
            if not branches:  # No branches, likely empty repo
                print("GIT_HELPER_PRINT: Repository is empty. Creating initial commit via direct subprocess")
                initial_commit_path = self.repo_dir / ".initial_commit_placeholder"
                with open(initial_commit_path, "w") as f:
                    f.write("Initial commit placeholder.")
                subprocess.run(
                    [git_executable, "add", str(initial_commit_path)],
                    cwd=str(self.repo_dir),
                    check=True,
                    shell=False
                )
                subprocess.run(
                    [git_executable, "commit", "-m", "Initial commit"],
                    cwd=str(self.repo_dir),
                    check=True,
                    shell=False
                )
                initial_commit_path.unlink()
                print("GIT_HELPER_PRINT: Initial commit created")
            if 'main' not in branches:
                print("GIT_HELPER_PRINT: 'main' branch not found. Creating via direct subprocess")
                subprocess.run(
                    [git_executable, "checkout", "-B", "main"],
                    cwd=str(self.repo_dir),
                    check=True,
                    shell=False
                )
            else:
                # Check current branch
                current_branch_result = subprocess.run(
                    [git_executable, "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(self.repo_dir),
                    capture_output=True,
                    text=True,
                    check=False,
                    shell=False
                )
                if current_branch_result.returncode == 0 and current_branch_result.stdout.strip() != 'main':
                    print(f"GIT_HELPER_PRINT: Current branch is {current_branch_result.stdout.strip()}. Checking out 'main' via direct subprocess")
                    subprocess.run(
                        [git_executable, "checkout", "main"],
                        cwd=str(self.repo_dir),
                        check=True,
                        shell=False
                    )
                else:
                    print("GIT_HELPER_PRINT: Already on 'main' branch or rev-parse failed")
            print("GIT_HELPER_PRINT: 'main' branch configured via direct subprocess")
            self.logger.info("GIT_HELPER_LOGGER: 'main' branch configured")
            
            # Since we've bypassed GitPython for critical operations, we don't need to create a Repo object
            # But for compatibility with any later code that might expect self.repo, we'll try to create it
            try:
                self.repo = Repo(str(self.repo_dir)) # No shell=True for Repo() constructor
                print(f"GIT_HELPER_PRINT: Repo() call completed for compatibility. self.repo is {self.repo}")
                self.logger.debug(f"Git repository object created for compatibility: {self.repo}")
            except Exception as e_repo:
                print(f"GIT_HELPER_PRINT: Failed to create Repo object for compatibility: {e_repo}")
                self.logger.warning(f"GIT_HELPER_LOGGER: Failed to create Repo object for compatibility, but direct Git operations succeeded: {e_repo}")
                self.repo = None  # Explicitly set to None to indicate we're not using GitPython for operations

        except GitCommandError as e:
            self.logger.error(f"Git command failed during Git configuration: {e}", exc_info=True)
            print(f"GIT_HELPER_PRINT: GitCommandError: {e}")
            raise GitSyncError(f"Git command failed: {e}") from e
        except (InvalidGitRepositoryError, NoSuchPathError) as e:
            self.logger.error(f"Git repository error during configuration: {e}", exc_info=True)
            print(f"GIT_HELPER_PRINT: InvalidGitRepositoryError/NoSuchPathError: {e}")
            raise GitSyncError(f"Git repository error: {e}") from e
        except TypeError as e: 
            self.logger.error(f"Outer TypeError during Git configuration at {self.repo_dir}: {e}.", exc_info=True)
            print(f"GIT_HELPER_PRINT: Outer TypeError: {e}")
            raise GitSyncError(f"Outer TypeError during Git configuration: {e}") from e
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Direct subprocess Git command failed: {e}. Stderr: {e.stderr}", exc_info=True)
            print(f"GIT_HELPER_PRINT: subprocess.CalledProcessError: {e}. Stderr: {e.stderr}")
            raise GitSyncError(f"Direct Git command failed: {e}") from e
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during Git configuration at {self.repo_dir}: {e}", exc_info=True)
            print(f"GIT_HELPER_PRINT: Unexpected Exception: {e}")
            raise GitSyncError(f"Failed to initialize/configure Git repo: {e}") from e
        finally:
            if self.logger.level != original_level:
                 self.logger.setLevel(original_level)
                 self.logger.debug("GIT_HELPER_LOGGER: Restored original git_helper logger level.")
            print("GIT_HELPER_PRINT: _configure_git finished.")

    def sync_to_github(self, commit_message: str = "Update knowledge base content") -> None:
        """Sync changes in kb-generated to GitHub repository using direct subprocess calls, overwriting remote state."""
        try:
            self._configure_git()
            git_executable = os.environ['GIT_PYTHON_GIT_EXECUTABLE']
            
            # Add all changes
            self.logger.info("GIT_HELPER_LOGGER: Adding all changes via direct subprocess")
            print("GIT_HELPER_PRINT: Adding all changes via direct subprocess")
            # First, ensure .gitignore excludes media files to prevent large files from being added
            self.logger.info("GIT_HELPER_LOGGER: Updating .gitignore to exclude media files")
            print("GIT_HELPER_PRINT: Updating .gitignore to exclude media files")
            gitignore_path = self.repo_dir / ".gitignore"
            media_extensions = [
                "# Ignore media files to prevent large uploads",
                "*.mp4", "*.avi", "*.mkv", "*.mov", "*.wmv", "*.flv", "*.webm",
                "*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.tiff", "*.webp",
                "*.mp3", "*.wav", "*.ogg", "*.flac"
            ]
            # Check if .gitignore exists and read its content
            existing_content = []
            if gitignore_path.exists():
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    existing_content = f.readlines()
                    # Check if media ignore rules are already present
                    if any("# Ignore media files to prevent large uploads" in line for line in existing_content):
                        self.logger.info("GIT_HELPER_LOGGER: .gitignore already has media ignore rules")
                        print("GIT_HELPER_PRINT: .gitignore already has media ignore rules")
                    else:
                        # Append media ignore rules
                        with open(gitignore_path, "a", encoding="utf-8") as f:
                            f.write("\n" + "\n".join(media_extensions) + "\n")
                        self.logger.info("GIT_HELPER_LOGGER: Added media ignore rules to .gitignore")
                        print("GIT_HELPER_PRINT: Added media ignore rules to .gitignore")
            else:
                # Create .gitignore with media ignore rules
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(media_extensions) + "\n")
                self.logger.info("GIT_HELPER_LOGGER: Created .gitignore with media ignore rules")
                print("GIT_HELPER_PRINT: Created .gitignore with media ignore rules")
            
            # Now add all changes (respecting .gitignore)
            subprocess.run(
                [git_executable, "add", "."],
                cwd=str(self.repo_dir),
                check=True,
                shell=False
            )
            
            # Check if there are changes to commit
            status_result = subprocess.run(
                [git_executable, "status", "--porcelain"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                check=False,
                shell=False
            )
            if status_result.returncode == 0 and status_result.stdout.strip():
                # There are changes to commit
                self.logger.info(f"GIT_HELPER_LOGGER: Committing changes with message: {commit_message}")
                print(f"GIT_HELPER_PRINT: Committing changes with message: {commit_message}")
                subprocess.run(
                    [git_executable, "commit", "-m", commit_message],
                    cwd=str(self.repo_dir),
                    check=True,
                    shell=False
                )
                self.logger.debug(f"Committed changes with message: {commit_message}")
            else:
                self.logger.info("GIT_HELPER_LOGGER: No changes to commit")
                print("GIT_HELPER_PRINT: No changes to commit")
            
            # Force push to overwrite remote state with retry mechanism
            self.logger.info("GIT_HELPER_LOGGER: Force pushing to remote repository via direct subprocess with retries")
            print("GIT_HELPER_PRINT: Force pushing to remote repository via direct subprocess with retries")
            # Increase http.postBuffer to handle large pushes or timeouts
            self.logger.info("GIT_HELPER_LOGGER: Setting http.postBuffer to 52428800 (50MB) for large pushes")
            print("GIT_HELPER_PRINT: Setting http.postBuffer to 52428800 (50MB) for large pushes")
            subprocess.run(
                [git_executable, "config", "http.postBuffer", "52428800"],
                cwd=str(self.repo_dir),
                check=True,
                shell=False
            )
            # Additional configurations to optimize push
            self.logger.info("GIT_HELPER_LOGGER: Setting additional Git configurations for push optimization")
            print("GIT_HELPER_PRINT: Setting additional Git configurations for push optimization")
            subprocess.run(
                [git_executable, "config", "pack.packSizeLimit", "50m"],
                cwd=str(self.repo_dir),
                check=True,
                shell=False
            )
            subprocess.run(
                [git_executable, "config", "pack.threads", "1"],
                cwd=str(self.repo_dir),
                check=True,
                shell=False
            )
            subprocess.run(
                [git_executable, "config", "pack.compression", "1"],
                cwd=str(self.repo_dir),
                check=True,
                shell=False
            )
            # Retry loop for push operation
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    push_result = subprocess.run(
                        [git_executable, "push", "origin", "main", "--force"],
                        cwd=str(self.repo_dir),
                        capture_output=True,
                        text=True,
                        check=True,
                        shell=False
                    )
                    self.logger.debug(f"GIT_HELPER_LOGGER: Force-pushed changes to remote repository. Output: {push_result.stdout}")
                    print(f"GIT_HELPER_PRINT: Force-pushed changes to remote repository. Output: {push_result.stdout}")
                    self.logger.info("Successfully synced to GitHub via direct subprocess")
                    print("GIT_HELPER_PRINT: Successfully synced to GitHub via direct subprocess")
                    break  # Exit loop on success
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"Push attempt {attempt + 1}/{max_retries} failed: {e}. Stderr: {e.stderr}")
                    print(f"GIT_HELPER_PRINT: Push attempt {attempt + 1}/{max_retries} failed: {e}. Stderr: {e.stderr}")
                    if attempt == max_retries - 1:  # Last attempt
                        raise
                    import time
                    time.sleep(5)  # Wait before retrying
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Direct Git command failed during sync: {e}. Stderr: {e.stderr}", exc_info=True)
            print(f"GIT_HELPER_PRINT: subprocess.CalledProcessError during sync: {e}. Stderr: {e.stderr}")
            raise GitSyncError(f"Direct Git sync command failed: {e}") from e
        except Exception as e:
            self.logger.error(f"GitHub sync failed: {e}", exc_info=True)
            print(f"GIT_HELPER_PRINT: Exception during sync: {e}")
            raise GitSyncError(f"Git sync failed: {e}") from e

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