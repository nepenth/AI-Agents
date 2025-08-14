# Security Guidelines

This document outlines comprehensive security guidelines for the AI Agent Backend system.

## Authentication and Authorization

### 1. JWT Token Management

**Token Structure:**
```python
# Access Token (30 minutes)
{
    "user_id": "user-123",
    "username": "john_doe",
    "roles": ["user", "moderator"],
    "permissions": ["content:read", "content:write"],
    "exp": 1640995200,
    "iat": 1640993400,
    "jti": "unique-token-id",
    "type": "access"
}

# Refresh Token (7 days)
{
    "user_id": "user-123",
    "username": "john_doe",
    "exp": 1641600000,
    "iat": 1640993400,
    "jti": "unique-refresh-id",
    "type": "refresh"
}
```

**Token Security Best Practices:**
- Use strong secret keys (minimum 256 bits)
- Implement token rotation on refresh
- Maintain token revocation list
- Set appropriate expiration times
- Include JTI (JWT ID) for token tracking

### 2. API Key Management

**API Key Format:**
```
ak_1234567890abcdef1234567890abcdef
```

**API Key Security:**
```python
class APIKeyService:
    def generate_api_key(self) -> str:
        # Generate cryptographically secure API key
        key = f"ak_{secrets.token_urlsafe(32)}"
        return key
    
    def hash_api_key(self, key: str) -> str:
        # Hash API key for storage
        return bcrypt.hashpw(key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_api_key(self, key: str, hash: str) -> bool:
        # Verify API key against hash
        return bcrypt.checkpw(key.encode('utf-8'), hash.encode('utf-8'))
```

**API Key Best Practices:**
- Store only hashed versions in database
- Implement key rotation policies
- Set expiration dates for keys
- Track key usage and last access
- Allow users to revoke keys

### 3. Role-Based Access Control (RBAC)

**Permission System:**
```python
class Permissions:
    # Content permissions
    CONTENT_READ = "content:read"
    CONTENT_CREATE = "content:create"
    CONTENT_UPDATE = "content:update"
    CONTENT_DELETE = "content:delete"
    
    # Admin permissions
    ADMIN_USERS = "admin:users"
    ADMIN_SYSTEM = "admin:system"
    
    # Wildcard permissions
    ADMIN_ALL = "admin:*"
    CONTENT_ALL = "content:*"

# Role definitions
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions
    "moderator": ["content:*", "chat:*"],
    "user": ["content:read", "content:create", "chat:read", "chat:create"],
    "viewer": ["content:read", "chat:read"]
}
```

**Authorization Decorators:**
```python
@require_permissions([Permissions.CONTENT_CREATE])
async def create_content(current_user: User = Depends(get_current_user)):
    pass

@admin_required
async def admin_operation(current_user: User = Depends(get_current_user)):
    pass

@require_roles(["moderator", "admin"])
async def moderate_content(current_user: User = Depends(get_current_user)):
    pass
```

## Input Validation and Sanitization

### 1. Request Validation

**Pydantic Models with Validation:**
```python
class ContentCreateRequest(BaseModel):
    title: str = Field(
        ..., 
        min_length=1, 
        max_length=500,
        regex=r'^[a-zA-Z0-9\s\-_.,!?]+$'  # Allow safe characters only
    )
    content: str = Field(..., min_length=1, max_length=1000000)
    source_url: Optional[str] = Field(
        default=None,
        regex=r'^https?://[^\s<>"{}|\\^`\[\]]+$'  # Validate URL format
    )
    tags: List[str] = Field(
        default_factory=list,
        max_items=10,
        description="Content tags"
    )
    
    @validator('tags')
    def validate_tags(cls, v):
        # Sanitize and validate tags
        sanitized_tags = []
        for tag in v:
            # Remove HTML and dangerous characters
            clean_tag = re.sub(r'[<>"\']', '', tag.strip())
            if len(clean_tag) > 0 and len(clean_tag) <= 50:
                sanitized_tags.append(clean_tag)
        return sanitized_tags[:10]  # Limit to 10 tags
```

### 1.1 Model Configuration Validation

Validate model configuration updates and per-run overrides:

```python
class PhaseModelSelector(BaseModel):
    backend: Literal['ollama','localai','openai']
    model: constr(strip_whitespace=True, min_length=1, max_length=200)
    params: Dict[str, Union[int, float, str, bool]] = Field(default_factory=dict)

    @validator('params')
    def validate_params(cls, v):
        allowed = {"temperature", "top_p", "max_tokens"}
        for k in v.keys():
            if k not in allowed:
                raise ValueError(f"Unsupported param: {k}")
        return v
