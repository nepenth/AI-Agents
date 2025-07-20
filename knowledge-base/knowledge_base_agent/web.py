# knowledge_base_agent/web.py
import os
print(f"WEB.PY LOADED: __name__={__name__}, cwd={os.getcwd()}", flush=True)

# Standard library imports
import asyncio
import logging
import sys
import threading
from typing import Optional, Iterable
from collections import deque
from datetime import datetime
import json
from logging import handlers
import pickle
import traceback
import tblib.pickling_support
from pathlib import Path

# Third-party imports
from flask import Flask, render_template, request, jsonify, current_app, url_for, send_file, abort, send_from_directory
from flask_socketio import SocketIO, emit
from flask_migrate import Migrate
import markdown
from markupsafe import Markup
from jinja2 import TemplateNotFound
from flask_sqlalchemy import SQLAlchemy

# Celery Migration Imports
from .celery_app import init_celery
from .enhanced_realtime_manager import EnhancedRealtimeManager

# Local imports - only import what's needed at module level
from .config import Config, PROJECT_ROOT
from .prompts import load_user_preferences
from .models import db, KnowledgeBaseItem, SubcategorySynthesis, Setting, AgentState
from .api.routes import bp as api_bp
from knowledge_base_agent.monitoring import initialize_monitoring

# --- Globals & App Initialization ---
logger = logging.getLogger(__name__)

# --- Logging Setup ---
class WebSocketHandler(logging.Handler):
    def emit(self, record):
        try:
            message = record.getMessage()
            
            # ENHANCED: Filter out system/debug messages - only show agent execution logs
            ignore_patterns = [
                'GET /socket.io/', 
                'POST /socket.io/',
                'Starting gevent server',
                'GPU memory configuration',
                'TaskProgressManager: Redis connections established',
                'RealtimeManager Redis listener started',
                'GPU monitoring task started',
                'Subscribed to Redis channels',
                'Redis pub/sub connection closed',
                'TaskProgressManager: Redis connections closed',
                'Debug logging removed',
                'Successfully loaded processing stats',
                'Successfully saved processing stats',
                'Processing categorization for',
                'Finished media processing for tweet',
                'KB item validation failed during final processing'
            ]
            
            # Filter out system logger messages that aren't agent-relevant
            system_loggers = [
                'werkzeug',
                'socketio',
                'engineio', 
                'gevent',
                'urllib3',
                'requests'
            ]
            
            if any(pattern in message for pattern in ignore_patterns):
                return
                
            if any(logger_name in record.name for logger_name in system_loggers):
                return
                
            # Only show INFO and above for Live Logs
            if record.levelno < logging.INFO: 
                return
                
            # Only show agent execution relevant logs
            agent_relevant_patterns = [
                '🚀',  # Agent start/execution
                '✅',  # Success messages
                '❌',  # Error messages  
                '📚',  # Bookmark operations
                '💾',  # Database operations
                '🔄',  # Processing operations
                '⚡',  # Performance/speed indicators
                'Agent',  # Agent-related messages
                'Phase',  # Phase updates
                'Processing',  # Processing updates
                'Completed',  # Completion messages
                'Failed',  # Failure messages
                'Error',  # Error messages
                'Starting',  # Starting operations (agent-level)
                'Finished',  # Finished operations (agent-level)
                'cached',  # Caching operations
                'processed',  # Processing operations
                'generated',  # Generation operations
                'synced',  # Sync operations
                'out of',  # Progress indicators (e.g., "5 out of 10")
                'Celery worker',  # Celery task messages
                'task started',  # Task execution
                'task completed',  # Task completion
            ]
            
            # Only emit if it's agent-relevant or an error/warning
            if (record.levelno >= logging.WARNING or 
                any(pattern.lower() in message.lower() for pattern in agent_relevant_patterns)):
                msg = self.format(record)
                # Additional filtering could be added here if needed
            else:
                return
                
        except Exception as e:
            print(f"CRITICAL: WebSocketHandler failed: {e}", file=sys.stderr)

