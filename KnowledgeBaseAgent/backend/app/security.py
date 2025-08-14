"""Security utilities and middleware."""

import re
import html
import logging
from typing import List, Optional, Dict, Any, Callable
from functools import wraps
from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.auth_service import get_auth_service, AuthenticationError, AuthorizationError
from app.models.auth import User, APIKey

logger = logging.getLogger(__name__)

# Security bearer for JWT tokens
security = HTTPBearer()


class SecurityMiddleware:
    """Security middleware for request validation and sanitization."""
    
    def __init__(self):
        self.max_request_size = 10 * 1024 * 1024  # 10MB
        self.rate_limit_requests = 1000  # per hour
        self.blocked_ips = set()
        self.suspicious_patterns = [
            r'<script[^>]*>.*?</script>',  # XSS
            r'javascript:',                # JavaScript URLs
            r'on\w+\s*=',                 # Event handlers
            r'union\s+select',             # SQL injection
            r'drop\s+table',               # SQL injection
            r'insert\s+into',              # SQL injection
            r'delete\s+from',              # SQL injection
        ]
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.suspicious_patterns]
    
    def validate_request_size(self, request: Request) -> bool:
        """Validate request size."""
        content_length = request.headers.get('content-length')
        if content_length and int(content_length) > self.max_request_size:
            return False
        return True
    
    def sanitize_input(self, data: Any) -> Any:
        """Sanitize input data to prevent XSS and injection attacks."""
        if isinstance(data, str):
            # HTML escape
            data = html.escape(data)
            
            # Check for suspicious patterns
            for pattern in self.compiled_patterns:
                if pattern.search(data):
                    logger.warning(f"Suspicious pattern detected in input: {data[:100]}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid input detected"
                    )
            
            return data
        
        elif isinstance(data, dict):
            return {key: self.sanitize_input(value) for key, value in data.items()}
        
        elif isinstance(data, list):
            return [self.sanitize_input(item) for item in data]
        
        else:
            return data
    
    def validate_ip_address(self, ip_address: str) -> bool:
        """Check if IP address is blocked."""
        return ip_address not in self.blocked_ips
    
    def block_ip(self, ip_address: str):
        """Block an IP address."""
        self.blocked_ips.add(ip_address)
        logger.warning(f"Blocked IP address: {ip_address}")


# Global security middleware instance
security_middleware = SecurityMiddleware()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Get current authenticated user from JWT token."""
    try:
        auth_service = get_auth_service()
        token_payload = await auth_service.verify_token(credentials.credentials)
        
        # Get user from database
        from app.repositories.auth import get_auth_repository
        from app.database.connection import get_db_session
        
        auth_repo = get_auth_repository()
        async with get_db_session() as db:
            user = await auth_repo.get_user_by_id(db, token_payload.user_id)
            
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive"
                )
            
            return user
            
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None."""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


async def get_api_key_user(request: Request) -> Optional[User]:
    """Get user from API key authentication."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return None
    
    try:
        auth_service = get_auth_service()
        api_key_record = await auth_service.verify_api_key(api_key)
        
        if not api_key_record:
            return None
        
        # Get user
        from app.repositories.auth import get_auth_repository
        from app.database.connection import get_db_session
        
        auth_repo = get_auth_repository()
        async with get_db_session() as db:
            user = await auth_repo.get_user_by_id(db, api_key_record.user_id)
            
            if not user or not user.is_active:
                return None
            
            # Store API key info in user object for permission checking
            user._api_key = api_key_record
            
            return user
            
    except Exception as e:
        logger.error(f"API key authentication error: {e}")
        return None


async def get_current_user_or_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """Get current user from JWT token or API key."""
    # Try JWT authentication first
    if credentials:
        try:
            return await get_current_user(credentials)
        except HTTPException:
            pass
    
    # Try API key authentication
    user = await get_api_key_user(request)
    if user:
        return user
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"}
    )


def require_permissions(permissions: List[str]):
    """Decorator to require specific permissions."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user from kwargs (injected by FastAPI)
            user = None
            for arg in args:
                if isinstance(arg, User):
                    user = arg
                    break
            
            if not user:
                for value in kwargs.values():
                    if isinstance(value, User):
                        user = value
                        break
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Check permissions
            auth_service = get_auth_service()
            
            # Get user permissions (from JWT token or API key)
            if hasattr(user, '_api_key') and user._api_key:
                # API key authentication
                api_key: APIKey = user._api_key
                user_permissions = api_key.permissions
            else:
                # JWT authentication
                user_permissions = await auth_service._get_user_permissions(user)
            
            # Check if user has required permissions
            for permission in permissions:
                if not auth_service.check_permission(user_permissions, permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission required: {permission}"
                    )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_roles(roles: List[str]):
    """Decorator to require specific roles."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user from kwargs (injected by FastAPI)
            user = None
            for arg in args:
                if isinstance(arg, User):
                    user = arg
                    break
            
            if not user:
                for value in kwargs.values():
                    if isinstance(value, User):
                        user = value
                        break
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Check roles
            auth_service = get_auth_service()
            
            for role in roles:
                if not auth_service.check_role(user.roles, role):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Role required: {role}"
                    )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def admin_required(func: Callable):
    """Decorator to require admin role."""
    return require_roles(["admin"])(func)


def sanitize_request_data(func: Callable):
    """Decorator to sanitize request data."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Sanitize all string arguments
        sanitized_kwargs = {}
        for key, value in kwargs.items():
            try:
                sanitized_kwargs[key] = security_middleware.sanitize_input(value)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error sanitizing input {key}: {e}")
                sanitized_kwargs[key] = value
        
        return await func(*args, **sanitized_kwargs)
    
    return wrapper


async def validate_request_security(request: Request):
    """Validate request for security issues."""
    # Check request size
    if not security_middleware.validate_request_size(request):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Request too large"
        )
    
    # Check IP address
    client_ip = request.client.host if request.client else "unknown"
    if not security_middleware.validate_ip_address(client_ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return True


# Permission constants
class Permissions:
    """Permission constants."""
    
    # Content permissions
    CONTENT_READ = "content:read"
    CONTENT_CREATE = "content:create"
    CONTENT_UPDATE = "content:update"
    CONTENT_DELETE = "content:delete"
    
    # Chat permissions
    CHAT_READ = "chat:read"
    CHAT_CREATE = "chat:create"
    CHAT_UPDATE = "chat:update"
    CHAT_DELETE = "chat:delete"
    
    # Search permissions
    SEARCH_READ = "search:read"
    SEARCH_CREATE = "search:create"
    
    # Agent permissions
    AGENT_READ = "agent:read"
    AGENT_CONTROL = "agent:control"
    AGENT_MONITOR = "agent:monitor"
    
    # Admin permissions
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"
    ADMIN_USERS = "admin:users"
    ADMIN_SYSTEM = "admin:system"
    
    # API permissions
    API_READ = "api:read"
    API_WRITE = "api:write"


# Role constants
class Roles:
    """Role constants."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    API_USER = "api_user"
    MODERATOR = "moderator"