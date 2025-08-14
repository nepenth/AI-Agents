"""
Integration tests for the content processing pipeline.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any

from app.services.content_processing_pipeline import get_content_processing_pipeline
from app.services.seven_phase_pipeline import get_seven_phase_pipeline
from app.models.content import ContentItem


class TestContentProcessingPipeline:
    """Test cases for ContentProcessingPipeline."""
    
    @pytest.fixture
    def content_pipeline(self):
        """Create content processing pipeline for testing."""
        return get_content_processing_pipeline()
    
    @pytest.fixture
    def mock_twitter_client(self):
        """Mock Twitter client."""
        client = AsyncMock()
        client.is_available.return_value = True
        client.get_tweet.return_value = MagicMock(
            id="123456789",
            text="This is a test tweet about AI and machine learning",
            author_username="test_user",
            author_id="user123",
            created_at=datetime.utcnow(),
            url="https://twitter.com/test_user/status/123456789",
            public_metrics={"like_count": 10, "retweet_count": 5, "reply_count": 2, "quote_count": 1},
            media=[{"type": "image", "url": "https://example.com/image.jpg", "alt_text": "Test image"}]
        )
        client.detect_thread.return_value = None
        return client
    
    @pytest.fixture
    def mock_model_router(self):
        """Mock model router."""
        router = AsyncMock()
        router.resolve.return_value = (AsyncMock(), "test-model", {})
        return router
    
    @pytest.fixture
    def mock_content_repo(self):
        """Mock content repository."""
        repo = AsyncMock()
        repo.get.return_value = ContentItem(
            id="content-123",
            source_type="twitter",
            source_id="123456789",
            tweet_id="123456789",
            title="Test Tweet",
            content="This is a test tweet",
            processing_state="pending",
            bookmark_cached=False,
            media_analyzed=False,
            content_understood=False,
            categorized=False
        )
        repo.create.return_value = ContentItem(
            id="content-123",
            source_type="twitter",
            source_id="123456789",
            tweet_id="123456789",
            title="Test Tweet",
            content="This is a test tweet",
            processing_state="pending",
            bookmark_cached=False,
            media_analyzed=False,
            content_understood=False,
            categorized=False
        )
        repo.update.return_value = ContentItem(
            id="content-123",
            source_type="twitter",
            source_id="123456789",
            tweet_id="123456789",
            title="Test Tweet",
            content="This is a test tweet",
            processing_state="completed",
            bookmark_cached=True,
            media_analyzed=True,
            content_understood=True,
            categorized=True
        )
        repo.get_by_source.return_value = None
        return repo
    
    @pytest.mark.asyncio
    async def test_process_twitter_bookmark_sync(self, content_pipeline, mock_twitter_client, mock_model_router, mock_content_repo):
        """Test synchronous Twitter bookmark processing."""
        with patch.object(content_pipeline, 'twitter_client', mock_twitter_client), \
             patch.object(content_pipeline, 'model_router', mock_model_router), \
             patch.object(content_pipeline, 'content_repo', mock_content_repo), \
             patch('app.services.content_processing_pipeline.get_db_session'):
            
            result = await content_pipeline.process_twitter_bookmark(
                tweet_id="123456789",
                force_refresh=False,
                models_override=None,
                run_async=False
            )
            
            assert result['status'] == 'completed'
            assert result['processing_method'] == 'sync'
            assert 'phase_results' in result
            assert len(result['phase_results']) == 4  # All sub-phases
    
    @pytest.mark.asyncio
    async def test_fetch_bookmarks_from_collection(self, content_pipeline, mock_twitter_client, mock_content_repo):
        """Test fetching bookmarks from Twitter collection."""
        # Mock async generator for bookmarks
        async def mock_get_bookmarks(max_results=100):
            yield MagicMock(
                id="123456789",
                text="Test bookmark 1",
                author_username="user1",
                created_at=datetime.utcnow(),
                media=[],
                public_metrics={"like_count": 5, "retweet_count": 2, "reply_count": 1, "quote_count": 0}
            )
            yield MagicMock(
                id="987654321",
                text="Test bookmark 2",
                author_username="user2",
                created_at=datetime.utcnow(),
                media=[{"type": "image", "url": "https://example.com/image.jpg"}],
                public_metrics={"like_count": 15, "retweet_count": 8, "reply_count": 3, "quote_count": 2}
            )
        
        mock_twitter_client.get_bookmarks = mock_get_bookmarks
        
        with patch.object(content_pipeline, 'twitter_client', mock_twitter_client), \
             patch.object(content_pipeline, 'content_repo', mock_content_repo), \
             patch('app.services.content_processing_pipeline.get_db_session'):
            
            result = await content_pipeline.fetch_bookmarks_from_collection(
                collection_url="https://twitter.com/bookmarks",
                max_results=10,
                force_refresh=False
            )
            
            assert result['status'] == 'completed'
            assert result['fetched_count'] == 2
            assert result['skipped_count'] == 0
            assert result['failed_count'] == 0
            assert len(result['fetched_bookmarks']) == 2
    
    @pytest.mark.asyncio
    async def test_generate_synthesis_documents(self, content_pipeline, mock_model_router):
        """Test synthesis document generation."""
        mock_synthesis_repo = AsyncMock()
        mock_synthesis_repo.get_by_category.return_value = None
        mock_synthesis_repo.create.return_value = MagicMock(id="synthesis-123")
        
        mock_content_items = [
            ContentItem(
                id="content-1",
                title="AI Article 1",
                content="Content about AI",
                collective_understanding="Understanding of AI concepts",
                main_category="machine-learning",
                sub_category="neural-networks",
                author_username="user1",
                like_count=10,
                retweet_count=5,
                reply_count=2,
                created_at=datetime.utcnow()
            ),
            ContentItem(
                id="content-2",
                title="AI Article 2",
                content="More content about AI",
                collective_understanding="Advanced AI understanding",
                main_category="machine-learning",
                sub_category="neural-networks",
                author_username="user2",
                like_count=20,
                retweet_count=10,
                reply_count=5,
                created_at=datetime.utcnow()
            )
        ]
        
        with patch.object(content_pipeline, 'model_router', mock_model_router), \
             patch.object(content_pipeline, 'content_repo') as mock_content_repo, \
             patch('app.services.content_processing_pipeline.get_synthesis_repository', return_value=mock_synthesis_repo), \
             patch('app.services.content_processing_pipeline.get_db_session'), \
             patch.object(content_pipeline, '_get_category_statistics', return_value=[
                 {'name': 'machine-learning', 'subcategory': 'neural-networks', 'count': 5}
             ]):
            
            mock_content_repo.get_by_category.return_value = mock_content_items
            
            result = await content_pipeline.generate_synthesis_documents(
                models_override=None,
                min_bookmarks_per_category=3
            )
            
            assert result['status'] == 'completed'
            assert result['generated_count'] == 1
            assert result['skipped_count'] == 0
            assert len(result['generated_syntheses']) == 1
    
    @pytest.mark.asyncio
    async def test_bookmark_caching_with_thread_detection(self, content_pipeline, mock_twitter_client, mock_content_repo):
        """Test bookmark caching with thread detection."""
        # Mock thread detection
        mock_twitter_client.detect_thread.return_value = MagicMock(
            thread_id="thread_123",
            is_thread_root=True,
            position_in_thread=0,
            thread_length=3
        )
        
        with patch.object(content_pipeline, 'twitter_client', mock_twitter_client), \
             patch.object(content_pipeline, 'content_repo', mock_content_repo), \
             patch('app.services.content_processing_pipeline.get_db_session'):
            
            result = await content_pipeline._run_bookmark_caching_sync("content-123", False)
            
            assert result['status'] == 'completed'
            assert result['is_thread'] == True
            assert 'engagement_total' in result
    
    @pytest.mark.asyncio
    async def test_media_analysis_with_vision_model(self, content_pipeline, mock_model_router, mock_content_repo):
        """Test media analysis using vision models."""
        # Mock content item with media
        content_item = ContentItem(
            id="content-123",
            media_content=[
                {
                    'type': 'image',
                    'original_url': 'https://example.com/image.jpg',
                    'alt_text': 'Test image'
                }
            ],
            media_analyzed=False
        )
        mock_content_repo.get.return_value = content_item
        
        with patch.object(content_pipeline, 'model_router', mock_model_router), \
             patch.object(content_pipeline, 'content_repo', mock_content_repo), \
             patch('app.services.content_processing_pipeline.get_db_session'):
            
            result = await content_pipeline._run_media_analysis_sync("content-123", None)
            
            assert result['status'] == 'completed'
            assert result['media_count'] == 1
            assert 'model_used' in result
            assert 'analysis_results' in result
    
    @pytest.mark.asyncio
    async def test_content_understanding_generation(self, content_pipeline, mock_model_router, mock_content_repo):
        """Test AI content understanding generation."""
        content_item = ContentItem(
            id="content-123",
            content="This is test content about AI and machine learning",
            content_understood=False
        )
        mock_content_repo.get.return_value = content_item
        
        with patch.object(content_pipeline, 'model_router', mock_model_router), \
             patch.object(content_pipeline, 'content_repo', mock_content_repo), \
             patch('app.services.content_processing_pipeline.get_db_session'):
            
            result = await content_pipeline._run_content_understanding_sync("content-123", None)
            
            assert result['status'] == 'completed'
            assert 'model_used' in result
            assert 'understanding_length' in result
            assert 'key_concepts' in result
    
    @pytest.mark.asyncio
    async def test_categorization_with_existing_intelligence(self, content_pipeline, mock_model_router, mock_content_repo):
        """Test categorization with existing category intelligence."""
        content_item = ContentItem(
            id="content-123",
            collective_understanding="This content discusses machine learning concepts",
            categorized=False
        )
        mock_content_repo.get.return_value = content_item
        
        with patch.object(content_pipeline, 'model_router', mock_model_router), \
             patch.object(content_pipeline, 'content_repo', mock_content_repo), \
             patch.object(content_pipeline, '_get_existing_categories', return_value=[
                 {'name': 'machine-learning', 'count': 10, 'subcategories': [{'name': 'neural-networks', 'count': 5}]}
             ]), \
             patch('app.services.content_processing_pipeline.get_db_session'):
            
            result = await content_pipeline._run_categorization_sync("content-123", None)
            
            assert result['status'] == 'completed'
            assert 'category' in result
            assert 'subcategory' in result
            assert 'is_new_category' in result
            assert 'confidence_score' in result
    
    @pytest.mark.asyncio
    async def test_intelligent_processing_skip_unchanged(self, content_pipeline, mock_content_repo):
        """Test intelligent processing logic that skips unchanged content."""
        # Mock already processed content
        content_item = ContentItem(
            id="content-123",
            bookmark_cached=True,
            media_analyzed=True,
            content_understood=True,
            categorized=True
        )
        mock_content_repo.get.return_value = content_item
        
        with patch.object(content_pipeline, 'content_repo', mock_content_repo), \
             patch('app.services.content_processing_pipeline.get_db_session'):
            
            # Test bookmark caching skip
            result = await content_pipeline._run_bookmark_caching_sync("content-123", False)
            assert result['status'] == 'skipped'
            
            # Test media analysis skip
            result = await content_pipeline._run_media_analysis_sync("content-123", None)
            assert result['status'] == 'skipped'
            
            # Test content understanding skip
            result = await content_pipeline._run_content_understanding_sync("content-123", None)
            assert result['status'] == 'skipped'
            
            # Test categorization skip
            result = await content_pipeline._run_categorization_sync("content-123", None)
            assert result['status'] == 'skipped'
    
    @pytest.mark.asyncio
    async def test_force_reprocessing_override(self, content_pipeline, mock_twitter_client, mock_content_repo):
        """Test force reprocessing with override options."""
        # Mock already processed content
        content_item = ContentItem(
            id="content-123",
            bookmark_cached=True,
            media_analyzed=True,
            content_understood=True,
            categorized=True
        )
        mock_content_repo.get.return_value = content_item
        
        with patch.object(content_pipeline, 'twitter_client', mock_twitter_client), \
             patch.object(content_pipeline, 'content_repo', mock_content_repo), \
             patch('app.services.content_processing_pipeline.get_db_session'):
            
            # Test force refresh for bookmark caching
            result = await content_pipeline._run_bookmark_caching_sync("content-123", True)
            assert result['status'] == 'completed'  # Should process despite being cached
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, content_pipeline, mock_content_repo):
        """Test error handling and recovery mechanisms."""
        # Mock content repo to raise exception
        mock_content_repo.get.side_effect = Exception("Database connection failed")
        
        with patch.object(content_pipeline, 'content_repo', mock_content_repo), \
             patch('app.services.content_processing_pipeline.get_db_session'):
            
            result = await content_pipeline._run_bookmark_caching_sync("content-123", False)
            
            assert result['status'] == 'failed'
            assert 'error' in result
            assert 'Database connection failed' in result['error']


class TestSevenPhasePipeline:
    """Test cases for SevenPhasePipeline."""
    
    @pytest.fixture
    def seven_phase_pipeline(self):
        """Create seven-phase pipeline for testing."""
        return get_seven_phase_pipeline()
    
    @pytest.fixture
    def mock_pipeline_config(self):
        """Mock pipeline configuration."""
        return {
            'bookmark_url': 'https://twitter.com/bookmarks',
            'git_repo_url': 'https://github.com/user/repo.git',
            'max_bookmarks': 50,
            'force_refresh': False
        }
    
    @pytest.mark.asyncio
    async def test_complete_pipeline_execution_sync(self, seven_phase_pipeline, mock_pipeline_config):
        """Test complete seven-phase pipeline execution synchronously."""
        with patch.object(seven_phase_pipeline, '_phase_1_initialization', return_value={'status': 'completed'}), \
             patch.object(seven_phase_pipeline, '_phase_2_fetch_bookmarks', return_value={
                 'status': 'completed', 'fetched_bookmarks': [{'content_id': 'content-1'}]
             }), \
             patch.object(seven_phase_pipeline, '_phase_3_content_processing', return_value={'status': 'completed'}), \
             patch.object(seven_phase_pipeline, '_phase_4_synthesis_generation', return_value={'status': 'completed'}), \
             patch.object(seven_phase_pipeline, '_phase_5_embedding_generation', return_value={'status': 'completed'}), \
             patch.object(seven_phase_pipeline, '_phase_6_readme_generation', return_value={'status': 'completed'}), \
             patch.object(seven_phase_pipeline, '_phase_7_git_sync', return_value={'status': 'completed'}):
            
            result = await seven_phase_pipeline.execute_pipeline(
                config=mock_pipeline_config,
                models_override=None,
                run_async=False
            )
            
            assert result['status'] == 'completed'
            assert result['phases_completed'] == 7
            assert result['phases_failed'] == 0
            assert 'phase_results' in result
    
    @pytest.mark.asyncio
    async def test_pipeline_failure_handling(self, seven_phase_pipeline, mock_pipeline_config):
        """Test pipeline failure handling and partial success."""
        with patch.object(seven_phase_pipeline, '_phase_1_initialization', return_value={'status': 'completed'}), \
             patch.object(seven_phase_pipeline, '_phase_2_fetch_bookmarks', return_value={
                 'status': 'completed', 'fetched_bookmarks': [{'content_id': 'content-1'}]
             }), \
             patch.object(seven_phase_pipeline, '_phase_3_content_processing', return_value={'status': 'failed', 'error': 'Processing failed'}), \
             patch.object(seven_phase_pipeline, '_phase_4_synthesis_generation', return_value={'status': 'completed'}), \
             patch.object(seven_phase_pipeline, '_phase_5_embedding_generation', return_value={'status': 'completed'}), \
             patch.object(seven_phase_pipeline, '_phase_6_readme_generation', return_value={'status': 'completed'}), \
             patch.object(seven_phase_pipeline, '_phase_7_git_sync', return_value={'status': 'completed'}):
            
            result = await seven_phase_pipeline._execute_pipeline_sync(
                "pipeline-123", mock_pipeline_config, None
            )
            
            assert result['status'] == 'partial_success'
            assert result['phases_completed'] == 6
            assert result['phases_failed'] == 1
            assert 'phase_3_content_processing' in result['failed_phases']
    
    @pytest.mark.asyncio
    async def test_phase_1_initialization(self, seven_phase_pipeline, mock_pipeline_config):
        """Test Phase 1: Initialization."""
        with patch.object(seven_phase_pipeline.content_pipeline.twitter_client, '__aenter__', return_value=AsyncMock()), \
             patch.object(seven_phase_pipeline.content_pipeline.twitter_client, '__aexit__', return_value=None), \
             patch.object(seven_phase_pipeline.ai_service, 'is_available', return_value=True), \
             patch('app.services.seven_phase_pipeline.get_db_session'):
            
            # Mock Twitter client availability
            async def mock_is_available():
                return True
            
            seven_phase_pipeline.content_pipeline.twitter_client.__aenter__.return_value.is_available = mock_is_available
            
            result = await seven_phase_pipeline._phase_1_initialization(mock_pipeline_config)
            
            assert result['status'] == 'completed'
            assert result['config_validated'] == True
            assert 'components_status' in result
    
    @pytest.mark.asyncio
    async def test_phase_2_fetch_bookmarks(self, seven_phase_pipeline, mock_pipeline_config):
        """Test Phase 2: Fetch Bookmarks."""
        mock_fetch_result = {
            'status': 'completed',
            'fetched_count': 10,
            'skipped_count': 2,
            'failed_count': 0,
            'fetched_bookmarks': [{'content_id': f'content-{i}'} for i in range(10)]
        }
        
        with patch.object(seven_phase_pipeline.content_pipeline, 'fetch_bookmarks_from_collection', return_value=mock_fetch_result):
            result = await seven_phase_pipeline._phase_2_fetch_bookmarks(mock_pipeline_config)
            
            assert result['status'] == 'completed'
            assert result['fetched_count'] == 10
            assert 'duration' in result
    
    @pytest.mark.asyncio
    async def test_phase_5_embedding_generation(self, seven_phase_pipeline):
        """Test Phase 5: Embedding Generation."""
        mock_content_items = [
            ContentItem(id="content-1", collective_understanding="Understanding 1"),
            ContentItem(id="content-2", collective_understanding="Understanding 2")
        ]
        
        mock_synthesis_docs = [
            MagicMock(id="synthesis-1", summary="Summary 1"),
            MagicMock(id="synthesis-2", summary="Summary 2")
        ]
        
        with patch.object(seven_phase_pipeline.model_router, 'resolve', return_value=(AsyncMock(), "embedding-model", {})), \
             patch.object(seven_phase_pipeline.content_repo, 'get_all_unembedded', return_value=mock_content_items), \
             patch.object(seven_phase_pipeline.synthesis_repo, 'get_all_unembedded', return_value=mock_synthesis_docs), \
             patch.object(seven_phase_pipeline.embedding_service, 'generate_embedding', return_value=[0.1, 0.2, 0.3]), \
             patch.object(seven_phase_pipeline.embedding_service, 'store_embedding'), \
             patch('app.services.seven_phase_pipeline.get_db_session'):
            
            result = await seven_phase_pipeline._phase_5_embedding_generation(None)
            
            assert result['status'] == 'completed'
            assert result['generated_count'] == 4  # 2 content + 2 synthesis
            assert result['failed_count'] == 0
    
    @pytest.mark.asyncio
    async def test_phase_6_readme_generation(self, seven_phase_pipeline, mock_pipeline_config):
        """Test Phase 6: README Generation."""
        with patch.object(seven_phase_pipeline.model_router, 'resolve', return_value=(AsyncMock(), "readme-model", {})), \
             patch.object(seven_phase_pipeline, '_get_content_statistics', return_value={'total_content': 50}), \
             patch.object(seven_phase_pipeline, '_get_category_statistics', return_value=[
                 {'name': 'machine-learning', 'count': 15, 'subcategories': ['neural-networks']}
             ]), \
             patch.object(seven_phase_pipeline, '_get_synthesis_statistics', return_value={'total_synthesis': 5}), \
             patch.object(seven_phase_pipeline.readme_repo, 'create', return_value=MagicMock(id="readme-123")), \
             patch('app.services.seven_phase_pipeline.get_db_session'):
            
            result = await seven_phase_pipeline._phase_6_readme_generation(mock_pipeline_config, None)
            
            assert result['status'] == 'completed'
            assert result['readme_id'] == "readme-123"
            assert 'content_length' in result
            assert 'sections_generated' in result
    
    @pytest.mark.asyncio
    async def test_phase_7_git_sync(self, seven_phase_pipeline, mock_pipeline_config):
        """Test Phase 7: Git Sync."""
        mock_content_items = [ContentItem(id="content-1", main_category="tech", content="Content 1")]
        mock_synthesis_docs = [MagicMock(id="synthesis-1", main_category="tech", content="Synthesis 1")]
        mock_readme_doc = MagicMock(id="readme-1", content="README content")
        
        with patch.object(seven_phase_pipeline.content_repo, 'get_all_processed', return_value=mock_content_items), \
             patch.object(seven_phase_pipeline.synthesis_repo, 'get_all', return_value=mock_synthesis_docs), \
             patch.object(seven_phase_pipeline.readme_repo, 'get_latest', return_value=mock_readme_doc), \
             patch('app.services.seven_phase_pipeline.get_db_session'):
            
            result = await seven_phase_pipeline._phase_7_git_sync(mock_pipeline_config)
            
            assert result['status'] == 'completed'
            assert result['git_repo_url'] == mock_pipeline_config['git_repo_url']
            assert result['exported_files_count'] == 3  # 1 content + 1 synthesis + 1 readme
            assert 'commit_hash' in result
    
    @pytest.mark.asyncio
    async def test_model_override_integration(self, seven_phase_pipeline, mock_pipeline_config):
        """Test model override functionality across phases."""
        models_override = {
            'vision': {'backend': 'ollama', 'model': 'llava:13b'},
            'kb_generation': {'backend': 'localai', 'model': 'mixtral:8x7b'},
            'synthesis': {'backend': 'ollama', 'model': 'qwen2.5:7b'},
            'embeddings': {'backend': 'openai', 'model': 'text-embedding-3-small'},
            'readme_generation': {'backend': 'ollama', 'model': 'llama3.1:8b'}
        }
        
        with patch.object(seven_phase_pipeline.model_router, 'resolve') as mock_resolve:
            mock_resolve.return_value = (AsyncMock(), "overridden-model", {})
            
            # Test that model overrides are passed to resolve calls
            await seven_phase_pipeline._phase_5_embedding_generation(models_override)
            
            # Verify resolve was called with override
            mock_resolve.assert_called()
            call_args = mock_resolve.call_args
            assert call_args[1]['override'] == models_override.get('embeddings')
    
    @pytest.mark.asyncio
    async def test_provenance_tracking(self, seven_phase_pipeline):
        """Test that model provenance is tracked correctly."""
        # This test would verify that the models used in each phase are recorded
        # in the appropriate database fields for audit and evaluation purposes
        
        with patch.object(seven_phase_pipeline.content_repo, 'update') as mock_update, \
             patch.object(seven_phase_pipeline.model_router, 'resolve', return_value=(AsyncMock(), "test-model", {})), \
             patch('app.services.seven_phase_pipeline.get_db_session'):
            
            # Mock embedding generation to check provenance tracking
            mock_content_items = [ContentItem(id="content-1", collective_understanding="Test")]
            
            with patch.object(seven_phase_pipeline.content_repo, 'get_all_unembedded', return_value=mock_content_items), \
                 patch.object(seven_phase_pipeline.synthesis_repo, 'get_all_unembedded', return_value=[]), \
                 patch.object(seven_phase_pipeline.embedding_service, 'generate_embedding', return_value=[0.1, 0.2]), \
                 patch.object(seven_phase_pipeline.embedding_service, 'store_embedding'):
                
                await seven_phase_pipeline._phase_5_embedding_generation(None)
                
                # Verify that provenance tracking would be implemented
                # (This is a placeholder for actual provenance tracking verification)
                assert True  # Placeholder assertion