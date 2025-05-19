import asyncio
import logging
from pathlib import Path
from flask import jsonify, send_from_directory
from ..config import Config # Import Config for type hinting

def get_log_content(filename: str, config: Config): # Accept config as an argument
    """API endpoint to get the content of a specific log file."""
    # Config is now passed in, no need to load it here
    # try:
    #     config = asyncio.run(load_config())
    #     configured_log_dir = Path(config.log_dir).expanduser().resolve()  # Expand ~ to full path and resolve
    # except Exception as config_e:
    #     logging.error(f"Failed to load config in /api/logs/<filename>: {config_e}", exc_info=True)
    #     return jsonify({"error": "Failed to load configuration"}), 500

    if not config or not hasattr(config, 'log_dir'):
        logging.error("Log Content API - Config object or log_dir attribute missing.")
        return jsonify({"error": "Configuration for log directory not available"}), 500

    configured_log_dir = Path(config.log_dir).expanduser().resolve()

    # Basic security check: ensure filename doesn't contain path separators
    # and ends with .log
    if '/' in filename or '\\' in filename or '..' in filename or not filename.endswith('.log'):
        logging.warning(f"Invalid log filename requested: {filename}")
        return jsonify({"error": "Invalid log filename"}), 400

    log_file_path = (configured_log_dir / filename).resolve()  # Resolve to absolute path

    # Security check: Ensure the resolved path is within the intended log_dir
    if not log_file_path.is_relative_to(configured_log_dir):
        logging.warning(f"Potential path traversal blocked for log file: {filename}")
        return jsonify({"error": "Access denied"}), 403

    if not log_file_path.is_file():
        logging.error(f"Log file not found: {log_file_path}")
        return jsonify({"error": "Log file not found"}), 404

    try:
        # Use send_from_directory for safer file serving. Needs the directory path.
        logging.debug(f"Serving log file: {filename} from directory {configured_log_dir}")
        return send_from_directory(
            configured_log_dir,  # Serve from absolute path
            filename,
            mimetype='text/plain',
            as_attachment=False  # Display in browser
        )
    except Exception as e:
        logging.error(f"Error reading log file {filename}: {e}", exc_info=True)
        return jsonify({"error": "Failed to read log file"}), 500 