"""
README generation service for creating structured index content.
"""
import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models import ReadmeContent, KnowledgeItem, ContentItem
from app.services.ai_service import get_ai_service
from app.services.model_router import get_model_router, ModelPhase
from app.database.connection import get_db_session


class ReadmeGeneratorService:
    """
    Service for generating README content and category indexes using AI.
    
    This service creates structured documentation for the knowledge base,
    including main README files, category indexes, and subcategory indexes.
    """
    
    def __init__(self):
        self.ai_service = get_ai_service()
        self.model_router = get_model_router()
    
    async def generate_main_readme(
        self, 
        models_override: Optional[Dict[str, Any]] = None
    ) -> ReadmeContent:
        """
        Generate the main README file for the knowledge base.
        
        Args:
            models_override: Optional model overrides for AI generation
            
        Returns:
            ReadmeContent: The generated main README content
        """
        async with get_db_session() as db:
            # Get statistics for the knowledge base
            stats = await self._get_knowledge_base_stats(db)
            
            # Get recent items for highlights
            recent_items = await self._get_recent_items(db, limit=5)
            
            # Get categories for navigation
            categories = await self._get_categories_with_counts(db)
            
            # Generate README content using AI
            backend, model, params = await self.model_router.resolve(
                ModelPhase.readme_generation,
                override=models_override.get("readme_generation") if models_override else None
            )
            
            prompt = self._build_main_readme_prompt(stats, recent_items, categories)
            
            content = await backend.generate_text(
                prompt=prompt,
                model=model,
                **params
            )
            
            # Create README content record
            readme_content = ReadmeContent(
                id=str(uuid.uuid4()),
                content_type="main_readme",
                title="Knowledge Base README",
                content=content,
                item_count=stats["total_items"],
                file_path="README.md",
                content_hash=self._calculate_content_hash(content),
                is_stale=False,
                generation_model_used=model,
                generation_prompt=prompt
            )
            
            # Save or update existing main README
            existing = await self._get_existing_readme(db, "main_readme")
            if existing:
                existing.content = content
                existing.item_count = stats["total_items"]
                existing.content_hash = readme_content.content_hash
                existing.is_stale = False
                existing.generation_model_used = model
                existing.generation_prompt = prompt
                existing.updated_at = datetime.utcnow()
                readme_content = existing
            else:
                db.add(readme_content)
            
            await db.commit()
            await db.refresh(readme_content)
            
            return readme_content
    
    async def generate_category_index(
        self, 
        category: str,
        models_override: Optional[Dict[str, Any]] = None
    ) -> ReadmeContent:
        """
        Generate an index file for a specific category.
        
        Args:
            category: The category to generate an index for
            models_override: Optional model overrides for AI generation
            
        Returns:
            ReadmeContent: The generated category index content
        """
        async with get_db_session() as db:
            # Get items in this category
            items = await self._get_category_items(db, category)
            
            # Get subcategories
            subcategories = await self._get_subcategories_with_counts(db, category)
            
            # Generate index content using AI
            backend, model, params = await self.model_router.resolve(
                ModelPhase.readme_generation,
                override=models_override.get("readme_generation") if models_override else None
            )
            
            prompt = self._build_category_index_prompt(category, items, subcategories)
            
            content = await backend.generate_text(
                prompt=prompt,
                model=model,
                **params
            )
            
            # Create category index record
            readme_content = ReadmeContent(
                id=str(uuid.uuid4()),
                content_type="category_index",
                category=category,
                title=f"{category.title()} - Category Index",
                content=content,
                item_count=len(items),
                file_path=f"{category}/README.md",
                content_hash=self._calculate_content_hash(content),
                is_stale=False,
                generation_model_used=model,
                generation_prompt=prompt
            )
            
            # Save or update existing category index
            existing = await self._get_existing_readme(db, "category_index", category=category)
            if existing:
                existing.content = content
                existing.item_count = len(items)
                existing.content_hash = readme_content.content_hash
                existing.is_stale = False
                existing.generation_model_used = model
                existing.generation_prompt = prompt
                existing.updated_at = datetime.utcnow()
                readme_content = existing
            else:
                db.add(readme_content)
            
            await db.commit()
            await db.refresh(readme_content)
            
            return readme_content
    
    async def generate_subcategory_index(
        self, 
        category: str,
        subcategory: str,
        models_override: Optional[Dict[str, Any]] = None
    ) -> ReadmeContent:
        """
        Generate an index file for a specific subcategory.
        
        Args:
            category: The main category
            subcategory: The subcategory to generate an index for
            models_override: Optional model overrides for AI generation
            
        Returns:
            ReadmeContent: The generated subcategory index content
        """
        async with get_db_session() as db:
            # Get items in this subcategory
            items = await self._get_subcategory_items(db, category, subcategory)
            
            # Generate index content using AI
            backend, model, params = await self.model_router.resolve(
                ModelPhase.readme_generation,
                override=models_override.get("readme_generation") if models_override else None
            )
            
            prompt = self._build_subcategory_index_prompt(category, subcategory, items)
            
            content = await backend.generate_text(
                prompt=prompt,
                model=model,
                **params
            )
            
            # Create subcategory index record
            readme_content = ReadmeContent(
                id=str(uuid.uuid4()),
                content_type="subcategory_index",
                category=category,
                subcategory=subcategory,
                title=f"{subcategory.title()} - Subcategory Index",
                content=content,
                item_count=len(items),
                file_path=f"{category}/{subcategory}/README.md",
                content_hash=self._calculate_content_hash(content),
                is_stale=False,
                generation_model_used=model,
                generation_prompt=prompt
            )
            
            # Save or update existing subcategory index
            existing = await self._get_existing_readme(
                db, "subcategory_index", 
                category=category, 
                subcategory=subcategory
            )
            if existing:
                existing.content = content
                existing.item_count = len(items)
                existing.content_hash = readme_content.content_hash
                existing.is_stale = False
                existing.generation_model_used = model
                existing.generation_prompt = prompt
                existing.updated_at = datetime.utcnow()
                readme_content = existing
            else:
                db.add(readme_content)
            
            await db.commit()
            await db.refresh(readme_content)
            
            return readme_content
    
    async def mark_stale_content(self, content_type: str, **filters) -> int:
        """
        Mark README content as stale when underlying data changes.
        
        Args:
            content_type: Type of content to mark stale
            **filters: Additional filters (category, subcategory)
            
        Returns:
            int: Number of items marked as stale
        """
        async with get_db_session() as db:
            query = select(ReadmeContent).where(ReadmeContent.content_type == content_type)
            
            if "category" in filters:
                query = query.where(ReadmeContent.category == filters["category"])
            if "subcategory" in filters:
                query = query.where(ReadmeContent.subcategory == filters["subcategory"])
            
            result = await db.execute(query)
            items = result.scalars().all()
            
            count = 0
            for item in items:
                item.is_stale = True
                item.updated_at = datetime.utcnow()
                count += 1
            
            await db.commit()
            return count
    
    async def get_stale_content(self) -> List[ReadmeContent]:
        """
        Get all README content that needs regeneration.
        
        Returns:
            List[ReadmeContent]: List of stale README content items
        """
        async with get_db_session() as db:
            result = await db.execute(
                select(ReadmeContent).where(ReadmeContent.is_stale == True)
            )
            return result.scalars().all()
    
    async def regenerate_all_stale_content(
        self, 
        models_override: Optional[Dict[str, Any]] = None
    ) -> List[ReadmeContent]:
        """
        Regenerate all stale README content.
        
        Args:
            models_override: Optional model overrides for AI generation
            
        Returns:
            List[ReadmeContent]: List of regenerated content items
        """
        stale_items = await self.get_stale_content()
        regenerated = []
        
        for item in stale_items:
            if item.content_type == "main_readme":
                new_item = await self.generate_main_readme(models_override)
            elif item.content_type == "category_index":
                new_item = await self.generate_category_index(item.category, models_override)
            elif item.content_type == "subcategory_index":
                new_item = await self.generate_subcategory_index(
                    item.category, item.subcategory, models_override
                )
            else:
                continue
            
            regenerated.append(new_item)
        
        return regenerated
    
    # Private helper methods
    
    async def _get_knowledge_base_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get statistics about the knowledge base."""
        # Total items
        total_result = await db.execute(select(func.count(KnowledgeItem.id)))
        total_items = total_result.scalar() or 0
        
        # Categories count
        categories_result = await db.execute(
            select(func.count(func.distinct(ContentItem.main_category)))
            .where(ContentItem.main_category.isnot(None))
        )
        categories_count = categories_result.scalar() or 0
        
        # Recent items count (last 30 days)
        thirty_days_ago = datetime.utcnow().replace(day=1)  # Simplified for example
        recent_result = await db.execute(
            select(func.count(KnowledgeItem.id))
            .where(KnowledgeItem.created_at >= thirty_days_ago)
        )
        recent_items = recent_result.scalar() or 0
        
        return {
            "total_items": total_items,
            "categories_count": categories_count,
            "recent_items": recent_items,
            "last_updated": datetime.utcnow()
        }
    
    async def _get_recent_items(self, db: AsyncSession, limit: int = 5) -> List[KnowledgeItem]:
        """Get recent knowledge items."""
        result = await db.execute(
            select(KnowledgeItem)
            .order_by(KnowledgeItem.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def _get_categories_with_counts(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Get categories with item counts."""
        result = await db.execute(
            select(
                ContentItem.main_category,
                func.count(KnowledgeItem.id).label("count")
            )
            .join(KnowledgeItem, ContentItem.id == KnowledgeItem.content_item_id)
            .where(ContentItem.main_category.isnot(None))
            .group_by(ContentItem.main_category)
            .order_by(func.count(KnowledgeItem.id).desc())
        )
        
        return [
            {"category": row.main_category, "count": row.count}
            for row in result.all()
        ]
    
    async def _get_category_items(self, db: AsyncSession, category: str) -> List[KnowledgeItem]:
        """Get knowledge items for a specific category."""
        result = await db.execute(
            select(KnowledgeItem)
            .join(ContentItem, KnowledgeItem.content_item_id == ContentItem.id)
            .where(ContentItem.main_category == category)
            .order_by(KnowledgeItem.created_at.desc())
        )
        return result.scalars().all()
    
    async def _get_subcategories_with_counts(
        self, 
        db: AsyncSession, 
        category: str
    ) -> List[Dict[str, Any]]:
        """Get subcategories for a category with item counts."""
        result = await db.execute(
            select(
                ContentItem.sub_category,
                func.count(KnowledgeItem.id).label("count")
            )
            .join(KnowledgeItem, ContentItem.id == KnowledgeItem.content_item_id)
            .where(
                and_(
                    ContentItem.main_category == category,
                    ContentItem.sub_category.isnot(None)
                )
            )
            .group_by(ContentItem.sub_category)
            .order_by(func.count(KnowledgeItem.id).desc())
        )
        
        return [
            {"subcategory": row.sub_category, "count": row.count}
            for row in result.all()
        ]
    
    async def _get_subcategory_items(
        self, 
        db: AsyncSession, 
        category: str, 
        subcategory: str
    ) -> List[KnowledgeItem]:
        """Get knowledge items for a specific subcategory."""
        result = await db.execute(
            select(KnowledgeItem)
            .join(ContentItem, KnowledgeItem.content_item_id == ContentItem.id)
            .where(
                and_(
                    ContentItem.main_category == category,
                    ContentItem.sub_category == subcategory
                )
            )
            .order_by(KnowledgeItem.created_at.desc())
        )
        return result.scalars().all()
    
    async def _get_existing_readme(
        self, 
        db: AsyncSession, 
        content_type: str,
        category: Optional[str] = None,
        subcategory: Optional[str] = None
    ) -> Optional[ReadmeContent]:
        """Get existing README content."""
        query = select(ReadmeContent).where(ReadmeContent.content_type == content_type)
        
        if category:
            query = query.where(ReadmeContent.category == category)
        if subcategory:
            query = query.where(ReadmeContent.subcategory == subcategory)
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    def _calculate_content_hash(self, content: str) -> str:
        """Calculate hash of content for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _build_main_readme_prompt(
        self, 
        stats: Dict[str, Any],
        recent_items: List[KnowledgeItem],
        categories: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for main README generation."""
        recent_titles = [item.display_title for item in recent_items[:3]]
        category_list = [f"- {cat['category']} ({cat['count']} items)" for cat in categories[:10]]
        
        return f"""Generate a comprehensive README.md file for a knowledge base with the following information:

STATISTICS:
- Total knowledge items: {stats['total_items']}
- Categories: {stats['categories_count']}
- Recent additions: {stats['recent_items']} items this month

RECENT HIGHLIGHTS:
{chr(10).join(f"- {title}" for title in recent_titles)}

TOP CATEGORIES:
{chr(10).join(category_list)}

Please create a professional README that includes:
1. A compelling introduction to the knowledge base
2. Overview of the content and organization
3. Navigation guide for categories
4. Statistics and recent updates
5. How to use and contribute to the knowledge base

Use markdown formatting with proper headers, lists, and emphasis. Make it engaging and informative."""
    
    def _build_category_index_prompt(
        self, 
        category: str,
        items: List[KnowledgeItem],
        subcategories: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for category index generation."""
        item_titles = [item.display_title for item in items[:10]]
        subcategory_list = [f"- {sub['subcategory']} ({sub['count']} items)" for sub in subcategories]
        
        return f"""Generate a category index README.md file for the "{category}" category with the following information:

CATEGORY: {category.title()}
TOTAL ITEMS: {len(items)}

SUBCATEGORIES:
{chr(10).join(subcategory_list) if subcategory_list else "No subcategories"}

RECENT ITEMS:
{chr(10).join(f"- {title}" for title in item_titles)}

Please create a category index that includes:
1. Introduction to the {category} category
2. Overview of topics covered
3. Subcategory navigation (if any)
4. Featured or recent items
5. Organization and structure explanation

Use markdown formatting with proper headers and navigation links."""
    
    def _build_subcategory_index_prompt(
        self, 
        category: str,
        subcategory: str,
        items: List[KnowledgeItem]
    ) -> str:
        """Build prompt for subcategory index generation."""
        item_titles = [item.display_title for item in items[:15]]
        
        return f"""Generate a subcategory index README.md file for "{subcategory}" under "{category}" with the following information:

CATEGORY: {category.title()}
SUBCATEGORY: {subcategory.title()}
TOTAL ITEMS: {len(items)}

ITEMS IN THIS SUBCATEGORY:
{chr(10).join(f"- {title}" for title in item_titles)}

Please create a subcategory index that includes:
1. Introduction to the {subcategory} subcategory
2. Context within the broader {category} category
3. List of all items with brief descriptions
4. Key themes and topics covered
5. Related subcategories or cross-references

Use markdown formatting with proper headers and organized lists."""


# Singleton instance
_readme_generator_service: Optional[ReadmeGeneratorService] = None


def get_readme_generator_service() -> ReadmeGeneratorService:
    """Get the singleton README generator service instance."""
    global _readme_generator_service
    if _readme_generator_service is None:
        _readme_generator_service = ReadmeGeneratorService()
    return _readme_generator_service