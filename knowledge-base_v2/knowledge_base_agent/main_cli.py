import argparse
import asyncio
import logging
import sys
import signal # For graceful shutdown
from typing import Optional, TYPE_CHECKING # Import TYPE_CHECKING

from . import config as ConfigModule
from . import log_setup
from . import database
from .exceptions import KnowledgeBaseAgentError, ConfigurationError
from .interfaces import http_client, ollama, playwright_client, git
from .processing import state, pipeline

# Import AccountsPool conditionally using TYPE_CHECKING
if TYPE_CHECKING:
    from twscrape import AccountsPool
else:
    try:
        from twscrape import AccountsPool
    except ImportError:
        AccountsPool = None # Define as None if import fails

logger = logging.getLogger(__name__) # Get logger after setup

# Global pipeline instance reference for signal handling
_pipeline_instance: Optional[pipeline.AgentPipeline] = None

async def main():
    """Main entry point for the CLI application."""
    global _pipeline_instance

    parser = argparse.ArgumentParser(description="Knowledge Base Agent - CLI Runner")
    parser.add_argument(
        "--force-recache",
        action="store_true",
        help="Force re-caching of all tweets, ignoring cache_complete flag.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the console logging level.",
    )
    # Add other arguments as needed (e.g., --skip-fetch, --skip-git)
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip the bookmark fetching phase.",
    )
    parser.add_argument(
        "--skip-git",
        action="store_true",
        help="Skip the Git synchronization phase.",
    )

    args = parser.parse_args()

    # --- Configuration ---
    try:
        cfg = ConfigModule.load_config()
    except ConfigurationError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)
    except SystemExit: # Raised by load_config on validation failure
        sys.exit(1)


    # --- Logging Setup ---
    log_level_int = getattr(logging, args.log_level.upper(), logging.INFO)
    log_setup.setup_logging(cfg, target='cli', level=log_level_int)
    logger.info("CLI Application Starting...")
    logger.info(f"Log Level set to: {args.log_level}")


    # --- Initialize Database (Important: Before Pipeline) ---
    try:
        logger.info("Initializing database connection...")
        database.init_engine_and_session(cfg.database_url)
        logger.info("Database initialization complete.")
    except ConfigurationError as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


    # --- Initialize Interfaces & Dependencies ---
    # Use string literal for type hint
    twscrape_pool_instance: Optional["AccountsPool"] = None

    try:
        # Create twscrape pool if library exists and credentials are provided
        # Removed the check for TWITTER_API_ENABLED
        if AccountsPool is not None and cfg.x_username and cfg.x_password:
             logger.info("Initializing twscrape account pool...")
             twscrape_pool_instance = AccountsPool()
             try:
                  # Ensure password secret value is accessed correctly
                  await twscrape_pool_instance.add_account(cfg.x_username, cfg.x_password.get_secret_value(), cfg.x_username)
                  await twscrape_pool_instance.login_all()
                  logger.info("twscrape pool initialized and logged in.")
             except Exception as e:
                  logger.error(f"Failed to initialize or login twscrape pool: {e}. Twitter features may fail.", exc_info=True)
                  twscrape_pool_instance = None # Ensure it's None on failure
        elif AccountsPool is None:
             logger.warning("twscrape library not found, cannot create account pool.")
        else: # AccountsPool exists but no credentials
             logger.warning("twscrape pool not initialized: X credentials missing.")


        async with http_client.HttpClientManager() as http_manager, \
                   ollama.OllamaClient(cfg, http_manager) as ollama_client:

            # Initialize optional clients based on config
            pw_client_instance = None
            if cfg.fetch_bookmarks_enabled:
                logger.info("Playwright fetching enabled, initializing client...")
                try:
                    # Running headless=True for CLI by default
                    pw_client_instance = playwright_client.PlaywrightClient(cfg, headless=True)
                    # Context manager handles startup/shutdown
                except Exception as e:
                     logger.error(f"Failed to initialize Playwright: {e}. Bookmark fetching disabled.", exc_info=True)
                     # Allow continuing without playwright? Or exit? Let's continue for now.
                     cfg.fetch_bookmarks_enabled = False # Disable if init fails


            git_client_instance = None
            if cfg.git_enabled:
                logger.info("Git synchronization enabled, initializing client...")
                try:
                    git_client_instance = git.GitClient(cfg)
                except ConfigurationError as e:
                     logger.error(f"Git client configuration error: {e}. Git sync disabled.")
                     cfg.git_enabled = False # Disable if init fails
                except Exception as e: # Catch other Git init errors
                     logger.error(f"Failed to initialize Git client: {e}. Git sync disabled.", exc_info=True)
                     cfg.git_enabled = False


            # --- State Manager ---
            state_manager = state.StateManager(cfg)

            # --- Pipeline ---
            _pipeline_instance = pipeline.AgentPipeline(
                config=cfg,
                state_manager=state_manager,
                http_manager=http_manager,
                ollama_client=ollama_client,
                playwright_client=pw_client_instance,
                git_client=git_client_instance,
                # Pass the twscrape pool if it was created
                twscrape_pool=twscrape_pool_instance # Pass the potentially initialized pool
            )

            # --- Signal Handling for Graceful Shutdown ---
            loop = asyncio.get_running_loop()
            stop_event = asyncio.Event()

            def signal_handler():
                logger.warning("Shutdown signal received. Requesting pipeline stop...")
                if _pipeline_instance:
                    _pipeline_instance.request_stop()
                # Give pipeline some time to stop phases, then signal main loop
                loop.call_later(1.0, stop_event.set) # Adjust delay if needed

            for sig in (signal.SIGINT, signal.SIGTERM):
                 loop.add_signal_handler(sig, signal_handler)


            # --- Run Pipeline ---
            run_prefs = {
                "force_recache": args.force_recache,
                "skip_fetch": args.skip_fetch,
                "skip_git": args.skip_git,
                # Add other preferences based on args
            }
            logger.info(f"Running pipeline with preferences: {run_prefs}")

            pipeline_task = asyncio.create_task(_pipeline_instance.run(run_prefs))

            # Wait for pipeline completion OR stop signal
            done, pending = await asyncio.wait(
                {pipeline_task, asyncio.create_task(stop_event.wait())},
                return_when=asyncio.FIRST_COMPLETED
            )

            if stop_event.is_set():
                 logger.warning("Shutdown initiated after stop signal.")
                 # Cancel pending tasks if necessary (pipeline should stop itself)
                 # for task in pending: task.cancel()
            else: # Pipeline finished normally
                 logger.info("Pipeline run completed normally.")

            # Check for exceptions in the pipeline task if it's done
            if pipeline_task in done and pipeline_task.exception():
                 logger.error(f"Pipeline task finished with an exception: {pipeline_task.exception()}")


    except KnowledgeBaseAgentError as e:
        logger.critical(f"A critical agent error occurred: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Ensure interfaces are closed if context managers didn't exit cleanly
        # (though they should in normal flow or via exceptions)
        logger.info("CLI Application Shutting Down.")


def cli_entry_point():
    """Entry point function for setup.py console_scripts."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user (KeyboardInterrupt).")
        sys.exit(130) # Standard exit code for Ctrl+C

if __name__ == "__main__":
    cli_entry_point()
