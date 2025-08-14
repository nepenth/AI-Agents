"""Tests for authentication and security system."""

import pytest
import jwt
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from fastapi import HTTPException

from app.services.auth_service import AuthService, AuthenticationError, AuthorizationError
from app.models.auth import User, APIKey
from app.security import SecurityMiddleware, get_current_user, require_permissions, Permissions
from app.schemas.auth import UserCreate


@pytest.fixture
def auth_service():
    """Create auth service for testing."""
    return AuthService()


@pytest.fixture
def security_middleware():
    """Create security middleware for testing."""
    return SecurityMiddleware()


@pytest.fixture
def sample_user():
    """Create sample user for testing."""
    return User(
        id="user-123",
        username="testuser",
        email="test@example.com",
        password_hash="$2b$12$hashed_password",
        roles=["user"],
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


class TestAuthService:
    """Test cases for AuthService."""
    
    @pytest.mark.asyncio
    async def test_register_user_success(self, auth_service):
        """Test successful user registration."""
        with patch('app.services.auth_service.get_auth_repository') as mock_repo:
            mock_auth_repo = Mock()
            mock_repo.return_value = mock_auth_repo
            
            # Mock database operations
            mock_auth_repo.get_user_by_username.return_value = None
            mock_auth_repo.get_user_by_email.return_value = None
            mock_auth_repo.create_user.return_value = User(
                id="user-123",
                username="newuser",
                email="new@example.com",
                password_hash="hashed",
                roles=["user"],
                is_active=True
            )
            
            with patch('app.services.auth_service.get_db_session'):
                with patch.object(auth_service, '_log_audit_event') as mock_audit:
                    mock_audit.return_value = None
                    
                    user = await auth_service.register_user(
                        username="newuser",
                        email="new@example.com",
                        password="password123"
                    )
                    
                    assert user.username == "newuser"
                    assert user.email == "new@example.com"
                    assert user.is_active is True
                    mock_audit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_user_duplicate_username(self, auth_service):
        """Test user registration with duplicate username."""
        with patch('app.services.auth_service.get_auth_repository') as mock_repo:
            mock_auth_repo = Mock()
            mock_repo.return_value = mock_auth_repo
            
            # Mock existing user
            mock_auth_repo.get_user_by_username.return_value = User(
                id="existing-user",
                username="existinguser",
                email="existing@example.com"
            )
            
            with patch('app.services.auth_service.get_db_session'):
                with pytest.raises(AuthenticationError, match="Username already exists"):
                    await auth_service.register_user(
                        username="existinguser",
                        email="new@example.com",
                        password="password123"
                    )
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, auth_service, sample_user):
        """Test successful user authentication."""
        with patch('app.services.auth_service.get_auth_repository') as mock_repo:
            mock_auth_repo = Mock()
            mock_repo.return_value = mock_auth_repo
            mock_auth_repo.get_user_by_username.return_value = sample_user
            mock_auth_repo.update_user_last_login.return_value = True
            
            with patch('app.services.auth_service.get_db_session'):
                with patch.object(auth_service, '_verify_password', return_value=True):
                    with patch.object(auth_service, '_log_audit_event') as mock_audit:
                        mock_audit.return_value = None
                        
                        user = await auth_service.authenticate_user("testuser", "password123")
                        
                        assert user is not None
                        assert user.username == "testuser"
                        mock_audit.assert_called()
    
    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_password(self, auth_service, sample_user):
        """Test authentication with invalid password."""
        with patch('app.services.auth_service.get_auth_repository') as mock_repo:
            mock_auth_repo = Mock()
            mock_repo.return_value = mock_auth_repo
            mock_auth_repo.get_user_by_username.return_value = sample_user
            
            with patch('app.services.auth_service.get_db_session'):
                with patch.object(auth_service, '_verify_password', return_value=False):
                    with patch.object(auth_service, '_log_audit_event') as mock_audit:
                        mock_audit.return_value = None
                        
                        user = await auth_service.authenticate_user("testuser", "wrongpassword")
                        
                        assert user is None
                        mock_audit.assert_called()
    
    @pytest.mark.asyncio
    async def test_create_access_token(self, auth_service, sample_user):
        """Test access token creation."""
        with patch.object(auth_service, '_get_user_permissions', return_value=["content:read", "chat:read"]):
            token = await auth_service.create_access_token(sample_user)
            
            assert token is not None
            
            # Decode token to verify contents
            payload = jwt.decode(token, auth_service.secret_key, algorithms=[auth_service.algorithm])
            
            assert payload["user_id"] == sample_user.id
            assert payload["username"] == sample_user.username
            assert payload["roles"] == sample_user.roles
            assert payload["type"] == "access"
            assert "permissions" in payload
            assert "exp" in payload
            assert "jti" in payload
    
    @pytest.mark.asyncio
    async def test_create_refresh_token(self, auth_service, sample_user):
        """Test refresh token creation."""
        token = await auth_service.create_refresh_token(sample_user)
        
        assert token is not None
        
        # Decode token to verify contents
        payload = jwt.decode(token, auth_service.secret_key, algorithms=[auth_service.algorithm])
        
        assert payload["user_id"] == sample_user.id
        assert payload["username"] == sample_user.username
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "jti" in payload
    
    @pytest.mark.asyncio
    async def test_verify_token_success(self, auth_service, sample_user):
        """Test successful token verification."""
        with patch.object(auth_service, '_get_user_permissions', return_value=["content:read"]):
            token = await auth_service.create_access_token(sample_user)
            
            token_payload = await auth_service.verify_token(token)
            
            assert token_payload.user_id == sample_user.id
            assert token_payload.username == sample_user.username
            assert token_payload.roles == sample_user.roles
    
    @pytest.mark.asyncio
    async def test_verify_token_expired(self, auth_service):
        """Test verification of expired token."""
        # Create expired token
        now = datetime.utcnow()
        expired_payload = {
            "user_id": "user-123",
            "username": "testuser",
            "roles": ["user"],
            "permissions": ["content:read"],
            "exp": now - timedelta(minutes=1),  # Expired
            "iat": now - timedelta(minutes=31),
            "jti": "test-jti",
            "type": "access"
        }
        
        expired_token = jwt.encode(expired_payload, auth_service.secret_key, algorithm=auth_service.algorithm)
        
        with pytest.raises(AuthenticationError, match="Token has expired"):
            await auth_service.verify_token(expired_token)
    
    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, auth_service):
        """Test verification of invalid token."""
        invalid_token = "invalid.token.here"
        
        with pytest.raises(AuthenticationError, match="Invalid token"):
            await auth_service.verify_token(invalid_token)
    
    @pytest.mark.asyncio
    async def test_verify_token_revoked(self, auth_service, sample_user):
        """Test verification of revoked token."""
        with patch.object(auth_service, '_get_user_permissions', return_value=["content:read"]):
            token = await auth_service.create_access_token(sample_user)
            
            # Revoke token
            auth_service.revoked_tokens.add(token)
            
            with pytest.raises(AuthenticationError, match="Token has been revoked"):
                await auth_service.verify_token(token)
    
    @pytest.mark.asyncio
    async def test_refresh_access_token(self, auth_service, sample_user):
        """Test refreshing access token."""
        refresh_token = await auth_service.create_refresh_token(sample_user)
        
        with patch('app.services.auth_service.get_auth_repository') as mock_repo:
            mock_auth_repo = Mock()
            mock_repo.return_value = mock_auth_repo
            mock_auth_repo.get_user_by_id.return_value = sample_user
            
            with patch('app.services.auth_service.get_db_session'):
                with patch.object(auth_service, '_log_audit_event') as mock_audit:
                    mock_audit.return_value = None
                    
                    token_response = await auth_service.refresh_access_token(refresh_token)
                    
                    assert token_response.access_token is not None
                    assert token_response.refresh_token is not None
                    assert token_response.token_type == "bearer"
                    assert refresh_token in auth_service.revoked_tokens
    
    @pytest.mark.asyncio
    async def test_create_api_key(self, auth_service):
        """Test API key creation."""
        with patch('app.services.auth_service.get_auth_repository') as mock_repo:
            mock_auth_repo = Mock()
            mock_repo.return_value = mock_auth_repo
            
            api_key_mock = APIKey(
                id="key-123",
                user_id="user-123",
                name="Test Key",
                key_hash="hashed_key",
                permissions=["api:read", "api:write"],
                is_active=True
            )
            mock_auth_repo.create_api_key.return_value = api_key_mock
            
            with patch('app.services.auth_service.get_db_session'):
                with patch.object(auth_service, '_log_audit_event') as mock_audit:
                    mock_audit.return_value = None
                    
                    api_key = await auth_service.create_api_key(
                        user_id="user-123",
                        name="Test Key",
                        permissions=["api:read", "api:write"]
                    )
                    
                    assert api_key.name == "Test Key"
                    assert api_key.permissions == ["api:read", "api:write"]
                    assert hasattr(api_key, 'key')  # Actual key should be present
                    assert api_key.key.startswith("ak_")
    
    @pytest.mark.asyncio
    async def test_verify_api_key_success(self, auth_service):
        """Test successful API key verification."""
        api_key_record = APIKey(
            id="key-123",
            user_id="user-123",
            name="Test Key",
            key_hash="$2b$12$hashed_key",
            permissions=["api:read"],
            is_active=True,
            expires_at=None
        )
        
        with patch('app.services.auth_service.get_auth_repository') as mock_repo:
            mock_auth_repo = Mock()
            mock_repo.return_value = mock_auth_repo
            mock_auth_repo.get_active_api_keys.return_value = [api_key_record]
            mock_auth_repo.update_api_key_last_used.return_value = True
            
            with patch('app.services.auth_service.get_db_session'):
                with patch.object(auth_service, '_verify_password', return_value=True):
                    result = await auth_service.verify_api_key("ak_test_key")
                    
                    assert result is not None
                    assert result.id == "key-123"
    
    @pytest.mark.asyncio
    async def test_verify_api_key_invalid_format(self, auth_service):
        """Test API key verification with invalid format."""
        result = await auth_service.verify_api_key("invalid_key_format")
        assert result is None
    
    def test_check_permission_exact_match(self, auth_service):
        """Test permission checking with exact match."""
        user_permissions = ["content:read", "content:write", "chat:read"]
        
        assert auth_service.check_permission(user_permissions, "content:read") is True
        assert auth_service.check_permission(user_permissions, "content:delete") is False
    
    def test_check_permission_wildcard(self, auth_service):
        """Test permission checking with wildcard."""
        user_permissions = ["content:*", "admin"]
        
        assert auth_service.check_permission(user_permissions, "content:read") is True
        assert auth_service.check_permission(user_permissions, "content:write") is True
        assert auth_service.check_permission(user_permissions, "content:delete") is True
        assert auth_service.check_permission(user_permissions, "chat:read") is False
    
    def test_check_permission_admin(self, auth_service):
        """Test permission checking with admin role."""
        user_permissions = ["admin"]
        
        assert auth_service.check_permission(user_permissions, "content:read") is True
        assert auth_service.check_permission(user_permissions, "admin:system") is True
        assert auth_service.check_permission(user_permissions, "any:permission") is True
    
    def test_check_role(self, auth_service):
        """Test role checking."""
        user_roles = ["user", "moderator"]
        
        assert auth_service.check_role(user_roles, "user") is True
        assert auth_service.check_role(user_roles, "moderator") is True
        assert auth_service.check_role(user_roles, "admin") is False
    
    def test_hash_and_verify_password(self, auth_service):
        """Test password hashing and verification."""
        password = "test_password_123"
        
        # Hash password
        password_hash = auth_service._hash_password(password)
        
        assert password_hash != password
        assert len(password_hash) > 50  # bcrypt hashes are long
        
        # Verify correct password
        assert auth_service._verify_password(password, password_hash) is True
        
        # Verify incorrect password
        assert auth_service._verify_password("wrong_password", password_hash) is False


