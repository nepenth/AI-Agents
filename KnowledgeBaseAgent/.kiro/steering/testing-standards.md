# Testing Standards

This document defines comprehensive testing standards and practices for the AI Agent Backend system.

## Testing Philosophy

### 1. Testing Pyramid
Our testing strategy follows the testing pyramid:

- **Unit Tests (70%)**: Fast, isolated tests for individual components
- **Integration Tests (20%)**: Tests for component interactions
- **End-to-End Tests (10%)**: Full system workflow tests

### 2. Test-Driven Development (TDD)
- Write tests before implementation
- Red-Green-Refactor cycle
- Maintain high test coverage (>80%)
- Focus on behavior, not implementation

### 3. Testing Principles
- **Fast**: Tests should run quickly
- **Independent**: Tests should not depend on each other
- **Repeatable**: Tests should produce consistent results
- **Self-Validating**: Tests should have clear pass/fail results
- **Timely**: Tests should be written at the right time

## Unit Testing Standards

### 1. Test Structure and Organization

**File Organization:**
```
backend/tests/
├── unit/
│   ├── test_services/
│   │   ├── test_content_service.py
│   │   ├── test_ai_service.py
│   │   └── test_auth_service.py
│   ├── test_repositories/
│   │   ├── test_content_repository.py
│   │   └── test_auth_repository.py
│   └── test_models/
│       ├── test_content_models.py
│       └── test_auth_models.py
├── integration/
│   ├── test_api_endpoints.py
│   ├── test_database_integration.py
│   └── test_ai_integration.py
├── e2e/
│   ├── test_content_workflow.py
│   └── test_user_journey.py
└── conftest.py
```

**Test Class Structure:**
```python
class TestContentService:
    """Test cases for ContentService."""
    
    @pytest.fixture
    def content_service(self):
        """Create content service for testing."""
        return ContentService()
    
    @pytest.fixture
    def sample_content_data(self):
        """Create sample content data."""
        return {
            "title": "Test Article",
            "content": "This is test content",
            "content_type": "text"
        }
    
    @pytest.mark.asyncio
    async def test_create_content_success(self, content_service, sample_content_data):
        """Test successful content creation."""
        # Arrange
        with patch('app.services.content.get_content_repository') as mock_repo:
            mock_repo.return_value.create.return_value = Mock(id="content-123")
            
            # Act
            result = await content_service.create_content(sample_content_data)
            
            # Assert
            assert result.id == "content-123"
            mock_repo.return_value.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_content_validation_error(self, content_service):
        """Test content creation with validation error."""
        # Arrange
        invalid_data = {"title": ""}  # Missing required fields
        
        # Act & Assert
        with pytest.raises(ValidationError):
            await content_service.create_content(invalid_data)
```

### 2. Mocking and Fixtures

**Service Mocking:**
```python
@pytest.fixture
def mock_ai_service():
    """Mock AI service for testing."""
    with patch('app.services.ai_service.get_ai_service') as mock:
        ai_service = Mock()
        ai_service.generate_text.return_value = "Generated text"
        ai_service.generate_embeddings.return_value = [[0.1, 0.2, 0.3]]
        mock.return_value = ai_service
        yield ai_service

@pytest.fixture
def mock_database():
    """Mock database session for testing."""
    with patch('app.database.connection.get_db_session') as mock:
        db_session = AsyncMock()
        mock.return_value.__aenter__.return_value = db_session
        yield db_session
```

