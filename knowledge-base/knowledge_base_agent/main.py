# knowledge_base_agent/main.py
import asyncio
import logging
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import os

from .config import Config  # Remove setup_logging import
from .agent import KnowledgeBaseAgent
from .exceptions import KnowledgeBaseError, ConfigurationError
from .prompts import UserPreferences, prompt_for_preferences
from .state_manager import StateManager

async def setup_directories(config: Config) -> None:
    """Ensure all required directories exist."""
    try:
        directories = [config.knowledge_base_dir, config.data_processing_dir, config.media_cache_dir]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logging.debug(f"Ensured directory exists: {directory}")
    except Exception as e:
        logging.error(f"Failed to create directories: {e}")
        raise ConfigurationError(f"Failed to create directories: {e}")

async def load_config() -> Config:
    """Load and initialize configuration."""
    try:
        # Check for required environment variables
        required_env_vars = [
            "TEXT_MODEL",
            "FALLBACK_MODEL",
            "VISION_MODEL",
            "OLLAMA_URL",
            "KNOWLEDGE_BASE_DIR",
            "DATA_PROCESSING_DIR",
            "MEDIA_CACHE_DIR",
            "GIT_ENABLED"
        ]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            raise ConfigurationError(f"Missing required environment variables: {', '.join(missing_vars)}")

        # Use the from_env() method to load configuration from environment variables
        config = Config.from_env()
        await setup_directories(config)
        config.setup_logging()  # Call as method on Config instance
        logging.info("Configuration loaded successfully")
        
        # Output relevant environment variables
        logging.info("=== Environment Variables ===")
        env_vars = {
            "TEXT_MODEL": config.text_model,
            "FALLBACK_MODEL": config.fallback_model,
            "VISION_MODEL": config.vision_model,
            "OLLAMA_URL": config.ollama_url,
            "KNOWLEDGE_BASE_DIR": config.knowledge_base_dir,
            "DATA_PROCESSING_DIR": config.data_processing_dir,
            "MEDIA_CACHE_DIR": config.media_cache_dir,
            "GIT_ENABLED": str(config.git_enabled)
        }
        for var_name, var_value in env_vars.items():
            logging.info(f"{var_name}: {var_value}")
        
        return config
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        raise ConfigurationError(f"Failed to load configuration: {e}")

async def run_agent(agent: KnowledgeBaseAgent, preferences: UserPreferences) -> None:
    """Run the agent with user preferences."""
    try:
        await agent.run(preferences)
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
    """Main entry point for CLI execution."""
    config = None
    try:
        config = await load_config()
        logging.info("\n=== New Agent Run Started ===")
        
        # Prompt for user input on fetching bookmarks and reprocessing tweets
        fetch_bookmarks_input = input("Fetch new bookmarks? (y/n): ").strip().lower()
        fetch_bookmarks = fetch_bookmarks_input == 'y'
        
        preferences = UserPreferences(
            update_bookmarks=fetch_bookmarks,
            regenerate_readme=False 
        )
        
        logging.info("=== User Selected Preferences ===")
        logging.info(f"- Fetch new bookmarks: {fetch_bookmarks}")
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
        if 'agent' in locals() and agent is not None:
             if agent.http_client:
                 await agent.http_client.close()
                 logging.debug("HTTP client session closed")
             # Explicitly call agent cleanup which might handle git handler or other resources
             await agent.cleanup()
             logging.debug("Agent cleanup called.")

        # Cleanup temporary files if config was loaded
        if config is not None:
            # Call the standalone cleanup function which removes temp files
            await cleanup(config)
        else:
            logging.info("Skipping file cleanup as config was not initialized")

        logging.info("Agent execution finished.") # Add a final log message

if __name__ == "__main__":
    asyncio.run(main())