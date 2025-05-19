import logging
import sys
import threading
import asyncio
from typing import Optional, Dict, TYPE_CHECKING # Added TYPE_CHECKING
import os
import pathlib

from flask import Flask
from flask_socketio import SocketIO

from . import config as ConfigModule
from . import log_setup
from . import database
from .exceptions import ConfigurationError, KnowledgeBaseAgentError
from .interfaces import http_client, ollama, playwright_client, git
from .processing import state, pipeline
from .processing.fetcher import Fetcher
from .web import routes as web_routes # Import blueprint
from .web import sockets as web_sockets # Import socket handlers
from .web import log_viewer # Import logs blueprint

# --- Application Setup ---
# Configure logging early
log_setup.setup_logging(ConfigModule.Config(log_dir='./logs'), target='web', level=logging.INFO) # Initial basic config for startup
logger = logging.getLogger(__name__) # Get logger after setup
print("DEBUG: Initial logging configured.")

# Load configuration
try:
    cfg = ConfigModule.load_config()
    # Reconfigure logging with loaded config
    log_setup.setup_logging(cfg, target='web', level=logging.INFO)
    logger.info("Configuration loaded successfully for web application.")
    print("DEBUG: Configuration loaded and logging reconfigured.")
except ConfigurationError as e:
    logger.critical(f"Configuration Error: {e}")
    sys.exit(1)
except SystemExit:
    sys.exit(1)

# Initialize Flask app
# Construct paths relative to this file's location
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) # This should be your knowledge-base_v2 directory

app = Flask(
    __name__,
    static_folder=os.path.join(project_root, 'static'),
    template_folder=os.path.join(project_root, 'templates'),
    static_url_path='/static'
)
app.config['SECRET_KEY'] = cfg.flask_secret_key.get_secret_value()
app.config['SQLALCHEMY_DATABASE_URI'] = cfg.database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Recommended practice
print("DEBUG: Flask app initialized and configured.")

# --- Make config accessible to blueprints/requests ---
app.agent_config = cfg

# >>> START DEBUG BLOCK <<<
cwd = pathlib.Path.cwd()
print(f"DEBUG: Current Working Directory: {cwd}")
db_url_from_config = app.config.get('SQLALCHEMY_DATABASE_URI')
print(f"DEBUG: Database URL from config: {db_url_from_config}")
if db_url_from_config and db_url_from_config.startswith('sqlite:///./'):
    relative_path = db_url_from_config[len('sqlite:///./'):]
    absolute_path = cwd / relative_path
    print(f"DEBUG: Calculated Absolute Path: {absolute_path}")
    print(f"DEBUG: Absolute Path Exists: {absolute_path.parent.exists()}")
    # Optionally force the absolute path if debugging
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{absolute_path}"
    print(f"DEBUG: Overriding DB URL with: {app.config['SQLALCHEMY_DATABASE_URI']}")
# >>> END DEBUG BLOCK <<<

# Initialize extensions
# Use 'threading', 'gevent', or 'eventlet'. 'threading' is simplest without extra deps.
socketio = SocketIO(app, async_mode='threading', logger=True, engineio_logger=True)
print("DEBUG: SocketIO initialized.")
database.db.init_app(app) # Initialize Flask-SQLAlchemy with app
print("DEBUG: SQLAlchemy initialized with app.")

# --- Database Initialization ---
try: # Add outer try-except to catch potential context errors
    with app.app_context():
        print("DEBUG: Entered app context for DB creation.")
        logger.info("Initializing database tables...")
        try:
            # Create tables if they don't exist
            database.db.create_all()
            print("DEBUG: db.create_all() executed.")
            logger.info("Database tables checked/created.")
            # Initialize engine for potential non-request use cases if needed?
            # No, CLI handles its own init. Flask uses db.session.
        except Exception as e:
             print(f"DEBUG: Exception during db.create_all(): {e}")
             logger.critical(f"Failed to initialize database tables: {e}", exc_info=True)
             sys.exit(1)
    print("DEBUG: Exited app context for DB creation.")
except Exception as e:
    print(f"DEBUG: Exception entering/during app context for DB creation: {e}")
    logger.critical(f"Critical error during app context for DB init: {e}", exc_info=True)
    sys.exit(1)

