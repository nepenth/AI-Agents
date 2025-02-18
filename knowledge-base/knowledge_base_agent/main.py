"""
Entry point for the knowledge base agent.

Handles initialization, configuration, and the main execution loop
with proper error handling and logging.
"""

import asyncio
import logging
import sys
from typing import List, Optional
from pathlib import Path
from datetime import datetime

from .config import Config, setup_logging
from .agent import KnowledgeBaseAgent
from .exceptions import KnowledgeBaseError, ConfigurationError
from .prompts import UserPreferences, prompt_for_preferences
from .state_manager import StateManager

def setup_logging():
    """Configure logging to output to both file and console."""
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(message)s')  # Simplified console output

    # File handler
    file_handler = logging.FileHandler('agent_program.log')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)  # Only show INFO and above on console

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

async def setup_directories(config: Config) -> None:
    """Ensure all required directories exist."""
    try:
        directories = [
            config.knowledge_base_dir,
            config.data_processing_dir,
            config.media_cache_dir
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logging.debug(f"Ensured directory exists: {directory}")
    except Exception as e:
        raise ConfigurationError(f"Failed to create directories: {e}")

async def load_config() -> Config:
    """
    Load and initialize configuration.
    
    Returns:
        Config: Initialized configuration object
        
    Raises:
        ConfigurationError: If configuration loading fails
    """
    try:
        config = Config()  # Loads from environment variables
        await setup_directories(config)
        setup_logging()
        return config
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration: {e}")

async def initialize_state(config: Config) -> StateManager:
    """Initialize state management."""
    try:
        state_manager = StateManager(config)
        await state_manager.initialize()
        return state_manager
    except Exception as e:
        raise KnowledgeBaseError(f"Failed to initialize state: {e}")

async def run_agent(config: Config, preferences: UserPreferences) -> None:
    """Initialize and run the agent with user preferences."""
    try:
        agent = KnowledgeBaseAgent(config)
        await agent.run(preferences)
        
        # Log final statistics
        metrics = agent.stats.get_performance_metrics()
        logging.info("=== Processing Statistics ===")
        for metric, value in metrics.items():
            logging.info(f"{metric}: {value}")
            
        # Save stats report
        await agent.stats.save_report(config.data_processing_dir / "processing_stats.json")
        
    except Exception as e:
        logging.exception("Agent run failed")
        raise KnowledgeBaseError("Failed to run agent") from e

async def cleanup(config: Config) -> None:
    """Cleanup temporary files and resources."""
    try:
        temp_files = list(config.data_processing_dir.glob("*.temp"))
        for temp_file in temp_files:
            temp_file.unlink()
        logging.info("Cleanup completed")
    except Exception as e:
        logging.warning(f"Cleanup failed: {e}")

async def main() -> None:
    """Main entry point for the knowledge base agent."""
    try:
        # Initialize configuration only
        config = await load_config()
        
        logging.info("\n=== New Agent Run Started ===")
        
        # Get user preferences before any processing
        preferences = prompt_for_preferences(config)
        
        # Log selected preferences immediately
        logging.info("=== User Selected Preferences ===")
        logging.info(f"- Fetch new bookmarks: {preferences.update_bookmarks}")
        logging.info(f"- Re-review processed tweets: {preferences.review_existing}")
        logging.info(f"- Re-cache all tweet data: {preferences.recreate_tweet_cache}")
        logging.info(f"- Regenerate README: {preferences.regenerate_readme}")
        
        # Initialize agent
        agent = KnowledgeBaseAgent(config)
        await agent.initialize()
        
        # Run agent with preferences
        logging.info("=== Starting Agent Operations ===")
        await agent.run(preferences)
        
    except Exception as e:
        logging.error(f"Agent execution failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
