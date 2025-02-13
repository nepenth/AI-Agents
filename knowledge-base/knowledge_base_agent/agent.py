from pathlib import Path
import logging
from typing import Optional

from knowledge_base_agent.category_manager import CategoryManager
from knowledge_base_agent.tweet_manager import TweetManager
from knowledge_base_agent.markdown_writer import MarkdownWriter
from knowledge_base_agent.git_helper import push_to_github
from knowledge_base_agent.exceptions import KnowledgeBaseError

class KnowledgeBaseAgent:
    def __init__(self, root_dir: Path, github_config: dict):
        self.root_dir = root_dir
        self.github_config = github_config  # Store GitHub configuration
        
        # Initialize logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Ensure root directory exists
        self.root_dir.mkdir(exist_ok=True)
        logging.info(f"Ensured root directory exists: {self.root_dir}")
        
        # Initialize managers with proper paths
        data_dir = Path("data")  # Use data directory for configuration files
        data_dir.mkdir(exist_ok=True)  # Ensure data directory exists
        
        categories_file = data_dir / 'categories.json'
        logging.info(f"Initializing CategoryManager with categories file: {categories_file}")
        self.category_manager = CategoryManager(categories_file)
        
        logging.info("Initializing TweetManager")
        self.tweet_manager = TweetManager(root_dir)
        
        logging.info("Initializing MarkdownWriter")
        self.markdown_writer = MarkdownWriter()

    def _git_push_changes(self) -> bool:
        """Push changes to the git repository using git_helper."""
        try:
            push_to_github(
                knowledge_base_dir=self.root_dir,
                github_repo_url=self.github_config['repo_url'],
                github_token=self.github_config['token'],
                git_user_name=self.github_config['user_name'],
                git_user_email=self.github_config['user_email']
            )
            return True
        except KnowledgeBaseError as e:
            print(f"❌ Failed to push to GitHub: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error during git operations: {e}")
            return False

    def process_tweets(self):
        """Process any unprocessed tweets and update the knowledge base"""
        try:
            unprocessed = self.tweet_manager.get_unprocessed_tweets()
            if not unprocessed:
                logging.info("No unprocessed tweets found")
            else:    
                logging.info(f"Processing {len(unprocessed)} unprocessed tweets...")
                
                for tweet in unprocessed:
                    try:
                        self._process_single_tweet(tweet)
                    except Exception as e:
                        logging.error(f"Failed to process tweet: {e}")

            changes_made = False  # Track if any changes were made
            
            # Always prompt for additional actions
            while True:
                print("\nWhat would you like to do?")
                print("1. Re-process existing knowledge items")
                print("2. Re-generate knowledge base README")
                print("3. Push/sync changes to repository")
                print("4. Exit")
                
                choice = input("\nEnter your choice (1-4): ").strip()
                
                if choice == "1":
                    logging.info("Re-processing existing knowledge items...")
                    # Implement re-processing logic
                    changes_made = True
                    pass
                elif choice == "2":
                    print("\nRegenerating knowledge base README...")
                    try:
                        self.markdown_writer.generate_root_readme(self.root_dir, self.category_manager)
                        print("✅ Knowledge base README has been successfully regenerated!")
                        print(f"   Location: {self.root_dir / 'README.md'}")
                        changes_made = True
                    except Exception as e:
                        print(f"❌ Failed to regenerate README: {e}")
                    print("\nPress Enter to continue...")
                    input()
                elif choice == "3":
                    if changes_made:
                        print("\nWould you like to push the changes to the repository? (y/n)")
                        if input().lower().strip() == 'y':
                            logging.info("Pushing changes to repository...")
                            if self._git_push_changes():
                                print("Changes pushed successfully!")
                        else:
                            print("Changes were not pushed.")
                    else:
                        print("No changes have been made to push.")
                elif choice == "4":
                    if changes_made:
                        print("\nYou have unsaved changes. Would you like to push them before exiting? (y/n)")
                        if input().lower().strip() == 'y':
                            logging.info("Pushing changes to repository...")
                            if self._git_push_changes():
                                print("Changes pushed successfully!")
                    logging.info("Exiting...")
                    break
                else:
                    print("Invalid choice. Please try again.")
        
        except Exception as e:
            logging.error(f"Error during processing: {e}")
            raise

    def _process_single_tweet(self, tweet):
        """Process a single tweet and add it to the knowledge base"""
        # Implementation for processing individual tweets
        pass 