ModelRouter testing for seven-phase pipeline:
```python
class TestModelRouter:
    @pytest.mark.asyncio
    async def test_resolve_with_configured_phase(self, mock_ollama_backend):
        settings = ModelSelectionSettings(per_phase={ModelPhase.chat: PhaseModelSelector(backend='ollama', model='llama3:8b')})
        router = ModelRouter(settings, { 'ollama': mock_ollama_backend })
        backend, model, params = await router.resolve(ModelPhase.chat)
        assert model == 'llama3:8b'

    @pytest.mark.asyncio
    async def test_resolve_vision_phase(self, mock_ollama_backend):
        settings = ModelSelectionSettings(per_phase={ModelPhase.vision: PhaseModelSelector(backend='ollama', model='llava:13b')})
        router = ModelRouter(settings, { 'ollama': mock_ollama_backend })
        backend, model, params = await router.resolve(ModelPhase.vision)
        assert model == 'llava:13b'
        assert 'vision' in mock_ollama_backend.capabilities[model]

    @pytest.mark.asyncio
    async def test_resolve_kb_generation_phase(self, mock_localai_backend):
        settings = ModelSelectionSettings(per_phase={ModelPhase.kb_generation: PhaseModelSelector(backend='localai', model='mixtral:8x7b')})
        router = ModelRouter(settings, { 'localai': mock_localai_backend })
        backend, model, params = await router.resolve(ModelPhase.kb_generation)
        assert model == 'mixtral:8x7b'

    @pytest.mark.asyncio
    async def test_resolve_synthesis_phase(self, mock_ollama_backend):
        settings = ModelSelectionSettings(per_phase={ModelPhase.synthesis: PhaseModelSelector(backend='ollama', model='qwen2.5:7b')})
        router = ModelRouter(settings, { 'ollama': mock_ollama_backend })
        backend, model, params = await router.resolve(ModelPhase.synthesis)
        assert model == 'qwen2.5:7b'

    @pytest.mark.asyncio
    async def test_resolve_fallback_when_missing(self, mock_backends_with_caps):
        router = ModelRouter(ModelSelectionSettings(), mock_backends_with_caps)
        backend, model, params = await router.resolve(ModelPhase.embeddings)
        assert 'embed' in mock_backends_with_caps[backend.name].capabilities[model]

    @pytest.mark.asyncio
    async def test_capability_validation_failure(self, mock_ollama_backend):
        settings = ModelSelectionSettings(per_phase={ModelPhase.vision: PhaseModelSelector(backend='ollama', model='llama3:8b')})
        router = ModelRouter(settings, { 'ollama': mock_ollama_backend })
        with pytest.raises(AIAgentException):
            await router.resolve(ModelPhase.vision)
```

**Data Factories:**
```python
class ContentFactory:
    """Factory for creating test content items."""
    
    @staticmethod
    def create_content_item(**kwargs) -> ContentItem:
        """Create a content item with default values."""
        defaults = {
            "id": str(uuid.uuid4()),
            "title": "Test Article",
            "content": "This is test content",
            "content_type": "text",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        defaults.update(kwargs)
        return ContentItem(**defaults)
    
    @staticmethod
    def create_content_create_request(**kwargs) -> ContentCreateRequest:
        """Create a content creation request."""
        defaults = {
            "title": "Test Article",
            "content": "This is test content",
            "content_type": "text"
        }
        defaults.update(kwargs)
        return ContentCreateRequest(**defaults)
```

### 3. Async Testing Patterns

**Async Test Setup:**
```python
@pytest.mark.asyncio
async def test_async_operation():
    """Test async operations properly."""
    # Use AsyncMock for async methods
    mock_service = AsyncMock()
    mock_service.async_method.return_value = "result"
    
    # Test async operation
    result = await mock_service.async_method()
    assert result == "result"

# Test async generators
@pytest.mark.asyncio
async def test_async_generator():
    """Test async generators."""
    async def mock_generator():
        yield "item1"
        yield "item2"
    
    items = []
    async for item in mock_generator():
        items.append(item)
    
    assert items == ["item1", "item2"]
```

## Integration Testing

### 1. API Endpoint Testing

