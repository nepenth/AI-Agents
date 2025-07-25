"""
Backup Management API Routes

RESTful API endpoints for backup creation, validation, restoration,
and monitoring operations.
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from typing import Dict, List, Any

from ..backup_manager import BackupManager
from ..config import Config


# Create blueprint for backup routes
backup_api = Blueprint('backup_api', __name__, url_prefix='/api/v2/backup')
logger = logging.getLogger(__name__)

# Global backup manager instance
backup_manager = None


def get_backup_manager() -> BackupManager:
    """Get or create backup manager instance."""
    global backup_manager
    if backup_manager is None:
        config = current_app.config.get('KB_CONFIG') or Config()
        backup_manager = BackupManager(config)
    return backup_manager


@backup_api.route('/create', methods=['POST'])
def create_backup():
    """
    Create a new backup.
    
    Expected JSON body:
    {
        "backup_type": "manual|daily|weekly|pre_migration",
        "description": "Optional description",
        "components": ["database", "json_files", "media", "logs"]  // optional
    }
    """
    try:
        data = request.get_json() or {}
        
        backup_type = data.get('backup_type', 'manual')
        description = data.get('description', '')
        components = data.get('components', None)
        
        # Validate backup type
        valid_types = ['manual', 'daily', 'weekly', 'pre_migration', 'monthly']
        if backup_type not in valid_types:
            return jsonify({
                'success': False,
                'error': f'Invalid backup type. Must be one of: {", ".join(valid_types)}'
            }), 400
        
        # Validate components if provided
        if components is not None:
            valid_components = ['database', 'json_files', 'media', 'logs']
            invalid_components = [c for c in components if c not in valid_components]
            if invalid_components:
                return jsonify({
                    'success': False,
                    'error': f'Invalid components: {", ".join(invalid_components)}'
                }), 400
        
        manager = get_backup_manager()
        backup_id = manager.create_backup(backup_type, description, components)
        
        return jsonify({
            'success': True,
            'backup_id': backup_id,
            'message': f'Backup {backup_id} created successfully'
        })
        
    except RuntimeError as e:
        logger.error(f"Backup creation failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 409  # Conflict - backup already running
        
    except Exception as e:
        logger.error(f"Backup creation error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Backup creation failed: {str(e)}'
        }), 500


@backup_api.route('/list', methods=['GET'])
def list_backups():
    """
    List all available backups with filtering and pagination.
    
    Query parameters:
    - backup_type: Filter by backup type
    - limit: Maximum number of results (default: 50)
    - offset: Number of results to skip (default: 0)
    """
    try:
        backup_type = request.args.get('backup_type')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        manager = get_backup_manager()
        backup_ids = manager.list_backups()
        
        # Filter by backup type if specified
        if backup_type:
            filtered_ids = []
            for backup_id in backup_ids:
                metadata = manager.get_backup_info(backup_id)
                if metadata and metadata.backup_type == backup_type:
                    filtered_ids.append(backup_id)
            backup_ids = filtered_ids
        
        # Apply pagination
        total_count = len(backup_ids)
        paginated_ids = backup_ids[offset:offset + limit]
        
        # Get detailed information for paginated results
        backups = []
        for backup_id in paginated_ids:
            metadata = manager.get_backup_info(backup_id)
            if metadata:
                backups.append({
                    'backup_id': metadata.backup_id,
                    'backup_type': metadata.backup_type,
                    'created_at': metadata.created_at.isoformat(),
                    'size_bytes': metadata.size_bytes,
                    'description': metadata.description,
                    'retention_date': metadata.retention_date.isoformat(),
                    'components': metadata.components,
                    'validation_status': metadata.validation_status,
                    'restore_tested': metadata.restore_tested
                })
        
        return jsonify({
            'success': True,
            'backups': backups,
            'pagination': {
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_next': offset + limit < total_count,
                'has_prev': offset > 0
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to list backups: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to list backups: {str(e)}'
        }), 500


@backup_api.route('/<backup_id>', methods=['GET'])
def get_backup_details(backup_id: str):
    """Get detailed information about a specific backup."""
    try:
        manager = get_backup_manager()
        metadata = manager.get_backup_info(backup_id)
        
        if not metadata:
            return jsonify({
                'success': False,
                'error': f'Backup {backup_id} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'backup': {
                'backup_id': metadata.backup_id,
                'backup_type': metadata.backup_type,
                'created_at': metadata.created_at.isoformat(),
                'size_bytes': metadata.size_bytes,
                'checksum': metadata.checksum,
                'description': metadata.description,
                'retention_date': metadata.retention_date.isoformat(),
                'components': metadata.components,
                'validation_status': metadata.validation_status,
                'restore_tested': metadata.restore_tested,
                'file_paths': metadata.file_paths
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get backup details for {backup_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to get backup details: {str(e)}'
        }), 500


@backup_api.route('/<backup_id>/validate', methods=['POST'])
def validate_backup(backup_id: str):
    """Validate a specific backup."""
    try:
        manager = get_backup_manager()
        validation_result = manager.validate_backup(backup_id)
        
        return jsonify({
            'success': True,
            'validation': {
                'is_valid': validation_result.is_valid,
                'checksum_verified': validation_result.checksum_verified,
                'content_verified': validation_result.content_verified,
                'restore_tested': validation_result.restore_tested,
                'errors': validation_result.errors,
                'warnings': validation_result.warnings,
                'validation_time': validation_result.validation_time.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to validate backup {backup_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Backup validation failed: {str(e)}'
        }), 500


@backup_api.route('/<backup_id>/restore', methods=['POST'])
def restore_backup(backup_id: str):
    """
    Restore from a specific backup.
    
    Expected JSON body:
    {
        "components": ["database", "json_files", "media", "logs"],  // optional
        "target_directory": "/custom/path",  // optional
        "create_rollback": true  // optional, default true
    }
    """
    try:
        data = request.get_json() or {}
        
        components = data.get('components', None)
        target_directory = data.get('target_directory', None)
        create_rollback = data.get('create_rollback', True)
        
        # Validate components if provided
        if components is not None:
            valid_components = ['database', 'json_files', 'media', 'logs']
            invalid_components = [c for c in components if c not in valid_components]
            if invalid_components:
                return jsonify({
                    'success': False,
                    'error': f'Invalid components: {", ".join(invalid_components)}'
                }), 400
        
        manager = get_backup_manager()
        restore_result = manager.restore_backup(
            backup_id, components, target_directory, create_rollback
        )
        
        return jsonify({
            'success': restore_result.success,
            'restore': {
                'backup_id': restore_result.backup_id,
                'components_restored': restore_result.components_restored,
                'errors': restore_result.errors,
                'warnings': restore_result.warnings,
                'restore_time': restore_result.restore_time.isoformat(),
                'rollback_available': restore_result.rollback_available
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to restore backup {backup_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Backup restoration failed: {str(e)}'
        }), 500


@backup_api.route('/<backup_id>', methods=['DELETE'])
def delete_backup(backup_id: str):
    """Delete a specific backup."""
    try:
        # Check if backup exists
        manager = get_backup_manager()
        metadata = manager.get_backup_info(backup_id)
        
        if not metadata:
            return jsonify({
                'success': False,
                'error': f'Backup {backup_id} not found'
            }), 404
        
        # Delete backup files and metadata
        backup_dir = manager.backup_base_dir / backup_id
        if backup_dir.exists():
            import shutil
            shutil.rmtree(backup_dir)
        
        metadata_file = manager.backup_base_dir / "metadata" / f"{backup_id}.json"
        if metadata_file.exists():
            metadata_file.unlink()
        
        logger.info(f"Backup {backup_id} deleted manually via API")
        
        return jsonify({
            'success': True,
            'message': f'Backup {backup_id} deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Failed to delete backup {backup_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to delete backup: {str(e)}'
        }), 500


@backup_api.route('/cleanup', methods=['POST'])
def cleanup_backups():
    """Run backup cleanup to remove expired backups."""
    try:
        manager = get_backup_manager()
        cleanup_stats = manager.cleanup_expired_backups()
        
        return jsonify({
            'success': True,
            'cleanup_stats': cleanup_stats,
            'message': f'Cleanup completed. Removed {cleanup_stats["successfully_deleted"]} expired backups'
        })
        
    except Exception as e:
        logger.error(f"Backup cleanup failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Backup cleanup failed: {str(e)}'
        }), 500


@backup_api.route('/statistics', methods=['GET'])
def get_backup_statistics():
    """Get comprehensive backup statistics and metrics."""
    try:
        manager = get_backup_manager()
        stats = manager.get_backup_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        logger.error(f"Failed to get backup statistics: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to get backup statistics: {str(e)}'
        }), 500


@backup_api.route('/status', methods=['GET'])
def get_backup_status():
    """Get current backup system status."""
    try:
        manager = get_backup_manager()
        
        status = {
            'backup_running': manager.backup_running,
            'last_backup_time': manager.last_backup_time.isoformat() if manager.last_backup_time else None,
            'backup_directory': str(manager.backup_base_dir),
            'retention_policies': {
                backup_type: str(policy) for backup_type, policy in manager.retention_policies.items()
            },
            'scheduler_active': True  # Assuming scheduler is always active when manager exists
        }
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Failed to get backup status: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to get backup status: {str(e)}'
        }), 500


@backup_api.route('/scheduler/start', methods=['POST'])
def start_backup_scheduler():
    """Start the automated backup scheduler."""
    try:
        manager = get_backup_manager()
        manager.schedule_automated_backups()
        
        return jsonify({
            'success': True,
            'message': 'Backup scheduler started successfully'
        })
        
    except Exception as e:
        logger.error(f"Failed to start backup scheduler: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to start backup scheduler: {str(e)}'
        }), 500


@backup_api.route('/retention-policies', methods=['GET'])
def get_retention_policies():
    """Get current backup retention policies."""
    try:
        manager = get_backup_manager()
        
        policies = {
            backup_type: {
                'retention_days': policy.days,
                'retention_string': str(policy)
            }
            for backup_type, policy in manager.retention_policies.items()
        }
        
        return jsonify({
            'success': True,
            'retention_policies': policies
        })
        
    except Exception as e:
        logger.error(f"Failed to get retention policies: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to get retention policies: {str(e)}'
        }), 500


@backup_api.route('/retention-policies', methods=['PUT'])
def update_retention_policies():
    """
    Update backup retention policies.
    
    Expected JSON body:
    {
        "daily": 7,     // days
        "weekly": 14,   // days
        "monthly": 90,  // days
        "manual": 30,   // days
        "pre_migration": 90  // days
    }
    """
    try:
        data = request.get_json() or {}
        
        manager = get_backup_manager()
        
        # Update policies
        for backup_type, days in data.items():
            if backup_type in manager.retention_policies:
                if isinstance(days, int) and days > 0:
                    from datetime import timedelta
                    manager.retention_policies[backup_type] = timedelta(days=days)
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Invalid retention period for {backup_type}: must be positive integer'
                    }), 400
            else:
                return jsonify({
                    'success': False,
                    'error': f'Unknown backup type: {backup_type}'
                }), 400
        
        logger.info(f"Backup retention policies updated: {data}")
        
        return jsonify({
            'success': True,
            'message': 'Retention policies updated successfully',
            'updated_policies': {
                backup_type: policy.days
                for backup_type, policy in manager.retention_policies.items()
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to update retention policies: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to update retention policies: {str(e)}'
        }), 500


# Error handlers for the backup blueprint
@backup_api.errorhandler(404)
def backup_not_found(error):
    """Handle 404 errors for backup routes."""
    return jsonify({
        'success': False,
        'error': 'Backup not found'
    }), 404


@backup_api.errorhandler(400)
def backup_bad_request(error):
    """Handle 400 errors for backup routes."""
    return jsonify({
        'success': False,
        'error': 'Bad request'
    }), 400


@backup_api.errorhandler(500)
def backup_internal_error(error):
    """Handle 500 errors for backup routes."""
    logger.error(f"Internal error in backup API: {error}")
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500 