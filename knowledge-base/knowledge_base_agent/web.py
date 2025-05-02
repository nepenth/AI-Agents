# knowledge_base_agent/web.py
import asyncio
import logging
import sys
from threading import Thread
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session
from flask_socketio import SocketIO, emit
from markdown import markdown
from .config import Config
from .models import db, KnowledgeBaseItem
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

# Configure logging to file per run
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)
run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = log_dir / f'agent_run_{run_timestamp}.log'

# Setup file handler for detailed logging
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add file handler to root logger
logging.getLogger('').addHandler(file_handler)

# Configure SocketIO to avoid recursive logging
socketio_logger = logging.getLogger('socketio')
socketio_logger.setLevel(logging.WARNING)  # Reduce verbosity for socketio logs

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///knowledge_base.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
socketio = SocketIO(app, async_mode='gevent', logger=False, engineio_logger=False)

agent = None
agent_thread = None
running = False

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
            msg = self.format(record)
            # Remove broadcast=True as it's not supported in all Flask-SocketIO versions
            socketio.emit('log', {'message': msg, 'level': record.levelname}, namespace='/')
        except Exception as e:
            print(f"ERROR: Failed to emit log to WebSocket: {e}", file=sys.stderr)

def setup_web_logging(config: Config):
    """Configure logging with WebSocket handler using Config."""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    config.setup_logging()
    
    ws_handler = WebSocketHandler()
    ws_handler.setLevel(logging.INFO)
    ws_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(ws_handler)
    
    root_logger.setLevel(logging.DEBUG)
    logging.debug("WebSocket logging initialized")

async def run_agent_async(preferences: UserPreferences):
    global agent, running
    config = None  # Initialize config as None to avoid UnboundLocalError
    try:
        config = await load_config()
        setup_web_logging(config)
        agent = KnowledgeBaseAgent(config)
        # Ensure initialization happens within app context
        with app.app_context():
            await agent.initialize()
        logging.info("=== Starting Agent Operations ===")
        # Run the agent within Flask app context for all DB operations
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, lambda: run_agent_with_context(agent, preferences))
        # After agent run, save processed items to database within context
        with app.app_context():
            await save_processed_items_to_db(config)
    except Exception as e:
        logging.error(f"Agent execution failed: {str(e)}")
        raise
    finally:
        running = False
        # Emit agent_complete event to notify the front-end
        socketio.emit('agent_complete', {'status': 'completed'}, namespace='/')
        if agent is not None:
            await agent.http_client.close()
        if config is not None:  # Check if config was initialized before calling cleanup
            await cleanup(config)
        else:
            logging.warning("Config not initialized, skipping cleanup.")

def run_agent_with_context(agent, preferences):
    """Wrapper to ensure run_agent is executed within Flask app context."""
    with app.app_context():
        # Ensure the agent's run method is called synchronously within context
        asyncio.run(agent.run(preferences))