**FastAPI Test Client:**
```python
from fastapi.testclient import TestClient
from httpx import AsyncClient

class TestTwitterContentAPI:
    """Integration tests for Twitter/X content API endpoints."""
    
    @pytest.fixture
    async def async_client(self):
        """Create async test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    def sample_twitter_content(self):
        """Create sample Twitter/X content data."""
        return {
            "title": "Test Tweet",
            "content": "This is a test tweet with #hashtag",
            "source_type": "twitter",
            "tweet_id": "1234567890",
            "author_username": "testuser",
            "author_id": "user123",
            "tweet_url": "https://twitter.com/testuser/status/1234567890",
            "like_count": 10,
            "retweet_count": 5,
            "reply_count": 2,
            "quote_count": 1,
            "media_content": [{
                "id": "media123",
                "type": "image",
                "url": "https://example.com/image.jpg"
            }]
        }
    
    @pytest.mark.asyncio
    async def test_create_twitter_content_endpoint(self, async_client, sample_twitter_content):
        """Test Twitter/X content creation endpoint."""
        # Act
        response = await async_client.post("/api/v1/content", json=sample_twitter_content)
        
        # Assert
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["tweet_id"] == sample_twitter_content["tweet_id"]
        assert response_data["author_username"] == sample_twitter_content["author_username"]
        assert response_data["total_engagement"] == 18  # 10+5+2+1
        assert "id" in response_data
    
    @pytest.mark.asyncio
    async def test_get_twitter_bookmarks_endpoint(self, async_client, sample_twitter_content):
        """Test Twitter/X bookmarks retrieval endpoint."""
        # Arrange - create Twitter content first
        create_response = await async_client.post("/api/v1/content", json=sample_twitter_content)
        
        # Act
        response = await async_client.get("/api/v1/content/twitter/bookmarks")
        
        # Assert
        assert response.status_code == 200
        bookmarks = response.json()
        assert len(bookmarks) >= 1
        assert bookmarks[0]["tweet_id"] == sample_twitter_content["tweet_id"]
    
    @pytest.mark.asyncio
    async def test_sub_phase_status_endpoint(self, async_client, sample_twitter_content):
        """Test sub-phase status endpoint."""
        # Arrange - create content with sub-phase states
        sample_twitter_content.update({
            "bookmark_cached": True,
            "media_analyzed": False,
            "content_understood": False,
            "categorized": False
        })
        create_response = await async_client.post("/api/v1/content", json=sample_twitter_content)
        content_id = create_response.json()["id"]
        
        # Act
        response = await async_client.get("/api/v1/content/sub-phases/status")
        
        # Assert
        assert response.status_code == 200
        status_data = response.json()
        assert len(status_data) >= 1
        
        # Find our content item
        our_item = next((item for item in status_data if item["content_id"] == content_id), None)
        assert our_item is not None
        assert our_item["bookmark_cached"] == True
        assert our_item["media_analyzed"] == False
        assert our_item["completion_percentage"] == 25.0  # 1 out of 4 phases complete
```

### 2. Database Integration Testing

**Database Test Setup:**
```python
@pytest.fixture(scope="session")
async def test_database():
    """Create test database for integration tests."""
    # Create test database
    test_db_url = "postgresql+asyncpg://test:test@localhost/test_ai_agent"
    
    # Create tables
    async with create_async_engine(test_db_url) as engine:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        yield engine
        
        # Cleanup
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.integration
class TestContentRepository:
    """Integration tests for content repository."""
    
    @pytest.mark.asyncio
    async def test_create_and_retrieve_content(self, test_database):
        """Test creating and retrieving content from database."""
        # Arrange
        content_repo = ContentRepository()
        content_data = ContentCreateRequest(
            title="Test Article",
            content="This is test content"
        )
        
        # Act
        async with AsyncSession(test_database) as db:
            created_content = await content_repo.create(db, content_data)
            retrieved_content = await content_repo.get(db, created_content.id)
        
        # Assert
        assert retrieved_content is not None
        assert retrieved_content.title == content_data.title
        assert retrieved_content.content == content_data.content
```

