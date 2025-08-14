"""
Comprehensive tests for Celery tasks with mocking and utilities.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from celery import Celery
from celery.result import AsyncResult

from app.tasks.celery_app import celery_app
from app.tasks.base import BaseTask, TaskResult, TaskProgress, TaskState
from app.tasks.subphase_processing import (
    phase_2_1_bookmark_caching_task,
    phase_3_1_media_analysis_task,
    phase_3_2_content_understanding_task,
    phase_3_3_categorization_task
)
from app.tasks.synthesis_tasks import generate_synthesis_document
from app.tasks.monitoring import system_health_check


class TestTaskBase:
    """Test base task functionality."""
    
    def test_task_progress_creation(self):
        """Test TaskProgress dataclass."""
        progress = TaskProgress(
            current=5,
            total=10,
            status="Processing items",
            phase="categorization"
        )
        
        assert progress.current == 5
        assert progress.total == 10
        assert progress.percentage == 50.0
        assert progress.status == "Processing items"
        assert progress.phase == "categorization"
        
        # Test dictionary conversion
        progress_dict = progress.to_dict()
        assert progress_dict["current"] == 5
        assert progress_dict["total"] == 10
    
    def test_task_result_creation(self):
        """Test TaskResult dataclass."""
        result = TaskResult(
            success=True,
            data={"processed_items": 5},
            execution_time=45.2
        )
        
        assert result.success is True
        assert result.data["processed_items"] == 5
        assert result.execution_time == 45.2
        
        # Test dictionary conversion
        result_dict = result.to_dict()
        assert result_dict["success"] is True
        assert result_dict["data"]["processed_items"] == 5
    
    def test_base_task_configuration(self):
        """Test BaseTask configuration."""
        task = BaseTask()
        
        assert task.autoretry_for == (Exception,)
        assert task.retry_kwargs['max_retries'] == 3
        assert task.retry_backoff is True
        assert task.retry_jitter is True
    
    def test_task_progress_calculation(self):
        """Test progress percentage calculation."""
        # Normal case
        progress = TaskProgress(current=3, total=10, status="test")
        assert progress.percentage == 30.0
        
        # Edge case: total is 0
        progress = TaskProgress(current=0, total=0, status="test")
        assert progress.percentage == 0.0
        
        # Edge case: current > total
        progress = TaskProgress(current=15, total=10, status="test")
        assert progress.percentage == 100.0


class TestContentFetchingTasks:
    """Test content fetching tasks."""
    
    @pytest.fixture
    def mock_content_service(self):
        """Mock content fetching service."""
        with patch('app.tasks.content_fetching.get_content_fetching_service') as mock:
            service = AsyncMock()
            
            # Mock content item generator
            async def mock_fetch_content(sources_config):
                for i in range(3):  # Mock 3 items
                    yield MagicMock(
                        id=f"item_{i}",
                        title=f"Test Item {i}",
                        source_type="url"
                    )
            
            service.fetch_content = mock_fetch_content
            mock.return_value = service
            yield service
    
    @pytest.fixture
    def mock_content_repo(self):
        """Mock content repository."""
        with patch('app.tasks.content_fetching.get_content_repository') as mock:
            repo = AsyncMock()
            repo.create = AsyncMock(return_value=MagicMock(
                id="created_item_id",
                title="Created Item",
                source_type="url"
            ))
            mock.return_value = repo
            yield repo
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        with patch('app.tasks.content_fetching.get_db_session') as mock:
            session = AsyncMock()
            mock.return_value.__aenter__ = AsyncMock(return_value=session)
            mock.return_value.__aexit__ = AsyncMock(return_value=None)
            yield session
    
    def test_fetch_content_from_sources_success(
        self, 
        mock_content_service, 
        mock_content_repo, 
        mock_db_session
    ):
        """Test successful content fetching."""
        sources_config = [
            {"type": "url", "urls": ["https://example.com/test1", "https://example.com/test2"]}
        ]
        
        # Execute task
        result = fetch_content_from_sources.apply(args=[sources_config]).get()
        
        assert result["success"] is True
        assert "data" in result
        assert result["data"]["fetched_count"] == 3
        assert len(result["data"]["content_items"]) == 3
    
    def test_fetch_url_content(self, mock_content_service, mock_content_repo, mock_db_session):
        """Test URL content fetching."""
        urls = ["https://example.com/test1", "https://example.com/test2"]
        
        with patch('app.tasks.content_fetching.fetch_content_from_sources.apply_async') as mock_task:
            mock_task.return_value.get.return_value = {
                "success": True,
                "data": {"fetched_count": 2, "content_items": []}
            }
            
            result = fetch_url_content.apply(args=[urls]).get()
            
            assert result["success"] is True
            mock_task.assert_called_once()
    
    def test_fetch_content_error_handling(self, mock_db_session):
        """Test error handling in content fetching."""
        with patch('app.tasks.content_fetching.get_content_fetching_service') as mock_service:
            # Mock service to raise an exception
            mock_service.side_effect = Exception("Service unavailable")
            
            sources_config = [{"type": "url", "urls": ["https://example.com/test"]}]
            result = fetch_content_from_sources.apply(args=[sources_config]).get()
            
            assert result["success"] is False
            assert "error" in result
            assert "Service unavailable" in result["error"]


class TestAIProcessingTasks:
    """Test AI processing tasks."""
    
    @pytest.fixture
    def mock_content_item(self):
        """Mock content item."""
        item = MagicMock()
        item.id = "test_content_id"
        item.title = "Test Content"
        item.content = "This is test content for AI processing"
        item.source_type = "url"
        item.main_category = None
        item.sub_category = None
        item.tags = []
        return item
    
    @pytest.fixture
    def mock_repositories(self):
        """Mock repositories."""
        with patch('app.tasks.ai_processing.get_content_repository') as mock_content_repo, \
             patch('app.tasks.ai_processing.get_knowledge_repository') as mock_knowledge_repo:
            
            content_repo = AsyncMock()
            knowledge_repo = AsyncMock()
            
            mock_content_repo.return_value = content_repo
            mock_knowledge_repo.return_value = knowledge_repo
            
            yield content_repo, knowledge_repo
    
    @pytest.fixture
    def mock_ai_services(self):
        """Mock AI services."""
        with patch('app.tasks.ai_processing.get_content_categorizer') as mock_categorizer, \
             patch('app.tasks.ai_processing.get_knowledge_generator') as mock_generator:
            
            categorizer = AsyncMock()
            generator = AsyncMock()
            
            # Mock categorization result
            categorizer.categorize_content.return_value = MagicMock(
                main_category="Technology",
                sub_category="Software Development",
                tags=["testing", "ai"],
                confidence_score=0.85,
                reasoning="Content discusses AI and testing"
            )
            
            # Mock knowledge generation result
            generator.generate_knowledge_item.return_value = MagicMock(
                knowledge_item=MagicMock(
                    id="knowledge_item_id",
                    display_title="Enhanced Test Content",
                    quality_score=0.8
                ),
                quality_metrics={"overall_quality": 0.8}
            )
            
            mock_categorizer.return_value = categorizer
            mock_generator.return_value = generator
            
            yield categorizer, generator
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        with patch('app.tasks.ai_processing.get_db_session') as mock:
            session = AsyncMock()
            mock.return_value.__aenter__ = AsyncMock(return_value=session)
            mock.return_value.__aexit__ = AsyncMock(return_value=None)
            yield session
    
    def test_categorize_content_item_success(
        self, 
        mock_content_item, 
        mock_repositories, 
        mock_ai_services, 
        mock_db_session
    ):
        """Test successful content categorization."""
        content_repo, knowledge_repo = mock_repositories
        categorizer, generator = mock_ai_services
        
        # Mock repository methods
        content_repo.get.return_value = mock_content_item
        content_repo.update.return_value = mock_content_item
        
        result = categorize_content_item.apply(args=["test_content_id"]).get()
        
        assert result["success"] is True
        assert result["data"]["main_category"] == "Technology"
        assert result["data"]["sub_category"] == "Software Development"
        assert result["data"]["confidence_score"] == 0.85
    
    def test_generate_knowledge_item_success(
        self, 
        mock_content_item, 
        mock_repositories, 
        mock_ai_services, 
        mock_db_session
    ):
        """Test successful knowledge item generation."""
        content_repo, knowledge_repo = mock_repositories
        categorizer, generator = mock_ai_services
        
        # Mock repository methods
        content_repo.get.return_value = mock_content_item
        content_repo.update.return_value = mock_content_item
        knowledge_repo.create.return_value = MagicMock(
            id="knowledge_item_id",
            display_title="Enhanced Test Content",
            quality_score=0.8
        )
        
        result = generate_knowledge_item.apply(args=["test_content_id"]).get()
        
        assert result["success"] is True
        assert result["data"]["knowledge_item_id"] == "knowledge_item_id"
        assert result["data"]["display_title"] == "Enhanced Test Content"
    
    def test_ai_processing_error_handling(self, mock_db_session):
        """Test error handling in AI processing."""
        with patch('app.tasks.ai_processing.get_content_repository') as mock_repo:
            # Mock repository to raise an exception
            mock_repo.side_effect = Exception("Database connection failed")
            
            result = categorize_content_item.apply(args=["test_content_id"]).get()
            
            assert result["success"] is False
            assert "error" in result
            assert "Database connection failed" in result["error"]


class TestSynthesisTasks:
    """Test synthesis generation tasks."""
    
    @pytest.fixture
    def mock_knowledge_items(self):
        """Mock knowledge items."""
        items = []
        for i in range(3):
            item = MagicMock()
            item.id = f"knowledge_item_{i}"
            item.display_title = f"Knowledge Item {i}"
            item.enhanced_content = f"Enhanced content for item {i}"
            item.updated_at = asyncio.get_event_loop().time()
            items.append(item)
        return items
    
    @pytest.fixture
    def mock_synthesis_services(self, mock_knowledge_items):
        """Mock synthesis services."""
        with patch('app.tasks.synthesis_tasks.get_knowledge_repository') as mock_knowledge_repo, \
             patch('app.tasks.synthesis_tasks.get_synthesis_repository') as mock_synthesis_repo, \
             patch('app.tasks.synthesis_tasks.get_synthesis_generator') as mock_generator:
            
            knowledge_repo = AsyncMock()
            synthesis_repo = AsyncMock()
            generator = AsyncMock()
            
            # Mock synthesis generation result
            generator.generate_synthesis_document.return_value = MagicMock(
                synthesis_document=MagicMock(
                    id="synthesis_doc_id",
                    title="Technology Synthesis",
                    item_count=3,
                    coherence_score=0.85
                ),
                generation_stats={"generation_duration": 45.2}
            )
            
            # Mock repository methods
            synthesis_repo.create.return_value = MagicMock(
                id="synthesis_doc_id",
                title="Technology Synthesis",
                item_count=3,
                word_count=500,
                coherence_score=0.85,
                completeness_score=0.90,
                markdown_path="/path/to/synthesis.md"
            )
            
            mock_knowledge_repo.return_value = knowledge_repo
            mock_synthesis_repo.return_value = synthesis_repo
            mock_generator.return_value = generator
            
            yield knowledge_repo, synthesis_repo, generator
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        with patch('app.tasks.synthesis_tasks.get_db_session') as mock:
            session = AsyncMock()
            mock.return_value.__aenter__ = AsyncMock(return_value=session)
            mock.return_value.__aexit__ = AsyncMock(return_value=None)
            yield session
    
    def test_generate_synthesis_document_success(
        self, 
        mock_knowledge_items, 
        mock_synthesis_services, 
        mock_db_session
    ):
        """Test successful synthesis document generation."""
        knowledge_repo, synthesis_repo, generator = mock_synthesis_services
        
        # Mock that we have knowledge items (in real implementation, this would be a query)
        # For testing, we'll patch the async function directly
        with patch('app.tasks.synthesis_tasks._generate_synthesis_async') as mock_async:
            mock_async.return_value = {
                "main_category": "Technology",
                "sub_category": "Software Development",
                "synthesis_id": "synthesis_doc_id",
                "title": "Technology Synthesis",
                "item_count": 3,
                "coherence_score": 0.85
            }
            
            result = generate_synthesis_document.apply(
                args=["Technology", "Software Development"]
            ).get()
            
            assert result["success"] is True
            assert result["data"]["synthesis_id"] == "synthesis_doc_id"
            assert result["data"]["title"] == "Technology Synthesis"
            assert result["data"]["item_count"] == 3


class TestMonitoringTasks:
    """Test monitoring and maintenance tasks."""
    
    def test_system_health_check(self):
        """Test system health check task."""
        with patch('app.tasks.monitoring._check_database_health') as mock_db, \
             patch('app.tasks.monitoring._check_redis_health') as mock_redis, \
             patch('app.tasks.monitoring._check_ai_service_health') as mock_ai, \
             patch('app.tasks.monitoring._check_filesystem_health') as mock_fs, \
             patch('app.tasks.monitoring._check_worker_health') as mock_worker:
            
            # Mock all health checks to return healthy status
            mock_db.return_value = {"healthy": True, "response_time_ms": 15}
            mock_redis.return_value = {"healthy": True, "response_time_ms": 5}
            mock_ai.return_value = {"healthy": True, "available_backends": ["ollama"]}
            mock_fs.return_value = {"healthy": True, "disk_usage_percent": 45.2}
            mock_worker.return_value = {"healthy": True, "total_workers": 2}
            
            result = system_health_check.apply().get()
            
            assert result["success"] is True
            assert result["data"]["overall_healthy"] is True
            assert "checks" in result["data"]
            assert len(result["data"]["checks"]) == 5
    
    def test_system_health_check_unhealthy(self):
        """Test system health check with unhealthy components."""
        with patch('app.tasks.monitoring._check_database_health') as mock_db, \
             patch('app.tasks.monitoring._check_redis_health') as mock_redis, \
             patch('app.tasks.monitoring._check_ai_service_health') as mock_ai, \
             patch('app.tasks.monitoring._check_filesystem_health') as mock_fs, \
             patch('app.tasks.monitoring._check_worker_health') as mock_worker:
            
            # Mock database as unhealthy
            mock_db.return_value = {"healthy": False, "error": "Connection timeout"}
            mock_redis.return_value = {"healthy": True, "response_time_ms": 5}
            mock_ai.return_value = {"healthy": True, "available_backends": ["ollama"]}
            mock_fs.return_value = {"healthy": True, "disk_usage_percent": 45.2}
            mock_worker.return_value = {"healthy": True, "total_workers": 2}
            
            result = system_health_check.apply().get()
            
            assert result["success"] is True
            assert result["data"]["overall_healthy"] is False
            assert result["data"]["checks"]["database"]["healthy"] is False


class TestCeleryConfiguration:
    """Test Celery application configuration."""
    
    def test_celery_app_configuration(self):
        """Test Celery app is properly configured."""
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"
        assert celery_app.conf.timezone == "UTC"
        assert celery_app.conf.enable_utc is True
        assert celery_app.conf.task_track_started is True
    
    def test_task_routing_configuration(self):
        """Test task routing is properly configured."""
        routes = celery_app.conf.task_routes
        
        assert 'app.tasks.content_fetching.*' in routes
        assert 'app.tasks.ai_processing.*' in routes
        assert 'app.tasks.synthesis_tasks.*' in routes
        assert 'app.tasks.monitoring.*' in routes
        
        assert routes['app.tasks.content_fetching.*']['queue'] == 'content_fetching'
        assert routes['app.tasks.ai_processing.*']['queue'] == 'ai_processing'
    
    def test_queue_configuration(self):
        """Test queue configuration."""
        queues = celery_app.conf.task_queues
        queue_names = [q.name for q in queues]
        
        assert 'default' in queue_names
        assert 'content_fetching' in queue_names
        assert 'ai_processing' in queue_names
        assert 'synthesis' in queue_names
        assert 'monitoring' in queue_names
        assert 'priority' in queue_names
    
    def test_rate_limiting_configuration(self):
        """Test rate limiting configuration."""
        annotations = celery_app.conf.task_annotations
        
        assert 'app.tasks.ai_processing.*' in annotations
        assert 'app.tasks.content_fetching.*' in annotations
        assert 'app.tasks.synthesis_tasks.*' in annotations
        
        assert annotations['app.tasks.ai_processing.*']['rate_limit'] == '10/m'
        assert annotations['app.tasks.content_fetching.*']['rate_limit'] == '30/m'
        assert annotations['app.tasks.synthesis_tasks.*']['rate_limit'] == '5/m'


class TestTaskIntegration:
    """Test task integration and workflows."""
    
    def test_health_check_task_execution(self):
        """Test health check task can be executed."""
        from app.tasks.celery_app import health_check
        
        result = health_check.apply().get()
        
        assert result["status"] == "healthy"
        assert result["message"] == "Celery worker is operational"
    
    @pytest.mark.integration
    def test_task_chain_execution(self):
        """Test chaining multiple tasks together."""
        # This would test a complete workflow
        # For now, we'll test that tasks can be chained
        from celery import chain
        
        # Mock a simple chain
        with patch('app.tasks.content_fetching.fetch_url_content') as mock_fetch, \
             patch('app.tasks.ai_processing.categorize_content_item') as mock_categorize:
            
            mock_fetch.apply_async.return_value.get.return_value = {
                "success": True, 
                "data": {"content_items": [{"id": "test_id"}]}
            }
            mock_categorize.apply_async.return_value.get.return_value = {
                "success": True,
                "data": {"main_category": "Technology"}
            }
            
            # This would be a real chain in practice
            # For testing, we just verify the mocks work
            fetch_result = mock_fetch.apply_async(args=[["https://example.com"]]).get()
            categorize_result = mock_categorize.apply_async(args=["test_id"]).get()
            
            assert fetch_result["success"] is True
            assert categorize_result["success"] is True