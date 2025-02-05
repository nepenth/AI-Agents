import subprocess
import logging
from pathlib import Path

def run_git_command(cmd, cwd, capture_output=False):
    try:
        if capture_output:
            result = subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, cwd=cwd, check=True)
            return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Git command {' '.join(cmd)} failed: {e}")
        return None

def push_to_github(config):
    knowledge_base_dir = config.knowledge_base_dir
    remote_url = config.github_repo_url.replace("https://", f"https://{config.github_token}@")

    if not (knowledge_base_dir / ".git").exists():
        run_git_command(["git", "init", "-b", "main"], cwd=knowledge_base_dir)
        run_git_command(["git", "remote", "add", "origin", remote_url], cwd=knowledge_base_dir)

    run_git_command(["git", "config", "user.name", config.github_user_name], cwd=knowledge_base_dir)
    run_git_command(["git", "config", "user.email", config.github_user_email], cwd=knowledge_base_dir)
    run_git_command(["git", "add", "-A"], cwd=knowledge_base_dir)

    commit_message = f"Update knowledge base: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    run_git_command(["git", "commit", "-m", commit_message], cwd=knowledge_base_dir)
    run_git_command(["git", "push", "origin", "main", "--force"], cwd=knowledge_base_dir)