### 3. External Service Integration

**AI Service Integration Testing:**
```python
@pytest.mark.integration
@pytest.mark.slow
class TestAIServiceIntegration:
    """Integration tests for AI service."""
    
    @pytest.mark.asyncio
    async def test_ai_text_generation(self):
        """Test AI text generation with real service."""
        # Skip if AI service not available
        ai_service = get_ai_service()
        if not await ai_service.is_available():
            pytest.skip("AI service not available")
        
        # Test text generation
        prompt = "Write a short summary about testing."
        result = await ai_service.generate_text(prompt)
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "test" in result.lower()
    
    @pytest.mark.asyncio
    async def test_embedding_generation(self):
        """Test embedding generation with real service."""
        ai_service = get_ai_service()
        if not await ai_service.is_available():
            pytest.skip("AI service not available")
        
        texts = ["Hello world", "Testing embeddings"]
        embeddings = await ai_service.generate_embeddings(texts)
        
        assert len(embeddings) == 2
        assert all(isinstance(emb, list) for emb in embeddings)
        assert all(len(emb) > 0 for emb in embeddings)
```

### 2. Seven-Phase Pipeline Testing

**Pipeline Integration Tests:**
```python
@pytest.mark.integration
class TestSevenPhasePipeline:
    """Integration tests for the seven-phase processing pipeline."""
    
    @pytest.fixture
    async def pipeline_service(self):
        """Create pipeline service for testing."""
        return SevenPhasePipelineService()
    
    @pytest.fixture
    def sample_bookmark_data(self):
        """Create sample bookmark data for pipeline testing."""
        return {
            "bookmarks": [
                {
                    "tweet_id": "1234567890",
                    "author": {"username": "testuser", "id": "user123"},
                    "text": "This is a test tweet about AI and machine learning",
                    "created_at": "2024-01-01T12:00:00Z",
                    "public_metrics": {"like_count": 10, "retweet_count": 5},
                    "media": [{"type": "image", "url": "https://example.com/image.jpg"}]
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_phase_1_initialization(self, pipeline_service):
        """Test Phase 1: System initialization."""
        # Act
        result = await pipeline_service.execute_phase_1({})
        
        # Assert
        assert result["phase"] == "1"
        assert result["status"] == "completed"
        assert "message" in result
    
    @pytest.mark.asyncio
    async def test_phase_2_fetch_bookmarks(self, pipeline_service, sample_bookmark_data, mock_twitter_client):
        """Test Phase 2: Bookmark fetching."""
        # Arrange
        mock_twitter_client.fetch_bookmarks.return_value = sample_bookmark_data["bookmarks"]
        
        # Act
        result = await pipeline_service.execute_phase_2({
            "bookmark_url": "https://api.twitter.com/2/users/me/bookmarks",
            "max_results": 10
        })
        
        # Assert
        assert result["phase"] == "2"
        assert result["status"] == "completed"
        assert result["bookmarks_fetched"] == 1
        assert result["new_bookmarks"] == 1
    
    @pytest.mark.asyncio
    async def test_phase_2_1_bookmark_caching(self, pipeline_service):
        """Test Sub-phase 2.1: Bookmark caching."""
        # Arrange - create content items first
        content_ids = await self.create_test_content_items()
        
        # Act
        result = await pipeline_service.execute_phase_2_1(content_ids)
        
        # Assert
        assert result["phase"] == "2.1"
        assert result["sub_phase"] == "bookmark_caching"
        assert result["status"] == "completed"
        assert result["items_processed"] == len(content_ids)
    
    @pytest.mark.asyncio
    async def test_phase_3_content_processing_full_cycle(self, pipeline_service):
        """Test Phase 3: Complete content processing cycle."""
        # Arrange - create cached content items
        content_ids = await self.create_cached_content_items()
        
        # Act - Execute all sub-phases
        media_result = await pipeline_service.execute_phase_3_1(content_ids)
        understanding_result = await pipeline_service.execute_phase_3_2(content_ids)
        categorization_result = await pipeline_service.execute_phase_3_3(content_ids)
        
        # Assert
        assert media_result["status"] == "completed"
        assert understanding_result["status"] == "completed"
        assert categorization_result["status"] == "completed"
        
        # Verify content items are fully processed
        for content_id in content_ids:
            content_item = await content_repo.get(content_id)
            assert content_item.media_analyzed == True
            assert content_item.content_understood == True
            assert content_item.categorized == True
            assert content_item.is_fully_processed == True
    
    @pytest.mark.asyncio
    async def test_pipeline_dependency_validation(self, pipeline_service):
        """Test pipeline phase dependency validation."""
        # Try to execute Phase 3 without Phase 2 completion
        with pytest.raises(PipelineDependencyError) as exc_info:
            await pipeline_service.execute_phase_3([])
        
        assert "Phase 2 not completed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_pipeline_error_recovery(self, pipeline_service):
        """Test pipeline error recovery and rollback."""
        # Arrange - create content that will cause processing error
        problematic_content_id = await self.create_problematic_content()
        
        # Act - Execute phase that will fail
        with pytest.raises(ProcessingError):
            await pipeline_service.execute_phase_3_1([problematic_content_id])
        
        # Assert - Verify rollback occurred
        content_item = await content_repo.get(problematic_content_id)
        assert content_item.media_analyzed == False  # Should be reset
        
        # Verify error was logged
        error_logs = await error_logger.get_recent_errors()
        assert any("media_analysis" in log["message"] for log in error_logs)
    
    async def create_test_content_items(self) -> List[str]:
        """Helper to create test content items."""
        content_items = []
        for i in range(3):
            content_item = ContentItem(
                id=str(uuid.uuid4()),
                source_type="twitter",
                tweet_id=f"tweet{i}",
                content=f"Test tweet content {i}",
                author_username="testuser",
                processing_state="fetched"
            )
            await content_repo.create(content_item)
            content_items.append(content_item.id)
        return content_items
    
    async def create_cached_content_items(self) -> List[str]:
        """Helper to create cached content items ready for Phase 3."""
        content_items = []
        for i in range(2):
            content_item = ContentItem(
                id=str(uuid.uuid4()),
                source_type="twitter",
                tweet_id=f"cached_tweet{i}",
                content=f"Cached tweet content {i}",
                author_username="testuser",
                processing_state="cached",
                bookmark_cached=True,
                media_content=[{
                    "id": f"media{i}",
                    "type": "image",
                    "url": f"https://example.com/image{i}.jpg"
                }]
            )
            await content_repo.create(content_item)
            content_items.append(content_item.id)
        return content_items
```

