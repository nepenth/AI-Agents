"""Authentication and authorization schemas."""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=500)


class UserCreate(UserBase):
    """Schema for creating a user."""
    password: str = Field(..., min_length=8, max_length=128)
    password_hash: Optional[str] = None  # Set internally
    roles: Optional[List[str]] = Field(default=["user"])
    is_active: bool = Field(default=True)


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(UserBase):
    """Schema for user response."""
    id: str
    roles: List[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenPayload(BaseModel):
    """Schema for token payload."""
    user_id: str
    username: str
    roles: List[str]
    permissions: List[str]
    exp: datetime
    iat: datetime
    jti: str


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""
    refresh_token: str


class APIKeyCreate(BaseModel):
    """Schema for creating an API key."""
    name: str = Field(..., min_length=1, max_length=100)
    permissions: List[str] = Field(..., min_items=1)
    expires_at: Optional[datetime] = None


class APIKeyResponse(BaseModel):
    """Schema for API key response."""
    id: str
    name: str
    key: Optional[str] = None  # Only included when first created
    permissions: List[str]
    is_active: bool
    last_used_at: Optional[datetime] = None
    usage_count: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""
    id: str
    user_id: Optional[str] = None
    action: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    """Schema for creating a role."""
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    is_active: bool = Field(default=True)


class RoleUpdate(BaseModel):
    """Schema for updating a role."""
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


class RoleResponse(BaseModel):
    """Schema for role response."""
    id: str
    name: str
    description: Optional[str] = None
    permissions: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PermissionCreate(BaseModel):
    """Schema for creating a permission."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    resource: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=50)
    is_active: bool = Field(default=True)


class PermissionResponse(BaseModel):
    """Schema for permission response."""
    id: str
    name: str
    description: Optional[str] = None
    resource: str
    action: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PasswordChangeRequest(BaseModel):
    """Schema for password change request."""
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class SessionResponse(BaseModel):
    """Schema for session response."""
    id: str
    user_id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool
    expires_at: datetime
    created_at: datetime
    last_accessed_at: datetime
    
    class Config:
        from_attributes = True