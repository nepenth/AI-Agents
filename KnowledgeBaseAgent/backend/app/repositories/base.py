"""
Base repository class with common CRUD operations.
"""
from typing import Generic, TypeVar, Type, List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations."""
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def create(self, **kwargs) -> ModelType:
        """Create a new instance."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance
    
    async def get_by_id(self, id: str) -> Optional[ModelType]:
        """Get instance by ID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(
        self, 
        offset: int = 0, 
        limit: int = 100,
        order_by: Optional[str] = None
    ) -> List[ModelType]:
        """Get all instances with pagination."""
        query = select(self.model)
        
        if order_by:
            if hasattr(self.model, order_by):
                query = query.order_by(getattr(self.model, order_by))
        
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def update(self, id: str, **kwargs) -> Optional[ModelType]:
        """Update instance by ID."""
        # Remove None values
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        
        if not update_data:
            return await self.get_by_id(id)
        
        # Add updated_at if the model has it
        if hasattr(self.model, 'updated_at'):
            update_data['updated_at'] = datetime.utcnow()
        
        await self.session.execute(
            update(self.model)
            .where(self.model.id == id)
            .values(**update_data)
        )
        await self.session.commit()
        return await self.get_by_id(id)
    
    async def delete(self, id: str) -> bool:
        """Delete instance by ID."""
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def count(self, **filters) -> int:
        """Count instances with optional filters."""
        query = select(func.count(self.model.id))
        
        if filters:
            conditions = []
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    conditions.append(getattr(self.model, key) == value)
            
            if conditions:
                query = query.where(and_(*conditions))
        
        result = await self.session.execute(query)
        return result.scalar()
    
    async def exists(self, id: str) -> bool:
        """Check if instance exists by ID."""
        result = await self.session.execute(
            select(func.count(self.model.id)).where(self.model.id == id)
        )
        return result.scalar() > 0
    
    async def find_by_filters(
        self,
        filters: Dict[str, Any],
        offset: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None
    ) -> List[ModelType]:
        """Find instances by filters."""
        query = select(self.model)
        
        # Apply filters
        conditions = []
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                if isinstance(value, list):
                    # Handle list filters (IN clause)
                    conditions.append(getattr(self.model, key).in_(value))
                else:
                    conditions.append(getattr(self.model, key) == value)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            query = query.order_by(getattr(self.model, order_by))
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def search_text(
        self,
        query: str,
        fields: List[str],
        offset: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """Search text in specified fields."""
        search_query = select(self.model)
        
        # Build text search conditions
        conditions = []
        for field in fields:
            if hasattr(self.model, field):
                field_attr = getattr(self.model, field)
                conditions.append(field_attr.ilike(f"%{query}%"))
        
        if conditions:
            search_query = search_query.where(or_(*conditions))
        
        search_query = search_query.offset(offset).limit(limit)
        result = await self.session.execute(search_query)
        return result.scalars().all()
    
    async def bulk_create(self, instances: List[Dict[str, Any]]) -> List[ModelType]:
        """Create multiple instances in bulk."""
        db_instances = [self.model(**instance_data) for instance_data in instances]
        self.session.add_all(db_instances)
        await self.session.commit()
        
        # Refresh all instances
        for instance in db_instances:
            await self.session.refresh(instance)
        
        return db_instances
    
    async def bulk_update(self, updates: List[Dict[str, Any]]) -> int:
        """Update multiple instances in bulk."""
        if not updates:
            return 0
        
        # Add updated_at if the model has it
        if hasattr(self.model, 'updated_at'):
            for update_data in updates:
                update_data['updated_at'] = datetime.utcnow()
        
        # Execute bulk update
        result = await self.session.execute(
            update(self.model),
            updates
        )
        await self.session.commit()
        return result.rowcount