**Command-Line Testing Integration:**
```python
@pytest.mark.cli
class TestCLIPipelineExecution:
    """Test command-line pipeline execution."""
    
    @pytest.mark.asyncio
    async def test_cli_phase_execution(self):
        """Test executing phases via CLI."""
        # Test Phase 2 execution
        result = await run_cli_command([
            "python", "cli_test_phases.py",
            "--phase", "2",
            "--config", '{"max_results": 10}'
        ])
        
        assert result.returncode == 0
        assert "Phase 2 completed successfully" in result.stdout
    
    @pytest.mark.asyncio
    async def test_cli_sub_phase_execution(self):
        """Test executing sub-phases via CLI."""
        # Test Phase 3.1 execution
        result = await run_cli_command([
            "python", "cli_test_phases.py",
            "--phase", "3",
            "--sub-phase", "1",
            "--content-ids", "id1,id2,id3"
        ])
        
        assert result.returncode == 0
        assert "Phase 3.1 completed successfully" in result.stdout
    
    @pytest.mark.asyncio
    async def test_cli_status_check(self):
        """Test checking pipeline status via CLI."""
        result = await run_cli_command([
            "python", "cli_test_phases.py",
            "--status",
            "--phase", "2"
        ])
        
        assert result.returncode == 0
        status_data = json.loads(result.stdout)
        assert "phase" in status_data
        assert "status" in status_data
```

