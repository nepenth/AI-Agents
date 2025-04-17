# knowledge_base_agent/web.py
import asyncio
import logging
import sys
from threading import Thread
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from .config import Config
from .agent import KnowledgeBaseAgent, socketio as agent_socketio
from .prompts import UserPreferences
from .main import load_config, run_agent, cleanup

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, async_mode='eventlet', logger=True, engineio_logger=True)
agent_socketio = socketio  # Set the global socketio in agent.py

agent = None
agent_thread = None
running = False

class WebSocketHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            socketio.emit('log', {'message': msg, 'level': record.levelname}, namespace='/')
            # Removed logging.debug here to avoid potential recursion
        except Exception as e:
            # Print to stderr instead of logging to break recursion
            print(f"ERROR: Failed to emit log to WebSocket: {e}", file=sys.stderr)

def setup_web_logging(config: Config):
    """Configure logging with WebSocket handler using Config."""
    # Clear existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Use Config's setup_logging
    config.setup_logging()
    
    # Add WebSocket handler
    ws_handler = WebSocketHandler()
    ws_handler.setLevel(logging.INFO)
    ws_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(ws_handler)
    
    root_logger.setLevel(logging.DEBUG)
    logging.debug("WebSocket logging initialized")

async def run_agent_async(preferences: UserPreferences):
    global agent, running
    try:
        config = await load_config()
        setup_web_logging(config)
        agent = KnowledgeBaseAgent(config)
        await agent.initialize()
        logging.info("=== Starting Agent Operations ===")
        await run_agent(agent, preferences)
    except Exception as e:
        logging.error(f"Agent execution failed: {str(e)}")
        raise
    finally:
        running = False
        if agent is not None:  # Check if agent was initialized
            await agent.http_client.close()
        await cleanup(config)

def run_agent_thread(preferences: UserPreferences):
    asyncio.run(run_agent_async(preferences))

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('start_agent')
def handle_start_agent(data):
    global agent_thread, running
    if running:
        emit('log', {'message': 'Agent is already running', 'level': 'WARNING'})
        return
    preferences = UserPreferences(
        update_bookmarks=data.get('update_bookmarks', False),
        review_existing=data.get('review_existing', False),
        recreate_tweet_cache=data.get('recreate_tweet_cache', False),
        regenerate_readme=data.get('regenerate_readme', False)
    )
    running = True
    from .agent import stop_flag
    stop_flag = False
    agent_thread = Thread(target=run_agent_thread, args=(preferences,))
    agent_thread.start()
    emit('log', {'message': 'Agent started with preferences: ' + str(preferences.__dict__), 'level': 'INFO'})

@socketio.on('stop_agent')
def handle_stop_agent():
    global running
    from .agent import stop_flag
    if running:
        stop_flag = True
        emit('log', {'message': 'Stopping agent...', 'level': 'INFO'})
    else:
        emit('log', {'message': 'No agent running', 'level': 'WARNING'})

@socketio.on('connect')
def handle_connect():
    emit('log', {'message': 'Connected to server', 'level': 'INFO'})
    logging.debug("Client connected to WebSocket")

@socketio.on('disconnect')
def handle_disconnect():
    logging.debug("Client disconnected from WebSocket")

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)