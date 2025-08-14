"""Authentication API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Request, status
from typing import List, Optional
from datetime import datetime

from app.services.auth_service import get_auth_service, AuthenticationError, AuthorizationError
from app.schemas.auth import (
    UserCreate, UserLogin, UserResponse, TokenResponse, RefreshTokenRequest,
    APIKeyCreate, APIKeyResponse, AuditLogResponse, PasswordChangeRequest
)
from app.security import (
    get_current_user, get_current_user_or_api_key, admin_required,
    require_permissions, sanitize_request_data, Permissions
)
from app.models.auth import User

router = APIRouter()


@router.post("/register", response_model=UserResponse)
@sanitize_request_data
async def register_user(user_create: UserCreate):
    """Register a new user."""
    try:
        auth_service = get_auth_service()
        user = await auth_service.register_user(
            username=user_create.username,
            email=user_create.email,
            password=user_create.password,
            roles=user_create.roles
        )
        
        return UserResponse.from_orm(user)
        
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed")


@router.post("/login", response_model=TokenResponse)
@sanitize_request_data
async def login_user(user_login: UserLogin):
    """Authenticate user and return tokens."""
    try:
        auth_service = get_auth_service()
        
        # Authenticate user
        user = await auth_service.authenticate_user(user_login.username, user_login.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Create tokens
        access_token = await auth_service.create_access_token(user)
        refresh_token = await auth_service.create_refresh_token(user)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=30 * 60  # 30 minutes
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_request: RefreshTokenRequest):
    """Refresh access token using refresh token."""
    try:
        auth_service = get_auth_service()
        token_response = await auth_service.refresh_access_token(refresh_request.refresh_token)
        
        return token_response
        
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token refresh failed")


@router.post("/logout")
async def logout_user(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Logout user and revoke token."""
    try:
        auth_service = get_auth_service()
        
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            await auth_service.revoke_token(token, current_user.id)
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user_or_api_key)):
    """Get current user information."""
    return UserResponse.from_orm(current_user)


@router.put("/me/password")
async def change_password(
    password_change: PasswordChangeRequest,
    current_user: User = Depends(get_current_user)
):
    """Change user password."""
    try:
        auth_service = get_auth_service()
        
        # Verify current password
        user = await auth_service.authenticate_user(current_user.username, password_change.current_password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        from app.repositories.auth import get_auth_repository
        from app.database.connection import get_db_session
        
        auth_repo = get_auth_repository()
        password_hash = auth_service._hash_password(password_change.new_password)
        
        async with get_db_session() as db:
            success = await auth_repo.update_user(
                db, current_user.id, {"password_hash": password_hash}
            )
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update password"
                )
        
        return {"message": "Password updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Password change failed")


@router.post("/api-keys", response_model=APIKeyResponse)
@require_permissions([Permissions.API_WRITE])
async def create_api_key(
    api_key_create: APIKeyCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new API key."""
    try:
        auth_service = get_auth_service()
        api_key = await auth_service.create_api_key(
            user_id=current_user.id,
            name=api_key_create.name,
            permissions=api_key_create.permissions,
            expires_at=api_key_create.expires_at
        )
        
        return APIKeyResponse.from_orm(api_key)
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="API key creation failed")


@router.get("/api-keys", response_model=List[APIKeyResponse])
@require_permissions([Permissions.API_READ])
async def list_api_keys(current_user: User = Depends(get_current_user)):
    """List user's API keys."""
    try:
        from app.repositories.auth import get_auth_repository
        from app.database.connection import get_db_session
        
        auth_repo = get_auth_repository()
        async with get_db_session() as db:
            api_keys = await auth_repo.get_user_api_keys(db, current_user.id)
        
        return [APIKeyResponse.from_orm(key) for key in api_keys]
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list API keys")


@router.delete("/api-keys/{api_key_id}")
@require_permissions([Permissions.API_WRITE])
async def revoke_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user)
):
    """Revoke an API key."""
    try:
        auth_service = get_auth_service()
        success = await auth_service.revoke_api_key(api_key_id, current_user.id)
        
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
        return {"message": "API key revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="API key revocation failed")


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_user_audit_logs(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Get user's audit logs."""
    try:
        auth_service = get_auth_service()
        logs = await auth_service.get_user_audit_logs(current_user.id, limit, offset)
        
        return [AuditLogResponse.from_orm(log) for log in logs]
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get audit logs")


@router.get("/security-events", response_model=List[AuditLogResponse])
@admin_required
async def get_security_events(
    limit: int = 100,
    offset: int = 0,
    action_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get security events (admin only)."""
    try:
        auth_service = get_auth_service()
        logs = await auth_service.get_security_events(limit, offset, action_filter)
        
        return [AuditLogResponse.from_orm(log) for log in logs]
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get security events")


@router.get("/users", response_model=List[UserResponse])
@admin_required
async def list_users(
    limit: int = 100,
    offset: int = 0,
    role_filter: Optional[str] = None,
    active_only: bool = True,
    current_user: User = Depends(get_current_user)
):
    """List users (admin only)."""
    try:
        from app.repositories.auth import get_auth_repository
        from app.database.connection import get_db_session
        
        auth_repo = get_auth_repository()
        async with get_db_session() as db:
            users = await auth_repo.list_users(db, limit, offset, role_filter, active_only)
        
        return [UserResponse.from_orm(user) for user in users]
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list users")


@router.put("/users/{user_id}/deactivate")
@admin_required
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Deactivate a user (admin only)."""
    try:
        from app.repositories.auth import get_auth_repository
        from app.database.connection import get_db_session
        
        auth_repo = get_auth_repository()
        async with get_db_session() as db:
            success = await auth_repo.deactivate_user(db, user_id)
        
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        return {"message": "User deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User deactivation failed")


@router.get("/permissions")
async def get_available_permissions():
    """Get list of available permissions."""
    from app.security import Permissions
    
    # Get all permission constants
    permissions = []
    for attr_name in dir(Permissions):
        if not attr_name.startswith('_'):
            attr_value = getattr(Permissions, attr_name)
            if isinstance(attr_value, str):
                permissions.append({
                    "name": attr_value,
                    "description": attr_name.replace('_', ' ').title()
                })
    
    return {"permissions": permissions}


@router.get("/roles")
async def get_available_roles():
    """Get list of available roles."""
    from app.security import Roles
    
    # Get all role constants
    roles = []
    for attr_name in dir(Roles):
        if not attr_name.startswith('_'):
            attr_value = getattr(Roles, attr_name)
            if isinstance(attr_value, str):
                roles.append({
                    "name": attr_value,
                    "description": attr_name.replace('_', ' ').title()
                })
    
    return {"roles": roles}


@router.get("/validate-token")
async def validate_token(current_user: User = Depends(get_current_user_or_api_key)):
    """Validate current token and return user info."""
    return {
        "valid": True,
        "user": UserResponse.from_orm(current_user),
        "timestamp": datetime.utcnow().isoformat()
    }