## End-to-End Testing

### 1. User Journey Testing

**Complete Workflow Tests:**
```python
@pytest.mark.e2e
class TestUserJourney:
    """End-to-end tests for complete user journeys."""
    
    @pytest.mark.asyncio
    async def test_content_creation_to_search_workflow(self, async_client):
        """Test complete workflow from content creation to search."""
        # Step 1: Create user account
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePassword123!"
        }
        register_response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == 201
        
        # Step 2: Login and get token
        login_data = {"username": "testuser", "password": "SecurePassword123!"}
        login_response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 3: Create content
        content_data = {
            "title": "AI Testing Best Practices",
            "content": "This article covers comprehensive testing strategies for AI systems.",
            "tags": ["ai", "testing", "best-practices"]
        }
        content_response = await async_client.post(
            "/api/v1/content", 
            json=content_data, 
            headers=headers
        )
        assert content_response.status_code == 201
        content_id = content_response.json()["id"]
        
        # Step 4: Wait for AI processing (in real system)
        await asyncio.sleep(2)  # Allow time for background processing
        
        # Step 5: Search for content
        search_response = await async_client.get(
            "/api/v1/search?query=AI testing",
            headers=headers
        )
        assert search_response.status_code == 200
        search_results = search_response.json()["results"]
        
        # Verify content appears in search results
        content_ids = [result["id"] for result in search_results]
        assert content_id in content_ids
        
        # Step 6: Start chat session
        chat_response = await async_client.post(
            "/api/v1/chat/sessions",
            json={"title": "Test Chat"},
            headers=headers
        )
        assert chat_response.status_code == 201
        session_id = chat_response.json()["id"]
        
        # Step 7: Send chat message
        message_data = {
            "content": "Tell me about AI testing best practices",
            "use_knowledge_base": True
        }
        message_response = await async_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json=message_data,
            headers=headers
        )
        assert message_response.status_code == 201
        
        # Verify AI response references our content
        ai_response = message_response.json()["content"]
        assert "testing" in ai_response.lower()
```

### 2. Performance Testing

**Load Testing:**
```python
@pytest.mark.performance
class TestPerformance:
    """Performance tests for critical endpoints."""
    
    @pytest.mark.asyncio
    async def test_content_creation_performance(self, async_client):
        """Test content creation performance under load."""
        import time
        
        # Create multiple content items concurrently
        tasks = []
        start_time = time.time()
        
        for i in range(50):
            content_data = {
                "title": f"Performance Test Article {i}",
                "content": f"This is test content for performance testing {i}"
            }
            task = async_client.post("/api/v1/content", json=content_data)
            tasks.append(task)
        
        # Wait for all requests to complete
        responses = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Assert performance requirements
        duration = end_time - start_time
        assert duration < 10.0  # Should complete within 10 seconds
        
        # Verify all requests succeeded
        success_count = sum(1 for r in responses if r.status_code == 201)
        assert success_count == 50
    
    @pytest.mark.asyncio
    async def test_search_performance(self, async_client):
        """Test search performance with large dataset."""
        # Assume database has been populated with test data
        
        search_queries = [
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "neural networks",
            "data science"
        ]
        
        start_time = time.time()
        
        # Execute searches concurrently
        tasks = [
            async_client.get(f"/api/v1/search?query={query}")
            for query in search_queries
        ]
        
        responses = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Assert performance requirements
        duration = end_time - start_time
        assert duration < 5.0  # Should complete within 5 seconds
        
        # Verify all searches returned results
        for response in responses:
            assert response.status_code == 200
            results = response.json()["results"]
            assert len(results) > 0
```

## Test Data Management

### 1. Test Data Factories

