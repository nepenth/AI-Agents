from flask import Blueprint, jsonify, request, current_app
from ..models import db, KnowledgeBaseItem, SubcategorySynthesis
from ..agent import KnowledgeBaseAgent
from .logs import list_logs
from .log_content import get_log_content
import shutil
from pathlib import Path
import os
from typing import Dict, Any, List
import logging
from ..config import Config

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
        data = request.json or {}
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

@bp.route('/chat/legacy', methods=['POST'])
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

@bp.route('/chat/enhanced', methods=['POST'])
def api_chat_enhanced():
    """Enhanced chat API endpoint with technical expertise and rich source metadata."""
    try:
        from ..models import ChatSession, ChatMessage, db
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
        from ..web import get_chat_manager
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
        logging.error(f"Error in enhanced chat API: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/chat/models/available', methods=['GET'])
def api_chat_models_available():
    """Get available chat models."""
    try:
        from ..web import get_chat_manager
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

@bp.route('/chat/sessions', methods=['GET'])
def api_get_chat_sessions():
    """Get all chat sessions."""
    try:
        from ..models import ChatSession
        
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

@bp.route('/chat/sessions/<session_id>', methods=['GET'])
def api_get_chat_session(session_id):
    """Get a specific chat session with messages."""
    try:
        from ..models import ChatSession, ChatMessage
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

@bp.route('/chat/sessions', methods=['POST'])
def api_create_chat_session():
    """Create a new chat session."""
    try:
        from ..models import ChatSession, db
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

@bp.route('/chat/sessions/<session_id>/archive', methods=['POST'])
def api_archive_chat_session(session_id):
    """Archive/unarchive a chat session."""
    try:
        from ..models import ChatSession, db
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

@bp.route('/chat/sessions/<session_id>', methods=['DELETE'])
def api_delete_chat_session(session_id):
    """Delete a chat session and all its messages."""
    try:
        from ..models import ChatSession, db
        
        session = ChatSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        db.session.delete(session)
        db.session.commit()
        
        return jsonify({'message': 'Session deleted successfully'})
    except Exception as e:
        logging.error(f"Error deleting chat session {session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete chat session'}), 500

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

@bp.route('/environment-variables', methods=['GET'])
def get_environment_variables():
    """Get all environment variables with metadata."""
    try:
        # Get current environment variables
        env_variables = dict(os.environ)
        
        # Get config field information
        config_fields = {}
        try:
            # Import Config to get field definitions
            from ..config import Config
            for field_name, field_info in Config.model_fields.items():
                config_fields[field_name] = {
                    'description': field_info.description or 'No description available',
                    'required': field_info.is_required(),
                    'type': str(field_info.annotation),
                    'alias': field_info.alias
                }
        except Exception as e:
            logging.warning(f"Could not load config field info: {e}")
            config_fields = {}

        # Get list of used environment variables (those with aliases in Config)
        used_env_vars = []
        unused_env_vars = []
        missing_env_vars = []
        
        # Create mapping of aliases to field names
        alias_to_field = {}
        for field_name, field_info in config_fields.items():
            if field_info.get('alias'):
                alias_to_field[field_info['alias']] = field_name
        
        # Check which env vars are used/unused
        for env_var in env_variables:
            if env_var in alias_to_field:
                used_env_vars.append(env_var)
            else:
                unused_env_vars.append(env_var)
        
        # Check for missing required variables
        for field_name, field_info in config_fields.items():
            alias = field_info.get('alias')
            if alias and field_info.get('required', False) and alias not in env_variables:
                missing_env_vars.append(alias)
        
        return jsonify({
            'success': True,
            'env_variables': env_variables,
            'config_fields': config_fields,
            'used_env_vars': used_env_vars,
            'unused_env_vars': unused_env_vars,
            'missing_env_vars': missing_env_vars
        })
    
    except Exception as e:
        logging.error(f"Error getting environment variables: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/environment-variables', methods=['POST'])
def update_environment_variables():
    """Update environment variables."""
    try:
        data = request.get_json()
        env_variables = data.get('env_variables', {})
        
        if not env_variables:
            return jsonify({
                'success': False,
                'error': 'No environment variables provided'
            }), 400
        
        # Update environment variables in the current process
        updated_count = 0
        for key, value in env_variables.items():
            os.environ[key] = str(value)
            updated_count += 1
        
        # Try to update .env file if it exists
        env_file_path = Path('.env')
        if env_file_path.exists():
            try:
                # Read existing .env file
                with open(env_file_path, 'r') as f:
                    lines = f.readlines()
                
                # Update or add variables
                updated_lines = []
                updated_vars = set()
                
                for line in lines:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        var_name = line.split('=')[0].strip()
                        if var_name in env_variables:
                            # Update existing variable
                            updated_lines.append(f"{var_name}={env_variables[var_name]}\n")
                            updated_vars.add(var_name)
                        else:
                            updated_lines.append(line + '\n')
                    else:
                        updated_lines.append(line + '\n')
                
                # Add new variables
                for var_name, var_value in env_variables.items():
                    if var_name not in updated_vars:
                        updated_lines.append(f"{var_name}={var_value}\n")
                
                # Write back to .env file
                with open(env_file_path, 'w') as f:
                    f.writelines(updated_lines)
                
                logging.info(f"Updated .env file with {updated_count} variables")
                
            except Exception as e:
                logging.warning(f"Could not update .env file: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Successfully updated {updated_count} environment variables',
            'updated_count': updated_count
        })
    
    except Exception as e:
        logging.error(f"Error updating environment variables: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/environment-variables/<variable_name>', methods=['DELETE'])
def delete_environment_variable(variable_name):
    """Delete an environment variable."""
    try:
        # Remove from current process environment
        if variable_name in os.environ:
            del os.environ[variable_name]
        
        # Try to remove from .env file if it exists
        env_file_path = Path('.env')
        if env_file_path.exists():
            try:
                with open(env_file_path, 'r') as f:
                    lines = f.readlines()
                
                # Filter out the variable
                updated_lines = []
                for line in lines:
                    line_stripped = line.strip()
                    if '=' in line_stripped and not line_stripped.startswith('#'):
                        var_name = line_stripped.split('=')[0].strip()
                        if var_name != variable_name:
                            updated_lines.append(line)
                    else:
                        updated_lines.append(line)
                
                with open(env_file_path, 'w') as f:
                    f.writelines(updated_lines)
                
                logging.info(f"Removed {variable_name} from .env file")
                
            except Exception as e:
                logging.warning(f"Could not update .env file: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Environment variable {variable_name} deleted successfully'
        })
    
    except Exception as e:
        logging.error(f"Error deleting environment variable: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/hardware-detection', methods=['GET'])
def get_hardware_detection():
    """Get detected hardware information."""
    try:
        from ..hardware_detector import HardwareDetector
        
        detector = HardwareDetector()
        system_info = detector.detect_system_info()
        
        return jsonify({
            'success': True,
            'hardware': {
                'gpu_count': len(system_info.gpus),
                'gpu_total_memory': sum(gpu.memory_total_mb for gpu in system_info.gpus),
                'gpu_devices': [
                    {
                        'name': gpu.name,
                        'memory': gpu.memory_total_mb,
                        'utilization': gpu.memory_free_mb  # Using free memory as utilization placeholder
                    } for gpu in system_info.gpus
                ],
                'cpu_cores': system_info.cpu.physical_cores,
                'total_memory': system_info.total_ram_gb * 1024 * 1024 * 1024,  # Convert to bytes
                'available_memory': system_info.available_ram_gb * 1024 * 1024 * 1024  # Convert to bytes
            }
        })
    
    except ImportError as e:
        return jsonify({
            'success': False,
            'error': f'Hardware detection not available: {e}'
        }), 500
    except Exception as e:
        logging.error(f"Error detecting hardware: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/ollama-optimization', methods=['POST'])
def generate_ollama_optimization():
    """Generate Ollama optimization settings based on hardware and profile."""
    try:
        data = request.get_json()
        profile = data.get('profile', 'balanced')
        apply_to_env = data.get('apply_to_env', False)
        
        if profile not in ['performance', 'balanced', 'memory_efficient']:
            return jsonify({
                'success': False,
                'error': 'Invalid profile. Must be one of: performance, balanced, memory_efficient'
            }), 400
        
        # Use the Config class method to generate optimization
        env_vars = Config.auto_configure_ollama_optimization(
            workload_type=profile,
            apply_to_env=apply_to_env
        )
        
        if not env_vars:
            return jsonify({
                'success': False,
                'error': 'Hardware detection failed or no optimization possible'
            }), 500
        
        # If apply_to_env is True, also update the .env file
        if apply_to_env:
            env_file_path = Path('.env')
            if env_file_path.exists():
                try:
                    # Read existing .env file
                    with open(env_file_path, 'r') as f:
                        lines = f.readlines()
                    
                    # Update or add variables
                    updated_lines = []
                    updated_vars = set()
                    
                    for line in lines:
                        line_stripped = line.strip()
                        if '=' in line_stripped and not line_stripped.startswith('#'):
                            var_name = line_stripped.split('=')[0].strip()
                            if var_name in env_vars:
                                # Update existing variable
                                updated_lines.append(f"{var_name}={env_vars[var_name]}\n")
                                updated_vars.add(var_name)
                            else:
                                updated_lines.append(line)
                        else:
                            updated_lines.append(line)
                    
                    # Add new variables with header
                    if any(var_name not in updated_vars for var_name in env_vars):
                        updated_lines.append(f"\n# Auto-generated Ollama optimization ({profile} profile)\n")
                        for var_name, var_value in env_vars.items():
                            if var_name not in updated_vars:
                                updated_lines.append(f"{var_name}={var_value}\n")
                    
                    # Write back to .env file
                    with open(env_file_path, 'w') as f:
                        f.writelines(updated_lines)
                    
                    logging.info(f"Applied {len(env_vars)} optimization variables to .env file")
                    
                except Exception as e:
                    logging.warning(f"Could not update .env file: {e}")
        
        return jsonify({
            'success': True,
            'profile': profile,
            'env_variables': env_vars,
            'applied_to_env': apply_to_env,
            'message': f'Generated {len(env_vars)} optimization settings for {profile} profile'
        })
    
    except Exception as e:
        logging.error(f"Error generating Ollama optimization: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/syntheses', methods=['GET'])
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

@bp.route('/gpu-stats', methods=['GET'])
def api_gpu_stats():
    """REST API endpoint for GPU statistics as a fallback to SocketIO"""
    try:
        from ..gpu_utils import get_gpu_stats
        stats = get_gpu_stats()
        if stats is None:
            return jsonify({'error': 'GPU stats not available - nvidia-smi not found or failed'}), 500
        return jsonify({'gpus': stats})
    except Exception as e:
        logging.error(f"Error getting GPU stats via API: {e}", exc_info=True)
        return jsonify({'error': f'Failed to get GPU stats: {str(e)}'}), 500

@bp.route('/gpu-status', methods=['GET'])
def get_gpu_status():
    """Check comprehensive GPU status including NVIDIA, CUDA, and Ollama."""
    try:
        from ..utils.gpu_check import check_nvidia_smi, check_cuda_environment, check_ollama_gpu
        
        gpu_info = {
            'nvidia': {},
            'cuda_env': {},
            'ollama': {}
        }
        
        # Check NVIDIA GPU status
        nvidia_success, nvidia_result = check_nvidia_smi()
        gpu_info['nvidia']['success'] = nvidia_success
        gpu_info['nvidia']['result'] = nvidia_result
        
        # Check CUDA environment
        cuda_vars = check_cuda_environment()
        gpu_info['cuda_env'] = cuda_vars
        
        # Check Ollama
        ollama_success, ollama_result = check_ollama_gpu()
        gpu_info['ollama']['success'] = ollama_success
        gpu_info['ollama']['result'] = ollama_result
        
        return jsonify(gpu_info)
    except Exception as e:
        logging.error(f"Error checking GPU status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@bp.route('/schedules', methods=['GET'])
def api_get_schedules():
    """Get all schedules."""
    try:
        from ..models import Schedule
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

@bp.route('/schedules', methods=['POST'])
def api_create_schedule():
    """Create a new schedule."""
    try:
        from ..models import Schedule, db
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

@bp.route('/schedules/<int:schedule_id>', methods=['PUT'])
def api_update_schedule(schedule_id):
    """Update an existing schedule."""
    try:
        from ..models import Schedule, db
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

@bp.route('/schedules/<int:schedule_id>', methods=['DELETE'])
def api_delete_schedule(schedule_id):
    """Delete a schedule."""
    try:
        from ..models import Schedule, db
        
        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        db.session.delete(schedule)
        db.session.commit()
        
        return jsonify({'message': 'Schedule deleted successfully'})
    except Exception as e:
        logging.error(f"Error deleting schedule {schedule_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete schedule'}), 500

@bp.route('/schedules/<int:schedule_id>/toggle', methods=['POST'])
def api_toggle_schedule(schedule_id):
    """Toggle schedule enabled/disabled status."""
    try:
        from ..models import Schedule, db
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

@bp.route('/schedules/<int:schedule_id>/run', methods=['POST'])
def api_run_schedule(schedule_id):
    """Run a schedule immediately."""
    try:
        from ..models import Schedule, ScheduleRun, db
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

@bp.route('/schedule-history', methods=['GET'])
def api_get_schedule_history():
    """Get schedule execution history."""
    try:
        from ..models import ScheduleRun, Schedule
        
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

@bp.route('/schedule-runs/<int:run_id>', methods=['DELETE'])
def delete_schedule_run(run_id):
    """API endpoint to delete a schedule run from history."""
    try:
        from ..models import ScheduleRun, db
        
        run = ScheduleRun.query.get(run_id)
        if not run:
            return jsonify({'error': 'Schedule run not found'}), 404
        
        db.session.delete(run)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Schedule run deleted successfully'})
    except Exception as e:
        logging.error(f"Error deleting schedule run {run_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500 