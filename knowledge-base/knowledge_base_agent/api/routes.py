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
    # This is a placeholder for handling chat interactions via API.
    # The primary interaction is via WebSockets, but this can be used for stateless queries.
    data = request.json
    # In a real implementation, you'd process the message and return a response.
    return jsonify({"response": f"You said: {data.get('message')}", "sources": []})

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