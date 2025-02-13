import subprocess
import datetime
import logging
from pathlib import Path
from .exceptions import KnowledgeBaseError

def run_git_command(cmd, cwd, capture_output: bool = False):
    try:
        if capture_output:
            result = subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, cwd=cwd, check=True)
            return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Git command {' '.join(cmd)} failed: {e}")
        raise KnowledgeBaseError(f"Git command failed: {' '.join(cmd)}") from e

def push_to_github(knowledge_base_dir: Path, github_repo_url: str, github_token: str, git_user_name: str, git_user_email: str):
    try:
        # Add debug logging
        logging.info(f"Attempting to push to GitHub: {github_repo_url}")
        
        # Ensure the remote URL includes the token
        if not github_repo_url.startswith('https://'):
            raise KnowledgeBaseError("GitHub URL must start with 'https://'")
            
        remote_url = f"https://{github_token}@{github_repo_url.split('https://')[-1]}"
        
        if not (knowledge_base_dir / ".git").exists():
            logging.info("Initializing new git repository")
            run_git_command(["git", "init", "-b", "main"], cwd=knowledge_base_dir)
            run_git_command(["git", "remote", "add", "origin", remote_url], cwd=knowledge_base_dir)
        else:
            # Update remote URL with token
            logging.info("Updating remote URL with token")
            run_git_command(["git", "remote", "set-url", "origin", remote_url], cwd=knowledge_base_dir)
        
        # Configure git
        run_git_command(["git", "config", "user.name", git_user_name], cwd=knowledge_base_dir)
        run_git_command(["git", "config", "user.email", git_user_email], cwd=knowledge_base_dir)
        
        # Check if there are changes to commit
        status = run_git_command(["git", "status", "--porcelain"], cwd=knowledge_base_dir, capture_output=True)
        if not status:
            logging.info("No changes to commit")
            return
            
        # Add and commit changes
        logging.info("Adding changes to git")
        run_git_command(["git", "add", "-A"], cwd=knowledge_base_dir)
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_message = f"Update knowledge base: {timestamp}"
        
        try:
            logging.info("Committing changes")
            run_git_command(["git", "commit", "-m", commit_message], cwd=knowledge_base_dir)
        except KnowledgeBaseError:
            logging.info("No changes to commit")
            return
            
        # Push changes
        logging.info("Pushing changes to GitHub")
        run_git_command(["git", "push", "origin", "main"], cwd=knowledge_base_dir)
        logging.info("Successfully pushed to GitHub")
        
    except Exception as e:
        logging.error(f"Failed to push to GitHub: {e}")
        raise KnowledgeBaseError(f"GitHub push failed: {e}")
