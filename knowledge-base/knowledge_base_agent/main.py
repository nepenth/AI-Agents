"""
Entry point for the knowledge base agent.

Handles initialization, configuration, and the main execution loop
with proper error handling and logging.
"""

import asyncio
import logging
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
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(message)s')

    file_handler = logging.FileHandler('agent_program.log')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)

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
        logging.error(f"Failed to create directories: {e}")
        raise ConfigurationError(f"Failed to create directories: {e}")

async def load_config() -> Config:
    """Load and initialize configuration."""
    try:
        config = Config()
        await setup_directories(config)
        setup_logging()
        logging.info("Configuration loaded successfully")
        return config
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        raise ConfigurationError(f"Failed to load configuration: {e}")

async def run_agent(agent: KnowledgeBaseAgent, preferences: UserPreferences) -> None:
    """Run the agent with user preferences."""
    try:
        await agent.run(preferences)
        
        # Log final statistics
        metrics = agent.stats.get_performance_metrics()
        logging.info("=== Processing Statistics ===")
        for metric, value in metrics.items():
            logging.info(f"{metric}: {value}")
        
        agent.stats.save_report(agent.config.data_processing_dir / "processing_stats.json")
        logging.info("Agent run completed successfully")
        
    except Exception as e:
        logging.error(f"Agent run failed: {e}")
        raise KnowledgeBaseError("Failed to run agent") from e

async def cleanup(config: Config) -> None:
    """Cleanup temporary files and resources."""
    try:
        temp_files = list(config.data_processing_dir.glob("*.temp"))
        for temp_file in temp_files:
            temp_file.unlink()
            logging.debug(f"Removed temporary file: {temp_file}")
        logging.info("Cleanup completed")
    except Exception as e:
        logging.warning(f"Cleanup failed: {e}")

async def main() -> None:
    """Main entry point for the knowledge base agent."""
    try:
        config = await load_config()
        
        logging.info("\n=== New Agent Run Started ===")
        
        preferences = prompt_for_preferences(config)
        
        logging.info("=== User Selected Preferences ===")
        logging.info(f"- Fetch new bookmarks: {preferences.update_bookmarks}")
        logging.info(f"- Re-review processed tweets: {preferences.review_existing}")
        logging.info(f"- Re-cache all tweet data: {preferences.recreate_tweet_cache}")
        logging.info(f"- Regenerate README: {preferences.regenerate_readme}")
        
        logging.info("Initializing agent...")
        agent = KnowledgeBaseAgent(config)
        await agent.initialize()

        logging.info("=== Starting Agent Operations ===")
        await run_agent(agent, preferences)
        
    except Exception as e:
        logging.error(f"Agent execution failed: {str(e)}")
        raise
    finally:
        if 'agent' in locals():
            await agent.http_client.close()
            logging.debug("HTTP client session closed")
        await cleanup(config)

if __name__ == "__main__":
    asyncio.run(main())