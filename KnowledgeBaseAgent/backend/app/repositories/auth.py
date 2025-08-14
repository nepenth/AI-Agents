"""Authentication repository for database operations."""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, desc
from sqlalchemy.orm import selectinload

from app.models.auth import User, APIKey, AuditLog, Role, Permission, Session
from app.schemas.auth import UserCreate, APIKeyCreate, RoleCreate, PermissionCreate
from app.repositories.base import BaseRepository


class AuthRepository(BaseRepository[User]):
    """Repository for authentication operations."""
    
    def __init__(self):
        super().__init__(User)
    
    async def create_user(self, db: AsyncSession, user_create: UserCreate) -> User:
        """Create a new user."""
        user = User(
            id=str(uuid.uuid4()),
            username=user_create.username,
            email=user_create.email,
            password_hash=user_create.password_hash,
            roles=user_create.roles or ["user"],
            is_active=user_create.is_active,
            full_name=user_create.full_name,
            avatar_url=user_create.avatar_url
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return user
    
    async def get_user_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        """Get user by username."""
        result = await db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email."""
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_user_last_login(self, db: AsyncSession, user_id: str) -> bool:
        """Update user's last login timestamp."""
        result = await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.utcnow())
        )
        await db.commit()
        return result.rowcount > 0
    
    async def update_user(
        self, 
        db: AsyncSession, 
        user_id: str, 
        updates: Dict[str, Any]
    ) -> bool:
        """Update user information."""
        updates["updated_at"] = datetime.utcnow()
        
        result = await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(**updates)
        )
        await db.commit()
        return result.rowcount > 0
    
    async def deactivate_user(self, db: AsyncSession, user_id: str) -> bool:
        """Deactivate a user."""
        return await self.update_user(db, user_id, {"is_active": False})
    
    async def list_users(
        self,
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        role_filter: Optional[str] = None,
        active_only: bool = True
    ) -> List[User]:
        """List users with optional filtering."""
        query = select(User)
        
        if active_only:
            query = query.where(User.is_active == True)
        
        if role_filter:
            query = query.where(User.roles.contains([role_filter]))
        
        query = query.offset(offset).limit(limit).order_by(desc(User.created_at))
        
        result = await db.execute(query)
        return result.scalars().all()
    
    # API Key operations
    async def create_api_key(
        self,
        db: AsyncSession,
        user_id: str,
        name: str,
        key_hash: str,
        permissions: List[str],
        expires_at: Optional[datetime] = None
    ) -> APIKey:
        """Create a new API key."""
        api_key = APIKey(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            permissions=permissions,
            expires_at=expires_at
        )
        
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        
        return api_key
    
    async def get_user_api_keys(
        self, 
        db: AsyncSession, 
        user_id: str,
        active_only: bool = True
    ) -> List[APIKey]:
        """Get all API keys for a user."""
        query = select(APIKey).where(APIKey.user_id == user_id)
        
        if active_only:
            query = query.where(APIKey.is_active == True)
        
        query = query.order_by(desc(APIKey.created_at))
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_active_api_keys(self, db: AsyncSession) -> List[APIKey]:
        """Get all active API keys."""
        result = await db.execute(
            select(APIKey).where(
                and_(
                    APIKey.is_active == True,
                    or_(
                        APIKey.expires_at.is_(None),
                        APIKey.expires_at > datetime.utcnow()
                    )
                )
            )
        )
        return result.scalars().all()
    
    async def update_api_key_last_used(self, db: AsyncSession, api_key_id: str) -> bool:
        """Update API key last used timestamp."""
        result = await db.execute(
            update(APIKey)
            .where(APIKey.id == api_key_id)
            .values(
                last_used_at=datetime.utcnow(),
                usage_count=APIKey.usage_count + 1
            )
        )
        await db.commit()
        return result.rowcount > 0
    
    async def revoke_api_key(self, db: AsyncSession, api_key_id: str, user_id: str) -> bool:
        """Revoke an API key."""
        result = await db.execute(
            update(APIKey)
            .where(and_(APIKey.id == api_key_id, APIKey.user_id == user_id))
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        await db.commit()
        return result.rowcount > 0
    
    # Audit log operations
    async def create_audit_log(
        self,
        db: AsyncSession,
        action: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Create an audit log entry."""
        audit_log = AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(audit_log)
        await db.commit()
        await db.refresh(audit_log)
        
        return audit_log
    
    async def get_user_audit_logs(
        self,
        db: AsyncSession,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """Get audit logs for a specific user."""
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.created_at))
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_security_events(
        self,
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        action_filter: Optional[str] = None
    ) -> List[AuditLog]:
        """Get security events (all audit logs)."""
        query = select(AuditLog).options(selectinload(AuditLog.user))
        
        if action_filter:
            query = query.where(AuditLog.action.contains(action_filter))
        
        query = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    # Role operations
    async def create_role(self, db: AsyncSession, role_create: RoleCreate) -> Role:
        """Create a new role."""
        role = Role(
            id=str(uuid.uuid4()),
            name=role_create.name,
            description=role_create.description,
            permissions=role_create.permissions,
            is_active=role_create.is_active
        )
        
        db.add(role)
        await db.commit()
        await db.refresh(role)
        
        return role
    
    async def get_role_by_name(self, db: AsyncSession, name: str) -> Optional[Role]:
        """Get role by name."""
        result = await db.execute(
            select(Role).where(Role.name == name)
        )
        return result.scalar_one_or_none()
    
    async def list_roles(
        self,
        db: AsyncSession,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Role]:
        """List roles."""
        query = select(Role)
        
        if active_only:
            query = query.where(Role.is_active == True)
        
        query = query.order_by(Role.name).offset(offset).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def update_role(
        self,
        db: AsyncSession,
        role_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update role information."""
        updates["updated_at"] = datetime.utcnow()
        
        result = await db.execute(
            update(Role)
            .where(Role.id == role_id)
            .values(**updates)
        )
        await db.commit()
        return result.rowcount > 0
    
    # Permission operations
    async def create_permission(
        self, 
        db: AsyncSession, 
        permission_create: PermissionCreate
    ) -> Permission:
        """Create a new permission."""
        permission = Permission(
            id=str(uuid.uuid4()),
            name=permission_create.name,
            description=permission_create.description,
            resource=permission_create.resource,
            action=permission_create.action,
            is_active=permission_create.is_active
        )
        
        db.add(permission)
        await db.commit()
        await db.refresh(permission)
        
        return permission
    
    async def get_permission_by_name(self, db: AsyncSession, name: str) -> Optional[Permission]:
        """Get permission by name."""
        result = await db.execute(
            select(Permission).where(Permission.name == name)
        )
        return result.scalar_one_or_none()
    
    async def list_permissions(
        self,
        db: AsyncSession,
        resource_filter: Optional[str] = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Permission]:
        """List permissions."""
        query = select(Permission)
        
        if active_only:
            query = query.where(Permission.is_active == True)
        
        if resource_filter:
            query = query.where(Permission.resource == resource_filter)
        
        query = query.order_by(Permission.resource, Permission.action).offset(offset).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    # Session operations
    async def create_session(
        self,
        db: AsyncSession,
        user_id: str,
        session_token: str,
        refresh_token_hash: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Session:
        """Create a new session."""
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_token=session_token,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at or datetime.utcnow(),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        return session
    
    async def get_session_by_token(self, db: AsyncSession, session_token: str) -> Optional[Session]:
        """Get session by token."""
        result = await db.execute(
            select(Session).where(
                and_(
                    Session.session_token == session_token,
                    Session.is_active == True,
                    Session.expires_at > datetime.utcnow()
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def update_session_access(self, db: AsyncSession, session_id: str) -> bool:
        """Update session last accessed timestamp."""
        result = await db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(last_accessed_at=datetime.utcnow())
        )
        await db.commit()
        return result.rowcount > 0
    
    async def revoke_session(self, db: AsyncSession, session_id: str) -> bool:
        """Revoke a session."""
        result = await db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(is_active=False)
        )
        await db.commit()
        return result.rowcount > 0
    
    async def revoke_user_sessions(self, db: AsyncSession, user_id: str) -> int:
        """Revoke all sessions for a user."""
        result = await db.execute(
            update(Session)
            .where(Session.user_id == user_id)
            .values(is_active=False)
        )
        await db.commit()
        return result.rowcount
    
    async def cleanup_expired_sessions(self, db: AsyncSession) -> int:
        """Clean up expired sessions."""
        result = await db.execute(
            delete(Session).where(
                or_(
                    Session.expires_at < datetime.utcnow(),
                    Session.is_active == False
                )
            )
        )
        await db.commit()
        return result.rowcount


# Global repository instance
_auth_repository: Optional[AuthRepository] = None


def get_auth_repository() -> AuthRepository:
    """Get the global auth repository instance."""
    global _auth_repository
    if _auth_repository is None:
        _auth_repository = AuthRepository()
    return _auth_repository