```

Rules:
- Only authenticated users can read available models; only admins can update configuration
- Reject models that fail capability checks for the specified phase
- Rate limit configuration updates to prevent abuse
- Sanitize strings to avoid log/HTML injection

### 2. Input Sanitization

**HTML Sanitization:**
```python
import bleach
from markupsafe import Markup

class ContentSanitizer:
    ALLOWED_TAGS = [
        'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'blockquote', 'code', 'pre'
    ]
    
    ALLOWED_ATTRIBUTES = {
        '*': ['class'],
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'width', 'height']
    }
    
    def sanitize_html(self, content: str) -> str:
        """Sanitize HTML content to prevent XSS."""
        return bleach.clean(
            content,
            tags=self.ALLOWED_TAGS,
            attributes=self.ALLOWED_ATTRIBUTES,
            strip=True
        )
    
    def sanitize_text(self, text: str) -> str:
        """Sanitize plain text input."""
        # Remove null bytes and control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Escape HTML entities
        return html.escape(text)
```

**SQL Injection Prevention:**
```python
# Always use parameterized queries with SQLAlchemy
async def get_content_by_title(db: AsyncSession, title: str) -> List[ContentItem]:
    # GOOD: Parameterized query
    result = await db.execute(
        select(ContentItem).where(ContentItem.title == title)
    )
    return result.scalars().all()

# NEVER do this (vulnerable to SQL injection)
# query = f"SELECT * FROM content WHERE title = '{title}'"
```

### 3. File Upload Security

**File Validation:**
```python
class FileUploadValidator:
    ALLOWED_EXTENSIONS = {'.txt', '.md', '.json', '.csv', '.pdf'}
    ALLOWED_MIME_TYPES = {
        'text/plain', 'text/markdown', 'application/json',
        'text/csv', 'application/pdf'
    }
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    def validate_file(self, file: UploadFile) -> None:
        # Check file size
        if file.size > self.MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        
        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail="File type not allowed")
        
        # Check MIME type
        if file.content_type not in self.ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=415, detail="MIME type not allowed")
        
        # Scan for malware (integrate with antivirus)
        self.scan_for_malware(file)
    
    def scan_for_malware(self, file: UploadFile) -> None:
        # Integrate with antivirus scanning service
        # This is a placeholder for actual implementation
        pass
```

## Data Protection and Privacy

### 1. Data Encryption

**Encryption at Rest:**
```python
from cryptography.fernet import Fernet

class DataEncryption:
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data before storing."""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data after retrieving."""
        return self.cipher.decrypt(encrypted_data.encode()).decode()

# Database model with encrypted fields
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    username = Column(String, nullable=False)
    email_encrypted = Column(String, nullable=False)  # Encrypted email
    
    @property
    def email(self) -> str:
        return encryption_service.decrypt_sensitive_data(self.email_encrypted)
    
    @email.setter
    def email(self, value: str) -> None:
        self.email_encrypted = encryption_service.encrypt_sensitive_data(value)
```

**Encryption in Transit:**
```python
# Force HTTPS in production
@app.middleware("http")
async def force_https(request: Request, call_next):
    if not request.url.scheme == "https" and not request.client.host in ["127.0.0.1", "localhost"]:
        https_url = request.url.replace(scheme="https")
        return RedirectResponse(url=str(https_url), status_code=301)
    
    response = await call_next(request)
    return response
```

### 2. PII Handling

**PII Detection and Masking:**
```python
import re

class PIIDetector:
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    PHONE_PATTERN = r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b'
    SSN_PATTERN = r'\b\d{3}-\d{2}-\d{4}\b'
    
    def detect_pii(self, text: str) -> List[str]:
        """Detect PII in text content."""
        pii_found = []
        
        if re.search(self.EMAIL_PATTERN, text):
            pii_found.append("email")
        
        if re.search(self.PHONE_PATTERN, text):
            pii_found.append("phone")
        
        if re.search(self.SSN_PATTERN, text):
            pii_found.append("ssn")
        
        return pii_found
    
    def mask_pii(self, text: str) -> str:
        """Mask PII in text content."""
        # Mask emails
        text = re.sub(self.EMAIL_PATTERN, '[EMAIL_REDACTED]', text)
        
        # Mask phone numbers
        text = re.sub(self.PHONE_PATTERN, '[PHONE_REDACTED]', text)
        
        # Mask SSNs
        text = re.sub(self.SSN_PATTERN, '[SSN_REDACTED]', text)
        
        return text