**Comprehensive Data Factories:**
```python
class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_user(**kwargs) -> User:
        """Create test user."""
        defaults = {
            "id": str(uuid.uuid4()),
            "username": f"testuser_{random.randint(1000, 9999)}",
            "email": f"test_{random.randint(1000, 9999)}@example.com",
            "password_hash": "$2b$12$hashed_password",
            "roles": ["user"],
            "is_active": True,
            "created_at": datetime.utcnow()
        }
        defaults.update(kwargs)
        return User(**defaults)
    
    @staticmethod
    def create_content_batch(count: int = 10) -> List[ContentItem]:
        """Create batch of test content items."""
        return [
            TestDataFactory.create_content_item(
                title=f"Test Article {i}",
                content=f"This is test content for article {i}"
            )
            for i in range(count)
        ]
    
    @staticmethod
    def create_ai_response_data() -> Dict[str, Any]:
        """Create mock AI response data."""
        return {
            "text": "This is a generated AI response for testing purposes.",
            "embeddings": [random.random() for _ in range(384)],
            "metadata": {
                "model": "test-model",
                "tokens": 50,
                "confidence": 0.95
            }
        }
```

### 2. Database Seeding

**Test Database Seeding:**
```python
class DatabaseSeeder:
    """Seed database with test data."""
    
    async def seed_test_database(self, db: AsyncSession):
        """Seed database with comprehensive test data."""
        # Create test users
        users = [
            TestDataFactory.create_user(username="admin", roles=["admin"]),
            TestDataFactory.create_user(username="moderator", roles=["moderator"]),
            TestDataFactory.create_user(username="user1", roles=["user"]),
            TestDataFactory.create_user(username="user2", roles=["user"])
        ]
        
        for user in users:
            db.add(user)
        
        await db.commit()
        
        # Create test content
        content_items = TestDataFactory.create_content_batch(100)
        for item in content_items:
            item.user_id = random.choice(users).id
            db.add(item)
        
        await db.commit()
        
        # Create test knowledge items
        for content in content_items[:50]:  # Create knowledge for half the content
            knowledge_item = KnowledgeItem(
                id=str(uuid.uuid4()),
                title=content.title,
                content=content.content,
                source_content_id=content.id,
                main_category="test",
                sub_category="seeded_data"
            )
            db.add(knowledge_item)
        
        await db.commit()

@pytest.fixture(scope="session")
async def seeded_database(test_database):
    """Database seeded with test data."""
    seeder = DatabaseSeeder()
    
    async with AsyncSession(test_database) as db:
        await seeder.seed_test_database(db)
    
    yield test_database
```

### 3. Test Data Cleanup

**Automatic Cleanup:**
```python
@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """Automatically cleanup test data after each test."""
    yield  # Run the test
    
    # Cleanup after test
    async with get_db_session() as db:
        # Delete test data created during test
        await db.execute(delete(ContentItem).where(ContentItem.title.like("Test%")))
        await db.execute(delete(User).where(User.username.like("testuser_%")))
        await db.commit()

class TestDataManager:
    """Manage test data lifecycle."""
    
    def __init__(self):
        self.created_items = []
    
    async def create_and_track(self, model_class, **kwargs):
        """Create item and track for cleanup."""
        async with get_db_session() as db:
            item = model_class(**kwargs)
            db.add(item)
            await db.commit()
            await db.refresh(item)
            
            self.created_items.append((model_class, item.id))
            return item
    
    async def cleanup_all(self):
        """Cleanup all tracked items."""
        async with get_db_session() as db:
            for model_class, item_id in reversed(self.created_items):
                await db.execute(delete(model_class).where(model_class.id == item_id))
            await db.commit()
            
        self.created_items.clear()
```

## Test Configuration and Environment

### 1. Test Configuration

