from flask import Blueprint, jsonify, request, current_app
from ..models import db, KnowledgeBaseItem, SubcategorySynthesis
from ..agent import KnowledgeBaseAgent
from .logs import list_logs
from .log_content import get_log_content
import shutil
from pathlib import Path

bp = Blueprint('api', __name__)

@bp.route('/chat/models', methods=['GET'])
def get_chat_models():
    """Returns the list of available chat models from the config."""
    app_config = current_app.config.get('APP_CONFIG')
    if not app_config or not hasattr(app_config, 'available_chat_models'):
        return jsonify({"error": "Chat models configuration not available"}), 500
    
    models = [{"id": model, "name": model} for model in app_config.available_chat_models]
    return jsonify(models)

@bp.route('/chat', methods=['POST'])
def chat():
    """Handle chat interactions via API using the knowledge base agent."""
    try:
        data = request.json
        query = data.get('message') or data.get('query')  # Support both parameter names
        model = data.get('model')
        
        if not query:
            return jsonify({"error": "No query provided"}), 400
            
        # Get the agent from the current app's config
        app_config = current_app.config.get('APP_CONFIG')
        if not app_config:
            return jsonify({"error": "Application configuration not available"}), 500
            
        # Import and create agent components
        from ..agent import KnowledgeBaseAgent
        from ..http_client import HTTPClient
        from ..embedding_manager import EmbeddingManager
        from ..chat_manager import ChatManager
        import asyncio
        
        # Create HTTP client and embedding manager
        http_client = HTTPClient(app_config)
        embedding_manager = EmbeddingManager(app_config, http_client)
        chat_manager = ChatManager(app_config, http_client, embedding_manager)
        
        # Process the chat query asynchronously
        async def process_chat():
            try:
                await http_client.initialize()
                # EmbeddingManager doesn't have an initialize method, it's ready to use
                response = await chat_manager.handle_chat_query(query, model)
                return response
            finally:
                await http_client.close()  # Use close() instead of cleanup()
        
        # Run the async chat processing
        response = asyncio.run(process_chat())
        
        if "error" in response:
            return jsonify(response), 500
            
        return jsonify(response)
        
    except Exception as e:
        current_app.logger.error(f"Chat API error: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@bp.route('/preferences', methods=['POST'])
def save_preferences():
    # Placeholder for saving user preferences
    data = request.json
    print(f"Preferences saved: {data}") # In a real app, save this to a user session or DB
    return jsonify({"status": "success"})

@bp.route('/synthesis', methods=['GET'])
def get_synthesis_documents():
    """API endpoint to get all synthesis documents."""
    try:
        syntheses = SubcategorySynthesis.query.order_by(SubcategorySynthesis.last_updated.desc()).all()
        synthesis_list = [{
            "id": synth.id,
            "title": synth.synthesis_title,
            "summary": (synth.synthesis_content or "")[:200] + '...',
            "topic": f"{synth.main_category}/{synth.sub_category}",
            "last_updated": synth.last_updated.isoformat()
        } for synth in syntheses]
        return jsonify(synthesis_list)
    except Exception as e:
        current_app.logger.error(f"API Error fetching syntheses: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch synthesis documents."}), 500

@bp.route('/logs', methods=['GET'])
def api_list_logs():
    """API endpoint to list available log files."""
    app_config = current_app.config.get('APP_CONFIG')
    if not app_config:
        return jsonify({"error": "Configuration not available"}), 500
    return list_logs(app_config)

@bp.route('/logs/<filename>', methods=['GET'])
def api_get_log_content(filename):
    """API endpoint to get the content of a specific log file."""
    app_config = current_app.config.get('APP_CONFIG')
    if not app_config:
        return jsonify({"error": "Configuration not available"}), 500
    return get_log_content(filename, app_config)

@bp.route('/logs/delete-all', methods=['POST'])
def api_delete_all_logs():
    """API endpoint to delete all log files."""
    try:
        app_config = current_app.config.get('APP_CONFIG')
        if not app_config or not hasattr(app_config, 'log_dir'):
            return jsonify({"error": "Configuration for log directory not available"}), 500

        log_dir = Path(app_config.log_dir).expanduser().resolve()
        if not log_dir.exists():
            return jsonify({"message": "No log directory found", "deleted_count": 0})

        # Count and delete .log files
        log_files = list(log_dir.glob('*.log'))
        deleted_count = len(log_files)
        
        for log_file in log_files:
            log_file.unlink()

        return jsonify({
            "message": f"Successfully deleted {deleted_count} log files",
            "deleted_count": deleted_count
        })
    except Exception as e:
        current_app.logger.error(f"Error deleting log files: {e}", exc_info=True)
        return jsonify({"error": f"Failed to delete log files: {str(e)}"}), 500 