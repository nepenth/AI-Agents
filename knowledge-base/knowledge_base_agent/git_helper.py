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
    if "@" not in github_repo_url:
        remote_url = github_repo_url.replace("https://", f"https://{github_token}@")
    else:
        remote_url = github_repo_url

    if not (knowledge_base_dir / ".git").exists():
        run_git_command(["git", "init", "-b", "main"], cwd=knowledge_base_dir)
        run_git_command(["git", "remote", "add", "origin", remote_url], cwd=knowledge_base_dir)
    run_git_command(["git", "config", "user.name", git_user_name], cwd=knowledge_base_dir)
    run_git_command(["git", "config", "user.email", git_user_email], cwd=knowledge_base_dir)
    run_git_command(["git", "config", "core.excludesFile", "/dev/null"], cwd=knowledge_base_dir)
    run_git_command(["git", "config", "core.attributesFile", "/dev/null"], cwd=knowledge_base_dir)
    run_git_command(["git", "add", "-A"], cwd=knowledge_base_dir)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_message = f"Update knowledge base: {timestamp}"
    try:
        run_git_command(["git", "commit", "-m", commit_message], cwd=knowledge_base_dir)
    except KnowledgeBaseError:
        run_git_command(["git", "commit", "--allow-empty", "-m", f"Empty commit: {timestamp}"], cwd=knowledge_base_dir)
    run_git_command(["git", "push", "origin", "main", "--force"], cwd=knowledge_base_dir)
