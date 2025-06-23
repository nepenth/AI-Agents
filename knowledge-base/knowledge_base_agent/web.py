# knowledge_base_agent/web.py
import os
print(f"WEB.PY LOADED: __name__={__name__}, cwd={os.getcwd()}", flush=True)

# Standard library imports
import asyncio
import logging
import sys

from typing import Optional
from collections import deque

# Third-party imports
from flask import Flask, render_template, request, jsonify, current_app, url_for, send_file, abort
from flask_socketio import SocketIO, emit
from flask_migrate import Migrate
import markdown
from markupsafe import Markup

# Local imports
from .config import Config
from .models import db, KnowledgeBaseItem, SubcategorySynthesis
from .main import load_config, run_agent_from_preferences
from .gpu_utils import get_gpu_stats
from .api.routes import bp as api_bp
from .chat_manager import ChatManager

# --- Helper Functions ---



# --- Globals and App Initialization ---

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'secret!' # Replace with a real secret key

# Explicitly construct the database path to avoid Flask-SQLAlchemy fallback behavior
# This resolves to: /path/to/project/instance/knowledge_base.db
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instance", "knowledge_base.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Log the database URI for debugging
print(f"DATABASE URI: {app.config['SQLALCHEMY_DATABASE_URI']}", flush=True)

db.init_app(app)
socketio = SocketIO(app, async_mode='gevent', logger=False, engineio_logger=False)
migrate = Migrate(app, db)
app.register_blueprint(api_bp, url_prefix='/api')

# Global state
agent_is_running = False
agent_thread = None
current_run_preferences: Optional[dict] = None
recent_logs = deque(maxlen=400)

# Initialize ChatManager if not already done
chat_manager = None

def get_chat_manager():
    """Get or create ChatManager instance."""
    global chat_manager
    if chat_manager is None:
        config = current_app.config.get('APP_CONFIG')
        if config:
            from .http_client import HTTPClient
            from .embedding_manager import EmbeddingManager
            
            http_client = HTTPClient(config)
            embedding_manager = EmbeddingManager(config, http_client)
            chat_manager = ChatManager(config, http_client, embedding_manager)
    return chat_manager

# --- Template Filters ---

@app.template_filter('markdown')
def markdown_filter(text):
    """Convert markdown text to HTML."""
    if not text:
        return ""
    return Markup(markdown.markdown(text, extensions=['extra', 'codehilite']))

@app.template_filter('fromjson')
def fromjson_filter(text):
    """Parse JSON string to Python object."""
    if not text:
        return None
    try:
        import json
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

# --- Logging Setup ---

class WebSocketHandler(logging.Handler):
    def emit(self, record):
        try:
            # Filter out noisy log messages
            message = record.getMessage()
            if any(noise in message.lower() for noise in [
                "emitting event", 
                "gpu stats result", 
                "gpu stats requested",
                "emitting gpu stats",
                "client connected",
                "client disconnected",
                "gpu stats for",
                "emitting gpu",
                "received initial_status_and_git_config",
                "agent status update"
            ]) or "gpu stats" in message.lower():
                return
                
            # Only show INFO level and above
            if record.levelno < logging.INFO: 
                return
                
            msg = self.format(record)
            recent_logs.append({'message': msg, 'level': record.levelname})
            socketio.emit('log', {'message': msg, 'level': record.levelname})
        except Exception as e:
            print(f"CRITICAL: WebSocketHandler failed: {e}", file=sys.stderr)

def setup_web_logging(config_instance: Config):
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config_instance.log_level.upper())
    console_handler.setFormatter(logging.Formatter(config_instance.log_format))
    root_logger.addHandler(console_handler)

    if config_instance.log_file:
        file_handler = logging.FileHandler(config_instance.log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(config_instance.log_format))
        root_logger.addHandler(file_handler)

    ws_handler = WebSocketHandler()
    ws_handler.setLevel(logging.INFO)
    ws_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(ws_handler)
    
    root_logger.setLevel(logging.DEBUG)
    logging.info("Web logging re-configured.")

# --- Main Application Routes ---

@app.route('/')
def index():
    app_config = current_app.config.get('APP_CONFIG')
    items = []
    syntheses = []
    try:
        items = KnowledgeBaseItem.query.order_by(KnowledgeBaseItem.last_updated.desc()).all()
        syntheses = SubcategorySynthesis.query.order_by(SubcategorySynthesis.last_updated.desc()).all()
    except Exception as e:
        logging.error(f"Error retrieving sidebar items: {e}", exc_info=True)
    return render_template('index.html', running=agent_is_running, items=items, syntheses=syntheses, config=app_config)
    
