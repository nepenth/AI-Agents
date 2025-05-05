import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Literal, Optional
from datetime import datetime

# Import Config type hint safely
# Use try-except to avoid circular dependency issues if this module
# is imported before config is fully initialized elsewhere, although
# the setup function itself requires a loaded Config object.
try:
    from .config import Config
except ImportError:
    # Define a dummy Config for type hinting if needed during static analysis
    # or if there's a complex import scenario.
    class Config:
        log_dir: Path = Path("./logs")
        # Add other fields if needed by static analysis, though log_dir is primary.


# --- WebSocket Handler Placeholder ---
# This handler would need actual implementation depending on the web framework/library.
# It should likely queue messages or directly emit them via SocketIO.
class WebSocketLogHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.emitter = None # Placeholder for the emitting function/object (e.g., socketio.emit)

    def set_emitter(self, emitter_func):
        """Sets the function used to emit log records."""
        self.emitter = emitter_func

    def emit(self, record):
        """Emits the formatted log record."""
        if self.emitter:
            try:
                log_entry = self.format(record)
                # Define the event name and data structure expected by the frontend
                self.emitter('log_message', {'level': record.levelname, 'message': log_entry})
            except Exception:
                self.handleError(record) # Default handler behavior on error

# Global instance of the WebSocket handler to be configured later
websocket_handler: Optional[WebSocketLogHandler] = None

# --- Store current log filename globally? ---
# This allows other parts (like log_viewer) to know the current file
_current_log_filename: Optional[str] = None

def get_current_log_filename() -> Optional[str]:
    """Gets the filename of the currently configured log file."""
    return _current_log_filename

def setup_logging(config: Config, target: Literal["cli", "web", "worker"] = "cli", level: int = logging.INFO):
    """Configures logging for the application, using timestamped files per run."""
    global websocket_handler, _current_log_filename

    log_dir = config.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    # --- Create Timestamped Filename ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"agent_run_{timestamp}.log"
    log_file_path = log_dir / log_filename
    _current_log_filename = log_filename # Store current filename

    # Define log formats
    # Example: 2023-10-27 15:30:00,123 - knowledge_base_agent.processing.cacher - INFO - Caching tweet 12345
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    # Example: [INFO] Caching tweet 12345 (from knowledge_base_agent.processing.cacher)
    console_formatter = logging.Formatter(
        "[%(levelname)s] %(message)s (from %(name)s)"
    )
    # Example for WebSocket: INFO: Caching tweet 12345
    websocket_formatter = logging.Formatter(
        "%(levelname)s: %(message)s"
    )

    # Get the root logger (or a specific application logger)
    # Configuring the root logger is common for application-wide setup
    logger = logging.getLogger() # Get root logger
    logger.setLevel(level) # Set minimum level for the logger itself

    # Remove existing handlers to avoid duplication if called multiple times
    # (useful in development or testing)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    # --- File Handler (using the new timestamped path) ---
    # Use basic FileHandler as rotation is handled by new file per run
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG) # Log DEBUG and above to file
    logger.addHandler(file_handler)

    # --- Console Handler (for CLI) ---
    if target == "cli":
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(level) # Use the overall specified level for console
        logger.addHandler(console_handler)

    # --- WebSocket Handler (for Web UI) ---
    if target == "web":
        # Create the handler instance if it doesn't exist
        if websocket_handler is None:
            websocket_handler = WebSocketLogHandler()
            websocket_handler.setFormatter(websocket_formatter)
            # Set a level for websockets - INFO might be appropriate to avoid flooding UI
            websocket_handler.setLevel(logging.INFO)
        logger.addHandler(websocket_handler)
        # Note: The emitter function needs to be set separately, likely in main_web.py
        # after SocketIO is initialized, e.g.:
        # from .log_setup import websocket_handler
        # websocket_handler.set_emitter(socketio.emit)

    # --- Worker Logging ---
    # Workers typically log only to files, maybe console if running interactively for debug
    if target == "worker":
        # File handler is already added.
        # Optionally add console handler for workers if needed for debugging:
        # console_handler = logging.StreamHandler(sys.stdout)
        # console_handler.setFormatter(console_formatter)
        # console_handler.setLevel(level)
        # logger.addHandler(console_handler)
        pass # File handler is sufficient by default

    # Silence overly verbose libraries if necessary
    # logging.getLogger("urllib3").setLevel(logging.WARNING)
    # logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.info(f"Logging configured for target '{target}' with level {logging.getLevelName(level)}. Log file: {log_file_path}")

def get_websocket_handler() -> Optional[WebSocketLogHandler]:
    """Returns the global WebSocketLogHandler instance."""
    return websocket_handler
