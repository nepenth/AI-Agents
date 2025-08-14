"""Migration API endpoints for data migration operations."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.services.migration_service import get_migration_service, MigrationConfig, MigrationResult
from app.security import get_current_user, admin_required
from app.models.auth import User

router = APIRouter()


class MigrationConfigRequest(BaseModel):
    """Request model for migration configuration."""
    source_directory: str = Field(..., description="Source directory containing legacy data")
    backup_directory: str = Field(..., description="Directory for backups and reports")
    batch_size: int = Field(default=100, ge=1, le=1000, description="Batch size for processing")
    validate_data: bool = Field(default=True, description="Whether to validate data before migration")
    create_backups: bool = Field(default=True, description="Whether to create backups")
    preserve_timestamps: bool = Field(default=True, description="Whether to preserve original timestamps")
    dry_run: bool = Field(default=False, description="Whether to perform a dry run")
    incremental: bool = Field(default=False, description="Whether to perform incremental migration")
    max_file_size: int = Field(default=50*1024*1024, description="Maximum file size to process (bytes)")
    skip_large_files: bool = Field(default=True, description="Whether to skip files larger than max_file_size")
    parallel_processing: bool = Field(default=False, description="Whether to use parallel processing")
    max_workers: int = Field(default=4, ge=1, le=16, description="Maximum number of worker threads")


class MigrationStatusResponse(BaseModel):
    """Response model for migration status."""
    migration_id: str
    status: str
    progress: float
    message: str
    started_at: datetime
    estimated_completion: Optional[datetime] = None


class ValidationResponse(BaseModel):
    """Response model for migration validation."""
    total_files: int
    valid_files: int
    invalid_files: int
    errors: list
    warnings: list


# In-memory storage for migration status (in production, use Redis or database)
migration_status = {}


@router.post("/validate")
@admin_required
async def validate_migration_data(
    config_request: MigrationConfigRequest,
    current_user: User = Depends(get_current_user)
):
    """Validate migration data without performing actual migration."""
    try:
        migration_service = get_migration_service()
        
        config = MigrationConfig(
            source_directory=config_request.source_directory,
            backup_directory=config_request.backup_directory,
            batch_size=config_request.batch_size,
            validate_data=config_request.validate_data,
            create_backups=config_request.create_backups,
            preserve_timestamps=config_request.preserve_timestamps,
            dry_run=True  # Always dry run for validation
        )
        
        validation_result = await migration_service.validate_migration(config)
        
        return ValidationResponse(
            total_files=validation_result['total_files'],
            valid_files=validation_result['valid_files'],
            invalid_files=validation_result['invalid_files'],
            errors=validation_result['errors'],
            warnings=validation_result['warnings']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/start")
@admin_required
async def start_migration(
    config_request: MigrationConfigRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Start data migration process."""
    try:
        migration_service = get_migration_service()
        
        config = MigrationConfig(
            source_directory=config_request.source_directory,
            backup_directory=config_request.backup_directory,
            batch_size=config_request.batch_size,
            validate_data=config_request.validate_data,
            create_backups=config_request.create_backups,
            preserve_timestamps=config_request.preserve_timestamps,
            dry_run=config_request.dry_run,
            incremental=config_request.incremental,
            max_file_size=config_request.max_file_size,
            skip_large_files=config_request.skip_large_files,
            parallel_processing=config_request.parallel_processing,
            max_workers=config_request.max_workers
        )
        
        # Generate migration ID
        migration_id = f"migration_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize status
        migration_status[migration_id] = {
            'status': 'starting',
            'progress': 0.0,
            'message': 'Migration starting...',
            'started_at': datetime.utcnow(),
            'config': config_request.dict(),
            'user_id': current_user.id
        }
        
        # Start migration in background
        background_tasks.add_task(
            run_migration_background,
            migration_id,
            config,
            migration_service
        )
        
        return {
            'migration_id': migration_id,
            'status': 'started',
            'message': 'Migration started successfully'
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start migration: {str(e)}")


@router.get("/status/{migration_id}")
@admin_required
async def get_migration_status(
    migration_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get status of a migration process."""
    if migration_id not in migration_status:
        raise HTTPException(status_code=404, detail="Migration not found")
    
    status_info = migration_status[migration_id]
    
    return MigrationStatusResponse(
        migration_id=migration_id,
        status=status_info['status'],
        progress=status_info['progress'],
        message=status_info['message'],
        started_at=status_info['started_at'],
        estimated_completion=status_info.get('estimated_completion')
    )


@router.get("/history")
@admin_required
async def get_migration_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get migration history."""
    # Sort by start time, newest first
    sorted_migrations = sorted(
        migration_status.items(),
        key=lambda x: x[1]['started_at'],
        reverse=True
    )
    
    history = []
    for migration_id, status_info in sorted_migrations[:limit]:
        history.append({
            'migration_id': migration_id,
            'status': status_info['status'],
            'progress': status_info['progress'],
            'message': status_info['message'],
            'started_at': status_info['started_at'],
            'completed_at': status_info.get('completed_at'),
            'user_id': status_info.get('user_id')
        })
    
    return {
        'migrations': history,
        'total': len(migration_status)
    }


@router.post("/rollback/{migration_id}")
@admin_required
async def rollback_migration(
    migration_id: str,
    current_user: User = Depends(get_current_user)
):
    """Rollback a completed migration."""
    try:
        if migration_id not in migration_status:
            raise HTTPException(status_code=404, detail="Migration not found")
        
        status_info = migration_status[migration_id]
        
        if status_info['status'] != 'completed':
            raise HTTPException(
                status_code=400, 
                detail="Can only rollback completed migrations"
            )
        
        rollback_info = status_info.get('rollback_info')
        if not rollback_info:
            raise HTTPException(
                status_code=400, 
                detail="No rollback information available"
            )
        
        migration_service = get_migration_service()
        success = await migration_service.rollback_migration(rollback_info)
        
        if success:
            # Update status
            migration_status[migration_id]['status'] = 'rolled_back'
            migration_status[migration_id]['message'] = 'Migration rolled back successfully'
            migration_status[migration_id]['rolled_back_at'] = datetime.utcnow()
            
            return {
                'migration_id': migration_id,
                'status': 'rolled_back',
                'message': 'Migration rolled back successfully'
            }
        else:
            raise HTTPException(status_code=500, detail="Rollback failed")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")


@router.delete("/cleanup/{migration_id}")
@admin_required
async def cleanup_migration(
    migration_id: str,
    current_user: User = Depends(get_current_user)
):
    """Clean up migration data and status."""
    if migration_id not in migration_status:
        raise HTTPException(status_code=404, detail="Migration not found")
    
    status_info = migration_status[migration_id]
    
    if status_info['status'] in ['running', 'starting']:
        raise HTTPException(
            status_code=400, 
            detail="Cannot cleanup running migration"
        )
    
    # Remove from status tracking
    del migration_status[migration_id]
    
    return {
        'migration_id': migration_id,
        'message': 'Migration data cleaned up successfully'
    }


@router.get("/stats")
@admin_required
async def get_migration_stats(current_user: User = Depends(get_current_user)):
    """Get overall migration statistics."""
    total_migrations = len(migration_status)
    completed_migrations = sum(1 for s in migration_status.values() if s['status'] == 'completed')
    failed_migrations = sum(1 for s in migration_status.values() if s['status'] == 'failed')
    running_migrations = sum(1 for s in migration_status.values() if s['status'] == 'running')
    
    return {
        'total_migrations': total_migrations,
        'completed_migrations': completed_migrations,
        'failed_migrations': failed_migrations,
        'running_migrations': running_migrations,
        'success_rate': completed_migrations / total_migrations if total_migrations > 0 else 0.0
    }


async def run_migration_background(
    migration_id: str,
    config: MigrationConfig,
    migration_service
):
    """Run migration in background task."""
    try:
        # Update status
        migration_status[migration_id]['status'] = 'running'
        migration_status[migration_id]['message'] = 'Migration in progress...'
        
        # Run migration
        result = await migration_service.migrate_legacy_data(config)
        
        # Update final status
        if result.success:
            migration_status[migration_id]['status'] = 'completed'
            migration_status[migration_id]['message'] = result.message
            migration_status[migration_id]['progress'] = 100.0
            migration_status[migration_id]['rollback_info'] = result.rollback_info
        else:
            migration_status[migration_id]['status'] = 'failed'
            migration_status[migration_id]['message'] = result.message
            migration_status[migration_id]['errors'] = result.errors
        
        migration_status[migration_id]['completed_at'] = datetime.utcnow()
        migration_status[migration_id]['stats'] = result.stats.to_dict()
        
    except Exception as e:
        migration_status[migration_id]['status'] = 'failed'
        migration_status[migration_id]['message'] = f'Migration failed: {str(e)}'
        migration_status[migration_id]['completed_at'] = datetime.utcnow()


@router.get("/export")
@admin_required
async def export_current_data(
    format: str = "json",
    current_user: User = Depends(get_current_user)
):
    """Export current data for backup purposes."""
    try:
        migration_service = get_migration_service()
        
        # This would implement data export functionality
        # For now, return a placeholder response
        
        return {
            'message': 'Data export functionality would be implemented here',
            'format': format,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/import")
@admin_required
async def import_data(
    file_path: str,
    format: str = "json",
    current_user: User = Depends(get_current_user)
):
    """Import data from backup file."""
    try:
        # This would implement data import functionality
        # For now, return a placeholder response
        
        return {
            'message': 'Data import functionality would be implemented here',
            'file_path': file_path,
            'format': format,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")