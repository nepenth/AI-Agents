from pathlib import Path
import logging
from typing import Optional

from .category_manager import CategoryManager
from .tweet_manager import TweetManager
from .markdown_writer import MarkdownWriter

class KnowledgeBaseAgent:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.category_manager = CategoryManager()
        self.tweet_manager = TweetManager(root_dir)
        self.markdown_writer = MarkdownWriter()
        
        # Initialize logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Ensure required directories exist
        self._setup_directories()
        
        # Configure categories during initialization
        self.configure_categories()

    def _setup_directories(self):
        """Ensure all required directories exist"""
        self.root_dir.mkdir(exist_ok=True)
        for category in self.category_manager.get_categories():
            category_dir = self.root_dir / category
            category_dir.mkdir(exist_ok=True)
            for subcategory in self.category_manager.get_subcategories(category):
                (category_dir / subcategory).mkdir(exist_ok=True)

    def configure_categories(self):
        """Configure all categories and subcategories upfront"""
        # Implementation as shown in previous response
        pass

    def process_tweets(self):
        """Main method to process tweets and update knowledge base"""
        self.process_unprocessed_tweets()
        self.markdown_writer.generate_root_readme(self.root_dir, self.category_manager)

    def process_unprocessed_tweets(self):
        """Process any unprocessed tweets in the queue"""
        # Implementation as shown in previous response
        pass

    def _process_single_tweet(self, tweet, category: str, subcategory: str):
        """Process a single tweet and add it to the knowledge base"""
        try:
            # Generate filename and content
            filename = self.markdown_writer.generate_filename(tweet)
            content = self.markdown_writer.generate_content(tweet)
            
            # Save to appropriate directory
            file_path = self.root_dir / category / subcategory / filename
            file_path.write_text(content)
            
            # Mark tweet as processed
            self.tweet_manager.mark_processed(tweet)
            
            logging.info(f"Successfully processed tweet to {file_path}")
            
        except Exception as e:
            logging.error(f"Failed to process tweet: {e}") 