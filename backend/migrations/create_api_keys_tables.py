"""
Migration script để tạo bảng api_keys và api_key_audit_logs
Chạy script này để tạo các bảng cần thiết cho API key management
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv("DB_HOST", "192.168.0.106")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ai_system")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def create_tables():
    """Tạo các bảng api_keys và api_key_audit_logs"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Tạo bảng api_keys
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                key_hash VARCHAR(255) NOT NULL UNIQUE,
                name VARCHAR(255) NOT NULL,
                user_id INTEGER,
                permissions TEXT,
                rate_limit VARCHAR(50) DEFAULT '100/minute',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                last_used_at TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """))
        
        # Tạo indexes cho api_keys
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON api_keys(expires_at)
        """))
        
        # Tạo bảng api_key_audit_logs
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS api_key_audit_logs (
                id SERIAL PRIMARY KEY,
                api_key_id INTEGER NOT NULL,
                endpoint VARCHAR(255) NOT NULL,
                method VARCHAR(10) NOT NULL,
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                status_code INTEGER NOT NULL,
                response_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE
            )
        """))
        
        # Tạo indexes cho api_key_audit_logs
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_api_key_id ON api_key_audit_logs(api_key_id)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON api_key_audit_logs(created_at)
        """))
        
        conn.commit()
        print("✅ Đã tạo thành công các bảng api_keys và api_key_audit_logs")
        print("✅ Đã tạo các indexes cần thiết")

if __name__ == "__main__":
    try:
        create_tables()
    except Exception as e:
        print(f"❌ Lỗi khi tạo bảng: {e}")
        sys.exit(1)