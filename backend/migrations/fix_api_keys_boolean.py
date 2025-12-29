"""
Migration script để sửa kiểu dữ liệu is_active từ INTEGER sang BOOLEAN
Chạy script này nếu gặp lỗi "operator does not exist: integer = boolean"
"""
import os
import sys
import io
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Fix encoding cho Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv("DB_HOST", "192.168.0.106")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ai_system")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def fix_boolean_column():
    """Sửa kiểu dữ liệu is_active thành BOOLEAN"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Kiểm tra xem cột is_active có tồn tại không và kiểu dữ liệu hiện tại
        result = conn.execute(text("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'api_keys' AND column_name = 'is_active'
        """))
        
        row = result.fetchone()
        if not row:
            print("[ERROR] Cot is_active khong ton tai. Chay create_api_keys_tables.py truoc.")
            return False
        
        current_type = row[0]
        print(f"[INFO] Kieu du lieu hien tai cua is_active: {current_type}")
        
        if current_type.lower() in ['boolean', 'bool']:
            print("[OK] Cot is_active da la BOOLEAN. Khong can sua.")
            return True
        
        # Nếu là integer hoặc numeric, cần convert
        if current_type.lower() in ['integer', 'int', 'int4', 'numeric', 'smallint']:
            print("[INFO] Dang chuyen doi is_active tu INTEGER sang BOOLEAN...")
            
            # Trước tiên, alter column type với USING clause để convert trực tiếp
            # PostgreSQL sẽ tự động convert: 0 -> false, 1 -> true, NULL -> NULL
            conn.execute(text("""
                ALTER TABLE api_keys 
                ALTER COLUMN is_active TYPE BOOLEAN 
                USING CASE 
                    WHEN is_active = 0 THEN FALSE
                    WHEN is_active = 1 THEN TRUE
                    ELSE TRUE
                END
            """))
            
            # Set default
            conn.execute(text("""
                ALTER TABLE api_keys 
                ALTER COLUMN is_active SET DEFAULT TRUE
            """))
            
            conn.commit()
            print("[OK] Da chuyen doi thanh cong is_active sang BOOLEAN")
            return True
        else:
            print(f"[WARNING] Kieu du lieu khong xac dinh: {current_type}. Vui long kiem tra thu cong.")
            return False

if __name__ == "__main__":
    try:
        fix_boolean_column()
    except Exception as e:
        print(f"[ERROR] Loi khi sua kieu du lieu: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)