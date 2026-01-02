"""
Base Repository class providing common database operations.
All repositories should inherit from this base class.
"""
from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, desc, asc
import logging

logger = logging.getLogger(__name__)

# Type variable for SQLAlchemy model
ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """Base repository class with common CRUD operations"""
    
    def __init__(self, session: Session, model: Type[ModelType]):
        """
        Initialize repository with database session and model class
        
        Args:
            session: SQLAlchemy session (sync)
            model: SQLAlchemy model class
        """
        self.session = session
        self.model = model
    
    def create(self, **kwargs) -> ModelType:
        """Create a new record"""
        try:
            instance = self.model(**kwargs)
            self.session.add(instance)
            self.session.commit()
            self.session.refresh(instance)
            return instance
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating {self.model.__name__}: {e}")
            raise
    
    def get_by_id(self, id: int) -> Optional[ModelType]:
        """Get record by ID"""
        return self.session.query(self.model).filter(self.model.id == id).first()
    
    def get_all(self, skip: int = 0, limit: int = 100, order_by: Optional[str] = None) -> List[ModelType]:
        """Get all records with pagination"""
        query = self.session.query(self.model)
        
        if order_by:
            # Support order_by format: "field_name" or "-field_name" (descending)
            if order_by.startswith("-"):
                field_name = order_by[1:]
                field = getattr(self.model, field_name, None)
                if field:
                    query = query.order_by(desc(field))
            else:
                field = getattr(self.model, order_by, None)
                if field:
                    query = query.order_by(asc(field))
        
        return query.offset(skip).limit(limit).all()
    
    def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """Update record by ID"""
        try:
            instance = self.get_by_id(id)
            if not instance:
                return None
            
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            
            self.session.commit()
            self.session.refresh(instance)
            return instance
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating {self.model.__name__} {id}: {e}")
            raise
    
    def delete(self, id: int) -> bool:
        """Delete record by ID"""
        try:
            instance = self.get_by_id(id)
            if not instance:
                return False
            
            self.session.delete(instance)
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting {self.model.__name__} {id}: {e}")
            raise
    
    def filter_by(self, **filters) -> List[ModelType]:
        """Filter records by provided criteria"""
        query = self.session.query(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.all()
    
    def filter_by_conditions(self, conditions: List) -> List[ModelType]:
        """Filter records by SQLAlchemy conditions"""
        query = self.session.query(self.model)
        if conditions:
            query = query.filter(and_(*conditions))
        return query.all()
    
    def count(self, **filters) -> int:
        """Count records matching filters"""
        query = self.session.query(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.count()


class AsyncBaseRepository(Generic[ModelType]):
    """Base repository class for async database operations"""
    
    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        """
        Initialize repository with async database session and model class
        
        Args:
            session: SQLAlchemy async session
            model: SQLAlchemy model class
        """
        self.session = session
        self.model = model
    
    async def create(self, **kwargs) -> ModelType:
        """Create a new record (async)"""
        try:
            instance = self.model(**kwargs)
            self.session.add(instance)
            await self.session.commit()
            await self.session.refresh(instance)
            return instance
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating {self.model.__name__}: {e}")
            raise
    
    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """Get record by ID (async)"""
        from sqlalchemy import select
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, skip: int = 0, limit: int = 100, order_by: Optional[str] = None) -> List[ModelType]:
        """Get all records with pagination (async)"""
        from sqlalchemy import select
        query = select(self.model)
        
        if order_by:
            if order_by.startswith("-"):
                field_name = order_by[1:]
                field = getattr(self.model, field_name, None)
                if field:
                    query = query.order_by(desc(field))
            else:
                field = getattr(self.model, order_by, None)
                if field:
                    query = query.order_by(asc(field))
        
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """Update record by ID (async)"""
        try:
            instance = await self.get_by_id(id)
            if not instance:
                return None
            
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            
            await self.session.commit()
            await self.session.refresh(instance)
            return instance
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating {self.model.__name__} {id}: {e}")
            raise
    
    async def delete(self, id: int) -> bool:
        """Delete record by ID (async)"""
        try:
            instance = await self.get_by_id(id)
            if not instance:
                return False
            
            await self.session.delete(instance)
            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting {self.model.__name__} {id}: {e}")
            raise