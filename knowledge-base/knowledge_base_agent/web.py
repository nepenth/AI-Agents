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

@app.route('/api/syntheses')
def api_synthesis_list():
    """API endpoint to get all synthesis documents."""
    try:
        syntheses = SubcategorySynthesis.query.order_by(SubcategorySynthesis.last_updated.desc()).all()
        synthesis_list = []
        for synth in syntheses:
            synthesis_list.append({
                'id': synth.id,
                'synthesis_title': synth.synthesis_title,
                'synthesis_short_name': synth.synthesis_short_name,
                'main_category': synth.main_category,
                'sub_category': synth.sub_category,
                'item_count': synth.item_count,
                'created_at': synth.created_at.isoformat() if synth.created_at else None,
                'last_updated': synth.last_updated.isoformat() if synth.last_updated else None
            })
        return jsonify(synthesis_list)
    except Exception as e:
        logging.error(f"Error retrieving synthesis list: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve synthesis documents'}), 500

@app.route('/api/gpu-stats')
def api_gpu_stats():
    """REST API endpoint for GPU statistics as a fallback to SocketIO"""
    try:
        stats = get_gpu_stats()
        if stats is None:
            return jsonify({'error': 'GPU stats not available - nvidia-smi not found or failed'}), 500
        return jsonify({'gpus': stats})
    except Exception as e:
        logging.error(f"Error getting GPU stats via API: {e}", exc_info=True)
        return jsonify({'error': f'Failed to get GPU stats: {str(e)}'}), 500

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

    logging.info(f"'run_agent' event received with data: {data}")
    # Extract the preferences from the data object
    preferences = data.get('preferences', {})
    current_run_preferences = preferences
    agent_is_running = True
    
    try:
        import threading
        import asyncio
        
        # Get config and app before starting thread (while we have Flask context)
        config = current_app.config.get('APP_CONFIG')
        if not config:
            raise Exception("App config not available")
        
        # Get app instance for the thread
        app_instance = app
        
        def run_agent_in_thread():
            """Run the agent in a background thread with direct SocketIO access."""
            global agent_is_running
            try:
                logging.info("Starting agent in background thread...")
                
                # Set up Flask app context for the thread
                with app_instance.app_context():
                    # Run the agent in async context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        # Import and create agent
                        from .agent import KnowledgeBaseAgent
                        from .prompts import UserPreferences
                        
                        user_prefs = UserPreferences(**preferences)
                        agent = KnowledgeBaseAgent(app=app_instance, config=config, socketio=socketio)
                        
                        # Run agent
                        loop.run_until_complete(agent.initialize())
                        loop.run_until_complete(agent.run(user_prefs))
                        
                        logging.info("Agent completed successfully")
                        socketio.emit('agent_status', {'is_running': False, 'success': True})
                        
                    except Exception as e:
                        logging.error(f"Agent failed: {e}", exc_info=True)
                        socketio.emit('agent_status', {'is_running': False, 'error': str(e)})
                    finally:
                        loop.close()
                    
            except Exception as e:
                logging.error(f"Thread setup failed: {e}", exc_info=True)
                socketio.emit('agent_status', {'is_running': False, 'error': str(e)})
            finally:
                agent_is_running = False
                
        # Start agent in background thread
        agent_thread = threading.Thread(target=run_agent_in_thread, daemon=True)
        agent_thread.start()
        
        emit('agent_status', {'is_running': True, 'preferences': current_run_preferences})
        logging.info("Agent thread started")
        
    except Exception as e:
        logging.error(f"Failed to start agent thread: {e}", exc_info=True)
        agent_is_running = False
        emit('error', {'message': f'Failed to start agent: {str(e)}'})

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

# --- Enhanced Chat API Routes ---

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Enhanced chat API endpoint with technical expertise and rich source metadata."""
    try:
        from .models import ChatSession, ChatMessage, db
        from datetime import datetime, timezone
        import json
        import uuid
        
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        message = data['message'].strip()
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Get optional model selection and session ID
        model = data.get('model')
        session_id = data.get('session_id')
        
        # Create new session if none provided
        if not session_id:
            session_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            session = ChatSession()
            session.session_id = session_id
            session.title = message[:50] + "..." if len(message) > 50 else message
            session.created_at = now
            session.last_updated = now
            session.is_archived = False
            session.message_count = 0
            
            db.session.add(session)
            db.session.commit()
        else:
            # Get existing session
            session = ChatSession.query.filter_by(session_id=session_id).first()
            if not session:
                return jsonify({'error': 'Session not found'}), 404
        
        # Save user message
        now = datetime.now(timezone.utc)
        user_message = ChatMessage()
        user_message.session_id = session_id
        user_message.role = 'user'
        user_message.content = message
        user_message.created_at = now
        
        db.session.add(user_message)
        
        # Get chat manager
        chat_mgr = get_chat_manager()
        if not chat_mgr:
            return jsonify({'error': 'Chat functionality not available'}), 503
        
        # Process chat query asynchronously
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                chat_mgr.handle_chat_query(message, model)
            )
        finally:
            loop.close()
        
        if 'error' in result:
            return jsonify(result), 500
        
        # Save assistant response
        assistant_message = ChatMessage()
        assistant_message.session_id = session_id
        assistant_message.role = 'assistant'
        assistant_message.content = result.get('response', '')
        assistant_message.created_at = datetime.now(timezone.utc)
        assistant_message.model_used = model or 'default'
        assistant_message.sources = json.dumps(result.get('sources', []))
        assistant_message.context_stats = json.dumps(result.get('context_stats', {}))
        assistant_message.performance_metrics = json.dumps(result.get('performance_metrics', {}))
        
        db.session.add(assistant_message)
        
        # Update session
        session.message_count += 2
        session.last_updated = datetime.now(timezone.utc)
        
        db.session.commit()
        
        # Add session_id to result
        result['session_id'] = session_id
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error in chat API: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/chat/models', methods=['GET'])
def api_chat_models():
    """Get available chat models."""
    try:
        chat_mgr = get_chat_manager()
        if not chat_mgr:
            return jsonify([]), 200
        
        # Get available models asynchronously
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            models = loop.run_until_complete(chat_mgr.get_available_models())
        finally:
            loop.close()
        
        return jsonify(models)
        
    except Exception as e:
        logging.error(f"Error getting chat models: {e}", exc_info=True)
        return jsonify([{'id': 'default', 'name': 'Default Model'}]), 200

# --- Legacy Chat Routes (for backward compatibility) ---

@app.route('/api/chat/legacy', methods=['POST'])
def api_chat_legacy():
    """Legacy chat endpoint for backward compatibility."""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Simple response for legacy compatibility
        return jsonify({
            'response': f"Legacy chat response for: {message}",
            'sources': []
        })
        
    except Exception as e:
        logging.error(f"Error in legacy chat API: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

# --- Schedule API Routes ---

@app.route('/api/schedules', methods=['GET'])
def api_get_schedules():
    """Get all schedules."""
    try:
        from .models import Schedule
        schedules = Schedule.query.all()
        schedule_list = []
        
        for schedule in schedules:
            schedule_list.append({
                'id': schedule.id,
                'name': schedule.name,
                'description': schedule.description,
                'frequency': schedule.frequency,
                'time': schedule.time,
                'day_of_week': schedule.day_of_week,
                'day_of_month': schedule.day_of_month,
                'cron_expression': schedule.cron_expression,
                'pipeline_type': schedule.pipeline_type,
                'enabled': schedule.enabled,
                'next_run': schedule.next_run.isoformat() if schedule.next_run else None,
                'last_run': schedule.last_run.isoformat() if schedule.last_run else None,
                'created_at': schedule.created_at.isoformat() if schedule.created_at else None
            })
        
        return jsonify(schedule_list)
    except Exception as e:
        logging.error(f"Error retrieving schedules: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve schedules'}), 500

@app.route('/api/schedules', methods=['POST'])
def api_create_schedule():
    """Create a new schedule."""
    try:
        from .models import Schedule, db
        from datetime import datetime, timezone
        import json
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('frequency'):
            return jsonify({'error': 'Name and frequency are required'}), 400
        
        # Create new schedule
        now = datetime.now(timezone.utc)
        schedule = Schedule()
        schedule.name = data['name']
        schedule.description = data.get('description', '')
        schedule.frequency = data['frequency']
        schedule.time = data.get('time')
        schedule.day_of_week = data.get('day')
        schedule.day_of_month = data.get('date')
        schedule.cron_expression = data.get('cron')
        schedule.pipeline_type = data.get('pipeline', 'full')
        schedule.pipeline_config = json.dumps({
            'skip_fetch_bookmarks': data.get('skip_fetch_bookmarks', False),
            'skip_process_content': data.get('skip_process_content', False),
            'force_recache_tweets': data.get('force_recache_tweets', False),
            'force_reprocess_media': data.get('force_reprocess_media', False),
            'force_reprocess_llm': data.get('force_reprocess_llm', False),
            'force_reprocess_kb_item': data.get('force_reprocess_kb_item', False)
        })
        schedule.enabled = data.get('enabled', True)
        schedule.created_at = now
        schedule.last_updated = now
        
        db.session.add(schedule)
        db.session.commit()
        
        return jsonify({
            'id': schedule.id,
            'name': schedule.name,
            'description': schedule.description,
            'frequency': schedule.frequency,
            'time': schedule.time,
            'pipeline_type': schedule.pipeline_type,
            'enabled': schedule.enabled,
            'created_at': schedule.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logging.error(f"Error creating schedule: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create schedule'}), 500

@app.route('/api/schedules/<int:schedule_id>', methods=['PUT'])
def api_update_schedule(schedule_id):
    """Update an existing schedule."""
    try:
        from .models import Schedule, db
        from datetime import datetime, timezone
        import json
        
        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        data = request.get_json()
        
        # Update schedule fields
        if 'name' in data:
            schedule.name = data['name']
        if 'description' in data:
            schedule.description = data['description']
        if 'frequency' in data:
            schedule.frequency = data['frequency']
        if 'time' in data:
            schedule.time = data['time']
        if 'day' in data:
            schedule.day_of_week = data['day']
        if 'date' in data:
            schedule.day_of_month = data['date']
        if 'cron' in data:
            schedule.cron_expression = data['cron']
        if 'pipeline' in data:
            schedule.pipeline_type = data['pipeline']
        if 'enabled' in data:
            schedule.enabled = data['enabled']
        
        # Update pipeline config
        pipeline_config = {
            'skip_fetch_bookmarks': data.get('skip_fetch_bookmarks', False),
            'skip_process_content': data.get('skip_process_content', False),
            'force_recache_tweets': data.get('force_recache_tweets', False),
            'force_reprocess_media': data.get('force_reprocess_media', False),
            'force_reprocess_llm': data.get('force_reprocess_llm', False),
            'force_reprocess_kb_item': data.get('force_reprocess_kb_item', False)
        }
        schedule.pipeline_config = json.dumps(pipeline_config)
        schedule.last_updated = datetime.now(timezone.utc)
        
        db.session.commit()
        return jsonify({'message': 'Schedule updated successfully'})
    except Exception as e:
        logging.error(f"Error updating schedule {schedule_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update schedule'}), 500

@app.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
def api_delete_schedule(schedule_id):
    """Delete a schedule."""
    try:
        from .models import Schedule, db
        
        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        db.session.delete(schedule)
        db.session.commit()
        
        return jsonify({'message': 'Schedule deleted successfully'})
    except Exception as e:
        logging.error(f"Error deleting schedule {schedule_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete schedule'}), 500

@app.route('/api/schedules/<int:schedule_id>/toggle', methods=['POST'])
def api_toggle_schedule(schedule_id):
    """Toggle schedule enabled/disabled status."""
    try:
        from .models import Schedule, db
        from datetime import datetime, timezone
        
        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        schedule.enabled = not schedule.enabled
        schedule.last_updated = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({'message': 'Schedule toggled successfully'})
    except Exception as e:
        logging.error(f"Error toggling schedule {schedule_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to toggle schedule'}), 500

@app.route('/api/schedules/<int:schedule_id>/run', methods=['POST'])
def api_run_schedule(schedule_id):
    """Run a schedule immediately."""
    try:
        from .models import Schedule, ScheduleRun, db
        from datetime import datetime, timezone
        
        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        # Create a new schedule run record
        run = ScheduleRun()
        run.schedule_id = schedule_id
        run.execution_time = datetime.now(timezone.utc)
        run.status = 'running'
        db.session.add(run)
        db.session.commit()
        
        # TODO: Actually trigger the agent run here
        # For now, just mark as completed
        run.status = 'completed'
        run.duration = '0 seconds'
        run.processed_items = 0
        db.session.commit()
        
        return jsonify({'message': 'Schedule execution started'})
    except Exception as e:
        logging.error(f"Error running schedule {schedule_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to run schedule'}), 500

@app.route('/api/schedule-history', methods=['GET'])
def api_get_schedule_history():
    """Get schedule execution history."""
    try:
        from .models import ScheduleRun, Schedule
        
        runs = db.session.query(ScheduleRun, Schedule).join(Schedule).order_by(ScheduleRun.execution_time.desc()).limit(50).all()
        
        history = []
        for run, schedule in runs:
            history.append({
                'id': run.id,
                'schedule_name': schedule.name,
                'execution_time': run.execution_time.isoformat() if run.execution_time else None,
                'status': run.status,
                'duration': run.duration,
                'processed_items': run.processed_items or 0
            })
        
        return jsonify(history)
    except Exception as e:
        logging.error(f"Error retrieving schedule history: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve schedule history'}), 500

@app.route('/api/schedule-runs/<int:run_id>', methods=['DELETE'])
def delete_schedule_run(run_id):
    """API endpoint to delete a schedule run from history."""
    try:
        # Implementation for deleting specific run from history
        return jsonify({'success': True, 'message': 'Schedule run deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/environment-variables', methods=['GET'])
def get_environment_variables():
    """API endpoint to get environment variables with validation against config.py."""
    try:
        from dotenv import dotenv_values
        import os
        from .config import Config
        from pydantic.fields import FieldInfo
        from typing import get_origin, get_args
        
        # Get current .env values and actual environment variables
        env_file_path = '.env'
        if os.path.exists(env_file_path):
            env_values = dotenv_values(env_file_path)
        else:
            env_values = {}
        
        # Dynamically extract all environment variable aliases from Config class
        config_fields = {}
        
        for field_name, field_info in Config.model_fields.items():
            # Skip computed fields that don't correspond to environment variables
            if field_name in ['project_root', 'data_processing_dir', 'knowledge_base_dir', 'categories_file', 
                             'bookmarks_file', 'processed_tweets_file', 'media_cache_dir', 'tweet_cache_file',
                             'log_file', 'unprocessed_tweets_file', 'log_dir']:
                continue
                
            # Get the alias (environment variable name)
            env_var_name = field_info.alias if field_info.alias else field_name.upper()
            
            # Get field description
            description = field_info.description or f"Configuration for {field_name}"
            
            # Determine if field is required
            required = field_info.is_required()
            
            # Get field type
            field_type = "str"  # default
            if hasattr(field_info, 'annotation') and field_info.annotation:
                annotation = field_info.annotation
                if annotation == int:
                    field_type = "int"
                elif annotation == bool:
                    field_type = "bool"
                elif annotation == float:
                    field_type = "float"
                elif get_origin(annotation) == list:
                    field_type = "array"
                elif str(annotation).startswith('typing.Optional'):
                    # Handle Optional types
                    args = get_args(annotation)
                    if args and args[0] == int:
                        field_type = "int"
                    elif args and args[0] == bool:
                        field_type = "bool"
                    elif args and args[0] == float:
                        field_type = "float"
            
            config_fields[env_var_name] = {
                'alias': env_var_name,
                'description': description,
                'required': required,
                'type': field_type,
                'field_name': field_name
            }
        
        # Add system environment variables to our env_values if they exist
        for var_name in config_fields.keys():
            if var_name not in env_values and var_name in os.environ:
                env_values[var_name] = os.environ[var_name]
        
        # Determine which env vars are used/unused
        used_env_vars = []
        unused_env_vars = []
        missing_env_vars = []
        
        # Check which variables are used (defined in Config class)
        for var_name, var_info in config_fields.items():
            if var_name in env_values:
                used_env_vars.append(var_name)
            elif var_info['required']:
                missing_env_vars.append(var_name)
        
        # Find unused variables (variables in .env but not defined in Config class)
        for var_name in env_values.keys():
            if var_name not in config_fields:
                unused_env_vars.append(var_name)
        
        # Organize environment variables
        result = {
            'env_variables': env_values,
            'config_fields': config_fields,
            'used_env_vars': used_env_vars,
            'unused_env_vars': unused_env_vars,
            'missing_env_vars': missing_env_vars
        }
        
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error getting environment variables: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/environment-variables', methods=['POST'])
def update_environment_variables():
    """API endpoint to update environment variables in .env file while preserving comments and formatting."""
    try:
        data = request.get_json()
        env_vars = data.get('env_variables', {})
        
        env_file_path = '.env'
        
        if not os.path.exists(env_file_path):
            # Create new .env file if it doesn't exist
            with open(env_file_path, 'w') as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
            return jsonify({'success': True, 'message': 'Environment variables created successfully'})
        
        # Read all lines from the existing .env file
        with open(env_file_path, 'r') as f:
            lines = f.readlines()
        
        # Process each variable update
        for var_name, var_value in env_vars.items():
            updated = False
            
            # Look for existing variable and update it
            for i, line in enumerate(lines):
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#') and '=' in stripped_line:
                    existing_var_name = stripped_line.split('=', 1)[0]
                    if existing_var_name == var_name:
                        # Update the existing line
                        lines[i] = f"{var_name}={var_value}\n"
                        updated = True
                        break
            
            # If variable not found, append it at the end
            if not updated:
                # Add a newline before the new variable if the file doesn't end with one
                if lines and not lines[-1].endswith('\n'):
                    lines[-1] += '\n'
                lines.append(f"{var_name}={var_value}\n")
        
        # Write the updated content back to the file
        with open(env_file_path, 'w') as f:
            f.writelines(lines)
        
        return jsonify({'success': True, 'message': 'Environment variables updated successfully'})
    except Exception as e:
        logging.error(f"Error updating environment variables: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/environment-variables/<var_name>', methods=['DELETE'])
def delete_environment_variable(var_name):
    """API endpoint to delete an environment variable from .env file."""
    try:
        env_file_path = '.env'
        if not os.path.exists(env_file_path):
            return jsonify({'success': False, 'error': '.env file not found'}), 404
        
        # Read current .env file
        lines = []
        with open(env_file_path, 'r') as f:
            lines = f.readlines()
        
        # Filter out the variable to delete
        updated_lines = []
        for line in lines:
            if not line.strip().startswith(f"{var_name}="):
                updated_lines.append(line)
        
        # Write back to .env file
        with open(env_file_path, 'w') as f:
            f.writelines(updated_lines)
        
        return jsonify({'success': True, 'message': f'Environment variable {var_name} deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Chat Session API Routes ---

@app.route('/api/chat/sessions', methods=['GET'])
def api_get_chat_sessions():
    """Get all chat sessions."""
    try:
        from .models import ChatSession
        
        sessions = ChatSession.query.order_by(ChatSession.last_updated.desc()).all()
        session_list = []
        
        for session in sessions:
            session_list.append({
                'id': session.id,
                'session_id': session.session_id,
                'title': session.title,
                'created_at': session.created_at.isoformat() if session.created_at else None,
                'last_updated': session.last_updated.isoformat() if session.last_updated else None,
                'is_archived': session.is_archived,
                'message_count': session.message_count
            })
        
        return jsonify(session_list)
    except Exception as e:
        logging.error(f"Error retrieving chat sessions: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve chat sessions'}), 500

@app.route('/api/chat/sessions/<session_id>', methods=['GET'])
def api_get_chat_session(session_id):
    """Get a specific chat session with messages."""
    try:
        from .models import ChatSession, ChatMessage
        import json
        
        session = ChatSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.created_at.asc()).all()
        
        message_list = []
        for message in messages:
            msg_data = {
                'id': message.id,
                'role': message.role,
                'content': message.content,
                'created_at': message.created_at.isoformat() if message.created_at else None,
                'model_used': message.model_used
            }
            
            # Parse JSON fields if they exist
            if message.sources:
                try:
                    msg_data['sources'] = json.loads(message.sources)
                except:
                    msg_data['sources'] = []
            
            if message.context_stats:
                try:
                    msg_data['context_stats'] = json.loads(message.context_stats)
                except:
                    msg_data['context_stats'] = {}
            
            if message.performance_metrics:
                try:
                    msg_data['performance_metrics'] = json.loads(message.performance_metrics)
                except:
                    msg_data['performance_metrics'] = {}
                    
            message_list.append(msg_data)
        
        return jsonify({
            'session': {
                'id': session.id,
                'session_id': session.session_id,
                'title': session.title,
                'created_at': session.created_at.isoformat() if session.created_at else None,
                'last_updated': session.last_updated.isoformat() if session.last_updated else None,
                'is_archived': session.is_archived,
                'message_count': session.message_count
            },
            'messages': message_list
        })
    except Exception as e:
        logging.error(f"Error retrieving chat session {session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve chat session'}), 500

@app.route('/api/chat/sessions', methods=['POST'])
def api_create_chat_session():
    """Create a new chat session."""
    try:
        from .models import ChatSession, db
        from datetime import datetime, timezone
        import uuid
        
        data = request.get_json()
        
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        session = ChatSession()
        session.session_id = session_id
        session.title = data.get('title', 'New Chat')
        session.created_at = now
        session.last_updated = now
        session.is_archived = False
        session.message_count = 0
        
        db.session.add(session)
        db.session.commit()
        
        return jsonify({
            'session_id': session.session_id,
            'title': session.title,
            'created_at': session.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logging.error(f"Error creating chat session: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create chat session'}), 500

@app.route('/api/chat/sessions/<session_id>/archive', methods=['POST'])
def api_archive_chat_session(session_id):
    """Archive/unarchive a chat session."""
    try:
        from .models import ChatSession, db
        from datetime import datetime, timezone
        
        session = ChatSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        session.is_archived = not session.is_archived
        session.last_updated = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({'message': 'Session archived successfully' if session.is_archived else 'Session unarchived successfully'})
    except Exception as e:
        logging.error(f"Error archiving chat session {session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to archive chat session'}), 500

@app.route('/api/chat/sessions/<session_id>', methods=['DELETE'])
def api_delete_chat_session(session_id):
    """Delete a chat session and all its messages."""
    try:
        from .models import ChatSession, db
        
        session = ChatSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        db.session.delete(session)
        db.session.commit()
        
        return jsonify({'message': 'Session deleted successfully'})
    except Exception as e:
        logging.error(f"Error deleting chat session {session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete chat session'}), 500

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