class TestSecurityMiddleware:
    """Test cases for SecurityMiddleware."""
    
    def test_sanitize_input_string(self, security_middleware):
        """Test input sanitization for strings."""
        # Safe input
        safe_input = "Hello world"
        result = security_middleware.sanitize_input(safe_input)
        assert result == "Hello world"
        
        # HTML characters
        html_input = "<div>Hello</div>"
        result = security_middleware.sanitize_input(html_input)
        assert result == "&lt;div&gt;Hello&lt;/div&gt;"
    
    def test_sanitize_input_suspicious_patterns(self, security_middleware):
        """Test input sanitization with suspicious patterns."""
        # XSS attempt
        with pytest.raises(HTTPException):
            security_middleware.sanitize_input("<script>alert('xss')</script>")
        
        # SQL injection attempt
        with pytest.raises(HTTPException):
            security_middleware.sanitize_input("'; DROP TABLE users; --")
        
        # JavaScript URL
        with pytest.raises(HTTPException):
            security_middleware.sanitize_input("javascript:alert('xss')")
    
    def test_sanitize_input_dict(self, security_middleware):
        """Test input sanitization for dictionaries."""
        input_dict = {
            "name": "John Doe",
            "description": "<p>Safe HTML</p>",
            "nested": {
                "value": "test"
            }
        }
        
        result = security_middleware.sanitize_input(input_dict)
        
        assert result["name"] == "John Doe"
        assert result["description"] == "&lt;p&gt;Safe HTML&lt;/p&gt;"
        assert result["nested"]["value"] == "test"
    
    def test_sanitize_input_list(self, security_middleware):
        """Test input sanitization for lists."""
        input_list = ["safe", "<script>", {"key": "value"}]
        
        with pytest.raises(HTTPException):
            security_middleware.sanitize_input(input_list)
    
    def test_validate_ip_address(self, security_middleware):
        """Test IP address validation."""
        # Valid IP
        assert security_middleware.validate_ip_address("192.168.1.1") is True
        
        # Block IP and test
        security_middleware.block_ip("192.168.1.100")
        assert security_middleware.validate_ip_address("192.168.1.100") is False
    
    def test_validate_request_size(self, security_middleware):
        """Test request size validation."""
        # Mock request with small size
        mock_request = Mock()
        mock_request.headers = {"content-length": "1000"}
        
        assert security_middleware.validate_request_size(mock_request) is True
        
        # Mock request with large size
        mock_request.headers = {"content-length": str(20 * 1024 * 1024)}  # 20MB
        
        assert security_middleware.validate_request_size(mock_request) is False