# --- Agent Pipeline Management ---
_pipeline_instance: Optional[pipeline.AgentPipeline] = None
_pipeline_thread: Optional[threading.Thread] = None
_pipeline_lock = threading.Lock() # Lock for accessing/modifying pipeline instance/thread

# Import AccountsPool conditionally for type hinting
if TYPE_CHECKING:
    from twscrape import AccountsPool, API as TwscrapeAPI_TYPE
else:
    try:
        from twscrape import AccountsPool, API as TwscrapeAPI_TYPE
    except ImportError:
        AccountsPool = None
        TwscrapeAPI_TYPE = None

def get_pipeline_status() -> Dict:
    """Returns the current status of the agent pipeline."""
    with _pipeline_lock:
        if _pipeline_thread and _pipeline_thread.is_alive():
            # How to check if stopping vs running? Add a flag in pipeline?
            status = "running"
            if _pipeline_instance and _pipeline_instance._stop_requested:
                 status = "stopping"
            return {"status": status}
        else:
            # Could check _pipeline_instance for last error?
            return {"status": "idle"} # Or "failed"?

# --- New async helper function for pipeline execution ---
async def _run_pipeline_async(run_preferences: Optional[Dict]):
    logger.info(f"DEBUG: _run_pipeline_async received run_preferences: {run_preferences}")
    global _pipeline_instance
    pipeline_instance_local = None
    twscrape_api_instance: Optional["TwscrapeAPI_TYPE"] = None
    pw_client_instance: Optional[playwright_client.PlaywrightClient] = None

    try:
        # Initialize twscrape API and pool if library exists and all X credentials are provided
        if TwscrapeAPI_TYPE is not None and cfg.x_username and cfg.x_password and cfg.x_email:
             logger.info("(Web Thread) Initializing twscrape API and account pool...")
             twscrape_api_instance = TwscrapeAPI_TYPE()
             try:
                  # Access pool via the api instance
                  await twscrape_api_instance.pool.add_account(
                      cfg.x_username, 
                      cfg.x_password.get_secret_value(), 
                      cfg.x_email, 
                      cfg.x_password.get_secret_value() 
                  )
                  await twscrape_api_instance.pool.login_all()
                  logger.info("(Web Thread) twscrape API and pool initialized, accounts logged in.")
             except Exception as e:
                  logger.error(f"(Web Thread) Failed to initialize or login twscrape accounts: {e}. Twitter features may fail.", exc_info=True)
                  twscrape_api_instance = None
        elif TwscrapeAPI_TYPE is None:
             logger.warning("(Web Thread) twscrape library not found or API class not imported, cannot create API instance. X/Twitter features will be skipped.")
        else:
             logger.warning("(Web Thread) twscrape API not initialized: Required X credentials (username, password, email) are missing. X/Twitter features will be skipped.")


        # Initialize other async-native instances
        async with http_client.HttpClientManager() as http_manager, \
                   ollama.OllamaClient(cfg, http_manager) as ollama_client:

            # --- Initialize Playwright Client only if fetching bookmarks ---
            pw_client_instance = None
            run_prefs = run_preferences or {}
            # Ensure this log reflects the actual decision-making value
            logger.info(f"DEBUG: In _run_pipeline_async, run_prefs for Playwright decision: {run_prefs}") 
            run_only_phase = run_prefs.get('run_only_phase', 'Full')
            skip_fetch = run_prefs.get('skip_fetch', False)
            logger.info(f"DEBUG: In _run_pipeline_async, derived run_only_phase='{run_only_phase}', skip_fetch='{skip_fetch}' for Playwright decision.")

            if cfg.x_username and cfg.x_password and cfg.x_bookmarks_url:
                if (run_only_phase == 'Full' and not skip_fetch) or (run_only_phase == 'InputAcquisition' and not skip_fetch):
                    logger.info("(Web Thread) X credentials and bookmarks URL present, initializing Playwright client for bookmark fetching...")
                    try:
                        pw_client_instance = playwright_client.PlaywrightClient(cfg, headless=True)
                        logger.info("(Web Thread) Attempting initial Playwright login for bookmark fetching...")
                        await pw_client_instance.login_to_x()
                        if not pw_client_instance._is_logged_in:
                            logger.warning("(Web Thread) Playwright initial login attempt appears to have failed. Bookmark fetching might fail.")
                        else:
                            logger.info("(Web Thread) Playwright initial login appears successful.")
                    except Exception as e:
                        logger.error(f"(Web Thread) Failed to initialize or login with Playwright: {e}. Bookmark fetching will fail.", exc_info=True)
                        pw_client_instance = None
                else:
                    logger.info(f"(Web Thread) Skipping Playwright client initialization as run mode '{run_only_phase}' does not involve fetching bookmarks or skip_fetch is {skip_fetch}.")
            else:
                logger.warning("(Web Thread) X credentials or bookmarks URL missing. Playwright client not initialized.")
            
            git_client_instance = git.GitClient(cfg) if cfg.git_enabled else None
            state_manager = state.StateManager(cfg)
            
            fetcher_instance = Fetcher(config=cfg, playwright_client=pw_client_instance)

            pipeline_instance_local = pipeline.AgentPipeline(
                config=cfg, state_manager=state_manager, http_manager=http_manager,
                ollama_client=ollama_client,
                playwright_client=pw_client_instance, 
                git_client=git_client_instance,
                fetcher=fetcher_instance,
                socketio=socketio
            )

            # Assign to global instance *after* creation, protected by lock
            with _pipeline_lock:
                _pipeline_instance = pipeline_instance_local

            # Emit status update *before* run
            socketio.emit('status_update', {'status': 'running', 'message': 'Agent starting...'}, namespace='/agent')

            # Run the pipeline's async method with the correct run_preferences
            await pipeline_instance_local.run(run_preferences)

    except Exception as e:
        logger.error(f"Exception in pipeline execution helper: {e}", exc_info=True)
        socketio.emit('status_update', {'status': 'failed', 'message': f'Agent helper thread failed: {e}'}, namespace='/agent')
    finally:
        if pw_client_instance:
            logger.info("(Web Thread) Ensuring Playwright client is closed...")
            try:
                await pw_client_instance.close()
            except Exception as e:
                logger.error(f"(Web Thread) Error closing Playwright client: {e}", exc_info=True)
        
        with _pipeline_lock:
            _pipeline_instance = None
        logger.debug("Pipeline async helper finished, clearing global instance reference.")


