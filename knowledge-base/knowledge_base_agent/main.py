# knowledge_base_agent/main.py
import asyncio
import logging
from typing import List, Optional, Any, Dict
from pathlib import Path
from datetime import datetime
import os
from flask_socketio import SocketIO
import multiprocessing as mp

from .config import Config, PROJECT_ROOT as global_project_root_ref
from .agent import KnowledgeBaseAgent
from .exceptions import KnowledgeBaseError, ConfigurationError
from .prompts import LLMPrompts, UserPreferences, load_user_preferences

logger = logging.getLogger(__name__)

# Store a single agent instance
agent_instance: Optional[KnowledgeBaseAgent] = None

async def load_config() -> Config:
    """Load configuration and initialize logging."""
    try:
        # Use dynamic project root detection from config.py instead of explicit setting
        config = Config.from_env()  # Let Config.from_env() handle dynamic detection
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

async def run_agent_from_preferences(preferences: Dict[str, Any], socketio_instance: Optional[SocketIO] = None):
    """
    Initializes and runs the agent with a given set of user preferences.
    This is the main entry point for starting an agent run.
    """
    logger.info("Executing agent from preferences...")
    try:
        # Import Flask app here to avoid circular imports - web.py imports from main.py
        from flask import Flask
        from .models import db
        
        # Create a minimal Flask app for database context
        flask_app = Flask(__name__)
        flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/knowledge_base.db'
        flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(flask_app)
        
        config = await load_config()
        user_prefs = UserPreferences(**preferences)
        
        # In a multiprocessing scenario, a new agent is created for each run.
        # The app context and update queue are passed for DB access and communication.
        agent = KnowledgeBaseAgent(app=flask_app, config=config, socketio=socketio_instance)
        
        await agent.run(user_prefs)
        logger.info("Agent run from preferences completed.")
        
    except Exception as e:
        logger.error(f"Error running agent from preferences: {e}", exc_info=True)
        # Error logging is now handled by the Celery task a
        pass

async def main_cli():
    """Main entry point for command-line execution."""
    # This function is for CLI usage and does not use the web UI's state or queue.
    try:
        # Import Flask app here to avoid circular imports - web.py imports from main.py  
        from flask import Flask
        from .models import db
        
        # Create a minimal Flask app for database context
        flask_app = Flask(__name__)
        flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/knowledge_base.db'
        flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(flask_app)
        
        config = await load_config()
        user_prefs = UserPreferences() # Load default preferences for CLI
        agent = KnowledgeBaseAgent(app=flask_app, config=config)
        await agent.run(user_prefs)
    except Exception as e:
        logger.critical(f"A critical error occurred in CLI mode: {e}", exc_info=True)

if __name__ == '__main__':
    # This allows running the agent directly from the command line.
    # Example: python -m knowledge_base_agent.main
    asyncio.run(main_cli())