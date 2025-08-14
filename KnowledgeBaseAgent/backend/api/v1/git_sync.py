"""Git sync API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from app.services.git_sync_service import get_git_sync_service, GitConfig, GitSyncResult
from app.security import get_current_user, admin_required
from app.models.auth import User

router = APIRouter()


class GitConfigRequest(BaseModel):
    """Request model for Git configuration."""
    repo_url: str = Field(..., description="Git repository URL")
    branch: str = Field(default="main", description="Git branch to sync to")
    username: Optional[str] = Field(default=None, description="Git username for authentication")
    password: Optional[str] = Field(default=None, description="Git password or token")
    ssh_key_path: Optional[str] = Field(default=None, description="Path to SSH private key")
    commit_author_name: str = Field(default="AI Agent", description="Commit author name")
    commit_author_email: str = Field(default="ai-agent@example.com", description="Commit author email")
    auto_push: bool = Field(default=True, description="Automatically push changes")
    auto_pull: bool = Field(default=True, description="Automatically pull before sync")


class GitSyncResponse(BaseModel):
    """Response model for Git sync operations."""
    success: bool
    message: str
    operation_id: str
    files_exported: int
    files_changed: int
    commit_hash: Optional[str] = None
    errors: List[str] = []


class GitSyncHistoryResponse(BaseModel):
    """Response model for Git sync history."""
    operations: List[Dict[str, Any]]
    total: int


# In-memory storage for sync status (in production, use Redis or database)
sync_status = {}


@router.post("/sync", response_model=GitSyncResponse)
@admin_required
async def sync_to_git(
    config_request: GitConfigRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Sync database content to Git repository."""
    try:
        git_sync_service = get_git_sync_service()
        
        config = GitConfig(
            repo_url=config_request.repo_url,
            branch=config_request.branch,
            username=config_request.username,
            password=config_request.password,
            ssh_key_path=config_request.ssh_key_path,
            commit_author_name=config_request.commit_author_name,
            commit_author_email=config_request.commit_author_email,
            auto_push=config_request.auto_push,
            auto_pull=config_request.auto_pull
        )
        
        # Generate sync ID
        sync_id = f"sync_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize status
        sync_status[sync_id] = {
            'status': 'starting',
            'progress': 0.0,
            'message': 'Git sync starting...',
            'started_at': datetime.utcnow(),
            'user_id': current_user.id
        }
        
        # Start sync in background
        background_tasks.add_task(
            run_git_sync_background,
            sync_id,
            config,
            git_sync_service
        )
        
        return GitSyncResponse(
            success=True,
            message="Git sync started successfully",
            operation_id=sync_id,
            files_exported=0,
            files_changed=0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start Git sync: {str(e)}")


@router.get("/status/{sync_id}")
@admin_required
async def get_sync_status(
    sync_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get status of a Git sync operation."""
    if sync_id not in sync_status:
        raise HTTPException(status_code=404, detail="Sync operation not found")
    
    return sync_status[sync_id]


@router.get("/history", response_model=GitSyncHistoryResponse)
@admin_required
async def get_sync_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get Git sync operation history."""
    try:
        git_sync_service = get_git_sync_service()
        operations = await git_sync_service.get_sync_history(limit=limit)
        
        return GitSyncHistoryResponse(
            operations=operations,
            total=len(operations)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync history: {str(e)}")


@router.post("/test-connection")
@admin_required
async def test_git_connection(
    config_request: GitConfigRequest,
    current_user: User = Depends(get_current_user)
):
    """Test Git repository connection."""
    try:
        # This would test the Git connection without performing a full sync
        # For now, return a simple validation
        
        if not config_request.repo_url:
            raise HTTPException(status_code=400, detail="Repository URL is required")
        
        if not config_request.repo_url.startswith(('http://', 'https://', 'git@')):
            raise HTTPException(status_code=400, detail="Invalid repository URL format")
        
        return {
            'success': True,
            'message': 'Git configuration appears valid',
            'repository_url': config_request.repo_url,
            'branch': config_request.branch
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")


@router.delete("/cleanup/{sync_id}")
@admin_required
async def cleanup_sync_operation(
    sync_id: str,
    current_user: User = Depends(get_current_user)
):
    """Clean up sync operation data."""
    if sync_id not in sync_status:
        raise HTTPException(status_code=404, detail="Sync operation not found")
    
    status_info = sync_status[sync_id]
    
    if status_info['status'] in ['running', 'starting']:
        raise HTTPException(
            status_code=400, 
            detail="Cannot cleanup running sync operation"
        )
    
    # Remove from status tracking
    del sync_status[sync_id]
    
    return {
        'sync_id': sync_id,
        'message': 'Sync operation data cleaned up successfully'
    }


@router.get("/stats")
@admin_required
async def get_sync_stats(current_user: User = Depends(get_current_user)):
    """Get overall Git sync statistics."""
    total_syncs = len(sync_status)
    completed_syncs = sum(1 for s in sync_status.values() if s['status'] == 'completed')
    failed_syncs = sum(1 for s in sync_status.values() if s['status'] == 'failed')
    running_syncs = sum(1 for s in sync_status.values() if s['status'] == 'running')
    
    return {
        'total_syncs': total_syncs,
        'completed_syncs': completed_syncs,
        'failed_syncs': failed_syncs,
        'running_syncs': running_syncs,
        'success_rate': completed_syncs / total_syncs if total_syncs > 0 else 0.0
    }


async def run_git_sync_background(
    sync_id: str,
    config: GitConfig,
    git_sync_service
):
    """Run Git sync in background task."""
    try:
        # Update status
        sync_status[sync_id]['status'] = 'running'
        sync_status[sync_id]['message'] = 'Git sync in progress...'
        sync_status[sync_id]['progress'] = 25.0
        
        # Run sync
        result = await git_sync_service.sync_to_repository(config)
        
        # Update final status
        if result.success:
            sync_status[sync_id]['status'] = 'completed'
            sync_status[sync_id]['message'] = result.message
            sync_status[sync_id]['progress'] = 100.0
            sync_status[sync_id]['files_exported'] = result.files_exported
            sync_status[sync_id]['files_changed'] = result.files_changed
            sync_status[sync_id]['commit_hash'] = result.commit_hash
        else:
            sync_status[sync_id]['status'] = 'failed'
            sync_status[sync_id]['message'] = result.message
            sync_status[sync_id]['errors'] = result.errors
        
        sync_status[sync_id]['completed_at'] = datetime.utcnow()
        
    except Exception as e:
        sync_status[sync_id]['status'] = 'failed'
        sync_status[sync_id]['message'] = f'Git sync failed: {str(e)}'
        sync_status[sync_id]['completed_at'] = datetime.utcnow()