def start_pipeline_thread(run_preferences: Optional[Dict] = None):
    """Starts the agent pipeline in a background thread."""
    global _pipeline_thread # Keep modifying global thread reference
    logger.info("Attempting to start agent pipeline thread...")
    with _pipeline_lock:
        if _pipeline_thread and _pipeline_thread.is_alive():
            logger.warning("Pipeline thread requested to start, but already running.")
            socketio.emit('status_update', {'status': 'running', 'message': 'Agent already running.'}, namespace='/agent')
            return False

        logger.info("Setting up background thread for pipeline...")

        # Target function for the thread - manages the asyncio loop
        def pipeline_thread_target():
            logger.info("Pipeline background thread started.")
            # Create and set a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                 # Run the async helper function until it completes
                 loop.run_until_complete(_run_pipeline_async(run_preferences))
            except Exception as e:
                 # Catch errors during async execution if not caught internally
                 logger.error(f"Error during loop.run_until_complete in pipeline thread: {e}", exc_info=True)
                 socketio.emit('status_update', {'status': 'failed', 'message': f'Agent critical error: {e}'}, namespace='/agent')
            finally:
                 logger.info("Pipeline background thread event loop finished.")
                 loop.close()
                 # Clear global pipeline instance inside the thread's finally? No, _run_pipeline_async handles it.

        try:
            _pipeline_thread = threading.Thread(target=pipeline_thread_target, daemon=True)
            _pipeline_thread.start()
            logger.info("Pipeline background thread started successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to create or start pipeline thread: {e}", exc_info=True)
            socketio.emit('status_update', {'status': 'failed', 'message': f'Failed to start agent thread: {e}'}, namespace='/agent')
            return False


def stop_pipeline_thread():
    """Requests the background pipeline thread to stop."""
    logger.info("Attempting to stop agent pipeline thread...")
    with _pipeline_lock:
        if _pipeline_instance and _pipeline_thread and _pipeline_thread.is_alive():
            _pipeline_instance.request_stop()
            logger.info("Stop request sent to pipeline instance.")
            socketio.emit('status_update', {'status': 'stopping', 'message': 'Stop requested...'}, namespace='/agent')
            return True
        elif _pipeline_thread and _pipeline_thread.is_alive():
            logger.warning("Pipeline thread is running, but no pipeline instance found to signal stop.")
            return False
        else:
            logger.info("Pipeline thread is not running.")
            socketio.emit('status_update', {'status': 'idle', 'message': 'Agent already stopped.'}, namespace='/agent')
            return False