```

### 3. Data Retention and Deletion

**Data Retention Policies:**
```python
class DataRetentionService:
    RETENTION_POLICIES = {
        "audit_logs": timedelta(days=2555),  # 7 years
        "user_sessions": timedelta(days=30),
        "temporary_files": timedelta(days=7),
        "deleted_content": timedelta(days=90)  # Soft delete retention
    }
    
    async def cleanup_expired_data(self):
        """Clean up expired data based on retention policies."""
        for data_type, retention_period in self.RETENTION_POLICIES.items():
            cutoff_date = datetime.utcnow() - retention_period
            await self.delete_expired_data(data_type, cutoff_date)
    
    async def delete_user_data(self, user_id: str):
        """Delete all user data (GDPR compliance)."""
        async with get_db_session() as db:
            # Delete user content
            await db.execute(delete(ContentItem).where(ContentItem.user_id == user_id))
            
            # Delete user sessions
            await db.execute(delete(Session).where(Session.user_id == user_id))
            
            # Anonymize audit logs (keep for compliance)
            await db.execute(
                update(AuditLog)
                .where(AuditLog.user_id == user_id)
                .values(user_id=None, details={"anonymized": True})
            )
            
            # Delete user account
            await db.execute(delete(User).where(User.id == user_id))
            
            await db.commit()
```

## Security Monitoring and Audit Logging

### 1. Audit Logging

**Comprehensive Audit Trail:**
```python
class AuditLogger:
    async def log_security_event(
        self,
        action: str,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        risk_level: str = "low"
    ):
        """Log security-sensitive events."""
        audit_log = AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            risk_level=risk_level,
            created_at=datetime.utcnow()
        )
        
        async with get_db_session() as db:
            db.add(audit_log)
            await db.commit()
        
        # Send high-risk events to security monitoring
        if risk_level in ["high", "critical"]:
            await self.send_security_alert(audit_log)

# Usage in authentication
async def authenticate_user(username: str, password: str, request: Request):
    user = await auth_service.authenticate_user(username, password)
    
    if user:
        await audit_logger.log_security_event(
            action="user_login_success",
            user_id=user.id,
            details={"username": username},
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            risk_level="low"
        )

Model configuration and usage audit:

```python
await audit_logger.log_security_event(
    action="model_config_updated",
    user_id=current_user.id,
    details={"per_phase": redacted_config},
    risk_level="low"
)

await audit_logger.log_security_event(
    action="agent_models_applied",
    user_id=current_user.id,
    details={"task_id": task_id, "overrides": overrides_summary},
    risk_level="low"
)
```
    else:
        await audit_logger.log_security_event(
            action="user_login_failed",
            details={"username": username, "reason": "invalid_credentials"},
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            risk_level="medium"
        )
```

### 2. Intrusion Detection

**Suspicious Activity Detection:**
```python
class SecurityMonitor:
    def __init__(self):
        self.failed_login_attempts = {}
        self.rate_limit_violations = {}
    
    async def detect_brute_force(self, ip_address: str, username: str) -> bool:
        """Detect brute force login attempts."""
        key = f"{ip_address}:{username}"
        current_time = datetime.utcnow()
        
        if key not in self.failed_login_attempts:
            self.failed_login_attempts[key] = []
        
        # Clean old attempts (older than 1 hour)
        self.failed_login_attempts[key] = [
            attempt for attempt in self.failed_login_attempts[key]
            if current_time - attempt < timedelta(hours=1)
        ]
        
        # Add current attempt
        self.failed_login_attempts[key].append(current_time)
        
        # Check if threshold exceeded (5 attempts in 1 hour)
        if len(self.failed_login_attempts[key]) >= 5:
            await self.block_ip_address(ip_address, "brute_force_detected")
            return True
        
        return False
    
    async def detect_anomalous_behavior(self, user_id: str, action: str) -> bool:
        """Detect anomalous user behavior."""
        # Get user's typical behavior patterns
        user_patterns = await self.get_user_behavior_patterns(user_id)
        
        # Check for unusual activity
        if self.is_unusual_activity(action, user_patterns):
            await audit_logger.log_security_event(
                action="anomalous_behavior_detected",
                user_id=user_id,
                details={"suspicious_action": action},
                risk_level="high"
            )
            return True
        
        return False
```

### 3. Security Headers and Middleware

**Security Middleware:**
```python
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    return response

@app.middleware("http")
async def request_validation_middleware(request: Request, call_next):
    # Validate request size
    if request.headers.get("content-length"):
        content_length = int(request.headers["content-length"])
        if content_length > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=413, detail="Request too large")
    
    # Check for suspicious patterns in URL
    if any(pattern in str(request.url) for pattern in ["../", "..\\", "<script", "javascript:"]):
        await audit_logger.log_security_event(
            action="suspicious_request_detected",
            details={"url": str(request.url), "pattern": "path_traversal_or_xss"},
            ip_address=request.client.host,
            risk_level="high"
        )
        raise HTTPException(status_code=400, detail="Invalid request")
    
    return await call_next(request)