async def save_processed_items_to_db(config: Config):
    """Save processed tweets to the database after agent run."""
    state_manager = StateManager(config)
    await state_manager.initialize()
    all_tweets = await state_manager.get_all_tweets()
    for tweet_id, tweet_data in all_tweets.items():
        if tweet_data.get('kb_item_created', False):
            kb_item_path = tweet_data.get('kb_item_path')
            if kb_item_path:
                kb_path = Path(kb_item_path)
                if kb_path.exists():
                    with open(kb_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    categories = tweet_data.get('categories', {})
                    item = KnowledgeBaseItem(
                        title=categories.get('item_name', f"Tweet {tweet_id}"),
                        description=tweet_data.get('full_text', '')[:200] if tweet_data.get('full_text') else '',
                        content=content,
                        main_category=categories.get('main_category', 'Uncategorized'),
                        sub_category=categories.get('sub_category', 'Uncategorized'),
                        item_name=categories.get('item_name', f"tweet_{tweet_id}"),
                        source_url=f"https://twitter.com/i/web/status/{tweet_id}",
                        created_at=datetime.now(timezone.utc),
                        last_updated=datetime.now(timezone.utc)
                    )
                    try:
                        with app.app_context():  # Ensure DB operation is in context
                            db.session.add(item)
                            db.session.commit()
                            logging.info(f"Saved tweet {tweet_id} to database")
                    except Exception as e:
                        logging.error(f"Failed to save tweet {tweet_id} to database: {str(e)}", exc_info=True)

def run_agent_thread(preferences: UserPreferences):
    asyncio.run(run_agent_async(preferences))

@app.route('/', methods=['GET', 'POST'])
def index():
    global running
    all_items = []
    try:
        all_items = KnowledgeBaseItem.query.all()
        logging.debug(f"Retrieved {len(all_items)} items for index page sidebar.")
    except Exception as e:
        logging.error(f"Error retrieving items for index sidebar: {e}", exc_info=True)

    if request.method == 'POST':
        preferences = UserPreferences(
            update_bookmarks=request.form.get('update_bookmarks') == 'on',
            review_existing=request.form.get('review_existing') == 'on',
            recreate_tweet_cache=request.form.get('recreate_tweet_cache') == 'on',
            regenerate_readme=request.form.get('regenerate_readme') == 'on'
        )
        # Store checkbox states in session
        session['checkbox_states'] = {
            'update_bookmarks': request.form.get('update_bookmarks') == 'on',
            'review_existing': request.form.get('review_existing') == 'on',
            'recreate_tweet_cache': request.form.get('recreate_tweet_cache') == 'on',
            'regenerate_readme': request.form.get('regenerate_readme') == 'on'
        }
        global agent_thread
        if running:
            return render_template('index.html', message="Agent is already running", running=running, items=all_items, checkbox_states=session.get('checkbox_states', {}))
        running = True
        from .agent import stop_flag
        stop_flag = False
        agent_thread = Thread(target=run_agent_thread, args=(preferences,))
        agent_thread.start()
        return render_template('index.html', message="Agent started with selected preferences", running=running, items=all_items, checkbox_states=session.get('checkbox_states', {}))
    return render_template('index.html', running=running, items=all_items, checkbox_states=session.get('checkbox_states', {}))

@app.route('/stop', methods=['POST'])
def stop_agent():
    global running
    from .agent import stop_flag
    if running:
        stop_flag = True
        return redirect(url_for('index', message="Stopping agent..."))
    return redirect(url_for('index', message="No agent running"))

@app.route('/knowledge_base')
def knowledge_base():
    logging.info("Accessing /knowledge_base route.")
    items = [] # Default to empty list
    try:
        items = KnowledgeBaseItem.query.all()
        logging.info(f"Retrieved {len(items)} items from the database.")
        if items:
            # Log the ID and title of the first item retrieved for confirmation
            logging.debug(f"First item retrieved: ID={items[0].id}, Title='{items[0].title}'")
        else:
            logging.warning("No items retrieved from the database for knowledge base page.")
        # Pass items to the template regardless of whether they were found
        return render_template('knowledge_base.html', items=items)
    except Exception as e:
        logging.error(f"Error retrieving items for /knowledge_base: {e}", exc_info=True) # Log traceback
        # Render the template with an empty list in case of error
        return render_template('knowledge_base.html', items=items, error="Error loading items.")

# --- Helper function to fix markdown image paths ---
def preprocess_markdown_media_paths(content: str, tweet_id: str, item_id: int) -> str:
    """Replaces relative markdown image paths (./...) with absolute server paths."""
    if not tweet_id:
        logging.warning(f"Item {item_id}: Cannot preprocess media paths, tweet_id is missing.")
        return content
    if not content:
        logging.warning(f"Item {item_id}: Cannot preprocess empty content.")
        return ""

    logging.debug(f"Item {item_id}: Starting markdown preprocessing for tweet_id {tweet_id}.")
    logging.debug(f"Item {item_id}: Original content snippet: {content[:150]}...")  # Log beginning of content

    # Counter for replacements made
    replacement_count = 0

    def replace_match(match):
        nonlocal replacement_count  # Allow modification of outer scope variable
        alt_text = match.group(1)
        relative_path = match.group(2)  # Path captured by the regex (e.g., ./image_1.jpg or image_1.jpg)
        filename = Path(relative_path).name  # Extracts image_1.jpg

        logging.debug(f"Item {item_id}: Found potential relative path match: '{match.group(0)}', Filename extracted: '{filename}'")

        try:
            # Look up the KB item path to construct the correct path
            kb_item = KnowledgeBaseItem.query.filter_by(id=item_id).first()
            if kb_item:
                kb_item_path = kb_item.content.split('kb-generated/')[1].split('/README.md')[0] if 'kb-generated/' in kb_item.content else ''
                if kb_item_path:
                    absolute_url = f"/kb-media/{kb_item_path}/{filename}"
                    logging.info(f"Item {item_id}: SUCCESS - Replacing markdown path '{relative_path}' with URL '{absolute_url}'")
                    replacement_count += 1
                    return f"![{alt_text}]({absolute_url})"
            # Fallback to original path if KB item path not found
            absolute_url = url_for('serve_media', tweet_id=tweet_id, filename=filename, _external=False)
            logging.info(f"Item {item_id}: Fallback - Replacing markdown path '{relative_path}' with URL '{absolute_url}'")
            replacement_count += 1
            return f"![{alt_text}]({absolute_url})"
        except RuntimeError as e:
            logging.error(f"Item {item_id}: url_for failed for {filename} (likely no request context): {e}", exc_info=True)
            return match.group(0)  # Return original on error
        except Exception as e:
            logging.error(f"Item {item_id}: Error generating URL for {filename}: {e}", exc_info=True)
            return match.group(0)  # Return original on error

    # Regex to match markdown image tags with relative paths
    pattern = r'!\[(.*?)\]\((.*?)\)'
    processed_content = re.sub(pattern, replace_match, content)
    logging.info(f"Item {item_id}: Completed preprocessing, replaced {replacement_count} image paths.")
    return processed_content
# --- End helper function ---

@app.route('/item/<int:id>', methods=['GET', 'POST'])
def item_detail(id):
    item = KnowledgeBaseItem.query.get_or_404(id)
    all_items = []
    try:
        all_items = KnowledgeBaseItem.query.all()
    except Exception as e:
        logging.error(f"Error retrieving items for item detail sidebar: {e}", exc_info=True)

    if request.method == 'POST':
        from datetime import datetime, timezone
        item.title = request.form['title']
        item.description = request.form['description']
        item.content = request.form['content']
        item.main_category = request.form['main_category']
        item.sub_category = request.form['sub_category']
        item.last_updated = datetime.now(timezone.utc)
        db.session.commit()
        return redirect(url_for('item_detail', id=id, message="Item updated successfully"))

    # --- Preprocess Markdown for Media Paths (fallback for older items) ---
    original_markdown = item.content if item.content else ""
    preprocessed_markdown = original_markdown  # Default if preprocessing fails
    if item.tweet_id:
        try:
            # Ensure this runs within the request context where url_for works
            logging.info(f"Item {id}: Calling preprocess_markdown_media_paths...")
            preprocessed_markdown = preprocess_markdown_media_paths(original_markdown, item.tweet_id, item.id)
            logging.info(f"Item {id}: Finished preprocess_markdown_media_paths.")
        except Exception as preproc_e:
            logging.error(f"Item {id}: Error during markdown preprocessing call: {preproc_e}", exc_info=True)
            preprocessed_markdown = original_markdown  # Fallback to original on error
    else:
        logging.warning(f"Item {id} has no tweet_id, cannot preprocess media paths in markdown.")

    # --- Render the preprocessed content ---
    rendered_content = ""  # Default empty
    try:
        logging.info(f"Item {id}: Rendering markdown...")
        # Log the exact content being passed to the renderer
        logging.debug(f"Item {id}: Content BEFORE markdown rendering snippet: {preprocessed_markdown[:150]}...")
        rendered_content = markdown(preprocessed_markdown, extensions=['extra', 'codehilite'])
        logging.info(f"Item {id}: Markdown rendered successfully.")
        # Log the beginning of the rendered HTML
        logging.debug(f"Item {id}: Content AFTER markdown rendering snippet: {rendered_content[:150]}...")
    except Exception as render_e:
        logging.error(f"Item {id}: Error rendering markdown: {render_e}", exc_info=True)
        rendered_content = f"<p>Error rendering content.</p><pre><code>{preprocessed_markdown}</code></pre>"  # Show raw preprocessed on error

    # --- Media Item List for "Associated Media" Section ---
    media_items = []
    if item.tweet_id:
        try:
            config = asyncio.run(load_config())
            state_manager = StateManager(config)
            asyncio.run(state_manager.initialize())
            tweet_data = asyncio.run(state_manager.get_tweet(item.tweet_id))
            if tweet_data and 'kb_media_paths' in tweet_data:
                logging.info(f"Item {id}: Using kb_media_paths from tweet_cache for media items.")
                for media_path in tweet_data.get('kb_media_paths', []):
                    media_file = Path(media_path)
                    if media_file.exists():
                        file_name = media_file.name
                        try:
                            file_url = url_for('serve_media', tweet_id=item.tweet_id, filename=file_name)
                            file_type = 'video' if file_name.startswith('video_') else 'image'
                            media_items.append({'type': file_type, 'url': file_url, 'name': file_name})
                            logging.debug(f"Item {id}: Added media item from kb_media_paths: type='{file_type}', name='{file_name}', url='{file_url}'")
                        except Exception as url_e:
                            logging.error(f"Item {id}: Failed to generate URL for media file '{file_name}': {url_e}")
                media_items.sort(key=lambda x: (x['type'] == 'video', x['url']))
            else:
                logging.warning(f"Item {id}: No kb_media_paths found in tweet_cache, falling back to directory scan.")
                if item.file_path:
                    kb_item_dir = Path(item.file_path).parent
                    resolved_kb_item_dir = kb_item_dir
                    if not kb_item_dir.is_absolute():
                        resolved_kb_item_dir = (Path(os.getcwd()) / kb_item_dir).resolve()
                    if resolved_kb_item_dir.is_dir():
                        logging.info(f"Item {id}: Scanning directory '{resolved_kb_item_dir}' for media files...")
                        try:
                            found_files = list(resolved_kb_item_dir.glob('image_*.*')) + list(resolved_kb_item_dir.glob('video_*.*'))
                            logging.info(f"Item {id}: Found {len(found_files)} potential media files via glob: {[f.name for f in found_files]}")
                            for media_file in found_files:
                                file_name = media_file.name
                                try:
                                    file_url = url_for('serve_media', tweet_id=item.tweet_id, filename=file_name)
                                    file_type = 'video' if file_name.startswith('video_') else 'image'
                                    media_items.append({'type': file_type, 'url': file_url, 'name': file_name})
                                    logging.debug(f"Item {id}: Added media item: type='{file_type}', name='{file_name}', url='{file_url}'")
                                except Exception as url_e:
                                    logging.error(f"Item {id}: Failed to generate URL for media file '{file_name}': {url_e}")
                            media_items.sort(key=lambda x: (x['type'] == 'video', x['url']))
                        except Exception as e:
                            logging.error(f"Item {id}: Error during media file glob/processing in '{resolved_kb_item_dir}': {e}", exc_info=True)
                    else:
                        logging.warning(f"Item {id}: Determined KB item directory '{resolved_kb_item_dir}' does not exist or is not a directory.")
                else:
                    logging.warning(f"Item {id}: Cannot scan for media because item.file_path is missing.")
        except Exception as e:
            logging.error(f"Item {id}: Error accessing tweet_cache for kb_media_paths: {e}", exc_info=True)
            # Fallback to directory scan if tweet_cache access fails
            if item.file_path:
                kb_item_dir = Path(item.file_path).parent
                resolved_kb_item_dir = kb_item_dir
                if not kb_item_dir.is_absolute():
                    resolved_kb_item_dir = (Path(os.getcwd()) / kb_item_dir).resolve()
                if resolved_kb_item_dir.is_dir():
                    logging.info(f"Item {id}: Scanning directory '{resolved_kb_item_dir}' for media files (fallback)...")
                    try:
                        found_files = list(resolved_kb_item_dir.glob('image_*.*')) + list(resolved_kb_item_dir.glob('video_*.*'))
                        logging.info(f"Item {id}: Found {len(found_files)} potential media files via glob (fallback): {[f.name for f in found_files]}")
                        for media_file in found_files:
                            file_name = media_file.name
                            try:
                                file_url = url_for('serve_media', tweet_id=item.tweet_id, filename=file_name)
                                file_type = 'video' if file_name.startswith('video_') else 'image'
                                media_items.append({'type': file_type, 'url': file_url, 'name': file_name})
                                logging.debug(f"Item {id}: Added media item (fallback): type='{file_type}', name='{file_name}', url='{file_url}'")
                            except Exception as url_e:
                                logging.error(f"Item {id}: Failed to generate URL for media file '{file_name}' (fallback): {url_e}")
                        media_items.sort(key=lambda x: (x['type'] == 'video', x['url']))
                    except Exception as e:
                        logging.error(f"Item {id}: Error during media file glob/processing in '{resolved_kb_item_dir}' (fallback): {e}", exc_info=True)
                else:
                    logging.warning(f"Item {id}: Determined KB item directory '{resolved_kb_item_dir}' does not exist or is not a directory (fallback).")
            else:
                logging.warning(f"Item {id}: Cannot scan for media because item.file_path is missing (fallback).")
    else:
        logging.warning(f"Item {id}: No tweet_id available, cannot load media items from tweet_cache.")
        if item.file_path:
            kb_item_dir = Path(item.file_path).parent
            resolved_kb_item_dir = kb_item_dir
            if not kb_item_dir.is_absolute():
                resolved_kb_item_dir = (Path(os.getcwd()) / kb_item_dir).resolve()
            if resolved_kb_item_dir.is_dir():
                logging.info(f"Item {id}: Scanning directory '{resolved_kb_item_dir}' for media files (no tweet_id fallback)...")
                try:
                    found_files = list(resolved_kb_item_dir.glob('image_*.*')) + list(resolved_kb_item_dir.glob('video_*.*'))
                    logging.info(f"Item {id}: Found {len(found_files)} potential media files via glob (no tweet_id fallback): {[f.name for f in found_files]}")
                    for media_file in found_files:
                        file_name = media_file.name
                        try:
                            file_url = url_for('serve_media', tweet_id=item.tweet_id if item.tweet_id else "unknown", filename=file_name)
                            file_type = 'video' if file_name.startswith('video_') else 'image'
                            media_items.append({'type': file_type, 'url': file_url, 'name': file_name})
                            logging.debug(f"Item {id}: Added media item (no tweet_id fallback): type='{file_type}', name='{file_name}', url='{file_url}'")
                        except Exception as url_e:
                            logging.error(f"Item {id}: Failed to generate URL for media file '{file_name}' (no tweet_id fallback): {url_e}")
                    media_items.sort(key=lambda x: (x['type'] == 'video', x['url']))
                except Exception as e:
                    logging.error(f"Item {id}: Error during media file glob/processing in '{resolved_kb_item_dir}' (no tweet_id fallback): {e}", exc_info=True)
            else:
                logging.warning(f"Item {id}: Determined KB item directory '{resolved_kb_item_dir}' does not exist or is not a directory (no tweet_id fallback).")
        else:
            logging.warning(f"Item {id}: Cannot scan for media because item.file_path is missing (no tweet_id fallback).")
    logging.info(f"Item {id}: Final media_items list count for template: {len(media_items)}")
    # --- End Media Item Logic ---

    # Pass rendered_content (which now has correct image paths)
    return render_template(
        'item_detail.html',
        item=item,
        rendered_content=rendered_content,  # Use the preprocessed & rendered content
        media_items=media_items,  # Pass the structured list for the "Associated Media" section
        items=all_items  # Pass all items for the sidebar
    )

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    search_results = [] # Results for main content
    all_items = [] # All items for sidebar
    try:
        all_items = KnowledgeBaseItem.query.all()
        logging.debug(f"Retrieved {len(all_items)} items for search results page sidebar.")
        if query:
            search_results = KnowledgeBaseItem.query.filter(
                db.or_(
                    KnowledgeBaseItem.title.ilike(f'%{query}%'),
                    KnowledgeBaseItem.description.ilike(f'%{query}%'),
                    KnowledgeBaseItem.content.ilike(f'%{query}%')
                )
            ).all()
            logging.info(f"Search for '{query}' found {len(search_results)} results.")
        else:
             search_results = [] # No query, no results for main content
    except Exception as e:
        logging.error(f"Error during search or sidebar item retrieval: {e}", exc_info=True)

    # Pass search_results (aliased as 'results' for the template) and all_items for the sidebar
    return render_template('search_results.html', results=search_results, query=query, items=all_items)

@app.route('/media/<tweet_id>/<filename>')
def serve_media(tweet_id, filename):
    if not tweet_id or not filename:
        return "Invalid request", 400

    # Find the KB item using the tweet_id
    item = KnowledgeBaseItem.query.filter_by(tweet_id=tweet_id).first()
    if not item:
        # Try to find item by extracting tweet_id from source_url
        items = KnowledgeBaseItem.query.all()
        for potential_item in items:
            if potential_item.source_url and tweet_id in potential_item.source_url:
                item = potential_item
                break
        if not item:
            logging.error(f"Serve media: Could not find KB item for tweet_id {tweet_id}")
            return "Item not found", 404
    if not item.file_path:
         logging.error(f"Serve media: KB item {item.id} for tweet_id {tweet_id} has no file_path.")
         return "Item file path missing", 404

    # item.file_path points to the README.md (e.g., kb-generated/cat/sub/item/README.md)
    # We need the parent directory containing the media.
    kb_item_dir = Path(item.file_path).parent

    # Ensure the directory path is valid and exists
    if not kb_item_dir.is_dir():
        # Try resolving relative to CWD if it's not absolute
        if not kb_item_dir.is_absolute():
             kb_item_dir = Path(os.getcwd()) / kb_item_dir
        # Check again if it exists now
        if not kb_item_dir.is_dir():
            logging.error(f"Serve media: KB item directory does not exist: {kb_item_dir}")
            return "Item directory not found", 404

    # Use absolute path for send_from_directory
    media_dir_abs = kb_item_dir.resolve()
    target_file_abs = (media_dir_abs / filename).resolve()

    logging.debug(f"Attempting to serve '{filename}' from resolved directory '{media_dir_abs}'")

    # Security check: Ensure the resolved file path is within the intended directory
    if not target_file_abs.is_relative_to(media_dir_abs):
        logging.warning(f"Potential path traversal attempt blocked: '{filename}' from '{media_dir_abs}'")
        return "Forbidden", 403

    try:
        # Serve the requested filename from the resolved absolute directory path
        return send_from_directory(str(media_dir_abs), filename)
    except FileNotFoundError:
        logging.error(f"Serve media: File '{filename}' not found in '{media_dir_abs}'")
        return "Media file not found", 404
    except Exception as e:
        logging.error(f"Error serving media file '{filename}' from '{media_dir_abs}': {e}", exc_info=True)
        return "Error serving file", 500

@socketio.on('connect')
def handle_connect():
    emit('log', {'message': 'Connected to server', 'level': 'INFO'})
    logging.debug("Client connected to WebSocket")

@socketio.on('disconnect')
def handle_disconnect():
    logging.debug("Client disconnected from WebSocket")

# --- FUNCTION TO HANDLE STARTUP SYNC ---
def run_startup_synchronization(app_instance):
    """Runs initialization (which includes DB sync) within app context."""
    with app_instance.app_context():
        try:
            logging.info("Attempting StateManager initialization (includes DB sync) on script startup...")
            from knowledge_base_agent.config import Config
            config = Config.from_env()
            state_manager = StateManager(config)
            # Run initialization synchronously within context to avoid async context issues
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(state_manager.initialize())
            loop.close()
            logging.info("StateManager initialization completed on script startup.")
        except Exception as e:
            logging.error(f"Failed during StateManager initialization on script startup: {str(e)}", exc_info=True)

@app.route('/regenerate_from_cache', methods=['POST'])
def regenerate_from_cache():
    try:
        config = asyncio.run(load_config())
        state_manager = StateManager(config)
        asyncio.run(state_manager.initialize())
        all_tweets = asyncio.run(state_manager.get_all_tweets())
        added_count = 0
        updated_count = 0
        
        for tweet_id, tweet_data in all_tweets.items():
            if tweet_data.get('kb_item_created', False) and tweet_data.get('kb_item_path'):
                try:
                    kb_path = Path(tweet_data['kb_item_path'])
                    readme_path = kb_path / "README.md"
                    if readme_path.exists():
                        with open(readme_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        categories = tweet_data.get('categories', {})
                        existing_item = KnowledgeBaseItem.query.filter_by(tweet_id=tweet_id).first()
                        if existing_item:
                            existing_item.content = content
                            existing_item.file_path = tweet_data['kb_item_path']
                            existing_item.last_updated = datetime.now(timezone.utc)
                            updated_count += 1
                        else:
                            new_item = KnowledgeBaseItem(
                                tweet_id=tweet_id,
                                title=categories.get('item_name', f"Tweet {tweet_id}"),
                                description=tweet_data.get('full_text', '')[:200] if tweet_data.get('full_text') else '',
                                content=content,
                                main_category=categories.get('main_category', 'Uncategorized'),
                                sub_category=categories.get('sub_category', 'Uncategorized'),
                                item_name=categories.get('item_name', f"tweet_{tweet_id}"),
                                source_url=f"https://twitter.com/i/web/status/{tweet_id}",
                                file_path=tweet_data['kb_item_path'],
                                created_at=datetime.now(timezone.utc),
                                last_updated=datetime.now(timezone.utc)
                            )
                            db.session.add(new_item)
                            added_count += 1
                            logging.info(f"Added KB item for tweet {tweet_id} to database from cache.")
                except Exception as e:
                    logging.error(f"Failed to process tweet {tweet_id} during regeneration: {e}", exc_info=True)
        
        db.session.commit()
        logging.info(f"Regeneration complete: Added {added_count}, Updated {updated_count} items to database.")
        return redirect(url_for('index', message=f"Regeneration complete: Added {added_count}, Updated {updated_count} items."))
    except Exception as e:
        logging.error(f"Error during regeneration from cache: {e}", exc_info=True)
        return redirect(url_for('index', message="Error during regeneration from cache."))

@app.route('/start_agent', methods=['POST'])
async def start_agent():
    global agent, running
    if running:
        return jsonify({'status': 'error', 'message': 'Agent is already running'})

    running = True
    options = request.json
    preferences = UserPreferences(
        update_bookmarks=options.get('update_bookmarks', False),
        review_existing=options.get('review_existing', False),
        recreate_tweet_cache=options.get('recreate_tweet_cache', False),
        regenerate_readme=options.get('regenerate_readme', False)
    )
    try:
        with app.app_context():  # Ensure all operations are within app context
            config = await load_config()
            setup_web_logging(config)
            agent = KnowledgeBaseAgent(config)
            await agent.initialize()
            logging.info("=== Starting Agent Operations ===")
            await agent.run(preferences)
        return jsonify({'status': 'success', 'message': 'Agent completed successfully'})
    except Exception as e:
        logging.error(f"Agent execution failed: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        running = False
        if agent is not None:
            await agent.http_client.close()
        if config is not None:
            await cleanup(config)
        else:
            logging.warning("Config not initialized, skipping cleanup.")

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
    all_items = [] # For sidebar consistency
    try:
        all_items = KnowledgeBaseItem.query.all()
    except Exception as e:
        logging.error(f"Error retrieving items for logs page sidebar: {e}", exc_info=True)
    # This route just renders the HTML shell; JS will fetch the actual log list/content.
    return render_template('logs.html', items=all_items)

@app.route('/api/logs', methods=['GET'])
def list_logs():
    """API endpoint to list available log files."""
    try:
        # Load config to get the correct log directory
        try:
            # Use asyncio.run since this is a sync route calling an async function
            config = asyncio.run(load_config())
            configured_log_dir = config.log_dir
        except Exception as config_e:
            logging.error(f"Failed to load config in /api/logs: {config_e}", exc_info=True)
            return jsonify({"error": "Failed to load configuration"}), 500

        if not configured_log_dir.is_dir():
            logging.error(f"Configured log directory not found: {configured_log_dir.resolve()}")
            return jsonify({"error": "Log directory not found"}), 500

        # List files from the configured directory, sort by modification time (newest first)
        log_files = sorted(
            [f for f in configured_log_dir.iterdir() if f.is_file() and f.suffix == '.log'],
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        log_filenames = [f.name for f in log_files]
        logging.debug(f"Found log files in {configured_log_dir}: {log_filenames}")
        return jsonify(log_filenames)
    except Exception as e:
        logging.error(f"Error listing log files: {e}", exc_info=True)
        return jsonify({"error": "Failed to list log files"}), 500

@app.route('/api/logs/<path:filename>', methods=['GET'])
def get_log_content(filename):
    """API endpoint to get the content of a specific log file."""
    # Load config to get the correct log directory
    try:
        config = asyncio.run(load_config())
        configured_log_dir = config.log_dir
    except Exception as config_e:
        logging.error(f"Failed to load config in /api/logs/<filename>: {config_e}", exc_info=True)
        return jsonify({"error": "Failed to load configuration"}), 500

    # Basic security check: ensure filename doesn't contain path separators
    # and ends with .log
    if '/' in filename or '\\' in filename or '..' in filename or not filename.endswith('.log'):
        logging.warning(f"Invalid log filename requested: {filename}")
        return jsonify({"error": "Invalid log filename"}), 400

    log_file_path = (configured_log_dir / filename).resolve() # Resolve to absolute path

    # Security check: Ensure the resolved path is within the intended log_dir
    if not log_file_path.is_relative_to(configured_log_dir.resolve()):
         logging.warning(f"Potential path traversal blocked for log file: {filename}")
         return jsonify({"error": "Access denied"}), 403

    if not log_file_path.is_file():
        logging.error(f"Log file not found: {log_file_path}")
        return jsonify({"error": "Log file not found"}), 404

    try:
        # Use send_from_directory for safer file serving. Needs the directory path.
        logging.debug(f"Serving log file: {filename} from directory {configured_log_dir.resolve()}")
        return send_from_directory(
            configured_log_dir.resolve(), # Serve from absolute path
            filename,
            mimetype='text/plain',
            as_attachment=False # Display in browser
        )
    except Exception as e:
        logging.error(f"Error reading log file {filename}: {e}", exc_info=True)
        return jsonify({"error": "Failed to read log file"}), 500

# --- End Log Viewer Routes ---

@app.route('/kb-media/<path:path>')
def serve_kb_media(path):
    """Serve media files from the kb-generated directory."""
    base_path = Path('kb-generated')
    file_path = base_path / path
    if file_path.exists():
        return send_from_directory(base_path, path)
    else:
        logging.warning(f"Media file not found: {file_path}")
        return "File not found", 404

if __name__ == "__main__":
    # --- Run startup initialization (includes sync) BEFORE starting the server ---
    run_startup_synchronization(app)
    # --- Now start the server ---
    logging.info("Starting Flask-SocketIO server...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)