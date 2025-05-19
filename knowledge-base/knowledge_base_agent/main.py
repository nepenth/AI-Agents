# knowledge_base_agent/main.py
import asyncio
import logging
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import os

from .config import Config, PROJECT_ROOT as global_project_root_ref, get_project_root
from .agent import KnowledgeBaseAgent
from .exceptions import KnowledgeBaseError, ConfigurationError
from .prompts import UserPreferences, prompt_for_preferences
from .state_manager import StateManager

async def setup_directories(config: Config) -> None:
    """Ensure all required directories exist."""
    # This function is now largely handled by Config.resolve_paths and Config.ensure_directories
    # Kept for conceptual clarity if specific pre-config directory setup were ever needed.
    # For now, we can rely on Config doing this.
    try:
        config.ensure_directories() # Call the method on the config instance
        logging.debug(f"Ensured directories exist via config.ensure_directories().")
    except Exception as e:
        logging.error(f"Failed to create directories: {e}")
        raise ConfigurationError(f"Failed to create directories: {e}")

async def load_config() -> Config:
    """Load and initialize configuration."""
    global global_project_root_ref # To modify the global PROJECT_ROOT in config.py
    try:
        # Determine Project Root (parent of the directory containing this main.py)
        # This makes it robust to where the script is called from, as long as structure is maintained.
        current_file_path = Path(__file__).resolve()
        # knowledge_base_agent -> parent (project_root)
        determined_project_root = current_file_path.parent.parent
        
        # Set the global PROJECT_ROOT in config.py before Config.from_env() is called
        # if it relies on the get_project_root() default factory.
        # Config.from_env will use this or the passed argument.
        global_project_root_ref = determined_project_root
        logging.info(f"Project root determined and set globally: {determined_project_root}")

        # Use the from_env() method to load configuration from environment variables
        # Pass the determined project_root so Config uses it directly.
        config = Config.from_env(project_root_path=determined_project_root)
        
        # config.resolve_paths() is called by Pydantic's model_validator
        # config.ensure_directories() should be called after paths are resolved if needed beyond parent creation.
        config.ensure_directories() 
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