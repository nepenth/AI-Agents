"""
Legacy content processing pipeline tests.

Note: This file contains legacy tests for the old content processing system.
The new comprehensive tests are in test_content_processing_pipeline_integration.py
"""

import pytest
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from app.services.content_processing_pipeline import get_content_processing_pipeline
from app.services.media_processor import get_media_processor
from app.services.content_categorizer import get_content_categorizer, CategoryResult
from app.services.knowledge_generator import get_knowledge_generator
from app.services.synthesis_generator import get_synthesis_generator
from app.models.content import ContentItem
from app.models.knowledge import KnowledgeItem


class TestLegacyContentProcessing:
    """Legacy tests for content processing components."""
    
    @pytest.mark.asyncio
    async def test_content_processing_pipeline_exists(self):
        """Test that the new content processing pipeline exists."""
        pipeline = get_content_processing_pipeline()
        assert pipeline is not None
        
        # Test that the pipeline has the expected methods
        assert hasattr(pipeline, 'process_twitter_bookmark')
        assert hasattr(pipeline, 'fetch_bookmarks_from_collection')
        assert hasattr(pipeline, 'generate_synthesis_documents')


    @pytest.mark.asyncio
    async def test_legacy_services_still_exist(self):
        """Test that legacy services still exist for backward compatibility."""
        # These services are still used by other parts of the system
        media_processor = get_media_processor()
        categorizer = get_content_categorizer()
        knowledge_generator = get_knowledge_generator()
        synthesis_generator = get_synthesis_generator()
        
        assert media_processor is not None
        assert categorizer is not None
        assert knowledge_generator is not None
        assert synthesis_generator is not None