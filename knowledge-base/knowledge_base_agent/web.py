# knowledge_base_agent/web.py
import gevent.monkey
gevent.monkey.patch_all() # Apply gevent monkey patching as early as possible

import asyncio
import logging
import sys
from typing import Optional # Import Optional
from threading import Thread
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session, current_app
from flask_socketio import SocketIO, emit, join_room, leave_room
from markdown import markdown
from .config import Config
from .models import db, KnowledgeBaseItem, SubcategorySynthesis
from .agent import KnowledgeBaseAgent
from .prompts import UserPreferences
from .main import load_config, run_agent, cleanup
from .state_manager import StateManager
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import re
import multiprocessing
from .content_processor import ContentProcessor
from concurrent.futures import ThreadPoolExecutor
from .api.logs import list_logs
from .api.log_content import get_log_content
import queue
from collections import deque
import knowledge_base_agent.shared_globals as sg # Import shared_globals
from knowledge_base_agent.agent import KnowledgeBaseAgent
from knowledge_base_agent.config import Config as PydanticConfig # Corrected import
from knowledge_base_agent.models import db, KnowledgeBaseItem as DBKnowledgeBaseItem # Corrected import
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.tweet_cacher import TweetCacheValidator # For type hinting
from knowledge_base_agent.prompts import UserPreferences # For type hinting
from knowledge_base_agent.shared_globals import stop_flag, sg_set_project_root, sg_get_project_root # Import stop_flag
from knowledge_base_agent.gpu_utils import get_gpu_stats # Import GPU utility
import threading
import time
from flask_migrate import Migrate
import aiofiles
import psutil

# Global config variable, to be initialized in __main__
config: Optional[Config] = None
log_file_path: Optional[Path] = None # Store log file path globally for file handler

# Server-side state storage
# agent_running = False  # REMOVE - Consolidate state
agent_is_running = False # Primary flag for agent execution status
recent_logs = deque(maxlen=400)  # Store recent logs to send to new connections
current_run_preferences: Optional[dict] = None # Store preferences of the active run

# Initial logging setup (before config is fully loaded, might be to stdout or a default file if needed)
# This initial setup is minimal. The main file handler will be set up after config is loaded.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure SocketIO to avoid recursive logging (can be done early)
socketio_logger = logging.getLogger('socketio')
socketio_logger.setLevel(logging.WARNING)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///knowledge_base.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
socketio = SocketIO(app, async_mode='gevent', logger=False, engineio_logger=False)
migrate = Migrate()
migrate.init_app(app, db)

agent_instance = None # Renamed from agent to agent_instance for clarity
agent_thread = None
# running = False # REMOVE - Consolidate state

# Initialize database
with app.app_context():
    db.create_all()  # Create tables if they don't exist, won't drop existing data
    logging.info("Database tables initialized.")

class WebSocketHandler(logging.Handler):
    def emit(self, record):
        try:
            # Avoid recursion by checking if the log message is about WebSocket emission
            if "Sending packet MESSAGE" in record.getMessage() or "emitting event" in record.getMessage():
                return
            
            # Filter out DEBUG logs from the Live Logs display - they should only go to files
            if record.levelno <= logging.DEBUG:
                return
                
            msg = self.format(record)
            
            # Store in recent_logs for new connections
            recent_logs.append({'message': msg, 'level': record.levelname})
            
            # Emit to connected clients only if socketio is available
            if socketio:
                socketio.emit('log', {'message': msg, 'level': record.levelname}, namespace='/')
        except Exception as e:
            print(f"ERROR: Failed to emit log to WebSocket: {e}", file=sys.stderr)

def setup_web_logging(current_config: Config): # Renamed param to avoid conflict with global
    """Configure logging with WebSocket handler using Config."""
    root_logger = logging.getLogger()
    
    # Store existing WebSocket handler before config.setup_logging() clears handlers
    existing_ws_handler = None
    for handler in root_logger.handlers[:]:
        if isinstance(handler, WebSocketHandler):
            existing_ws_handler = handler
            break
    
    # Let Config object set up its own file and console logging
    current_config.setup_logging()
    
    # Add back WebSocketHandler if it existed or create new one
    if existing_ws_handler:
        root_logger.addHandler(existing_ws_handler)
        logging.debug("Re-added existing WebSocket logging handler")
    else:
        # Add WebSocketHandler if not already present
        ws_handler = WebSocketHandler()
        ws_handler.setLevel(logging.INFO)  # Filter out debug logs from Live Logs display
        ws_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        root_logger.addHandler(ws_handler)
        logging.debug("Added new WebSocket logging handler")
    
    # Ensure root logger level allows all messages to reach handlers
    root_logger.setLevel(logging.DEBUG)
    
    # Log the current handler configuration for debugging
    handler_types = [type(h).__name__ for h in root_logger.handlers]
    logging.info(f"Logging configured with handlers: {handler_types}")
    
    # Test logging to ensure file logging is working
    logging.info("Web logging setup complete - this message should appear in log file")

