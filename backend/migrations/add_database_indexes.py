"""
Migration script để thêm database indexes cho query optimization
Chạy script này để tạo các indexes cần thiết cho:
- agent_conversations(session_id, created_at)
- conversation_feedback(conversation_id, rating)
- conversation_embeddings(conversation_id)
"""
import os
import sys
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv("DB_HOST", "192.168.0.106")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ai_system")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# SSL configuration
DB_SSL_MODE = os.getenv("DB_SSL_MODE", "prefer")
DB_SSL_ROOT_CERT = os.getenv("DB_SSL_ROOT_CERT", None)
DB_SSL_CERT = os.getenv("DB_SSL_CERT", None)
DB_SSL_KEY = os.getenv("DB_SSL_KEY", None)

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

DB_CONNECT_ARGS = {
    "connect_timeout": 10,
    "sslmode": DB_SSL_MODE
}

if DB_SSL_ROOT_CERT:
    DB_CONNECT_ARGS["sslrootcert"] = DB_SSL_ROOT_CERT
if DB_SSL_CERT:
    DB_CONNECT_ARGS["sslcert"] = DB_SSL_CERT
if DB_SSL_KEY:
    DB_CONNECT_ARGS["sslkey"] = DB_SSL_KEY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def index_exists(conn, table_name: str, index_name: str) -> bool:
    """Kiểm tra xem index đã tồn tại chưa"""
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM pg_indexes 
            WHERE tablename = :table_name 
            AND indexname = :index_name
        )
    """), {"table_name": table_name, "index_name": index_name})
    return result.scalar()


def create_indexes():
    """Tạo các indexes cần thiết cho query optimization"""
    engine = create_engine(DATABASE_URL, connect_args=DB_CONNECT_ARGS)
    
    indexes_to_create = [
        # Indexes cho agent_conversations
        {
            "name": "idx_agent_conversations_session_id",
            "table": "agent_conversations",
            "columns": "session_id",
            "description": "Index cho session_id để query conversations theo session nhanh hơn"
        },
        {
            "name": "idx_agent_conversations_created_at",
            "table": "agent_conversations",
            "columns": "created_at",
            "description": "Index cho created_at để sort và filter theo thời gian nhanh hơn"
        },
        {
            "name": "idx_agent_conversations_session_created",
            "table": "agent_conversations",
            "columns": "session_id, created_at",
            "description": "Composite index cho session_id và created_at (thường query cùng lúc)"
        },
        
        # Indexes cho conversation_feedback
        {
            "name": "idx_conversation_feedback_conversation_id",
            "table": "conversation_feedback",
            "columns": "conversation_id",
            "description": "Index cho conversation_id để join và filter feedback theo conversation"
        },
        {
            "name": "idx_conversation_feedback_rating",
            "table": "conversation_feedback",
            "columns": "rating",
            "description": "Index cho rating để filter feedback theo rating nhanh hơn"
        },
        {
            "name": "idx_conversation_feedback_conv_rating",
            "table": "conversation_feedback",
            "columns": "conversation_id, rating",
            "description": "Composite index cho conversation_id và rating (thường filter cùng lúc)"
        },
        
        # Indexes cho conversation_embeddings
        {
            "name": "idx_conversation_embeddings_conversation_id",
            "table": "conversation_embeddings",
            "columns": "conversation_id",
            "description": "Index cho conversation_id để join embeddings với conversations nhanh hơn"
        },
    ]
    
    with engine.connect() as conn:
        created_count = 0
        skipped_count = 0
        
        for idx in indexes_to_create:
            try:
                # Kiểm tra xem index đã tồn tại chưa
                if index_exists(conn, idx["table"], idx["name"]):
                    logger.info(f"⏭️  Index {idx['name']} đã tồn tại, bỏ qua")
                    skipped_count += 1
                    continue
                
                # Kiểm tra xem bảng có tồn tại không
                inspector = inspect(engine)
                if idx["table"] not in inspector.get_table_names():
                    logger.warning(f"⚠️  Bảng {idx['table']} không tồn tại, bỏ qua index {idx['name']}")
                    skipped_count += 1
                    continue
                
                # Tạo index
                create_sql = f"""
                    CREATE INDEX {idx['name']} 
                    ON {idx['table']} ({idx['columns']})
                """
                
                conn.execute(text(create_sql))
                conn.commit()
                
                logger.info(f"✅ Đã tạo index: {idx['name']} trên {idx['table']}({idx['columns']})")
                logger.debug(f"   Mô tả: {idx['description']}")
                created_count += 1
                
            except Exception as e:
                logger.error(f"❌ Lỗi khi tạo index {idx['name']}: {e}")
                conn.rollback()
        
        logger.info(f"\n📊 Tổng kết:")
        logger.info(f"   ✅ Đã tạo: {created_count} indexes")
        logger.info(f"   ⏭️  Đã bỏ qua: {skipped_count} indexes")
        
        # Analyze tables để PostgreSQL cập nhật statistics
        logger.info("\n🔄 Đang chạy ANALYZE để cập nhật statistics...")
        for idx in indexes_to_create:
            try:
                conn.execute(text(f"ANALYZE {idx['table']}"))
                logger.debug(f"   Đã analyze bảng {idx['table']}")
            except Exception as e:
                logger.warning(f"⚠️  Không thể analyze bảng {idx['table']}: {e}")
        
        conn.commit()
        logger.info("✅ Hoàn thành!")


if __name__ == "__main__":
    try:
        logger.info("🚀 Bắt đầu tạo database indexes...")
        create_indexes()
    except Exception as e:
        logger.error(f"❌ Lỗi khi tạo indexes: {e}")
        sys.exit(1)