class WsgiLogFilter:
    """A file-like object that filters WSGI log messages."""
    def __init__(self, target_logger, paths_to_ignore):
        self.target_logger = target_logger
        self.paths_to_ignore = paths_to_ignore

    def write(self, message: str):
        """
        Intercepts raw log messages from the WSGI server, filters them,
        and writes the desired ones to the target logger.
        """
        message = message.strip()
        if not message:
            return
        
        # Suppress noisy, successful polling requests
        if any(ignored_path in message for ignored_path in self.paths_to_ignore):
            # Also check for ' 200 ' or ' 304 ' to ensure we only suppress successful requests
            if ' 200 ' in message or ' 304 ' in message:
                return
        
        # Write the filtered message to the actual application logger
        self.target_logger.info(message)

    def flush(self):
        """Required method for file-like objects."""
        pass

    def writelines(self, lines: Iterable[str]):
        """Required for file-like object protocol compliance."""
        for line in lines:
            self.write(line)


class IgnoreLoggersFilter(logging.Filter):
    """A filter to ignore log records from specific loggers."""
    def __init__(self, loggers_to_ignore):
        super().__init__()
        self.loggers_to_ignore = set(loggers_to_ignore)

    def filter(self, record):
        return record.name not in self.loggers_to_ignore

def setup_web_logging(config_instance: Config, add_ws_handler: bool = True):
    root_logger = logging.getLogger()
    
    # This function is now simplified. Most setup is done in config.py.
    # We only add the real-time handler here.
    
    # Configure SocketIO handler if needed
    if add_ws_handler:
        socketio_handler = WebSocketHandler()
        socketio_handler.setLevel(logging.INFO)
        # Add a filter to prevent the socketio/werkzeug logger from creating a feedback loop
        loggers_to_ignore = {'socketio', 'engineio', 'werkzeug'}
        socketio_handler.addFilter(IgnoreLoggersFilter(loggers_to_ignore))
        root_logger.addHandler(socketio_handler)

    # All other logger configuration is removed as it was ineffective.
    # The WSGI server's access logging is now controlled via the `log` parameter
    # in the gevent.pywsgi.WSGIServer instance created in main().
    
    # --- DEPRECATED: Old Werkzeug logging configuration ---
    # This code is left here as a reference but is no longer used.
    # It was causing a NameError because RequestPathFilter was removed.
    # The new gevent server uses the WsgiLogFilter passed in main().
    #
    # werkzeug_logger = logging.getLogger('werkzeug')
    # werkzeug_logger.setLevel(logging.INFO) 
    # paths_to_ignore = ['/api/agent/status', '/api/logs/recent', '/api/gpu-stats', '/api/system/info']
    # werkzeug_logger.addFilter(RequestPathFilter(paths_to_ignore))
    
    logging.info("Web logging re-configured for real-time handler.")

# Move setup_project_root here
def setup_project_root():
    """Determines and sets the project root directory dynamically for portability."""
    try:
        from .shared_globals import sg_set_project_root
        from . import config
        current_file_dir = Path(__file__).parent
        potential_roots = [
            current_file_dir.parent,
            Path.cwd(),
            current_file_dir.parent.parent,
        ]
        project_root = None
        for root_candidate in potential_roots:
            if (root_candidate / '.env').exists() and (root_candidate / 'knowledge_base_agent').is_dir():
                project_root = root_candidate
                break
        if project_root is None:
            project_root = current_file_dir.parent
            logging.warning(f"Could not detect project root from indicators. Using fallback: {project_root}")
        sg_set_project_root(project_root)
        config.PROJECT_ROOT = project_root
        logging.info(f"PROJECT_ROOT dynamically detected: {project_root}")
        sys.path.insert(0, str(project_root))
    except Exception as e:
        logging.error(f"Error setting up project root: {e}", exc_info=True)

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder='templates', static_folder='static')
    
    # Set the project root directory
    project_root = setup_project_root()
    app.config['PROJECT_ROOT'] = project_root
    
    # Load configuration
    try:
        config_instance = Config()  # type: ignore[call-arg]  # Suppress linter false positive: Pydantic loads from env
        app.config.from_object(config_instance)
        app.config['APP_CONFIG'] = config_instance
        # Add this line to set the SQLAlchemy URI from the Config's database_url
        app.config['SQLALCHEMY_DATABASE_URI'] = config_instance.database_url
        # Set the Celery configuration for init_celery() to find
        app.config['CELERY_CONFIG'] = config_instance.celery_config
        
        # Configure logging as early as possible
        setup_web_logging(config_instance, add_ws_handler=True)
        
    except Exception as e:
        # Use basicConfig for fatal errors before full logging is set up
        logging.basicConfig()
        logging.critical(f"FATAL: Could not load configuration. Error: {e}", exc_info=True)
        sys.exit(1)

    # FIX 1: Enable CORS to allow the frontend to connect to Socket.IO
    socketio = SocketIO(async_mode='gevent', logger=False, engineio_logger=False, cors_allowed_origins="*")
    migrate = Migrate()
    realtime_manager = EnhancedRealtimeManager(socketio, config_instance)

    db.init_app(app)
    socketio.init_app(app)
    migrate.init_app(app, db)
    
    # The new Celery implementation is now the only path.
    # No conditional logic is needed.
    init_celery(app)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # CRITICAL FIX: Start EnhancedRealtimeManager during app initialization
    # This ensures log events are never lost due to late initialization
    try:
        realtime_manager.start_listener()
        logging.info("🚀 EnhancedRealtimeManager started successfully during app initialization")
    except Exception as e:
        logging.error(f"❌ CRITICAL: Failed to start EnhancedRealtimeManager during app initialization: {e}", exc_info=True)
        # Continue app startup but log critical error - this allows the app to start
        # even if realtime manager fails, preventing complete system failure
    
    return app, socketio, migrate, realtime_manager

