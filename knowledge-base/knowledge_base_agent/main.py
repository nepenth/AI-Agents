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

async def setup_directories(config: Config) -> None:
    """Ensure all required directories exist."""
    try:
        directories = [
            config.knowledge_base_dir,
            config.data_processing_dir,
            config.cache_dir,
            config.log_dir
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
        setup_logging(config.log_dir / "agent.log")
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
    """
    Initialize and run the agent with user preferences.
    
    Args:
        config: Configuration object
        preferences: User preferences for processing
        
    Raises:
        KnowledgeBaseError: If agent execution fails
    """
    try:
        agent = KnowledgeBaseAgent(config)
        await agent.run()
        logging.info("Agent run completed successfully")
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
    """
    Main entry point for the knowledge base agent.
    
    Handles the complete execution flow:
    1. Configuration loading
    2. Directory setup
    3. State initialization
    4. User preference collection
    5. Agent execution
    6. Cleanup
    """
    start_time = datetime.now()
    try:
        # Initialize configuration
        config = await load_config()
        logging.info(f"Using Ollama URL: {config.ollama_url}")
        
        # Initialize state
        state_manager = await initialize_state(config)
        
        # Get user preferences
        preferences = prompt_for_preferences()
        
        # Run agent
        await run_agent(config, preferences)
        
        # Cleanup
        await cleanup(config)
        
        # Log execution time
        duration = datetime.now() - start_time
        logging.info(f"Execution completed in {duration}")
        
    except ConfigurationError as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(1)
    except KnowledgeBaseError as e:
        logging.error(f"Knowledge base error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        logging.info("Agent execution finished")

if __name__ == "__main__":
    asyncio.run(main())
