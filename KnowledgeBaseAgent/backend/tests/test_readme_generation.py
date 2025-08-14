"""
Tests for README generation system.
"""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.services.readme_generator import ReadmeGeneratorService
from app.repositories.readme import ReadmeRepository
from app.models.readme import ReadmeContent
from app.models.knowledge import KnowledgeItem
from app.models.content import ContentItem


class TestReadmeGeneratorService:
    """Test cases for README generator service."""
    
    @pytest.fixture
    def readme_service(self):
        """Create README generator service for testing."""
        return ReadmeGeneratorService()
    
    @pytest.fixture
    def mock_ai_service(self):
        """Mock AI service for testing."""
        with patch('app.services.readme_generator.get_ai_service') as mock:
            ai_service = AsyncMock()
            ai_service.generate_text.return_value = "Generated README content"
            mock.return_value = ai_service
            yield ai_service
    
    @pytest.fixture
    def mock_model_router(self):
        """Mock model router for testing."""
        with patch('app.services.readme_generator.get_model_router') as mock:
            router = AsyncMock()
            router.resolve.return_value = (AsyncMock(), "test-model", {})
            mock.return_value = router
            yield router
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for testing."""
        with patch('app.services.readme_generator.get_db_session') as mock:
            db_session = AsyncMock()
            mock.return_value.__aenter__.return_value = db_session
            yield db_session
    
    @pytest.mark.asyncio
    async def test_generate_main_readme(
        self, 
        readme_service, 
        mock_ai_service, 
        mock_model_router,
        mock_db_session
    ):
        """Test main README generation."""
        # Mock database queries
        mock_db_session.execute.return_value.scalar.return_value = 10
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value.all.return_value = []
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        
        # Test generation
        result = await readme_service.generate_main_readme()
        
        # Verify AI service was called
        mock_ai_service.generate_text.assert_called_once()
        
        # Verify model router was used
        mock_model_router.resolve.assert_called_once()
        
        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_category_index(
        self, 
        readme_service, 
        mock_ai_service, 
        mock_model_router,
        mock_db_session
    ):
        """Test category index generation."""
        # Mock database queries
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value.all.return_value = []
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        
        # Test generation
        result = await readme_service.generate_category_index("technology")
        
        # Verify AI service was called with category-specific prompt
        mock_ai_service.generate_text.assert_called_once()
        call_args = mock_ai_service.generate_text.call_args
        assert "technology" in call_args.kwargs["prompt"].lower()
        
        # Verify model router was used
        mock_model_router.resolve.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_subcategory_index(
        self, 
        readme_service, 
        mock_ai_service, 
        mock_model_router,
        mock_db_session
    ):
        """Test subcategory index generation."""
        # Mock database queries
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        
        # Test generation
        result = await readme_service.generate_subcategory_index("technology", "ai")
        
        # Verify AI service was called with subcategory-specific prompt
        mock_ai_service.generate_text.assert_called_once()
        call_args = mock_ai_service.generate_text.call_args
        prompt = call_args.kwargs["prompt"].lower()
        assert "technology" in prompt
        assert "ai" in prompt
    
    @pytest.mark.asyncio
    async def test_mark_stale_content(
        self, 
        readme_service, 
        mock_db_session
    ):
        """Test marking content as stale."""
        # Mock existing README items
        mock_readme = ReadmeContent(
            id="test-id",
            content_type="category_index",
            category="technology",
            title="Test README",
            content="Test content",
            item_count=5,
            file_path="technology/README.md",
            is_stale=False
        )
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [mock_readme]
        
        # Test marking as stale
        count = await readme_service.mark_stale_content("category_index", category="technology")
        
        # Verify item was marked as stale
        assert mock_readme.is_stale == True
        assert count == 1
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_stale_content(
        self, 
        readme_service, 
        mock_db_session
    ):
        """Test getting stale content."""
        # Mock stale README items
        stale_items = [
            ReadmeContent(
                id="stale-1",
                content_type="main_readme",
                title="Stale Main README",
                content="Old content",
                item_count=10,
                file_path="README.md",
                is_stale=True
            ),
            ReadmeContent(
                id="stale-2",
                content_type="category_index",
                category="technology",
                title="Stale Category Index",
                content="Old category content",
                item_count=5,
                file_path="technology/README.md",
                is_stale=True
            )
        ]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = stale_items
        
        # Test getting stale content
        result = await readme_service.get_stale_content()
        
        # Verify correct items returned
        assert len(result) == 2
        assert all(item.is_stale for item in result)
    
    @pytest.mark.asyncio
    async def test_regenerate_all_stale_content(
        self, 
        readme_service, 
        mock_ai_service, 
        mock_model_router,
        mock_db_session
    ):
        """Test regenerating all stale content."""
        # Mock stale items
        stale_main = ReadmeContent(
            id="stale-main",
            content_type="main_readme",
            title="Stale Main README",
            content="Old content",
            item_count=10,
            file_path="README.md",
            is_stale=True
        )
        stale_category = ReadmeContent(
            id="stale-category",
            content_type="category_index",
            category="technology",
            title="Stale Category Index",
            content="Old category content",
            item_count=5,
            file_path="technology/README.md",
            is_stale=True
        )
        
        # Mock get_stale_content to return stale items
        with patch.object(readme_service, 'get_stale_content') as mock_get_stale:
            mock_get_stale.return_value = [stale_main, stale_category]
            
            # Mock individual generation methods
            with patch.object(readme_service, 'generate_main_readme') as mock_gen_main:
                with patch.object(readme_service, 'generate_category_index') as mock_gen_cat:
                    mock_gen_main.return_value = stale_main
                    mock_gen_cat.return_value = stale_category
                    
                    # Test regeneration
                    result = await readme_service.regenerate_all_stale_content()
                    
                    # Verify all methods were called
                    mock_gen_main.assert_called_once()
                    mock_gen_cat.assert_called_once_with("technology", None)
                    assert len(result) == 2
    
    def test_calculate_content_hash(self, readme_service):
        """Test content hash calculation."""
        content1 = "This is test content"
        content2 = "This is different content"
        content3 = "This is test content"  # Same as content1
        
        hash1 = readme_service._calculate_content_hash(content1)
        hash2 = readme_service._calculate_content_hash(content2)
        hash3 = readme_service._calculate_content_hash(content3)
        
        # Verify hashes
        assert hash1 != hash2  # Different content should have different hashes
        assert hash1 == hash3  # Same content should have same hash
        assert len(hash1) == 16  # Hash should be 16 characters (truncated SHA256)
    
    def test_build_main_readme_prompt(self, readme_service):
        """Test main README prompt building."""
        stats = {
            "total_items": 100,
            "categories_count": 10,
            "recent_items": 5
        }
        recent_items = [
            KnowledgeItem(id="1", display_title="Recent Item 1", content_item_id="c1", enhanced_content="content1"),
            KnowledgeItem(id="2", display_title="Recent Item 2", content_item_id="c2", enhanced_content="content2"),
            KnowledgeItem(id="3", display_title="Recent Item 3", content_item_id="c3", enhanced_content="content3")
        ]
        categories = [
            {"category": "technology", "count": 50},
            {"category": "science", "count": 30},
            {"category": "business", "count": 20}
        ]
        
        prompt = readme_service._build_main_readme_prompt(stats, recent_items, categories)
        
        # Verify prompt contains expected information
        assert "100" in prompt  # Total items
        assert "10" in prompt   # Categories count
        assert "5" in prompt    # Recent items
        assert "Recent Item 1" in prompt
        assert "technology" in prompt
        assert "science" in prompt
        assert "README" in prompt


class TestReadmeRepository:
    """Test cases for README repository."""
    
    @pytest.fixture
    def readme_repo(self):
        """Create README repository for testing."""
        return ReadmeRepository()
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for testing."""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_get_by_type(self, readme_repo, mock_db_session):
        """Test getting README content by type."""
        # Mock database result
        mock_items = [
            ReadmeContent(
                id="main-1",
                content_type="main_readme",
                title="Main README",
                content="Main content",
                item_count=100,
                file_path="README.md"
            )
        ]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_items
        
        # Test repository method
        result = await readme_repo.get_by_type(mock_db_session, "main_readme")
        
        # Verify result
        assert len(result) == 1
        assert result[0].content_type == "main_readme"
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_by_category(self, readme_repo, mock_db_session):
        """Test getting README content by category."""
        # Mock database result
        mock_items = [
            ReadmeContent(
                id="cat-1",
                content_type="category_index",
                category="technology",
                title="Technology Index",
                content="Tech content",
                item_count=50,
                file_path="technology/README.md"
            )
        ]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_items
        
        # Test repository method
        result = await readme_repo.get_by_category(mock_db_session, "technology")
        
        # Verify result
        assert len(result) == 1
        assert result[0].category == "technology"
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_stale_content(self, readme_repo, mock_db_session):
        """Test getting stale README content."""
        # Mock database result
        mock_items = [
            ReadmeContent(
                id="stale-1",
                content_type="main_readme",
                title="Stale README",
                content="Old content",
                item_count=10,
                file_path="README.md",
                is_stale=True
            )
        ]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_items
        
        # Test repository method
        result = await readme_repo.get_stale_content(mock_db_session)
        
        # Verify result
        assert len(result) == 1
        assert result[0].is_stale == True
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_mark_stale_by_category(self, readme_repo, mock_db_session):
        """Test marking README content as stale by category."""
        # Mock database result
        mock_item = ReadmeContent(
            id="cat-1",
            content_type="category_index",
            category="technology",
            title="Technology Index",
            content="Tech content",
            item_count=50,
            file_path="technology/README.md",
            is_stale=False
        )
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [mock_item]
        
        # Test repository method
        count = await readme_repo.mark_stale_by_category(mock_db_session, "technology")
        
        # Verify result
        assert count == 1
        assert mock_item.is_stale == True
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_content(self, readme_repo, mock_db_session):
        """Test searching README content."""
        # Mock database result
        mock_items = [
            ReadmeContent(
                id="search-1",
                content_type="main_readme",
                title="Technology README",
                content="Content about AI and machine learning",
                item_count=10,
                file_path="README.md"
            )
        ]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_items
        
        # Test repository method
        result = await readme_repo.search_content(mock_db_session, "technology")
        
        # Verify result
        assert len(result) == 1
        assert "Technology" in result[0].title
        mock_db_session.execute.assert_called_once()


@pytest.mark.integration
class TestReadmeGenerationIntegration:
    """Integration tests for README generation system."""
    
    @pytest.mark.asyncio
    async def test_full_readme_generation_workflow(self):
        """Test complete README generation workflow."""
        # This would be an integration test that:
        # 1. Creates sample knowledge items in the database
        # 2. Generates README content using the service
        # 3. Verifies the content is stored correctly
        # 4. Tests marking content as stale and regeneration
        
        # For now, this is a placeholder for the integration test
        # In a real implementation, this would use a test database
        pass