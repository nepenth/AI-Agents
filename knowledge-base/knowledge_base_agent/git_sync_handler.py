import logging
from knowledge_base_agent.git_helper import push_to_github

class GitSyncHandler:
    def __init__(self, config):
        self.config = config

    async def sync_to_github(self):
        """Sync changes to GitHub repository"""
        try:
            await push_to_github(
                self.config.github_token,
                self.config.github_user_name,
                self.config.github_user_email,
                self.config.github_repo_url
            )
        except Exception as e:
            logging.error(f"Failed to sync to GitHub: {e}")
            raise 