@app.route('/', methods=['GET'])
# Removed POST handling as it's superseded by SocketIO for agent runs
def index():
    global agent_is_running
    app_config = getattr(current_app, 'config_instance', None) # Get app_config
    all_items = []
    all_syntheses = []
    try:
        all_items = KnowledgeBaseItem.query.order_by(KnowledgeBaseItem.last_updated.desc()).all()
        all_syntheses = SubcategorySynthesis.query.order_by(SubcategorySynthesis.last_updated.desc()).all()
        # Changed from debug to avoid cluttering Live Logs - this happens on every page load
        # logging.debug(f"Retrieved {len(all_items)} items for index page sidebar.")
    except Exception as e:
        logging.error(f"Error retrieving items for index sidebar: {e}", exc_info=True)
    
    return render_template('index.html', running=agent_is_running, items=all_items, syntheses=all_syntheses, current_item_id=None, config=app_config) # Pass app_config

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    app_config = getattr(current_app, 'config_instance', None)
    if not app_config:
        logging.error("Application configuration not found in item_detail.")
        if request.headers.get('Accept') == 'application/json':
            return jsonify({"error": "Application configuration not found"}), 500
        return "Application configuration not found.", 500

    item = KnowledgeBaseItem.query.get_or_404(item_id)
    
    if not item.file_path:
        logging.error(f"Content file path (file_path) missing for item {item_id}")
        if request.headers.get('Accept') == 'application/json':
            return jsonify({"error": "KB Item content file path not set"}), 404
        return "Error: KB Item content file path not set.", 404

    content_file_abs_path = Path(item.file_path).resolve()

    if not content_file_abs_path.exists():
        logging.error(f"Content file does not exist for item {item_id} at path: {content_file_abs_path}")
        if request.headers.get('Accept') == 'application/json':
            return jsonify({"error": f"KB Item content file not found at {content_file_abs_path}"}), 404
        return f"Error: KB Item content file not found at {content_file_abs_path}.", 404

    markdown_content = ""
    try:
        with open(content_file_abs_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
    except Exception as e:
        logging.error(f"Error reading content file {content_file_abs_path} for item {item_id}: {e}")
        if request.headers.get('Accept') == 'application/json':
            return jsonify({"error": "Could not read KB Item content file"}), 500
        return "Error: Could not read KB Item content file.", 500

    # Try to parse raw_json_content if available for better display
    processed_json_content = None
    if item.raw_json_content:
        try:
            processed_json_content = json.loads(item.raw_json_content)
            logging.debug(f"Successfully parsed raw_json_content for item {item_id}")
        except json.JSONDecodeError:
            logging.warning(f"Failed to parse raw_json_content for item {item_id}")

    relative_item_dir = ""
    try:
        if not app_config.knowledge_base_dir:
            logging.error("Configuration error: app_config.knowledge_base_dir is not set. Cannot determine media paths.")
            raise ValueError("Server configuration issue for media paths.")

        kb_root = Path(app_config.knowledge_base_dir).resolve()
        
        if not content_file_abs_path.is_relative_to(kb_root):
             logging.error(f"Content file {content_file_abs_path} is not relative to KB root {kb_root}.")
             raise ValueError(f"Content path {content_file_abs_path} is not under KB root {kb_root}.")

        relative_readme_path = content_file_abs_path.relative_to(kb_root) 
        # For KB items, the structure is: category/subcategory/item_name/README.md
        # So we want just the category/subcategory/item_name part
        relative_item_dir = str(relative_readme_path.parent)
        
    except ValueError as e: 
        logging.error(f"Error deriving relative path for item {item_id}. Content path {content_file_abs_path}, KB root {app_config.knowledge_base_dir}: {e}")
        if request.headers.get('Accept') == 'application/json':
            return jsonify({"error": f"KB Item path misconfiguration ({e})"}), 500
        return f"Error: KB Item path misconfiguration ({e}).", 500
    
    # Simplified media URL construction - should point directly to the item's directory
    base_media_url_prefix = f"/kb-media/{relative_item_dir}" if relative_item_dir else "/kb-media"

    def replace_media_paths(text, prefix):
        processed_text = re.sub(r"!\[(.*?)\]\(./(.*?)\)", rf"![\1]({prefix}/\2)", text)
        processed_text = re.sub(r'(<[^>]*?(?:src|href)=["\'])\./([^"\']+)(["\'])', rf'\1{prefix}/\2\3', processed_text)
        return processed_text

    modified_markdown = replace_media_paths(markdown_content, base_media_url_prefix)
    html_content = markdown(modified_markdown, extensions=['fenced_code', 'tables', 'sane_lists', 'md_in_html']) 
    all_items_for_sidebar = KnowledgeBaseItem.query.order_by(KnowledgeBaseItem.last_updated.desc()).all()
    all_syntheses_for_sidebar = SubcategorySynthesis.query.order_by(SubcategorySynthesis.last_updated.desc()).all()

    media_list = []
    if item.kb_media_paths:
        try:
            media_list = json.loads(item.kb_media_paths)
        except json.JSONDecodeError:
            logging.error(f"Failed to parse kb_media_paths JSON for item {item_id}: {item.kb_media_paths}")

    # Debug logging to understand the media path structure - changed to debug level
    logging.debug(f"Item {item_id}: relative_item_dir='{relative_item_dir}', base_media_url_prefix='{base_media_url_prefix}'")
    logging.debug(f"Item {item_id}: media_list={media_list}")

    # If this is an AJAX request for JSON data, return JSON response
    if request.headers.get('Accept') == 'application/json':
        return jsonify({
            'id': item.id,
            'item_name': item.item_name or item.title,
            'display_title': item.display_title or item.title,
            'title': item.title,
            'main_category': item.main_category,
            'sub_category': item.sub_category,
            'description': item.description,
            'content_html': html_content,
            'content_markdown': markdown_content,
            'source_url': item.source_url,
            'tweet_url': item.source_url,
            'created_at': item.created_at.isoformat() if item.created_at else None,
            'last_updated': item.last_updated.isoformat() if item.last_updated else None,
            'media_list': media_list,
            'kb_json_data': processed_json_content,
            'base_media_url_prefix': base_media_url_prefix
        })

    # Otherwise, render the full page template (for direct navigation)
    return render_template('item_detail.html', 
                           item=item, 
                           content=html_content, 
                           items=all_items_for_sidebar, 
                           syntheses=all_syntheses_for_sidebar,
                           current_item_id=item_id,
                           media_list=media_list,
                           kb_json_data=processed_json_content,
                           config=app_config)

async def _run_agent_async_logic(preferences_data: dict):
    """Helper async function to contain the core agent running logic."""
    global agent_instance, agent_is_running, config, current_run_preferences # Use the global config

    logging.info(f"--- _run_agent_async_logic INITIATED with preferences: {preferences_data} ---")
    logging.info(f"Current agent_is_running: {agent_is_running}")

    if agent_is_running:
        logging.warning("Agent is already running. Ignoring request.")
        socketio.emit('log', {'message': 'Agent is already running. Please wait or stop the current run.', 'level': 'WARNING'})
        return

    agent_is_running = True
    sg.clear_stop_flag() # Reset shared stop_flag
    current_run_preferences = preferences_data # Store the preferences for this run
    socketio.emit('agent_status', {'is_running': True, 'active_run_preferences': current_run_preferences})
    logging.info(f"Agent status set to running. Stop flag reset. User Preferences: {preferences_data}")

    # Create UserPreferences object from the received dictionary
    try:
        preferences = UserPreferences(**preferences_data)
        logging.info(f"UserPreferences object created: {preferences}")
    except TypeError as e:
        logging.error(f"Error creating UserPreferences from data: {preferences_data}, error: {e}", exc_info=True)
        socketio.emit('log', {'message': f'Error processing agent preferences: {e}', 'level': 'ERROR'})
        agent_is_running = False # Reset status
        current_run_preferences = None # Clear stored preferences
        socketio.emit('agent_status', {'is_running': False, 'active_run_preferences': None})
        return
    
    try:
        if not config: # Should be loaded at startup, but as a fallback
            logging.warning("Global config not found in _run_agent_async_logic, attempting to load.")
            config = await load_config()
            setup_web_logging(config) # Re-setup logging if config was reloaded

        if not agent_instance:
            logging.info("Agent instance not found in _run_agent_async_logic, creating a new one.")
            # Ensure app is accessible here. 'app' is global in this file.
            agent_instance = KnowledgeBaseAgent(app, config, socketio=socketio)
        
        # Ensure socketio is properly assigned
        agent_instance.socketio = socketio
        if agent_instance.content_processor: # Ensure content_processor exists
            agent_instance.content_processor.socketio = socketio
        else:
            logging.warning("Content processor not found on agent instance during run setup.")


        with app.app_context(): # Ensure DB operations and other Flask context needs are met
            await agent_instance.initialize() # Initialize or re-initialize state
        
        logging.info("=== Starting Agent Operations via _run_agent_async_logic ===")
        await agent_instance.run(preferences)
            
    except Exception as e:
        logging.error(f"Agent execution failed within _run_agent_async_logic: {str(e)}", exc_info=True)
        socketio.emit('log', {'message': f'Agent execution STOPPED due to error: {str(e)}', 'level': 'ERROR'})
    finally:
        agent_is_running = False
        active_prefs_on_stop = current_run_preferences # Capture before clearing
        current_run_preferences = None # Clear stored preferences on run end
        socketio.emit('agent_complete', {'status': 'completed'}) 
        socketio.emit('agent_status', {'is_running': False, 'active_run_preferences': None, 'final_run_preferences_for_plan': active_prefs_on_stop}) # Send None for active, but might send final for plan view
        logging.info("Agent run finished or failed. Status reset.")
        if agent_instance and agent_instance.http_client:
            await agent_instance.http_client.close()
        # Cleanup is usually for global resources, ensure it's handled carefully
        # if config: # Config should always be there if we reached this point
        #     await cleanup(config)

@socketio.on('request_agent_status')
def handle_request_agent_status():
    global agent_is_running, current_run_preferences
    # Changed from debug to avoid cluttering Live Logs - this is called frequently by UI
    # logging.debug(f"Client requested agent status. Current status: {'Running' if agent_is_running else 'Not Running'}")
    socketio.emit('agent_status', {'is_running': agent_is_running, 'active_run_preferences': current_run_preferences if agent_is_running else None})

@socketio.on('run_agent')
def run_agent_socket(data: dict):
    logging.info("--- run_agent_socket event handler (sync wrapper) INITIATED ---")
    logging.info(f"'run_agent' event received. Data: {data}")

    actual_preferences = data.get('preferences')
    if actual_preferences is None:
        logging.error("'preferences' key not found in data from client for 'run_agent' event.")
        socketio.emit('log', {'message': "Error processing agent request: 'preferences' data missing.", 'level': 'ERROR'})
        return

    def thread_target(prefs_for_async_logic):
        """Target function for the new thread to run asyncio logic."""
        try:
            asyncio.run(_run_agent_async_logic(prefs_for_async_logic))
        except Exception as e:
            logging.error(f"Critical error in agent execution thread: {e}", exc_info=True)
            # Ensure global state is updated and client is notified in case of crash
            global agent_is_running, current_run_preferences
            agent_is_running = False
            current_run_preferences = None # Clear stored preferences
            socketio.emit('agent_status', {'is_running': False, 'active_run_preferences': None})
            socketio.emit('log', {'message': f'Agent execution CRASHED due to an internal error: {e}', 'level': 'CRITICAL'})
            socketio.emit('agent_complete', {'status': 'crashed'}) # Notify UI of unexpected termination
            socketio.emit('agent_run_completed', {  # Add this to ensure UI is updated
                'is_running': False,
                'summary_message': f'Agent execution crashed: {str(e)}',
                'plan_statuses': {}  # Empty plan statuses since we crashed
            })

    # Run the asyncio logic in a new daemon thread
    # daemon=True ensures the thread doesn't block application exit
    agent_execution_thread = threading.Thread(target=thread_target, args=(actual_preferences,), daemon=True)
    agent_execution_thread.start()
    logging.info("--- Agent execution started in a new dedicated thread --- ")

@socketio.on('stop_agent')
def handle_stop_agent():
    logging.info("SocketIO: Received stop_agent request.")
    global agent_instance
    if agent_instance and agent_instance._is_running:
        logging.info("Setting stop flag via shared_globals...")
        sg.set_stop_flag() # <-- NEW
        socketio.emit('log', {'message': 'Stop signal sent to agent. It may take a moment for all operations to cease.', 'level': 'WARN'})
    else:
        logging.info("Agent is not currently running.")
        socketio.emit('log', {'message': 'Agent is not currently running.', 'level': 'INFO'})

@app.route('/get_log_file/<path:log_path>', methods=['GET'])
def get_log_file(log_path):
    log_path = Path(log_path)
    if log_path.exists() and log_path.is_file():
        with open(log_path, 'r') as f:
            content = f.read()
        return jsonify({'status': 'success', 'content': content})
    return jsonify({'status': 'error', 'message': 'Log file not found'})

# --- NEW: Log Viewer Routes ---

@app.route('/logs')
def logs_page():
    """Render the dedicated log viewer page."""
    app_config = getattr(current_app, 'config_instance', None) # Get app_config
    all_items = []  # For sidebar consistency
    all_syntheses = []  # For sidebar consistency
    try:
        all_items = KnowledgeBaseItem.query.all()
        all_syntheses = SubcategorySynthesis.query.all()
    except Exception as e:
        logging.error(f"Error retrieving items for logs page sidebar: {e}", exc_info=True)
    # This route just renders the HTML shell; JS will fetch the actual log list/content.
    return render_template('logs.html', items=all_items, syntheses=all_syntheses, config=app_config) # Pass app_config

@app.route('/api/logs', methods=['GET'])
def api_logs():
    """API endpoint to list available log files."""
    # Get the config from current_app if it's set
    app_config = getattr(current_app, 'config_instance', config)
    if not app_config:
        logging.error("API /api/logs: Application configuration not found.")
        return jsonify({"error": "Application configuration not available"}), 500
    
    # Pass the config to list_logs
    return list_logs(app_config)

@app.route('/api/logs/<path:filename>', methods=['GET'])
def api_log_content(filename):
    """API endpoint to get content of a specific log file."""
    app_config = getattr(current_app, 'config_instance', config)
    if not app_config:
        logging.error(f"API /api/logs/{filename}: Application configuration not found.")
        return jsonify({"error": "Application configuration not available"}), 500
    
    # Validate filename to prevent path traversal
    if '..' in filename or filename.startswith('/'):
        return jsonify({"error": "Invalid filename"}), 400
    
    try:
        # Construct the full path using the configured log directory
        log_path = Path(app_config.log_dir).expanduser().resolve() / filename
        
        # Check if file exists and is a regular file
        if not log_path.exists() or not log_path.is_file():
            return jsonify({"error": f"Log file {filename} not found"}), 404
            
        # Read and return the file content
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        return content
    except Exception as e:
        logging.error(f"Error reading log file {filename}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to read log file: {str(e)}"}), 500