class TestSecurityDecorators:
    """Test cases for security decorators."""
    
    @pytest.mark.asyncio
    async def test_require_permissions_success(self):
        """Test require_permissions decorator with valid permissions."""
        @require_permissions([Permissions.CONTENT_READ])
        async def test_function(user: User):
            return {"message": "success"}
        
        # Mock user with required permission
        mock_user = Mock(spec=User)
        mock_user.roles = ["user"]
        
        with patch('app.security.get_auth_service') as mock_auth_service:
            mock_service = Mock()
            mock_auth_service.return_value = mock_service
            mock_service._get_user_permissions.return_value = [Permissions.CONTENT_READ]
            mock_service.check_permission.return_value = True
            
            result = await test_function(mock_user)
            assert result["message"] == "success"
    
    @pytest.mark.asyncio
    async def test_require_permissions_failure(self):
        """Test require_permissions decorator with insufficient permissions."""
        @require_permissions([Permissions.ADMIN_SYSTEM])
        async def test_function(user: User):
            return {"message": "success"}
        
        # Mock user without required permission
        mock_user = Mock(spec=User)
        mock_user.roles = ["user"]
        
        with patch('app.security.get_auth_service') as mock_auth_service:
            mock_service = Mock()
            mock_auth_service.return_value = mock_service
            mock_service._get_user_permissions.return_value = [Permissions.CONTENT_READ]
            mock_service.check_permission.return_value = False
            
            with pytest.raises(HTTPException) as exc_info:
                await test_function(mock_user)
            
            assert exc_info.value.status_code == 403
            assert "Permission required" in str(exc_info.value.detail)