```

## Vulnerability Management

### 1. Dependency Security

**Dependency Scanning:**
```bash
# Regular security scanning
pip-audit --requirement requirements.txt --format json --output security-report.json

# Safety check for known vulnerabilities
safety check --json --output safety-report.json
```

**Automated Updates:**
```python
# requirements-security.txt - Security-focused dependencies
cryptography>=41.0.0  # Latest security patches
pyjwt>=2.8.0         # JWT security fixes
bcrypt>=4.0.0        # Password hashing security
```

### 2. Security Testing

**Security Test Cases:**
```python
class TestSecurity:
    @pytest.mark.security
    async def test_sql_injection_protection(self):
        """Test SQL injection protection."""
        malicious_input = "'; DROP TABLE users; --"
        
        response = await client.get(f"/api/v1/content?search={malicious_input}")
        
        # Should not cause server error
        assert response.status_code != 500
        
        # Database should still be intact
        users = await get_all_users()
        assert len(users) > 0
    
    @pytest.mark.security
    async def test_xss_protection(self):
        """Test XSS protection."""
        xss_payload = "<script>alert('xss')</script>"
        
        response = await client.post("/api/v1/content", json={
            "title": "Test",
            "content": xss_payload
        })
        
        # Content should be sanitized
        content = response.json()
        assert "<script>" not in content["content"]
    
    @pytest.mark.security
    async def test_authentication_bypass(self):
        """Test authentication bypass attempts."""
        # Try to access protected endpoint without auth
        response = await client.get("/api/v1/admin/users")
        assert response.status_code == 401
        
        # Try with invalid token
        headers = {"Authorization": "Bearer invalid_token"}
        response = await client.get("/api/v1/admin/users", headers=headers)
        assert response.status_code == 401
```

### 3. Security Configuration

**Production Security Settings:**
```python
class SecurityConfig:
    # JWT Settings
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # Must be set in production
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    # Password Settings
    PASSWORD_MIN_LENGTH = 12
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_NUMBERS = True
    PASSWORD_REQUIRE_SPECIAL_CHARS = True
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE = 60
    RATE_LIMIT_BURST_SIZE = 10
    
    # File Upload
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES = [".txt", ".md", ".json", ".csv"]
    
    # Session Security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "strict"
    
    # CORS Settings
    ALLOWED_ORIGINS = ["https://yourdomain.com"]
    ALLOW_CREDENTIALS = True
    
    @classmethod
    def validate_config(cls):
        """Validate security configuration."""
        if not cls.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY must be set")
        
        if len(cls.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        
        if not cls.ALLOWED_ORIGINS:
            raise ValueError("ALLOWED_ORIGINS must be configured")
```

## Incident Response

### 1. Security Incident Detection

**Automated Alerting:**
```python
class SecurityAlertManager:
    async def send_security_alert(self, incident: SecurityIncident):
        """Send security alert to administrators."""
        alert_message = {
            "type": "security_incident",
            "severity": incident.severity,
            "description": incident.description,
            "timestamp": incident.timestamp.isoformat(),
            "affected_resources": incident.affected_resources,
            "recommended_actions": incident.recommended_actions
        }
        
        # Send to security team
        await self.send_email_alert(alert_message)
        await self.send_slack_alert(alert_message)
        
        # Log to security monitoring system
        await self.log_to_siem(alert_message)
```

### 2. Incident Response Procedures

**Automated Response Actions:**
```python
class IncidentResponseSystem:
    async def respond_to_brute_force(self, ip_address: str):
        """Respond to brute force attack."""
        # Block IP address
        await self.block_ip_address(ip_address, duration=timedelta(hours=24))
        
        # Notify security team
        await self.send_security_alert(SecurityIncident(
            type="brute_force_attack",
            severity="high",
            description=f"Brute force attack detected from {ip_address}",
            affected_resources=[ip_address],
            recommended_actions=["Review logs", "Extend IP block if necessary"]
        ))
    
    async def respond_to_data_breach(self, affected_users: List[str]):
        """Respond to potential data breach."""
        # Revoke all user sessions
        for user_id in affected_users:
            await self.revoke_all_user_sessions(user_id)
        
        # Force password reset
        await self.force_password_reset(affected_users)
        
        # Notify affected users
        await self.notify_affected_users(affected_users)
        
        # Alert security team
        await self.send_critical_security_alert("data_breach_detected")
```