app, socketio, migrate, realtime_manager = create_app()

# Install tblib support for serializing tracebacks
tblib.pickling_support.install()

# --- State Management Helper ---
def get_or_create_agent_state():
    """Gets the agent state from DB, creating it if it doesn't exist."""
    state = AgentState.query.first()
    if not state:
        logging.info("No agent state found in database, creating a new default one.")
        state = AgentState(
            is_running=False,
            current_phase_message="Idle",
            last_update=datetime.utcnow()
        )
        db.session.add(state)
        db.session.commit()
        logging.info("Default agent state created.")
    return state

# --- Global State ---
# DEPRECATED: These are now managed in the AgentState model in the database.
# agent_is_running = False
# agent_thread = None
# current_run_preferences: Optional[dict] = None
chat_manager = None

# --- Helper Functions & Template Filters ---
def get_chat_manager():
    global chat_manager
    if chat_manager is None:
        config = current_app.config.get('APP_CONFIG')
        if config:
            # Import here to avoid circular imports
            from .http_client import HTTPClient
            from .embedding_manager import EmbeddingManager
            from .chat_manager import ChatManager
            http_client = HTTPClient(config)
            embedding_manager = EmbeddingManager(config, http_client)
            chat_manager = ChatManager(config, http_client, embedding_manager)
    return chat_manager

def get_gpu_stats():
    """Get GPU statistics - import here to avoid circular imports"""
    from .gpu_utils import get_gpu_stats as _get_gpu_stats
    return _get_gpu_stats()

@app.template_filter('markdown')
def markdown_filter(text):
    if not text: return ""
    return Markup(markdown.markdown(text, extensions=['extra', 'codehilite']))

@app.template_filter('fromjson')
def fromjson_filter(text):
    if not text: return None
    try:
        import json
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

# --- Main Application Routes (V1 & V2 Pages) ---
@app.route('/')
def index():
    return render_template('v2/_layout.html')

@app.route('/v2/')
def index_v2():
    # Filter favicon.ico requests at the view level before they hit the logger
    if request.path == '/favicon.ico':
        return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
    return render_template('v2/_layout.html')

@app.route('/v2/page/<string:page_name>')
def serve_v2_page(page_name):
    """Serves the HTML content for different pages of the V2 UI."""
    logging.info(f"V2 page request received: {page_name}")
    
    template_map = {
        'index': 'v2/index.html',
        'chat': 'v2/chat_content.html',
        'kb': 'v2/kb_content.html',
        'synthesis': 'v2/synthesis_content.html',
        'schedule': 'v2/schedule_content.html',
        'logs': 'v2/logs_content.html',
        'environment': 'v2/environment_content.html',
    }
    
    template_name = template_map.get(page_name)
    if template_name:
        try:
            logging.debug(f"Attempting to load template: {template_name}")
            # This is the correct way to check if a template exists with Flask
            template = app.jinja_env.get_template(template_name)
            logging.debug(f"Template {template_name} found, rendering...")
            result = render_template(template_name)
            logging.info(f"Successfully rendered template {template_name}, length: {len(result)}")
            return result
        except TemplateNotFound as e:
            logging.error(f"Template not found: {template_name} - {e}")
            # If the template doesn't exist, fall through to abort
            pass
        except Exception as e:
            logging.error(f"Error rendering template {template_name}: {e}", exc_info=True)
            abort(500)
    
    logging.warning(f"Page name not found in template map: {page_name}")
    abort(404)

