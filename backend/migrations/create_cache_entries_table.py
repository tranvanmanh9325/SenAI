"""
Migration script để tạo bảng cache_entries cho L3 cache
LƯU Ý: Bảng này sẽ TỰ ĐỘNG được tạo khi chạy `python app.py` lần đầu tiên
       (nếu AUTO_MIGRATE_CACHE_TABLE=true trong .env, mặc định là true)

Chỉ cần chạy script này thủ công nếu:
- AUTO_MIGRATE_CACHE_TABLE=false và bạn muốn tạo bảng thủ công
- Hoặc bạn muốn tạo lại bảng sau khi đã xóa
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback to individual components
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "senai_db")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def create_cache_entries_table():
    """Tạo bảng cache_entries"""
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Check if table exists
            check_table = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'cache_entries'
                );
            """)
            
            result = conn.execute(check_table)
            table_exists = result.scalar()
            
            if table_exists:
                logger.info("Table cache_entries already exists. Skipping creation.")
                return
            
            # Create table
            create_table = text("""
                CREATE TABLE cache_entries (
                    id SERIAL PRIMARY KEY,
                    cache_key VARCHAR(512) UNIQUE NOT NULL,
                    cache_value TEXT NOT NULL,
                    cache_type VARCHAR(50) NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            conn.execute(create_table)
            
            # Create indexes
            create_indexes = [
                text("CREATE INDEX idx_cache_entries_key ON cache_entries(cache_key);"),
                text("CREATE INDEX idx_cache_entries_type ON cache_entries(cache_type);"),
                text("CREATE INDEX idx_cache_entries_expires ON cache_entries(expires_at);"),
                text("CREATE INDEX idx_cache_entries_access_count ON cache_entries(access_count);"),
                text("CREATE INDEX idx_cache_entries_last_accessed ON cache_entries(last_accessed);"),
            ]
            
            for index_sql in create_indexes:
                conn.execute(index_sql)
            
            conn.commit()
            logger.info("✅ Table cache_entries created successfully with indexes")
            
    except Exception as e:
        logger.error(f"❌ Error creating cache_entries table: {e}")
        raise

if __name__ == "__main__":
    logger.info("Starting migration: create_cache_entries_table")
    create_cache_entries_table()
    logger.info("Migration completed")