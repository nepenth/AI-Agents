import asyncio # Import asyncio for async route
import logging
from pathlib import Path
from collections import defaultdict # Import defaultdict

from flask import (
    Blueprint, render_template, abort, request, jsonify, current_app, url_for, redirect
)
from sqlalchemy.orm import Session

from ..database import db, KnowledgeBaseItem
from ..types import KnowledgeBaseItemRecord
from ..utils import file_io, markdown as md_utils # Import markdown utils
from ..utils.file_io import FileOperationError
from . import persistence # Import persistence functions

logger = logging.getLogger(__name__)

# Adjust template/static paths if needed based on project structure
main_bp = Blueprint('main', __name__, template_folder='../../templates', static_folder='../../static')

# --- Context Processor for Global Template Data ---
@main_bp.app_context_processor
def inject_kb_tree_data():
    """Fetches KB structure and makes it available to all templates."""
    try:
        items_orm = db.session.execute(db.select(KnowledgeBaseItem).order_by(
            KnowledgeBaseItem.main_category,
            KnowledgeBaseItem.sub_category,
            KnowledgeBaseItem.item_name
        )).scalars().all()

        grouped_items = defaultdict(lambda: defaultdict(list))
        for item_orm in items_orm:
            # Basic validation, skip if essential fields missing
            if not item_orm.main_category or not item_orm.sub_category or not item_orm.item_name:
                logger.warning(f"Skipping KB item ID {item_orm.id} due to missing category/name fields.")
                continue
            # Use model_validate for type conversion and potential validation
            item = KnowledgeBaseItemRecord.model_validate(item_orm, from_attributes=True)
            grouped_items[item.main_category][item.sub_category].append(item)

        # Convert defaultdicts back to regular dicts for easier template iteration
        final_grouped_items = {
            main_cat: {sub_cat: items for sub_cat, items in sub_cats.items()}
            for main_cat, sub_cats in grouped_items.items()
        }
        return dict(kb_tree_data=final_grouped_items)

    except Exception as e:
        logger.error(f"Error fetching KB items for context processor: {e}", exc_info=True)
        return dict(kb_tree_data={}) # Return empty dict on error

@main_bp.route('/')
def index():
    """Serves the main dashboard page."""
    logger.debug("Serving index page.")
    # kb_tree_data is automatically injected by the context processor
    return render_template('index.html', title="Agent Dashboard")

# --- Knowledge Base Routes ---
@main_bp.route('/knowledge-base/')
def list_kb_items():
     """Lists all knowledge base items (uses data from context processor)."""
     logger.debug("Serving knowledge base listing page.")
     # The context processor already provides kb_tree_data
     # We just need a template to display it differently if needed,
     # or redirect to index if the sidebar is sufficient.
     # For now, let's create a basic list template.
     return render_template('kb_list.html', title="Knowledge Base")

@main_bp.route('/item/<int:item_id>')
async def kb_item_detail(item_id: int):
     """Displays detail for a single knowledge base item, including README."""
     logger.debug(f"Serving detail page for KB item ID: {item_id}")
     if not hasattr(current_app, 'agent_config'):
          logger.error("Agent configuration not found in Flask app context for KB detail.")
          abort(500, description="Server configuration error")
          return # Added return for clarity after abort

     config = current_app.agent_config
     readme_html = "(Error loading README)" # Default error message

     try:
          item_orm = db.session.get(KnowledgeBaseItem, item_id)
          if item_orm is None:
               abort(404, description="Knowledge base item not found.")

          # Use model_validate for consistent data structure
          item = KnowledgeBaseItemRecord.model_validate(item_orm, from_attributes=True)

          # Construct the absolute path to the README
          # Ensure kb_item_path is not None or empty
          if not item.kb_item_path:
                logger.error(f"KB Item ID {item_id} has missing kb_item_path.")
                abort(500, description="KB item data is incomplete.")
                return # Added return

          base_kb_path = Path(config.knowledge_base_dir).resolve()
          item_rel_path = Path(item.kb_item_path)

          # Basic path safety check - ensure item path doesn't try to escape base path
          if '..' in item_rel_path.parts:
               logger.error(f"Invalid kb_item_path detected for item {item_id}: {item.kb_item_path}")
               abort(400, description="Invalid KB item path.")
               return # Added return

          readme_file_path = base_kb_path / item_rel_path / "README.md"

          logger.debug(f"Attempting to read README from: {readme_file_path}")
          try:
               readme_markdown = await file_io.read_text_async(readme_file_path)
               logger.debug(f"Successfully read README markdown for item {item_id}")
               # Render Markdown to HTML
               readme_html = md_utils.render_markdown(readme_markdown)

          except FileNotFoundError:
                logger.warning(f"README file not found at {readme_file_path} for item {item_id}")
                readme_html = "<p>(README file not found)</p>"
          except FileOperationError as e:
               logger.error(f"Failed to read README file {readme_file_path} for item {item_id}: {e}")
               readme_html = f"<p>(Error: Could not read README file: {e})</p>"
          except Exception as e:
                logger.error(f"Unexpected error reading/rendering README {readme_file_path}: {e}", exc_info=True)
                readme_html = "<p>(Error: Unexpected problem loading README)</p>"

          # Pass rendered HTML to template (kb_tree_data comes from context processor)
          return render_template('kb_detail.html', title=f"KB: {item.item_name}", item=item, readme_html=readme_html)

     except Exception as e:
          logger.error(f"Error fetching KB item {item_id} details: {e}", exc_info=True)
          abort(500, description="Error retrieving knowledge base item details.")


# --- UI Persistence API Routes ---
@main_bp.route('/api/ui-state', methods=['GET'])
async def get_ui_state_api():
    """API endpoint to get the current UI state."""
    if not hasattr(current_app, 'agent_config'): abort(500)
    config = current_app.agent_config
    state = await persistence.load_ui_state(config)
    return jsonify(state)

@main_bp.route('/api/ui-state', methods=['POST'])
async def save_ui_state_api():
    """API endpoint to save the entire UI state."""
    if not hasattr(current_app, 'agent_config'): abort(500)
    config = current_app.agent_config
    new_state = request.get_json()
    if not isinstance(new_state, dict):
         return jsonify({"error": "Invalid state data"}), 400
    await persistence.save_ui_state(config, new_state)
    return jsonify({"success": True}), 200

@main_bp.route('/api/ui-state/<key>', methods=['PUT'])
async def update_ui_state_key_api(key: str):
    """API endpoint to update a single key in the UI state."""
    if not hasattr(current_app, 'agent_config'): abort(500)
    config = current_app.agent_config
    data = request.get_json()
    if not isinstance(data, dict) or 'value' not in data:
         return jsonify({"error": "Invalid request data, 'value' key missing"}), 400
    value = data['value']
    await persistence.update_ui_state_key(config, key, value)
    return jsonify({"success": True}), 200

# Add other routes as needed (e.g., /logs page if WebSocket isn't sufficient)