# --- Shared Business Logic Functions ---
"""
HYBRID ARCHITECTURE: REST-First with SocketIO Notifications

This section implements our hybrid approach where:
1. REST APIs are the PRIMARY interface for all operations and state management
2. SocketIO serves as a PURE NOTIFICATION LAYER for real-time updates
3. All business logic is centralized in shared functions
4. Both REST and SocketIO endpoints call the same underlying business logic
5. SocketIO handlers are thin wrappers that delegate to shared functions

Benefits:
- Consistent behavior between REST and SocketIO
- Easy testing through REST endpoints
- Reliable fallbacks when SocketIO is unavailable  
- External integrations possible via REST
- Real-time UX through SocketIO notifications

Usage Pattern:
- Frontend uses REST for primary operations (CRUD, state changes)
- Frontend uses SocketIO for real-time notifications (logs, progress, status)
- All SocketIO handlers have REST equivalents
- Business logic functions accept socketio_emit parameter to control notifications
"""

# DEPRECATED and will be removed after full migration
def start_agent_operation(preferences_data, socketio_emit=True):
    """DEPRECATED: Shared business logic for starting agent."""
    logger.warning("Using deprecated start_agent_operation. This will be removed.")
    return {'success': False, 'error': 'Multiprocessing agent start is disabled.'}

def stop_agent_operation(socketio_emit=True):
    """DEPRECATED: Shared business logic for stopping agent."""
    logger.warning("Using deprecated stop_agent_operation. This will be removed.")
    return {'success': False, 'error': 'Multiprocessing agent stop is disabled.'}


def get_gpu_stats_operation(socketio_emit=True):
    """Shared business logic for getting GPU stats. Used by both REST and SocketIO."""
    try:
        stats = get_gpu_stats()
        
        if stats is None:
            error_msg = 'GPU stats not available - nvidia-smi not found or failed'
            logging.warning(error_msg)
            if socketio_emit:
                socketio.emit('gpu_stats', {'error': error_msg})
            return {'success': False, 'error': error_msg}
        else:
            if socketio_emit:
                socketio.emit('gpu_stats', {'gpus': stats})
            return {'success': True, 'gpus': stats}
            
    except Exception as e:
        error_msg = f'Failed to get GPU stats: {str(e)}'
        logging.error(f"Error getting GPU stats: {e}", exc_info=True)
        if socketio_emit:
            socketio.emit('gpu_stats', {'error': error_msg})
        return {'success': False, 'error': error_msg}

def clear_logs_operation(socketio_emit=True):
    """Shared business logic for clearing logs. Used by both REST and SocketIO."""
    logging.info("Server logs cleared")
    
    if socketio_emit:
        # Notify all clients to clear their logs too
        socketio.emit('logs_cleared')
    
    return {'success': True, 'message': 'Server logs cleared successfully'}

# --- Socket.IO Handlers (Now Thin Notification Layer) ---

# Track if background tasks are started
_background_tasks_started = False

@socketio.on('connect')
def handle_connect(auth=None):
    """SocketIO: Notify client of connection and send initial state."""
    global _background_tasks_started
    
    logging.info("Client connected")
    
    # Start background tasks on first client connection only
    if not _background_tasks_started:
        if get_gpu_stats() is not None:
            socketio.start_background_task(monitor_gpu_stats, socketio)
        _background_tasks_started = True
        logging.debug("GPU monitoring task started on first client connection.")

    # REMOVED: Realtime manager initialization - now handled during app startup
    # This ensures logs are never lost due to late initialization
    
    state = get_or_create_agent_state()
    emit('agent_status', state.to_dict())
    emit('initial_logs', {'logs': []})
    config = current_app.config.get('APP_CONFIG')
    if config:
        # Use safe attribute access with defaults - Git is now always available
        git_auto_commit = getattr(config, 'git_auto_commit', False)  # Default to manual control
        git_auto_push = getattr(config, 'git_auto_push', False)      # Default to manual control
        emit('git_config_status', {'auto_commit': git_auto_commit, 'auto_push': git_auto_push})