# --- Web Setup ---
try: # Add try-except for web setup phase
    print("DEBUG: About to register blueprints.")
    app.register_blueprint(web_routes.main_bp)
    app.register_blueprint(log_viewer.logs_bp) # Register logs API blueprint
    logger.info("Registered Flask blueprints.")
    print("DEBUG: Blueprints registered.")

    print("DEBUG: About to register SocketIO handlers.")
    web_sockets.register_handlers(socketio, start_pipeline_thread, stop_pipeline_thread, get_pipeline_status)
    logger.info("Registered SocketIO handlers.")
    print("DEBUG: SocketIO handlers registered.")

    print("DEBUG: About to configure WebSocket log handler.")
    ws_handler = log_setup.get_websocket_handler()
    if ws_handler:
        def emit_log(event, data):
            try:
                logger.debug(f"Attempting to emit log via WebSocket - Event: {event}, Namespace: /logs") # Log attempt
                socketio.emit(event, data, namespace='/logs')
                logger.debug(f"Successfully emitted log event '{event}' to /logs namespace.")
            except Exception as e:
                 logger.error(f"Error emitting log via websocket: {e}", exc_info=True) # Log full exception
                 print(f"Error emitting log via websocket: {e}", file=sys.stderr)

        ws_handler.set_emitter(emit_log)
        logger.info("WebSocket log handler configured with emitter.")

        # <<< TEST EMIT START >>>
        # Send a direct test message to the /logs namespace AFTER configuration
        try:
            logger.info("Sending direct TEST message to /logs namespace as 'new_log'...")
            socketio.emit('new_log', {'log_line': 'SERVER_INIT: WebSocket for /logs configured.'}, namespace='/logs')
            logger.info("Direct TEST message emitted using 'new_log'.")
        except Exception as test_emit_e:
             logger.error(f"Failed to emit direct TEST message: {test_emit_e}", exc_info=True)
        # <<< TEST EMIT END >>>

    else:
        logger.warning("WebSocket log handler not found/configured.") # Changed to warning
except Exception as e:
    print(f"DEBUG: Exception during Web Setup (blueprints/sockets/logging): {e}")
    logger.critical(f"Critical error during web setup: {e}", exc_info=True)
    sys.exit(1)

print("DEBUG: Reached end of setup before main block.")

if __name__ == "__main__":
    # Config 'cfg' is already loaded and logging is set up earlier in the script.
    # We just need the logger instance for this block.
    logger = logging.getLogger(__name__) # Get the logger configured earlier

    # Use the port defined in the loaded configuration object 'cfg'
    port = cfg.flask_run_port

    logger.info(f"Attempting to start the web server on port {port}...")
    print(f"DEBUG: Using port {port} from configuration.")
    print("DEBUG: About to call socketio.run()")

    # Determine debug status from the actual logger level
    effective_log_level = logging.getLogger().getEffectiveLevel()
    is_debug_mode = effective_log_level <= logging.DEBUG
    print(f"DEBUG: Calculated is_debug_mode: {is_debug_mode}") # Add print statement

    try:
        # Ensure SocketIO uses the configured async mode
        # Temporarily FORCE debug=True for verbose error output
        socketio.run(
            app,
            host="0.0.0.0",
            port=port,
            debug=True, # FORCE TRUE FOR DEBUGGING
            use_reloader=False, # Keep reloader off for now
            log_output=True, # FORCE TRUE FOR DEBUGGING
        )
        # This should only print if the server stops gracefully (e.g., Ctrl+C)
        print("DEBUG: socketio.run() finished.")
    except OSError as e:
        if "Address already in use" in str(e):
             logger.error(f"Port {port} is already in use. Please ensure no other service is running on this port or change FLASK_RUN_PORT in your .env file.")
             print(f"ERROR: Port {port} is already in use.")
        else:
             logger.exception("An OS error occurred while starting the web server.")
             print(f"DEBUG: OSError during socketio.run(): {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("Failed to start the web server.")
        print(f"DEBUG: Exception during socketio.run(): {e}")
        sys.exit(1)
    finally:
        # This will print when the script exits, even after Ctrl+C
        print("DEBUG: Script execution finished.")
