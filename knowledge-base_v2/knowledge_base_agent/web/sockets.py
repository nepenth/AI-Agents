import logging
from flask_socketio import SocketIO, emit

logger = logging.getLogger(__name__)

# --- Global references (will be set by main_web.py) ---
sio: SocketIO = None
start_pipeline_func = None
stop_pipeline_func = None
get_status_func = None

def register_handlers(socketio_instance: SocketIO, start_func, stop_func, status_func):
    """Registers SocketIO event handlers."""
    global sio, start_pipeline_func, stop_pipeline_func, get_status_func
    sio = socketio_instance
    start_pipeline_func = start_func
    stop_pipeline_func = stop_func
    get_status_func = status_func

    # Register the handlers
    sio.on('connect', namespace='/agent')(handle_connect)
    sio.on('disconnect', namespace='/agent')(handle_disconnect)
    sio.on('get_status', namespace='/agent')(handle_get_status)
    sio.on('start_agent', namespace='/agent')(handle_start_agent)
    sio.on('stop_agent', namespace='/agent')(handle_stop_agent)

    # Add handlers for the /logs namespace
    sio.on('connect', namespace='/logs')(handle_logs_connect)
    sio.on('disconnect', namespace='/logs')(handle_logs_disconnect)

    logger.info("SocketIO handlers registered for /agent and /logs namespaces.")


# --- Event Handlers ---

def handle_connect(auth=None):
    """Handles new client connections."""
    # Auth is optional data passed from client connect()
    logger.info(f"Client connected to /agent namespace. Auth: {auth}")
    # Send current status on connect
    handle_get_status()

def handle_disconnect():
    """Handles client disconnections."""
    logger.info("Client disconnected from /agent namespace.")

def handle_get_status():
    """Sends the current agent status to the requesting client."""
    if not get_status_func:
         logger.error("get_status_func not set!")
         return
    status = get_status_func()
    logger.debug(f"Sending status update: {status}")
    # Emit only to the requesting client? Or broadcast? Let's emit.
    emit('status_update', status) # Namespace taken care of by decorator/registration

def handle_start_agent(data=None):
    """Handles request to start the agent pipeline."""
    if not start_pipeline_func:
         logger.error("start_pipeline_func not set!")
         emit('status_update', {'status': 'error', 'message': 'Agent start function not configured.'})
         return

    logger.info(f"Received start_agent request. Data: {data}")
    # Extract preferences from data if needed
    run_preferences = data if isinstance(data, dict) else {}
    success = start_pipeline_func(run_preferences)
    # Status update will be emitted by start_pipeline_func itself

def handle_stop_agent():
    """Handles request to stop the agent pipeline."""
    if not stop_pipeline_func:
         logger.error("stop_pipeline_func not set!")
         emit('status_update', {'status': 'error', 'message': 'Agent stop function not configured.'})
         return

    logger.info("Received stop_agent request.")
    success = stop_pipeline_func()
    # Status update will be emitted by stop_pipeline_func itself

# --- /logs Namespace Handlers ---
def handle_logs_connect(auth=None):
    """Handles new client connections to the /logs namespace."""
    logger.info(f"Client connected to /logs namespace. Auth: {auth}")
    # You could emit a welcome message or initial state if needed, e.g.:
    # emit('log_history_status', {'message': 'Connected to log stream.'})

def handle_logs_disconnect():
    """Handles client disconnections from the /logs namespace."""
    logger.info("Client disconnected from /logs namespace.")