@socketio.on('request_initial_status_and_git_config')
def handle_request_initial_status_and_git_config():
    """SocketIO: Send initial status and git config (notification only)."""
    state = get_or_create_agent_state()
    config = current_app.config.get('APP_CONFIG')
    git_config = {}
    if config:
        # Use safe attribute access with defaults - Git is now always available
        git_auto_commit = getattr(config, 'git_auto_commit', False)  # Default to manual control
        git_auto_push = getattr(config, 'git_auto_push', False)      # Default to manual control
        git_config = {'auto_commit': git_auto_commit, 'auto_push': git_auto_push}
    
    status_data = state.to_dict()
    status_data['git_config'] = git_config
    
    emit('initial_status_and_git_config', status_data)
    
    emit('initial_logs', {'logs': []})

@socketio.on('request_initial_logs')
def handle_request_initial_logs():
    """SocketIO: Send current logs to the requesting client (notification only)."""
    emit('initial_logs', {'logs': []})

@socketio.on('clear_server_logs')
def handle_clear_server_logs():
    """SocketIO: Delegate to shared business logic for clearing logs."""
    clear_logs_operation(socketio_emit=True)

@socketio.on('disconnect')
def handle_disconnect():
    """SocketIO: Handle client disconnection (notification only)."""
    logging.info("Client disconnected")

@socketio.on('run_agent')
def handle_run_agent(data):
    """SocketIO handler now delegates to Celery."""
    from .tasks import run_agent_task, generate_task_id
    
    preferences = data.get('preferences', {})
    task_id = generate_task_id()
    
    # Queue Celery task
    run_agent_task.apply_async(
        args=[task_id, preferences],
        task_id=task_id
    )

    # Emit immediate response (preserves current UI behavior)
    emit('agent_status_update', {
        'is_running': True,
        'task_id': task_id,
        'current_phase_message': 'Agent execution queued'
    })

@socketio.on('stop_agent')
def handle_stop_agent(data):
    """SocketIO handler to stop a Celery task."""
    from .celery_app import celery_app
    
    task_id = data.get('task_id')
    if task_id:
        celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
        emit('agent_status_update', {'is_running': False, 'current_phase_message': 'Agent stop requested.'})

@socketio.on('request_gpu_stats')
def handle_request_gpu_stats():
    """SocketIO: Delegate to shared business logic for GPU stats."""
    get_gpu_stats_operation(socketio_emit=True)

# --- Main Execution ---

def monitor_gpu_stats(socketio_instance):
    """Monitors GPU stats and emits them periodically."""
    # This function remains as it is, independent of Celery migration
    while True:
        try:
            stats = get_gpu_stats()
            if stats:
                socketio_instance.emit('gpu_stats', stats)
        except Exception as e:
            logger.error(f"Error in GPU monitor: {e}", exc_info=True)
        socketio_instance.sleep(5) 



def main():
    """
    Main entry point for running the web server.
    Uses the globally initialized app and socketio instances.
    """
    config = app.config.get('APP_CONFIG')
    if not config:
        logging.error("APP_CONFIG not found in Flask app config. Cannot start server.")
        return

    # FIX: Add the real-time WebSocket logging handler, only when running as a web server.
        setup_web_logging(config, add_ws_handler=True)

    logging.info(f"Starting gevent server on {config.web_server_host}:{config.web_server_port}")
    
    # FIX: Manually create the gevent WSGI server to pass our custom logger.
    # This avoids the 'multiple values for keyword argument "log"' TypeError
    # that occurs with some versions of flask-socketio's run() method.
    from gevent import pywsgi

    paths_to_ignore = ['/api/agent/status', '/api/logs/recent', '/api/gpu-stats', '/api/system/info', '/socket.io/']
    wsgi_log_filter = WsgiLogFilter(logging.getLogger(), paths_to_ignore)
    
    # The Flask `app` object is already patched by `socketio.init_app(app)`,
    # so it can handle WebSocket requests when served this way.
    server = pywsgi.WSGIServer(
        (config.web_server_host, config.web_server_port), 
        app,
        log=wsgi_log_filter
    )
    
    server.serve_forever()


if __name__ == '__main__':
    main()