@app.route('/agent_control_panel')
def agent_control_panel():
    return render_template('agent_control_panel.html')

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    item = KnowledgeBaseItem.query.get_or_404(item_id)
    
    # Check if JSON response is requested
    if request.args.get('format') == 'json' or request.headers.get('Accept') == 'application/json':
        # Parse raw JSON content if it exists
        raw_json_content_parsed = None
        if item.raw_json_content:
            try:
                import json
                raw_json_content_parsed = json.loads(item.raw_json_content)
            except (json.JSONDecodeError, TypeError):
                raw_json_content_parsed = None
        
        # Parse media paths
        media_files_for_template = []
        if item.kb_media_paths:
            try:
                import json
                media_paths = json.loads(item.kb_media_paths)
                if isinstance(media_paths, list):
                    for media_path in media_paths:
                        filename = media_path.split('/')[-1] if media_path else 'unknown'
                        media_type = 'image' if any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']) else 'video' if any(filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']) else 'other'
                        media_files_for_template.append({
                            'name': filename,
                            'url': url_for('serve_kb_media_generic', path=media_path),
                            'type': media_type
                        })
            except (json.JSONDecodeError, TypeError):
                pass
        
        item_data = {
            'id': item.id,
            'tweet_id': item.tweet_id,
            'title': item.title,
            'display_title': item.display_title,
            'description': item.description,
            'content': item.content,
            'main_category': item.main_category,
            'sub_category': item.sub_category,
            'item_name': item.item_name,
            'source_url': item.source_url,
            'created_at': item.created_at.isoformat() if item.created_at else None,
            'last_updated': item.last_updated.isoformat() if item.last_updated else None,
            'file_path': item.file_path,
            'kb_media_paths': item.kb_media_paths,
            'raw_json_content': item.raw_json_content,
            'raw_json_content_parsed': raw_json_content_parsed,
            'media_files_for_template': media_files_for_template
        }
        return jsonify(item_data)
    
    return render_template('item_detail_content.html', item=item)

@app.route('/synthesis/<int:synthesis_id>')
def synthesis_detail(synthesis_id):
    synth = SubcategorySynthesis.query.get_or_404(synthesis_id)
    
    # Check if JSON response is requested
    if request.args.get('format') == 'json' or request.headers.get('Accept') == 'application/json':
        # Parse raw JSON content if it exists
        raw_json_content_parsed = None
        if synth.raw_json_content:
            try:
                import json
                raw_json_content_parsed = json.loads(synth.raw_json_content)
            except (json.JSONDecodeError, TypeError):
                raw_json_content_parsed = None
        
        synthesis_data = {
            'id': synth.id,
            'synthesis_title': synth.synthesis_title,
            'synthesis_short_name': synth.synthesis_short_name,
            'main_category': synth.main_category,
            'sub_category': synth.sub_category,
            'synthesis_content': synth.synthesis_content,
            'raw_json_content': synth.raw_json_content,
            'raw_json_content_parsed': raw_json_content_parsed,
            'item_count': synth.item_count,
            'file_path': synth.file_path,
            'created_at': synth.created_at.isoformat() if synth.created_at else None,
            'last_updated': synth.last_updated.isoformat() if synth.last_updated else None
        }
        return jsonify(synthesis_data)
    
    return render_template('synthesis_detail_content.html', synthesis=synth)

@app.route('/syntheses')
def syntheses_list_page():
    return render_template('syntheses_list_content.html')

@app.route('/chat')
def chat_page():
    return render_template('chat_content.html')

@app.route('/schedule')
def schedule_page():
    return render_template('schedule_content.html')

@app.route('/environment')
def environment_page():
    return render_template('environment_content.html')

@app.route('/logs')
def logs_page():
    return render_template('logs_content.html')

@app.route('/media/<path:path>')
def serve_kb_media_generic(path):
    """Serve media files from the knowledge base."""
    try:
        config = current_app.config.get('APP_CONFIG')
        if not config:
            abort(500, description="App config not available")
        
        # Construct full path to media file
        media_file_path = config.knowledge_base_dir / path
        
        # Security check - ensure path is within knowledge base directory
        try:
            media_file_path.resolve().relative_to(config.knowledge_base_dir.resolve())
        except ValueError:
            abort(403, description="Access forbidden")
        
        if not media_file_path.exists():
            abort(404, description="Media file not found")
        
        return send_file(str(media_file_path))
    except Exception as e:
        logging.error(f"Error serving media file {path}: {e}", exc_info=True)
        abort(500, description="Failed to serve media file")

# --- API Routes ---

# API routes moved to api/routes.py for better organization

# --- Socket.IO Handlers ---

@socketio.on('connect')
def handle_connect(auth=None):
    logging.info("Client connected")
    emit('agent_status', {'is_running': agent_is_running, 'preferences': current_run_preferences})
    emit('initial_logs', {'logs': list(recent_logs)})
    config = current_app.config.get('APP_CONFIG')
    if config:
        # Use safe attribute access with defaults - Git is now always available
        git_auto_commit = getattr(config, 'git_auto_commit', False)  # Default to manual control
        git_auto_push = getattr(config, 'git_auto_push', False)      # Default to manual control
        emit('git_config_status', {'auto_commit': git_auto_commit, 'auto_push': git_auto_push})

