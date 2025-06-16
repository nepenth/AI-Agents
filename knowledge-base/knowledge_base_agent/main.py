# knowledge_base_agent/main.py
import asyncio
import logging
from typing import List, Optional, Any
from pathlib import Path
from datetime import datetime
import os

from .config import Config, PROJECT_ROOT as global_project_root_ref
from .agent import KnowledgeBaseAgent
from .exceptions import KnowledgeBaseError, ConfigurationError
from .prompts import LLMPrompts, UserPreferences





async def load_config() -> Config:
    """Load configuration and initialize logging."""
    try:
        determined_project_root = Path(__file__).parent.parent
        config = Config.from_env(project_root_path=determined_project_root)
        config.ensure_directories()
        # Note: Logging is already configured by the main application
        return config
    except Exception as e:
        logging.error("Failed to load configuration", exc_info=True)
        raise

async def run_agent(agent: KnowledgeBaseAgent, preferences: UserPreferences) -> None:
    """Run the agent with user preferences."""
    try:
        await agent.run(preferences)
        metrics = agent.stats.get_performance_metrics()
        logging.info("=== Processing Statistics ===")
        for metric, value in metrics.items():
            logging.info(f"{metric}: {value}")
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

async def run_agent_from_preferences(preferences: dict, status_queue=None):
    """Configures and runs the agent based on preferences from the UI.
    
    Note: status_queue parameter is kept for backward compatibility but not used
    in the new threading approach.
    """
    config = await load_config()
    user_prefs = UserPreferences(**preferences)
    
    # This function is now only used when called directly, not in multiprocessing context
    agent = KnowledgeBaseAgent(app=None, config=config, socketio=None)
    
    await agent.initialize()
    await agent.run(user_prefs)

async def main(preferences: Optional[dict] = None):
    """Main entry point for running the agent."""
    config = None
    agent = None
    try:
        config = await load_config()

        if preferences:
            user_prefs = UserPreferences(**preferences)
        else:
            # This part can be enhanced to take CLI args
            print("Running with default preferences as no CLI arguments were provided.")
            user_prefs = UserPreferences()

        prompts = LLMPrompts(config.prompts_file)
        agent = KnowledgeBaseAgent(app=None, config=config, socketio=None)

        await agent.run(user_prefs)

    except ConfigurationError as e:
        logging.error(f"Configuration error: {e}")
    except KnowledgeBaseError as e:
        logging.error(f"Knowledge base error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred in main: {e}", exc_info=True)
    finally:
        if agent:
            if agent.http_client:
                await agent.http_client.close()
                logging.debug("HTTP client session closed")
            await agent.cleanup()
            logging.debug("Agent cleanup called.")

        if config:
            await cleanup(config)
        else:
            logging.info("Skipping file cleanup as config was not initialized")

        logging.info("Agent run finished.")

if __name__ == "__main__":
    asyncio.run(main())