**Test Settings:**
```python
class TestConfig:
    """Configuration for testing environment."""
    
    # Database
    DATABASE_URL = "postgresql+asyncpg://test:test@localhost/test_ai_agent"
    
    # AI Service (use mock by default)
    AI_PROVIDER = "mock"
    
    # Redis (use fake redis for tests)
    REDIS_URL = "redis://localhost:6379/1"
    USE_FAKE_REDIS = True
    
    # Security (relaxed for testing)
    JWT_SECRET_KEY = "test-secret-key-for-testing-only"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60  # Longer for tests
    
    # File uploads
    UPLOAD_DIRECTORY = "/tmp/test_uploads"
    MAX_FILE_SIZE = 1024 * 1024  # 1MB for tests
    
    # Logging
    LOG_LEVEL = "DEBUG"
    LOG_TO_FILE = False
    
    # Performance
    CELERY_TASK_ALWAYS_EAGER = True  # Execute tasks synchronously in tests
    
    @classmethod
    def setup_test_environment(cls):
        """Setup test environment."""
        os.environ.update({
            "DATABASE_URL": cls.DATABASE_URL,
            "AI_PROVIDER": cls.AI_PROVIDER,
            "REDIS_URL": cls.REDIS_URL,
            "JWT_SECRET_KEY": cls.JWT_SECRET_KEY,
            "LOG_LEVEL": cls.LOG_LEVEL
        })
```

### 2. Test Markers and Categories

**Pytest Markers:**
```python
# pytest.ini
[tool:pytest]
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow tests that take more than 1 second
    performance: Performance tests
    security: Security tests
    ai: Tests that require AI service
    database: Tests that require database
    redis: Tests that require Redis
    external: Tests that require external services

# Run specific test categories
# pytest -m unit                    # Run only unit tests
# pytest -m "not slow"              # Skip slow tests
# pytest -m "integration and not ai" # Integration tests without AI
```

### 3. Continuous Integration

**CI Test Pipeline:**
```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_USER: test
          POSTGRES_DB: test_ai_agent
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt
    
    - name: Run unit tests
      run: pytest tests/unit -v --cov=app --cov-report=xml
    
    - name: Run integration tests
      run: pytest tests/integration -v
      env:
        DATABASE_URL: postgresql+asyncpg://test:test@localhost/test_ai_agent
        REDIS_URL: redis://localhost:6379/1
    
    - name: Run security tests
      run: pytest -m security -v
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## Test Reporting and Metrics

### 1. Coverage Reporting

**Coverage Configuration:**
```ini
# .coveragerc
[run]
source = app
omit = 
    app/tests/*
    app/migrations/*
    app/cli/*
    */venv/*
    */virtualenv/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    class .*\(Protocol\):
    @(abc\.)?abstractmethod

[html]
directory = htmlcov
```

### 2. Test Metrics

**Custom Test Metrics:**
```python
class TestMetrics:
    """Collect and report test metrics."""
    
    def __init__(self):
        self.test_results = []
        self.performance_metrics = []
    
    def record_test_result(self, test_name: str, duration: float, status: str):
        """Record test execution result."""
        self.test_results.append({
            "test_name": test_name,
            "duration": duration,
            "status": status,
            "timestamp": datetime.utcnow()
        })
    
    def record_performance_metric(self, operation: str, duration: float, throughput: float):
        """Record performance test metric."""
        self.performance_metrics.append({
            "operation": operation,
            "duration": duration,
            "throughput": throughput,
            "timestamp": datetime.utcnow()
        })
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "passed"])
        failed_tests = len([r for r in self.test_results if r["status"] == "failed"])
        
        avg_duration = sum(r["duration"] for r in self.test_results) / total_tests if total_tests > 0 else 0
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "average_duration": avg_duration
            },
            "performance": {
                "metrics": self.performance_metrics,
                "slowest_operations": sorted(
                    self.performance_metrics,
                    key=lambda x: x["duration"],
                    reverse=True
                )[:10]
            }
        }
```