@app.route('/api/logs/delete-all', methods=['POST'])
def api_delete_all_logs():
    """API endpoint to delete all log files."""
    app_config = getattr(current_app, 'config_instance', config)
    if not app_config:
        logging.error("API /api/logs/delete-all: Application configuration not found.")
        return jsonify({"error": "Application configuration not available"}), 500
    
    try:
        # Get the log directory
        log_dir = Path(app_config.log_dir).expanduser().resolve()
        if not log_dir.is_dir():
            return jsonify({"error": f"Log directory {log_dir} is not a valid directory"}), 500
        
        # Get all log files
        log_files = [f for f in log_dir.iterdir() if f.is_file() and f.suffix == '.log']
        deleted_count = 0
        
        # Don't delete the currently active log file (if any)
        current_log_file = getattr(logging.getLoggerClass().root.handlers[0], 'baseFilename', None)
        current_log_path = Path(current_log_file).resolve() if current_log_file else None
        
        # Delete each file
        for log_file in log_files:
            try:
                # Skip the currently active log file
                if current_log_path and log_file.resolve() == current_log_path:
                    logging.info(f"Skipping current active log file: {log_file}")
                    continue
                    
                log_file.unlink()
                deleted_count += 1
                logging.info(f"Deleted log file: {log_file}")
            except Exception as e:
                logging.error(f"Failed to delete log file {log_file}: {e}")
        
        return jsonify({
            "success": True,
            "message": f"Successfully deleted {deleted_count} log files.",
            "deleted_count": deleted_count
        })
    except Exception as e:
        logging.error(f"Error deleting log files: {e}", exc_info=True)
        return jsonify({"error": f"Failed to delete log files: {str(e)}"}), 500

