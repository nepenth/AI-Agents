import asyncio
import logging
from pathlib import Path
from flask import jsonify, send_from_directory
from ..config import Config # Import Config for type hinting

def list_logs(config: Config): # Accept config as an argument
    """API endpoint to list available log files."""
    try:
        # Validation to ensure we have a valid config
        if not config or not hasattr(config, 'log_dir'):
            logging.error("Log API - Config object or log_dir attribute missing.")
            return jsonify({"error": "Configuration for log directory not available"}), 500

        # Get log directory from config and ensure it exists
        configured_log_dir = Path(config.log_dir).expanduser().resolve()
        logging.info(f"Listing logs from directory: {configured_log_dir}")
        
        # Create directory if it doesn't exist (logs might not have been written yet)
        configured_log_dir.mkdir(parents=True, exist_ok=True)

        if not configured_log_dir.is_dir():
            logging.error(f"Configured log directory is not a directory: {configured_log_dir}")
            return jsonify({"error": f"Log directory {configured_log_dir} is not a valid directory"}), 500

        # List files from the configured directory, sort by modification time (newest first)
        log_files = sorted(
            [f for f in configured_log_dir.iterdir() if f.is_file() and f.suffix == '.log'],
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        log_filenames = [f.name for f in log_files]
        logging.info(f"Found {len(log_filenames)} log files in {configured_log_dir}")
        
        return jsonify(log_filenames)
    except Exception as e:
        logging.error(f"Error listing log files: {e}", exc_info=True)
        return jsonify({"error": f"Failed to list log files: {str(e)}"}), 500 