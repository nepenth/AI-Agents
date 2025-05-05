import asyncio
import logging
import os # Import os for listdir
from pathlib import Path
from typing import List, Optional

import aiofiles
from flask import Blueprint, jsonify, request, current_app, abort, render_template

from ..config import Config
from .. import log_setup # Import log_setup to potentially get current filename

logger = logging.getLogger(__name__)

# Rename blueprint and adjust URL prefix for the PAGE route
logs_bp = Blueprint('logs', __name__, url_prefix='/logs', template_folder='../../templates') # Use 'logs', set template folder

# --- Route for the HTML page ---
@logs_bp.route('/', methods=['GET'])
def view_logs_page():
    """Serves the log history page."""
    logger.debug("Serving log history page.")
    return render_template('logs.html', title="Log History")

# --- Helper: Read specific log file ---
async def read_log_file_lines(log_file_path: Path, max_lines: Optional[int] = None) -> List[str]:
    """Asynchronously reads lines from a specific log file, optionally limiting."""
    lines = []
    if not await asyncio.to_thread(log_file_path.is_file): # Use thread for sync check
        logger.warning(f"Log file not found: {log_file_path}")
        return [f"Log file not found: {log_file_path.name}"]
    try:
        async with aiofiles.open(log_file_path, mode='r', encoding='utf-8', errors='ignore') as f:
            all_lines = await f.readlines()
            if max_lines is not None and max_lines > 0:
                 lines = all_lines[-max_lines:] # Get last N lines
            else:
                 lines = all_lines # Get all lines if no limit
            lines = [line.strip() for line in lines] # Strip whitespace
    except Exception as e:
        logger.error(f"Error reading log file {log_file_path}: {e}", exc_info=True)
        return [f"Error reading log file '{log_file_path.name}': {e}"]
    return lines

# --- API Endpoints (Note: URL prefix is now /logs) ---

@logs_bp.route('/api/list', methods=['GET']) # Full path: /logs/api/list
async def list_log_files():
    """API endpoint to list available log files."""
    if not hasattr(current_app, 'agent_config'): abort(500, "Server configuration error")
    config: Config = current_app.agent_config
    log_dir = config.log_dir.resolve()

    try:
        # List files synchronously within a thread
        def list_sync():
             if not log_dir.is_dir(): return []
             # Filter for expected pattern and sort reverse chronologically
             log_files = [
                 f.name for f in log_dir.iterdir()
                 if f.is_file() and f.name.startswith("agent_run_") and f.name.endswith(".log")
             ]
             log_files.sort(reverse=True) # Newest first
             return log_files

        filenames = await asyncio.to_thread(list_sync)
        return jsonify({"log_files": filenames})
    except Exception as e:
         logger.error(f"Error listing log files in {log_dir}: {e}", exc_info=True)
         return jsonify({"error": "Failed to list log files"}), 500


@logs_bp.route('/api/view/<string:filename>', methods=['GET']) # Full path: /logs/api/view/<filename>
async def get_log_content(filename: str):
    """API endpoint to get the content of a specific log file."""
    if not hasattr(current_app, 'agent_config'): abort(500, "Server configuration error")
    config: Config = current_app.agent_config
    log_dir = config.log_dir.resolve()

    # Basic filename validation to prevent path traversal
    if not filename.startswith("agent_run_") or not filename.endswith(".log") or "/" in filename or "\\" in filename:
         abort(400, "Invalid log filename format.")

    log_file_path = log_dir / filename

    try:
        # Limit lines for performance? Or fetch all? Let's fetch all for now.
        # max_lines = request.args.get('max_lines', default=None, type=int) # Example limit
        lines = await read_log_file_lines(log_file_path, max_lines=None) # Fetch all lines
        return jsonify({"filename": filename, "logs": lines})
    except Exception as e: # Catch potential errors during read
         logger.error(f"Error fetching content for log file {filename}: {e}", exc_info=True)
         return jsonify({"error": f"Failed to read log file {filename}"}), 500
