"""
Repository for README content operations.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.readme import ReadmeContent
from app.repositories.base import BaseRepository


class ReadmeRepository(BaseRepository[ReadmeContent]):
    """Repository for README content operations."""
    
    def __init__(self):
        super().__init__(ReadmeContent)
    
    async def get_by_type(
        self, 
        db: AsyncSession, 
        content_type: str
    ) -> List[ReadmeContent]:
        """
        Get README content by type.
        
        Args:
            db: Database session
            content_type: Type of content to retrieve
            
        Returns:
            List[ReadmeContent]: List of README content items
        """
        result = await db.execute(
            select(ReadmeContent)
            .where(ReadmeContent.content_type == content_type)
            .order_by(ReadmeContent.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_by_category(
        self, 
        db: AsyncSession, 
        category: str,
        subcategory: Optional[str] = None
    ) -> List[ReadmeContent]:
        """
        Get README content by category and optionally subcategory.
        
        Args:
            db: Database session
            category: Category to filter by
            subcategory: Optional subcategory to filter by
            
        Returns:
            List[ReadmeContent]: List of README content items
        """
        query = select(ReadmeContent).where(ReadmeContent.category == category)
        
        if subcategory:
            query = query.where(ReadmeContent.subcategory == subcategory)
        
        result = await db.execute(
            query.order_by(ReadmeContent.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_stale_content(self, db: AsyncSession) -> List[ReadmeContent]:
        """
        Get all README content that is marked as stale.
        
        Args:
            db: Database session
            
        Returns:
            List[ReadmeContent]: List of stale README content items
        """
        result = await db.execute(
            select(ReadmeContent)
            .where(ReadmeContent.is_stale == True)
            .order_by(ReadmeContent.updated_at.asc())
        )
        return result.scalars().all()
    
    async def get_by_file_path(
        self, 
        db: AsyncSession, 
        file_path: str
    ) -> Optional[ReadmeContent]:
        """
        Get README content by file path.
        
        Args:
            db: Database session
            file_path: File path to search for
            
        Returns:
            Optional[ReadmeContent]: README content item if found
        """
        result = await db.execute(
            select(ReadmeContent).where(ReadmeContent.file_path == file_path)
        )
        return result.scalar_one_or_none()
    
    async def mark_stale_by_category(
        self, 
        db: AsyncSession, 
        category: str,
        subcategory: Optional[str] = None
    ) -> int:
        """
        Mark README content as stale by category.
        
        Args:
            db: Database session
            category: Category to mark as stale
            subcategory: Optional subcategory to mark as stale
            
        Returns:
            int: Number of items marked as stale
        """
        query = select(ReadmeContent).where(ReadmeContent.category == category)
        
        if subcategory:
            query = query.where(ReadmeContent.subcategory == subcategory)
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        count = 0
        for item in items:
            item.is_stale = True
            count += 1
        
        await db.commit()
        return count
    
    async def mark_all_stale(self, db: AsyncSession) -> int:
        """
        Mark all README content as stale.
        
        Args:
            db: Database session
            
        Returns:
            int: Number of items marked as stale
        """
        result = await db.execute(select(ReadmeContent))
        items = result.scalars().all()
        
        count = 0
        for item in items:
            item.is_stale = True
            count += 1
        
        await db.commit()
        return count
    
    async def get_content_for_export(self, db: AsyncSession) -> List[ReadmeContent]:
        """
        Get all README content that should be exported to Git.
        
        Args:
            db: Database session
            
        Returns:
            List[ReadmeContent]: List of README content items for export
        """
        result = await db.execute(
            select(ReadmeContent)
            .where(ReadmeContent.is_stale == False)
            .order_by(ReadmeContent.file_path)
        )
        return result.scalars().all()
    
    async def search_content(
        self, 
        db: AsyncSession, 
        query: str,
        content_type: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[ReadmeContent]:
        """
        Search README content by text query.
        
        Args:
            db: Database session
            query: Search query
            content_type: Optional content type filter
            category: Optional category filter
            
        Returns:
            List[ReadmeContent]: List of matching README content items
        """
        search_query = select(ReadmeContent).where(
            or_(
                ReadmeContent.title.ilike(f"%{query}%"),
                ReadmeContent.content.ilike(f"%{query}%")
            )
        )
        
        if content_type:
            search_query = search_query.where(ReadmeContent.content_type == content_type)
        
        if category:
            search_query = search_query.where(ReadmeContent.category == category)
        
        result = await db.execute(
            search_query.order_by(ReadmeContent.updated_at.desc())
        )
        return result.scalars().all()


# Singleton instance
_readme_repository: Optional[ReadmeRepository] = None


def get_readme_repository() -> ReadmeRepository:
    """Get the singleton README repository instance."""
    global _readme_repository
    if _readme_repository is None:
        _readme_repository = ReadmeRepository()
    return _readme_repository