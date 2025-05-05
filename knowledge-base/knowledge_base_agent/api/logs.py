import asyncio
import logging
from pathlib import Path
from flask import jsonify, send_from_directory
from ..main import load_config

def list_logs():
    """API endpoint to list available log files."""
    try:
        # Load config to get the correct log directory
        try:
            # Use asyncio.run since this is a sync route calling an async function
            config = asyncio.run(load_config())
            configured_log_dir = Path(config.log_dir).expanduser().resolve()  # Expand ~ to full path and resolve
            logging.info(f"Listing logs from directory: {configured_log_dir}")
            
            # Add detailed debug info to diagnose empty log list
            print(f"Log API - Looking for logs in: {configured_log_dir}")
            print(f"Log API - Directory exists: {configured_log_dir.exists()}")
            print(f"Log API - Is directory: {configured_log_dir.is_dir()}")
            if configured_log_dir.exists() and configured_log_dir.is_dir():
                all_files = list(configured_log_dir.iterdir())
                print(f"Log API - All files in directory: {[str(f) for f in all_files]}")
        except Exception as config_e:
            logging.error(f"Failed to load config in /api/logs: {config_e}", exc_info=True)
            print(f"Log API - Error loading config: {config_e}")
            return jsonify({"error": "Failed to load configuration"}), 500

        if not configured_log_dir.is_dir():
            logging.error(f"Configured log directory not found: {configured_log_dir}")
            return jsonify({"error": "Log directory not found"}), 500

        # List files from the configured directory, sort by modification time (newest first)
        log_files = sorted(
            [f for f in configured_log_dir.iterdir() if f.is_file() and f.suffix == '.log'],
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        log_filenames = [f.name for f in log_files]
        logging.info(f"Found {len(log_filenames)} log files in {configured_log_dir}: {log_filenames[:5]} (first 5 shown)")
        print(f"Log API - Found {len(log_filenames)} log files: {log_filenames[:5] if log_filenames else 'none'}")
        return jsonify(log_filenames)
    except Exception as e:
        logging.error(f"Error listing log files: {e}", exc_info=True)
        print(f"Log API - Unexpected error: {e}")
        return jsonify({"error": "Failed to list log files"}), 500 