@app.route('/api/kb_items', methods=['GET'])
def api_kb_items():
    """API endpoint to fetch all knowledge base items."""
    try:
        all_items = KnowledgeBaseItem.query.order_by(KnowledgeBaseItem.last_updated.desc()).all()
        items_data = []
        for item in all_items:
            items_data.append({
                'id': item.id,
                'item_name': item.item_name or item.title,
                'display_title': item.display_title or item.title,
                'title': item.title,
                'main_category': item.main_category,
                'sub_category': item.sub_category,
                'description': item.description,
                'source_url': item.source_url,
                'created_at': item.created_at.isoformat() if item.created_at else None,
                'last_updated': item.last_updated.isoformat() if item.last_updated else None,
                'tweet_url': item.source_url
            })
        return jsonify(items_data)
    except Exception as e:
        logging.error(f"Error fetching KB items via API: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch knowledge base items'}), 500

@app.route('/api/kb_items/<int:item_id>', methods=['GET'])
def api_kb_item_detail(item_id):
    """API endpoint to fetch a specific knowledge base item."""
    try:
        item = KnowledgeBaseItem.query.get_or_404(item_id)
        
        # Read markdown content
        markdown_content = ""
        if item.file_path:
            try:
                content_file_abs_path = Path(item.file_path).resolve()
                if content_file_abs_path.exists():
                    with open(content_file_abs_path, 'r', encoding='utf-8') as f:
                        markdown_content = f.read()
            except Exception as e:
                logging.error(f"Error reading content file for item {item_id}: {e}")
        
        # Parse media paths
        media_list = []
        if item.kb_media_paths:
            try:
                media_list = json.loads(item.kb_media_paths)
            except json.JSONDecodeError:
                logging.error(f"Failed to parse kb_media_paths for item {item_id}")
        
        item_data = {
            'id': item.id,
            'item_name': item.item_name or item.title,
            'display_title': item.display_title or item.title,
            'title': item.title,
            'main_category': item.main_category,
            'sub_category': item.sub_category,
            'description': item.description,
            'content_markdown': markdown_content,
            'source_url': item.source_url,
            'tweet_url': item.source_url,
            'created_at': item.created_at.isoformat() if item.created_at else None,
            'created_at_tweet': item.created_at.isoformat() if item.created_at else None,
            'last_updated': item.last_updated.isoformat() if item.last_updated else None,
            'media_list': media_list,
            'source': 'tweet'  # Default source type
        }
        return jsonify(item_data)
    except Exception as e:
        logging.error(f"Error fetching KB item {item_id} via API: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch knowledge base item'}), 500

# --- Synthesis API Routes ---

@app.route('/api/synthesis', methods=['GET'])
def api_synthesis_list():
    """Get list of all synthesis documents."""
    logging.info("API call received: /api/synthesis")
    try:
        syntheses = SubcategorySynthesis.query.order_by(
            SubcategorySynthesis.main_category,
            SubcategorySynthesis.sub_category
        ).all()
        
        logging.info(f"Found {len(syntheses)} synthesis documents in the database.")
        
        synthesis_list = []
        for i, synthesis in enumerate(syntheses):
            synthesis_data = {
                'id': synthesis.id,
                'main_category': synthesis.main_category,
                'sub_category': synthesis.sub_category,
                'synthesis_title': synthesis.synthesis_title,
                'item_count': synthesis.item_count,
                'created_at': synthesis.created_at.isoformat() if synthesis.created_at else None,
                'last_updated': synthesis.last_updated.isoformat() if synthesis.last_updated else None,
                'file_path': synthesis.file_path
            }
            synthesis_list.append(synthesis_data)
            # logging.debug(f"Prepared synthesis data for item {i}: {synthesis_data.get('synthesis_title')}") # Too verbose for INFO
        
        logging.info(f"Successfully prepared {len(synthesis_list)} synthesis documents for API response.")
        return jsonify(synthesis_list)
    except Exception as e:
        logging.error(f"Error fetching synthesis list via API: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch synthesis documents'}), 500

@app.route('/api/synthesis/<int:synthesis_id>', methods=['GET'])
def api_synthesis_detail(synthesis_id):
    """Get detailed data for a specific synthesis document."""
    logging.info(f"API call received: /api/synthesis/{synthesis_id}")
    try:
        synthesis = SubcategorySynthesis.query.get_or_404(synthesis_id)
        logging.info(f"Found synthesis document ID {synthesis_id}: {synthesis.synthesis_title}")
        
        # Load markdown content if file_path exists
        content_html = ""
        content_markdown = ""
        if synthesis.file_path:
            file_path = Path(synthesis.file_path)
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content_markdown = f.read()
                        content_html = markdown(content_markdown, extensions=['fenced_code', 'tables', 'sane_lists', 'md_in_html'])
                except Exception as e:
                    logging.error(f"Error reading synthesis file {file_path}: {e}")
        
        # Parse raw JSON if available
        raw_json_data = None
        if synthesis.raw_json_content:
            try:
                raw_json_data = json.loads(synthesis.raw_json_content)
            except json.JSONDecodeError as e:
                logging.warning(f"Failed to parse raw_json_content for synthesis {synthesis_id}: {e}")
        
        synthesis_data = {
            'id': synthesis.id,
            'main_category': synthesis.main_category,
            'sub_category': synthesis.sub_category,
            'synthesis_title': synthesis.synthesis_title,
            'synthesis_content': synthesis.synthesis_content,
            'item_count': synthesis.item_count,
            'created_at': synthesis.created_at.isoformat() if synthesis.created_at else None,
            'last_updated': synthesis.last_updated.isoformat() if synthesis.last_updated else None,
            'file_path': synthesis.file_path,
            'content_html': content_html,
            'content_markdown': content_markdown,
            'raw_json_data': raw_json_data
        }
        
        return jsonify(synthesis_data)
    except Exception as e:
        logging.error(f"Error fetching synthesis {synthesis_id} via API: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch synthesis document'}), 500

@app.route('/synthesis/<int:synthesis_id>')
def synthesis_detail(synthesis_id):
    """Render synthesis document detail page."""
    try:
        synthesis = SubcategorySynthesis.query.get_or_404(synthesis_id)
        
        # Load markdown content if file_path exists
        content_html = ""
        if synthesis.file_path:
            file_path = Path(synthesis.file_path)
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content_markdown = f.read()
                        content_html = markdown(content_markdown, extensions=['fenced_code', 'tables', 'sane_lists', 'md_in_html'])
                except Exception as e:
                    logging.error(f"Error reading synthesis file {file_path}: {e}")
                    content_html = f"<p>Error loading content: {e}</p>"
            else:
                content_html = "<p>Synthesis file not found on disk.</p>"
        else:
            # Fallback to synthesis_content from database
            content_html = markdown(synthesis.synthesis_content, extensions=['fenced_code', 'tables', 'sane_lists', 'md_in_html'])
        
        # Parse raw JSON if available
        raw_json_data = None
        if synthesis.raw_json_content:
            try:
                raw_json_data = json.loads(synthesis.raw_json_content)
            except json.JSONDecodeError as e:
                logging.warning(f"Failed to parse raw_json_content for synthesis {synthesis_id}: {e}")
        
        # Get all items for sidebar (both regular items and syntheses)
        all_items = KnowledgeBaseItem.query.order_by(KnowledgeBaseItem.last_updated.desc()).all()
        all_syntheses = SubcategorySynthesis.query.order_by(SubcategorySynthesis.last_updated.desc()).all()
        
        app_config = getattr(current_app, 'config_instance', None)
        
        # If this is an AJAX request for JSON data, return JSON response
        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                'id': synthesis.id,
                'type': 'synthesis',
                'synthesis_title': synthesis.synthesis_title,
                'main_category': synthesis.main_category,
                'sub_category': synthesis.sub_category,
                'content_html': content_html,
                'item_count': synthesis.item_count,
                'created_at': synthesis.created_at.isoformat() if synthesis.created_at else None,
                'last_updated': synthesis.last_updated.isoformat() if synthesis.last_updated else None,
                'raw_json_data': raw_json_data
            })
        
        # Otherwise, render the full page template
        return render_template('synthesis_detail.html',
                               synthesis=synthesis,
                               content=content_html,
                               items=all_items,
                               syntheses=all_syntheses,
                               current_synthesis_id=synthesis_id,
                               raw_json_data=raw_json_data,
                               config=app_config)
    except Exception as e:
        logging.error(f"Error rendering synthesis detail {synthesis_id}: {e}", exc_info=True)
        return f"Error loading synthesis: {e}", 500

# --- End Synthesis API Routes ---

# --- End Log Viewer Routes ---

@app.route('/kb-media/<path:path>')
def serve_kb_media_generic(path): # Generic handler for single path pattern
    """Serve media files from the kb-generated directory using a single path argument."""
    app_config = getattr(current_app, 'config_instance', None)
    if not app_config:
        return "Application configuration not found", 500

    # Use app_config.knowledge_base_dir as the base path
    base_path = Path(app_config.knowledge_base_dir).resolve()
    file_path = base_path / path
    
    # Validate the path is within the knowledge base directory
    try:
        if not file_path.exists():
            logging.warning(f"Media file not found: {file_path}")
            return "File not found", 404
        
        # Check if the file is within the knowledge base directory
        if not file_path.is_relative_to(base_path):
            logging.warning(f"Attempted to access file outside knowledge base directory: {file_path}")
            return "Access denied", 403
            
        return send_from_directory(base_path, path)
    except Exception as e:
        logging.error(f"Error serving media file {path}: {e}")
        return "Error serving file", 500

# Serve media files with specific category/subcategory/item path pattern
@app.route('/kb-media/<path:category>/<path:subcategory>/<path:item_name>/<path:filename>')
def serve_kb_media(category, subcategory, item_name, filename):
    app_config = getattr(current_app, 'config_instance', None)
    if not app_config:
        return "Application configuration not found", 500
    
    # Construct the path relative to the knowledge_base_dir
    kb_root = Path(app_config.knowledge_base_dir).resolve()
    media_dir = kb_root / category / subcategory / item_name
    file_path = media_dir / filename
    
    try:
        # Security validation - check that the file exists and is within the knowledge base directory
        if not file_path.exists():
            logging.warning(f"Media file not found: {file_path}")
            return "File not found", 404
            
        if not file_path.is_relative_to(kb_root):
            logging.warning(f"Attempted to access file outside knowledge base directory: {file_path}")
            return "Access denied", 403
            
        # Send the file
        return send_from_directory(media_dir, filename)
    except Exception as e:
        logging.error(f"Error serving media file {category}/{subcategory}/{item_name}/{filename}: {e}")
        return "Error serving file", 500

# Serve media files from the media_cache_dir
@app.route('/media_cache/<path:filename>')
def serve_media(filename):
    app_config = getattr(current_app, 'config_instance', None)
    if not app_config:
        return "Application configuration not found", 500
    # media_cache_dir is already an absolute path from Pydantic Config
    return send_from_directory(Path(app_config.media_cache_dir), filename)

# --- FUNCTION TO HANDLE STARTUP SYNC ---
def run_startup_synchronization(app_instance, loaded_config: Config):
    """Runs StateManager initialization (which includes DB sync) within app context."""
    global agent_instance
    with app_instance.app_context():
        try:
            logging.info("Attempting StateManager initialization (includes DB sync) on script startup...")
            if loaded_config:
                state_manager = StateManager(loaded_config)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(state_manager.initialize())
                finally:
                    loop.close()
                logging.info("StateManager initialization completed on script startup.")
                
                # Initialize agent instance at startup for status queries
                logging.info("Creating agent instance at startup...")
                agent_instance = KnowledgeBaseAgent(app_instance, loaded_config, socketio=socketio)
                
                # Initialize the agent to ensure it can respond to status queries
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(agent_instance.initialize())
                    logging.info("Agent instance initialized successfully at startup.")
                except Exception as e:
                    logging.error(f"Failed to initialize agent instance at startup: {e}", exc_info=True)
                finally:
                    loop.close()
            else:
                logging.error("Config not provided to startup synchronization. Skipping StateManager initialization.")
        except Exception as e:
            logging.error(f"Failed during StateManager initialization on script startup: {str(e)}", exc_info=True)
# --- END STARTUP SYNC FUNCTION ---

# Background thread for GPU stats
gpu_stats_thread = None
gpu_stats_stop_event = threading.Event()

def gpu_stats_emitter_thread(app):
    """Periodically fetches GPU stats and emits them via SocketIO."""
    with app.app_context():
        while not gpu_stats_stop_event.is_set():
            try:
                stats = get_gpu_stats()
                if stats:
                    socketio.emit('gpu_stats_update', {'gpus': stats})
                else:
                    socketio.emit('gpu_stats_update', {'error': 'GPU stats not available or nvidia-smi failed.'})
            except Exception as e:
                logging.error(f"Error in GPU stats emitter thread: {e}")
                socketio.emit('gpu_stats_update', {'error': f'Error fetching GPU stats: {str(e)}'})
            
            # Use a shorter interval for more responsive updates
            gpu_stats_stop_event.wait(2)  # Update every 2 seconds

@socketio.on('connect')
def handle_connect(auth=None): # Added auth=None to handle potential argument
    global agent_instance, agent_is_running, current_run_preferences, config # Ensure config is accessible
    emit('log', {'message': 'Client connected', 'level': 'INFO'})
    
    # Build a complete state object to synchronize this client with current state
    initial_state_payload = {
        'agent_is_running': agent_is_running,
        'active_run_preferences': current_run_preferences if agent_is_running else None,
        'full_plan_statuses': {},  # Changed from 'plan_statuses' to match client expectation
        'current_phase_id': None,
        'current_step_in_current_phase_progress_message': None,
        # Safely access config attributes using getattr
        'git_ssh_command': getattr(config, 'git_ssh_command', None) if config else None,
        'git_remote_name': getattr(config, 'git_remote', None) if config else None,
        'git_branch_name': getattr(config, 'git_branch', None) if config else None,
        # Add log history for new client connections
        'log_history': list(recent_logs),
        # Enhanced time estimation data
        'phase_estimated_completion_times': {},  # Legacy support
        'dynamic_phase_estimates': {},  # New: Dynamic phase estimates
        'phase_estimates_timestamp': time.time()  # For cache invalidation
    }

    # Get complete state from agent instance if it exists and agent is running
    if agent_instance and hasattr(agent_instance, 'get_current_state'):
        try:
            agent_state_from_instance = agent_instance.get_current_state()
            
            # Map agent's plan_statuses to client's expected full_plan_statuses
            if 'plan_statuses' in agent_state_from_instance:
                initial_state_payload['full_plan_statuses'] = agent_state_from_instance['plan_statuses']
                del agent_state_from_instance['plan_statuses']  # Remove to avoid overwriting
            
            # Update payload with agent state including dynamic estimates
            initial_state_payload.update(agent_state_from_instance)
            
            # Ensure active_run_preferences is set correctly
            if agent_is_running and current_run_preferences:
                initial_state_payload['active_run_preferences'] = current_run_preferences
            
            # Add the current step message for detailed progress display
            if agent_is_running and agent_state_from_instance.get('current_phase_message'):
                initial_state_payload['current_step_in_current_phase_progress_message'] = agent_state_from_instance['current_phase_message']
            
            # Log the enhanced state information
            dynamic_estimates_count = len(agent_state_from_instance.get('dynamic_phase_estimates', {}))
            current_app.logger.info(f"Emitting initial_status_and_git_config to new client with complete agent state. Running: {agent_is_running}, Phase: {initial_state_payload.get('current_phase_id')}, Plan statuses: {len(initial_state_payload.get('full_plan_statuses', {}))}, Dynamic estimates: {dynamic_estimates_count}")
        except Exception as e:
            current_app.logger.error(f"Error getting agent state: {e}")
    elif not agent_instance:
        current_app.logger.warning("Agent instance not available during client connection - status queries will be limited")
    
    # Send recent log history to new client (but don't overwhelm with too many)
    if recent_logs:
        # Send the last 50 log entries to avoid overwhelming the new client
        recent_logs_list = list(recent_logs)[-50:]
        current_app.logger.info(f"Sending {len(recent_logs_list)} recent log entries to new client")
        for log_entry in recent_logs_list:
            emit('log', log_entry)
    else:
        current_app.logger.warning("No recent logs to send to new client")

    emit('initial_status_and_git_config', initial_state_payload)

@socketio.on('disconnect')
def handle_disconnect():
    current_app.logger.info("Client disconnected")
    pass

@socketio.on('request_initial_status_and_git_config')
def handle_request_initial_status_and_git_config():
    current_app.logger.info("'request_initial_status_and_git_config' event received. Re-emitting current state.")
    handle_connect() # Re-run connect logic to send current state

@socketio.on('clear_server_logs')
def handle_clear_server_logs():
    global recent_logs
    count = len(recent_logs)
    recent_logs.clear()
    logging.info(f"Server-side recent_logs (last {count} entries) cleared by user request.")
    # Emit a log message back to the client to confirm and to be added to the (now empty) UI log display
    socketio.emit('log', {'message': 'Log history cleared by user.', 'level': 'INFO'})

if __name__ == "__main__":
    # Load configuration first
    temp_config = None
    log_file_path_main = None # Specific to main block to avoid confusion with global log_file_path
    try:
        # This is the primary place to load config when script is run directly
        logging.info("Main: Loading configuration...")
        temp_config = asyncio.run(load_config()) # load_config also calls setup_logging and setup_directories
        
        if temp_config:
            # Determine log file path from the loaded config for the main file handler
            log_dir_main = Path(temp_config.log_dir).expanduser().resolve()
            # log_dir_main.mkdir(parents=True, exist_ok=True) # setup_directories in load_config should do this
            run_timestamp_main = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file_path_main = log_dir_main / f'agent_web_main_{run_timestamp_main}.log'
            
            # Update the config's log_file to use our new timestamp-specific path
            temp_config.log_file = str(log_file_path_main)
            
            # Setup web logging (which calls config.setup_logging internally)
            setup_web_logging(temp_config)
            logging.info(f"Main: Configuration loaded. Logging to: {log_file_path_main}")
            
            # Assign to global config *after* successful load and initial log setup
            config = temp_config
            
            # Set config as an app attribute for routes to access
            app.config_instance = config

            # Set the project root in shared_globals as well
            if hasattr(config, 'project_root') and config.project_root:
                sg_set_project_root(config.project_root)
                logging.info(f"Shared global project root set to: {config.project_root}")
            else:
                logging.error("Project root not found on config object after loading. Cannot set shared global project root.")

        else:
            logging.error("Main: Failed to load configuration. Cannot proceed with full initialization.")
            # Basic logging to stdout/stderr will continue via initial basicConfig

    except Exception as e:
        logging.error(f"Main: Critical error during initial config loading: {e}", exc_info=True)
        # Server might not start or run correctly if config fails to load.
        # basicConfig logging will show this error.

    # Run startup synchronization (includes DB sync) IF config was loaded
    if config: # Use the globally assigned config
        # Web logging was already set up during config loading
        run_startup_synchronization(app, config)
    else:
        logging.warning("Main: Skipping startup synchronization because config failed to load.")

    # --- Now start the server ---
    logging.info("Starting Flask-SocketIO server...")

    # Start GPU stats emitter thread if config indicates GPU usage
    if config and getattr(config, 'enable_gpu_stats_monitoring', True):  # Default to True if not specified
        if gpu_stats_thread is None or not gpu_stats_thread.is_alive():
            logging.info("Starting GPU stats emitter thread...")
            gpu_stats_stop_event.clear()  # Ensure the event is cleared
            gpu_stats_thread = threading.Thread(target=gpu_stats_emitter_thread, args=(app,), daemon=True)
            gpu_stats_thread.start()
            logging.info("GPU stats emitter thread started successfully.")
        else:
            logging.info("GPU stats emitter thread already running.")
    else:
        logging.info("GPU stats monitoring is disabled in config.")

    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)