class TestAPIKeyModel:
    """Test cases for APIKey model."""
    
    def test_api_key_has_permission(self):
        """Test API key permission checking."""
        api_key = APIKey(
            id="key-123",
            user_id="user-123",
            name="Test Key",
            key_hash="hash",
            permissions=["content:read", "content:write", "api:*"]
        )
        
        # Exact match
        assert api_key.has_permission("content:read") is True
        assert api_key.has_permission("content:write") is True
        
        # Wildcard match
        assert api_key.has_permission("api:read") is True
        assert api_key.has_permission("api:write") is True
        
        # No match
        assert api_key.has_permission("admin:system") is False
    
    def test_api_key_is_expired(self):
        """Test API key expiration checking."""
        # Non-expiring key
        api_key = APIKey(
            id="key-123",
            user_id="user-123",
            name="Test Key",
            key_hash="hash",
            permissions=["api:read"],
            expires_at=None
        )
        assert api_key.is_expired() is False
        
        # Expired key
        api_key.expires_at = datetime.utcnow() - timedelta(days=1)
        assert api_key.is_expired() is True
        
        # Future expiration
        api_key.expires_at = datetime.utcnow() + timedelta(days=1)
        assert api_key.is_expired() is False


class TestUserModel:
    """Test cases for User model."""
    
    def test_user_has_role(self, sample_user):
        """Test user role checking."""
        sample_user.roles = ["user", "moderator"]
        
        assert sample_user.has_role("user") is True
        assert sample_user.has_role("moderator") is True
        assert sample_user.has_role("admin") is False
    
    def test_user_has_any_role(self, sample_user):
        """Test user multiple role checking."""
        sample_user.roles = ["user", "moderator"]
        
        assert sample_user.has_any_role(["admin", "user"]) is True
        assert sample_user.has_any_role(["admin", "superuser"]) is False
        assert sample_user.has_any_role(["user", "moderator"]) is True
    
    def test_user_to_dict(self, sample_user):
        """Test user dictionary conversion."""
        user_dict = sample_user.to_dict()
        
        assert user_dict["id"] == sample_user.id
        assert user_dict["username"] == sample_user.username
        assert user_dict["email"] == sample_user.email
        assert user_dict["roles"] == sample_user.roles
        assert user_dict["is_active"] == sample_user.is_active
        assert "password_hash" not in user_dict  # Should not include sensitive data