@socketio.on('request_initial_status_and_git_config')
def handle_request_initial_status_and_git_config():
    config = current_app.config.get('APP_CONFIG')
    git_config = {}
    if config:
        # Use safe attribute access with defaults - Git is now always available
        git_auto_commit = getattr(config, 'git_auto_commit', False)  # Default to manual control
        git_auto_push = getattr(config, 'git_auto_push', False)      # Default to manual control
        git_config = {'auto_commit': git_auto_commit, 'auto_push': git_auto_push}
    
    emit('initial_status_and_git_config', {
        'agent_is_running': agent_is_running,
        'is_running': agent_is_running,
        'current_phase_id': None,  # This would need to be tracked if needed
        'active_run_preferences': current_run_preferences,
        'git_config': git_config
    })
    
    # Also send current logs
    emit('initial_logs', {'logs': list(recent_logs)})

@socketio.on('request_initial_logs')
def handle_request_initial_logs():
    """Send current logs to the requesting client"""
    emit('initial_logs', {'logs': list(recent_logs)})

@socketio.on('clear_server_logs')
def handle_clear_server_logs():
    """Clear the server-side log buffer"""
    global recent_logs
    recent_logs.clear()
    logging.info("Server logs cleared by client request")
    # Notify all clients to clear their logs too
    emit('logs_cleared', broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    logging.info("Client disconnected")

@socketio.on('run_agent')
def handle_run_agent(data):
    global agent_is_running, agent_thread, current_run_preferences
    if agent_is_running:
        emit('error', {'message': 'Agent is already running.'})
        return

    logging.info(f"Agent run initiated with preferences: {data}")

    def run_agent_in_thread():
        """Run the agent in a background thread with direct SocketIO access."""
        global agent_is_running, agent_thread, current_run_preferences
        # Push an application context to make 'current_app' and other Flask globals available.
        with app.app_context():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                app_config = current_app.config.get('APP_CONFIG')
                if not app_config:
                    logging.error("Failed to get APP_CONFIG for agent thread.")
                    return

                # Re-apply WebSocket logging to this new thread
                setup_web_logging(app_config)
                
                logging.info("Agent thread started. Executing agent from preferences.")
                
                # Pass the received preferences to the agent runner
                loop.run_until_complete(run_agent_from_preferences(preferences=data))
                
            except Exception as e:
                logging.error(f"Exception in agent thread: {e}", exc_info=True)
                socketio.emit('agent_error', {'message': f'An error occurred: {e}'})
            finally:
                # Ensure state is always reset, regardless of success or failure
                logging.info("Agent thread finished, resetting global state.")
                agent_is_running = False
                agent_thread = None
                current_run_preferences = None
                socketio.emit('agent_status_update', {'is_running': False})

    agent_thread = socketio.start_background_task(run_agent_in_thread)

@socketio.on('stop_agent')
def handle_stop_agent():
    global agent_is_running, agent_thread, current_run_preferences
    logging.info("'stop_agent' event received.")
    
    # Set the stop flag for the agent
    from .agent import stop_flag
    stop_flag.set()
    
    agent_is_running = False
    current_run_preferences = None
    emit('agent_status', {'is_running': False, 'preferences': None})
    emit('info', {'message': 'Agent run stopped by user.'})
    logging.info("Stop flag set, agent should stop gracefully.")

@socketio.on('request_gpu_stats')
def handle_request_gpu_stats():
    try:
        logging.debug("GPU stats requested via SocketIO")
        stats = get_gpu_stats()
        logging.debug(f"GPU stats result: {stats}")
        
        if stats is None:
            logging.warning("GPU stats returned None - nvidia-smi not available or failed")
            emit('gpu_stats', {'error': 'GPU stats not available - nvidia-smi not found or failed'})
        else:
            logging.debug(f"Emitting GPU stats for {len(stats)} GPU(s)")
            emit('gpu_stats', {'gpus': stats})
    except Exception as e:
        logging.error(f"Error getting GPU stats: {e}", exc_info=True)
        emit('gpu_stats', {'error': f'Failed to get GPU stats: {str(e)}'})

# Chat API routes moved to api/routes.py

# Schedule API routes moved to api/routes.py

# Environment variable endpoints moved to api/routes.py to avoid conflicts

# Chat session API routes moved to api/routes.py

# --- Main Execution ---

if __name__ == "__main__":
    # Ensure basic logging is configured early so configuration errors are shown
    import logging
    logging.basicConfig(level=logging.DEBUG)
    try:
        config_instance = asyncio.run(load_config())
        print("CONFIG LOADED OK", flush=True)
        app.config['APP_CONFIG'] = config_instance
        
        with app.app_context():
            db.create_all()
            logging.info("Database tables verified/created.")
            print("DB create_all OK", flush=True)

        setup_web_logging(config_instance)
        print("SETUP_WEB_LOGGING OK", flush=True)
        
        # Provide clear console feedback and start server without undefined debug attribute
        print("=== Starting Flask-SocketIO server on http://0.0.0.0:5000 ===", flush=True)
        logging.info("Starting Flask-SocketIO server...")
        socketio.run(app, host='0.0.0.0', port=5000, use_reloader=False)

    except Exception:
        # Print full traceback to stderr so we see what went wrong during startup
        import traceback, sys as _sys
        _sys.stderr.write("Startup exception in web.py. Full traceback below:\n")
        traceback.print_exc(file=_sys.stderr)
        _sys.exit(1)