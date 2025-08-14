"""Authentication service for JWT-based user authentication."""

import jwt
import bcrypt
import logging
import secrets
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from app.config import get_settings
from app.repositories.auth import get_auth_repository
from app.database.connection import get_db_session
from app.schemas.auth import UserCreate, UserLogin, TokenResponse
from app.models.auth import User, APIKey, AuditLog

logger = logging.getLogger(__name__)


@dataclass
class TokenPayload:
    """JWT token payload structure."""
    user_id: str
    username: str
    roles: List[str]
    permissions: List[str]
    exp: datetime
    iat: datetime
    jti: str  # JWT ID for token revocation


class AuthenticationError(Exception):
    """Authentication related errors."""
    pass


class AuthorizationError(Exception):
    """Authorization related errors."""
    pass


class AuthService:
    """Service for handling authentication and authorization."""
    
    def __init__(self):
        self.settings = get_settings()
        # Use SECRET_KEY from settings
        self.secret_key = self.settings.SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
        self.revoked_tokens = set()  # In production, use Redis or database
    
    async def register_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: Optional[List[str]] = None
    ) -> User:
        """Register a new user."""
        try:
            auth_repo = get_auth_repository()
            
            # Check if user already exists
            async with get_db_session() as db:
                existing_user = await auth_repo.get_user_by_username(db, username)
                if existing_user:
                    raise AuthenticationError("Username already exists")
                
                existing_email = await auth_repo.get_user_by_email(db, email)
                if existing_email:
                    raise AuthenticationError("Email already exists")
                
                # Hash password
                password_hash = self._hash_password(password)
                
                # Create user
                user_create = UserCreate(
                    username=username,
                    email=email,
                    password_hash=password_hash,
                    roles=roles or ["user"],
                    is_active=True
                )
                
                user = await auth_repo.create_user(db, user_create)
                
                # Log registration
                await self._log_audit_event(
                    user_id=user.id,
                    action="user_registration",
                    details={"username": username, "email": email}
                )
                
                logger.info(f"User registered: {username}")
                return user
                
        except Exception as e:
            logger.error(f"Failed to register user {username}: {e}")
            raise
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password."""
        try:
            auth_repo = get_auth_repository()
            
            async with get_db_session() as db:
                user = await auth_repo.get_user_by_username(db, username)
                
                if not user or not user.is_active:
                    await self._log_audit_event(
                        action="failed_login_attempt",
                        details={"username": username, "reason": "user_not_found_or_inactive"}
                    )
                    return None
                
                if not self._verify_password(password, user.password_hash):
                    await self._log_audit_event(
                        user_id=user.id,
                        action="failed_login_attempt",
                        details={"username": username, "reason": "invalid_password"}
                    )
                    return None
                
                # Update last login
                await auth_repo.update_user_last_login(db, user.id)
                
                await self._log_audit_event(
                    user_id=user.id,
                    action="successful_login",
                    details={"username": username}
                )
                
                logger.info(f"User authenticated: {username}")
                return user
                
        except Exception as e:
            logger.error(f"Failed to authenticate user {username}: {e}")
            return None
    
    async def create_access_token(self, user: User) -> str:
        """Create JWT access token for user."""
        try:
            now = datetime.utcnow()
            expire = now + timedelta(minutes=self.access_token_expire_minutes)
            
            # Get user permissions
            permissions = await self._get_user_permissions(user)
            
            payload = {
                "user_id": user.id,
                "username": user.username,
                "roles": user.roles,
                "permissions": permissions,
                "exp": expire,
                "iat": now,
                "jti": secrets.token_urlsafe(32),
                "type": "access"
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            logger.debug(f"Created access token for user: {user.username}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create access token for user {user.username}: {e}")
            raise
    
    async def create_refresh_token(self, user: User) -> str:
        """Create JWT refresh token for user."""
        try:
            now = datetime.utcnow()
            expire = now + timedelta(days=self.refresh_token_expire_days)
            
            payload = {
                "user_id": user.id,
                "username": user.username,
                "exp": expire,
                "iat": now,
                "jti": secrets.token_urlsafe(32),
                "type": "refresh"
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            logger.debug(f"Created refresh token for user: {user.username}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create refresh token for user {user.username}: {e}")
            raise
    
    async def verify_token(self, token: str) -> TokenPayload:
        """Verify and decode JWT token."""
        try:
            # Check if token is revoked
            if token in self.revoked_tokens:
                raise AuthenticationError("Token has been revoked")
            
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token type
            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")
            
            # Create token payload object
            token_payload = TokenPayload(
                user_id=payload["user_id"],
                username=payload["username"],
                roles=payload["roles"],
                permissions=payload["permissions"],
                exp=datetime.fromtimestamp(payload["exp"]),
                iat=datetime.fromtimestamp(payload["iat"]),
                jti=payload["jti"]
            )
            
            return token_payload
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid token")
        except Exception as e:
            logger.error(f"Failed to verify token: {e}")
            raise AuthenticationError("Token verification failed")
    
    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Create new access token using refresh token."""
        try:
            # Check if token is revoked
            if refresh_token in self.revoked_tokens:
                raise AuthenticationError("Refresh token has been revoked")
            
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token type
            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid token type")
            
            # Get user
            auth_repo = get_auth_repository()
            async with get_db_session() as db:
                user = await auth_repo.get_user_by_id(db, payload["user_id"])
                
                if not user or not user.is_active:
                    raise AuthenticationError("User not found or inactive")
                
                # Create new tokens
                new_access_token = await self.create_access_token(user)
                new_refresh_token = await self.create_refresh_token(user)
                
                # Revoke old refresh token
                self.revoked_tokens.add(refresh_token)
                
                await self._log_audit_event(
                    user_id=user.id,
                    action="token_refresh",
                    details={"username": user.username}
                )
                
                return TokenResponse(
                    access_token=new_access_token,
                    refresh_token=new_refresh_token,
                    token_type="bearer",
                    expires_in=self.access_token_expire_minutes * 60
                )
                
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Refresh token has expired")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid refresh token")
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            raise
    
    async def revoke_token(self, token: str, user_id: str):
        """Revoke a JWT token."""
        try:
            # Decode token to get JTI
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"verify_exp": False}  # Allow expired tokens for revocation
            )
            
            # Add to revoked tokens
            self.revoked_tokens.add(token)
            
            await self._log_audit_event(
                user_id=user_id,
                action="token_revocation",
                details={"jti": payload.get("jti")}
            )
            
            logger.info(f"Token revoked for user: {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            raise
    
    async def create_api_key(
        self,
        user_id: str,
        name: str,
        permissions: List[str],
        expires_at: Optional[datetime] = None
    ) -> APIKey:
        """Create API key for user."""
        try:
            auth_repo = get_auth_repository()
            
            # Generate secure API key
            key = f"ak_{secrets.token_urlsafe(32)}"
            key_hash = self._hash_password(key)
            
            async with get_db_session() as db:
                api_key = await auth_repo.create_api_key(
                    db=db,
                    user_id=user_id,
                    name=name,
                    key_hash=key_hash,
                    permissions=permissions,
                    expires_at=expires_at
                )
                
                await self._log_audit_event(
                    user_id=user_id,
                    action="api_key_creation",
                    details={"api_key_name": name, "permissions": permissions}
                )
                
                # Return API key with the actual key (only time it's shown)
                api_key.key = key  # Temporarily add for response
                
                logger.info(f"API key created for user {user_id}: {name}")
                return api_key
                
        except Exception as e:
            logger.error(f"Failed to create API key for user {user_id}: {e}")
            raise
    
    async def verify_api_key(self, api_key: str) -> Optional[APIKey]:
        """Verify API key and return associated key info."""
        try:
            if not api_key.startswith("ak_"):
                return None
            
            auth_repo = get_auth_repository()
            
            async with get_db_session() as db:
                # Get all active API keys (in production, optimize this)
                api_keys = await auth_repo.get_active_api_keys(db)
                
                for key_record in api_keys:
                    if self._verify_password(api_key, key_record.key_hash):
                        # Check expiration
                        if key_record.expires_at and key_record.expires_at < datetime.utcnow():
                            continue
                        
                        # Update last used
                        await auth_repo.update_api_key_last_used(db, key_record.id)
                        
                        return key_record
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to verify API key: {e}")
            return None
    
    async def revoke_api_key(self, api_key_id: str, user_id: str):
        """Revoke an API key."""
        try:
            auth_repo = get_auth_repository()
            
            async with get_db_session() as db:
                success = await auth_repo.revoke_api_key(db, api_key_id, user_id)
                
                if success:
                    await self._log_audit_event(
                        user_id=user_id,
                        action="api_key_revocation",
                        details={"api_key_id": api_key_id}
                    )
                    
                    logger.info(f"API key revoked: {api_key_id}")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to revoke API key {api_key_id}: {e}")
            raise
    
    def check_permission(self, user_permissions: List[str], required_permission: str) -> bool:
        """Check if user has required permission."""
        # Admin role has all permissions
        if "admin" in user_permissions:
            return True
        
        # Check exact permission match
        if required_permission in user_permissions:
            return True
        
        # Check wildcard permissions
        for permission in user_permissions:
            if permission.endswith("*"):
                prefix = permission[:-1]
                if required_permission.startswith(prefix):
                    return True
        
        return False
    
    def check_role(self, user_roles: List[str], required_role: str) -> bool:
        """Check if user has required role."""
        return required_role in user_roles
    
    async def _get_user_permissions(self, user: User) -> List[str]:
        """Get all permissions for user based on roles."""
        # Define role-based permissions
        role_permissions = {
            "admin": ["*"],  # Admin has all permissions
            "user": [
                "content:read",
                "content:create",
                "chat:read",
                "chat:create",
                "search:read"
            ],
            "viewer": [
                "content:read",
                "chat:read",
                "search:read"
            ],
            "api_user": [
                "api:read",
                "api:write",
                "content:read",
                "content:create"
            ]
        }
        
        permissions = set()
        for role in user.roles:
            if role in role_permissions:
                permissions.update(role_permissions[role])
        
        return list(permissions)
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception:
            return False
    
    async def _log_audit_event(
        self,
        action: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log security audit event."""
        try:
            auth_repo = get_auth_repository()
            
            async with get_db_session() as db:
                await auth_repo.create_audit_log(
                    db=db,
                    user_id=user_id,
                    action=action,
                    details=details or {},
                    ip_address="127.0.0.1",  # Would get from request context
                    user_agent="Unknown"     # Would get from request context
                )
                
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
    
    async def get_user_audit_logs(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """Get audit logs for a user."""
        try:
            auth_repo = get_auth_repository()
            
            async with get_db_session() as db:
                logs = await auth_repo.get_user_audit_logs(db, user_id, limit, offset)
                return logs
                
        except Exception as e:
            logger.error(f"Failed to get audit logs for user {user_id}: {e}")
            return []
    
    async def get_security_events(
        self,
        limit: int = 100,
        offset: int = 0,
        action_filter: Optional[str] = None
    ) -> List[AuditLog]:
        """Get security events (admin only)."""
        try:
            auth_repo = get_auth_repository()
            
            async with get_db_session() as db:
                logs = await auth_repo.get_security_events(db, limit, offset, action_filter)
                return logs
                
        except Exception as e:
            logger.error(f"Failed to get security events: {e}")
            return []


# Global service instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get the global auth service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service