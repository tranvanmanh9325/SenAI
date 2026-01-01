"""
Batch Processing Utilities
Cung cấp các hàm tiện ích cho batch operations (bulk insert, bulk update, etc.)
"""
import logging
from typing import List, Dict, Any, Optional, Callable, TypeVar, Generic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, insert
from sqlalchemy.orm import DeclarativeBase
import asyncio

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=DeclarativeBase)


class BatchProcessor:
    """Utility class cho batch processing operations"""
    
    @staticmethod
    async def bulk_insert(
        db: AsyncSession,
        model_class: type[T],
        items: List[Dict[str, Any]],
        batch_size: int = 1000
    ) -> int:
        """
        Bulk insert nhiều records vào database
        
        Args:
            db: Async database session
            model_class: SQLAlchemy model class
            items: List of dictionaries với data để insert
            batch_size: Số records mỗi batch
            
        Returns:
            Số records đã insert
        """
        if not items:
            return 0
        
        total_inserted = 0
        
        # Chia thành batches
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            try:
                # Tạo model instances
                instances = [model_class(**item) for item in batch]
                db.add_all(instances)
                await db.flush()  # Flush để lấy IDs nhưng chưa commit
                total_inserted += len(batch)
            except Exception as e:
                logger.error(f"Error in bulk insert batch {i//batch_size + 1}: {e}")
                await db.rollback()
                raise
        
        # Commit tất cả batches
        await db.commit()
        logger.info(f"Bulk inserted {total_inserted} records of {model_class.__name__}")
        
        return total_inserted
    
    @staticmethod
    async def bulk_update(
        db: AsyncSession,
        model_class: type[T],
        updates: List[Dict[str, Any]],
        key_field: str = "id",
        batch_size: int = 1000
    ) -> int:
        """
        Bulk update nhiều records
        
        Args:
            db: Async database session
            model_class: SQLAlchemy model class
            updates: List of dictionaries với {key_field: value, ...other_fields}
            key_field: Field name để identify record (default: "id")
            batch_size: Số records mỗi batch
            
        Returns:
            Số records đã update
        """
        if not updates:
            return 0
        
        total_updated = 0
        
        # Chia thành batches
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            
            try:
                for item in batch:
                    key_value = item.pop(key_field)
                    update_stmt = (
                        update(model_class)
                        .where(getattr(model_class, key_field) == key_value)
                        .values(**item)
                    )
                    await db.execute(update_stmt)
                
                await db.flush()
                total_updated += len(batch)
            except Exception as e:
                logger.error(f"Error in bulk update batch {i//batch_size + 1}: {e}")
                await db.rollback()
                raise
        
        await db.commit()
        logger.info(f"Bulk updated {total_updated} records of {model_class.__name__}")
        
        return total_updated
    
    @staticmethod
    async def bulk_delete(
        db: AsyncSession,
        model_class: type[T],
        ids: List[Any],
        id_field: str = "id",
        batch_size: int = 1000
    ) -> int:
        """
        Bulk delete nhiều records
        
        Args:
            db: Async database session
            model_class: SQLAlchemy model class
            ids: List of IDs để delete
            id_field: Field name của ID (default: "id")
            batch_size: Số records mỗi batch
            
        Returns:
            Số records đã delete
        """
        if not ids:
            return 0
        
        total_deleted = 0
        
        # Chia thành batches
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            
            try:
                delete_stmt = (
                    delete(model_class)
                    .where(getattr(model_class, id_field).in_(batch_ids))
                )
                result = await db.execute(delete_stmt)
                await db.flush()
                total_deleted += result.rowcount
            except Exception as e:
                logger.error(f"Error in bulk delete batch {i//batch_size + 1}: {e}")
                await db.rollback()
                raise
        
        await db.commit()
        logger.info(f"Bulk deleted {total_deleted} records of {model_class.__name__}")
        
        return total_deleted
    
    @staticmethod
    async def process_in_batches(
        items: List[Any],
        processor: Callable[[List[Any]], Any],
        batch_size: int = 100,
        max_concurrent: int = 5
    ) -> List[Any]:
        """
        Process items trong batches với concurrency control
        
        Args:
            items: List of items để process
            processor: Async function để process mỗi batch
            batch_size: Số items mỗi batch
            max_concurrent: Số batches chạy đồng thời
            
        Returns:
            List of results từ processor
        """
        if not items:
            return []
        
        results = []
        batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
        
        # Process batches với concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_batch_with_semaphore(batch):
            async with semaphore:
                return await processor(batch)
        
        tasks = [process_batch_with_semaphore(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = [r for r in results if not isinstance(r, Exception)]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        if exceptions:
            logger.warning(f"Encountered {len(exceptions)} exceptions during batch processing")
            for exc in exceptions:
                logger.error(f"Batch processing exception: {exc}")
        
        return valid_results
    
    @staticmethod
    async def bulk_upsert(
        db: AsyncSession,
        model_class: type[T],
        items: List[Dict[str, Any]],
        unique_fields: List[str],
        batch_size: int = 1000
    ) -> Dict[str, int]:
        """
        Bulk upsert (insert or update) nhiều records
        
        Args:
            db: Async database session
            model_class: SQLAlchemy model class
            items: List of dictionaries với data
            unique_fields: List of field names để check uniqueness
            batch_size: Số records mỗi batch
            
        Returns:
            Dict với counts: {"inserted": X, "updated": Y}
        """
        if not items:
            return {"inserted": 0, "updated": 0}
        
        inserted = 0
        updated = 0
        
        # Chia thành batches
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            try:
                for item in batch:
                    # Build filter condition từ unique_fields
                    filters = {field: item[field] for field in unique_fields if field in item}
                    
                    # Check if record exists
                    stmt = select(model_class)
                    for field, value in filters.items():
                        stmt = stmt.where(getattr(model_class, field) == value)
                    
                    result = await db.execute(stmt)
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        # Update existing record
                        for key, value in item.items():
                            if key not in unique_fields:
                                setattr(existing, key, value)
                        updated += 1
                    else:
                        # Insert new record
                        instance = model_class(**item)
                        db.add(instance)
                        inserted += 1
                
                await db.flush()
            except Exception as e:
                logger.error(f"Error in bulk upsert batch {i//batch_size + 1}: {e}")
                await db.rollback()
                raise
        
        await db.commit()
        logger.info(f"Bulk upserted {inserted} inserted, {updated} updated records of {model_class.__name__}")
        
        return {"inserted": inserted, "updated": updated}


# Global instance
batch_processor = BatchProcessor()


