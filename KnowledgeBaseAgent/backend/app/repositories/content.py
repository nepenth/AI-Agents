"""
Repository for content item operations.
"""
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime

from app.models import ContentItem
from app.schemas.content import ContentItemFilter
from .base import BaseRepository


class ContentItemRepository(BaseRepository[ContentItem]):
    """Repository for content item operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(ContentItem, session)
    
    async def get_by_source(self, source_type: str, source_id: str) -> Optional[ContentItem]:
        """Get content item by source type and ID."""
        result = await self.session.execute(
            select(ContentItem).where(
                and_(
                    ContentItem.source_type == source_type,
                    ContentItem.source_id == source_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_processing_state(
        self, 
        state: str, 
        offset: int = 0, 
        limit: int = 100
    ) -> List[ContentItem]:
        """Get content items by processing state."""
        result = await self.session.execute(
            select(ContentItem)
            .where(ContentItem.processing_state == state)
            .order_by(ContentItem.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
    
# Factory helper for task modules needing a repository without DI container
_content_repo_singleton = None

def get_content_repository() -> ContentItemRepository:  # type: ignore[name-defined]
    """Return a lazily constructed ContentItemRepository.

    Tasks that import this should still prefer to use explicit DB sessions
    via app.database.connection.get_db_session for operations. This helper
    exists to satisfy imports and provide a default repository instance
    when one isn't injected.
    """
    global _content_repo_singleton
    if _content_repo_singleton is None:
        # Create a repository bound to a session factory; methods that need
        # a live session should receive one explicitly in calls to BaseRepository
        from app.database.connection import get_session_factory
        session_factory = get_session_factory()
        # Instantiate with a session placeholder; callers should pass sessions
        _content_repo_singleton = ContentItemRepository(session_factory())  # type: ignore[arg-type]
    return _content_repo_singleton

    async def get_by_category(
        self, 
        main_category: str, 
        sub_category: Optional[str] = None,
        offset: int = 0,
        limit: int = 100
    ) -> List[ContentItem]:
        """Get content items by category."""
        conditions = [ContentItem.main_category == main_category]
        
        if sub_category:
            conditions.append(ContentItem.sub_category == sub_category)
        
        result = await self.session.execute(
            select(ContentItem)
            .where(and_(*conditions))
            .order_by(ContentItem.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def search_content(
        self,
        query: str,
        filters: Optional[ContentItemFilter] = None,
        offset: int = 0,
        limit: int = 100
    ) -> Tuple[List[ContentItem], int]:
        """Search content items with optional filters."""
        # Build base query
        search_query = select(ContentItem)
        count_query = select(func.count(ContentItem.id))
        
        # Text search conditions
        text_conditions = [
            ContentItem.title.ilike(f"%{query}%"),
            ContentItem.content.ilike(f"%{query}%")
        ]
        
        base_condition = or_(*text_conditions)
        
        # Apply filters if provided
        if filters:
            filter_conditions = []
            
            if filters.source_type:
                filter_conditions.append(ContentItem.source_type == filters.source_type)
            
            if filters.processing_state:
                filter_conditions.append(ContentItem.processing_state == filters.processing_state)
            
            if filters.main_category:
                filter_conditions.append(ContentItem.main_category == filters.main_category)
            
            if filters.sub_category:
                filter_conditions.append(ContentItem.sub_category == filters.sub_category)
            
            if filters.has_media is not None:
                if filters.has_media:
                    filter_conditions.append(func.json_array_length(ContentItem.media_files) > 0)
                else:
                    filter_conditions.append(func.json_array_length(ContentItem.media_files) == 0)
            
            if filters.tags:
                # Check if any of the provided tags exist in the item's tags
                for tag in filters.tags:
                    filter_conditions.append(ContentItem.tags.op('@>')([tag]))
            
            if filters.created_after:
                created_after = datetime.fromisoformat(filters.created_after.replace('Z', '+00:00'))
                filter_conditions.append(ContentItem.created_at >= created_after)
            
            if filters.created_before:
                created_before = datetime.fromisoformat(filters.created_before.replace('Z', '+00:00'))
                filter_conditions.append(ContentItem.created_at <= created_before)
            
            if filter_conditions:
                base_condition = and_(base_condition, *filter_conditions)
        
        # Apply conditions to queries
        search_query = search_query.where(base_condition)
        count_query = count_query.where(base_condition)
        
        # Execute count query
        count_result = await self.session.execute(count_query)
        total = count_result.scalar()
        
        # Execute search query with pagination
        search_query = search_query.order_by(ContentItem.created_at.desc()).offset(offset).limit(limit)
        search_result = await self.session.execute(search_query)
        items = search_result.scalars().all()
        
        return items, total
    
    async def get_processing_stats(self) -> Dict[str, int]:
        """Get processing state statistics."""
        result = await self.session.execute(
            select(
                ContentItem.processing_state,
                func.count(ContentItem.id).label('count')
            )
            .group_by(ContentItem.processing_state)
        )
        
        stats = {}
        for row in result:
            stats[row.processing_state] = row.count
        
        return stats
    
    async def get_category_stats(self) -> Dict[str, int]:
        """Get category statistics."""
        result = await self.session.execute(
            select(
                ContentItem.main_category,
                func.count(ContentItem.id).label('count')
            )
            .where(ContentItem.main_category.is_not(None))
            .group_by(ContentItem.main_category)
        )
        
        stats = {}
        for row in result:
            stats[row.main_category] = row.count
        
        return stats
    
    async def get_source_stats(self) -> Dict[str, int]:
        """Get source type statistics."""
        result = await self.session.execute(
            select(
                ContentItem.source_type,
                func.count(ContentItem.id).label('count')
            )
            .group_by(ContentItem.source_type)
        )
        
        stats = {}
        for row in result:
            stats[row.source_type] = row.count
        
        return stats
    
    async def mark_as_processed(self, id: str, category: str, sub_category: str) -> Optional[ContentItem]:
        """Mark content item as processed with category assignment."""
        return await self.update(
            id,
            processing_state="completed",
            processed_at=datetime.utcnow(),
            main_category=category,
            sub_category=sub_category
        )
    
    async def get_unprocessed_items(self, limit: int = 100) -> List[ContentItem]:
        """Get unprocessed content items for batch processing."""
        result = await self.session.execute(
            select(ContentItem)
            .where(ContentItem.processing_state == "pending")
            .order_by(ContentItem.created_at.asc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_items_by_tags(self, tags: List[str], offset: int = 0, limit: int = 100) -> List[ContentItem]:
        """Get content items that have any of the specified tags."""
        conditions = []
        for tag in tags:
            conditions.append(ContentItem.tags.op('@>')([tag]))
        
        result = await self.session.execute(
            select(ContentItem)
            .where(or_(*conditions))
            .order_by(ContentItem.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_by_hash(self, content_hash: str) -> Optional[ContentItem]:
        """Get content item by hash."""
        result = await self.session.execute(
            select(ContentItem).where(ContentItem.content_hash == content_hash)
        )
        return result.scalar_one_or_none()
    
    async def get_by_metadata_field(self, field_name: str, field_value: str) -> List[ContentItem]:
        """Get content items by metadata field value."""
        result = await self.session.execute(
            select(ContentItem).where(
                ContentItem.metadata[field_name].astext == field_value
            )
        )
        return result.scalars().all()
    
    async def count_recent_items(self, hours: int = 24) -> int:
        """Count content items created in the last N hours."""
        from datetime import timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(func.count(ContentItem.id)).where(
                ContentItem.created_at >= cutoff_time
            )
        )
        return result.scalar() or 0
    
    async def count_duplicate_hashes(self) -> int:
        """Count duplicate content hashes."""
        result = await self.session.execute(
            select(func.count()).select_from(
                select(ContentItem.content_hash)
                .where(ContentItem.content_hash.isnot(None))
                .group_by(ContentItem.content_hash)
                .having(func.count(ContentItem.content_hash) > 1)
                .subquery()
            )
        )
        return result.scalar() or 0