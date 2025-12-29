"""
Migration script để encrypt existing sensitive data trong database

Chạy script này để encrypt các fields nhạy cảm đã có trong database:
- conversation_feedback.comment
- conversation_feedback.user_correction

Usage:
    cd backend
    venv\Scripts\activate
    python migrations/encrypt_sensitive_fields.py
"""
import os
import sys
from pathlib import Path

# Add parent directory to path để import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import ConversationFeedback, Base
from services.encryption_service import encryption_service

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv("DB_HOST", "192.168.0.106")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ai_system")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SSL configuration
DB_SSL_MODE = os.getenv("DB_SSL_MODE", "prefer")
DB_CONNECT_ARGS = {
    "connect_timeout": 10,
    "sslmode": DB_SSL_MODE
}

if os.getenv("DB_SSL_ROOT_CERT"):
    DB_CONNECT_ARGS["sslrootcert"] = os.getenv("DB_SSL_ROOT_CERT")
if os.getenv("DB_SSL_CERT"):
    DB_CONNECT_ARGS["sslcert"] = os.getenv("DB_SSL_CERT")
if os.getenv("DB_SSL_KEY"):
    DB_CONNECT_ARGS["sslkey"] = os.getenv("DB_SSL_KEY")

# Create database engine
engine = create_engine(DATABASE_URL, connect_args=DB_CONNECT_ARGS)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def encrypt_existing_data(dry_run: bool = True):
    """
    Encrypt existing sensitive data trong database
    
    Args:
        dry_run: Nếu True, chỉ hiển thị những gì sẽ được encrypt mà không thực sự encrypt
    """
    db = SessionLocal()
    
    try:
        # Lấy tất cả feedback records
        feedbacks = db.query(ConversationFeedback).all()
        
        print(f"Found {len(feedbacks)} feedback records to process")
        
        encrypted_count = 0
        skipped_count = 0
        error_count = 0
        
        for fb in feedbacks:
            updated = False
            
            # Encrypt comment nếu có và chưa được encrypt
            if fb.comment:
                if not encryption_service.is_encrypted(fb.comment):
                    if dry_run:
                        print(f"  [DRY RUN] Would encrypt comment for feedback ID {fb.id}: {fb.comment[:50]}...")
                    else:
                        try:
                            fb.comment = encryption_service.encrypt(fb.comment)
                            updated = True
                            encrypted_count += 1
                        except Exception as e:
                            print(f"  [ERROR] Failed to encrypt comment for feedback ID {fb.id}: {e}")
                            error_count += 1
                else:
                    skipped_count += 1
            
            # Encrypt user_correction nếu có và chưa được encrypt
            if fb.user_correction:
                if not encryption_service.is_encrypted(fb.user_correction):
                    if dry_run:
                        print(f"  [DRY RUN] Would encrypt user_correction for feedback ID {fb.id}: {fb.user_correction[:50]}...")
                    else:
                        try:
                            fb.user_correction = encryption_service.encrypt(fb.user_correction)
                            updated = True
                            encrypted_count += 1
                        except Exception as e:
                            print(f"  [ERROR] Failed to encrypt user_correction for feedback ID {fb.id}: {e}")
                            error_count += 1
                else:
                    skipped_count += 1
            
            # Commit changes nếu có update
            if updated and not dry_run:
                db.commit()
        
        print("\n" + "="*60)
        if dry_run:
            print("DRY RUN COMPLETE - No data was modified")
            print(f"Would encrypt: {encrypted_count} fields")
            print(f"Already encrypted (skipped): {skipped_count} fields")
        else:
            print("ENCRYPTION COMPLETE")
            print(f"Encrypted: {encrypted_count} fields")
            print(f"Already encrypted (skipped): {skipped_count} fields")
            print(f"Errors: {error_count} fields")
        print("="*60)
        
    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
        raise
    finally:
        db.close()


def verify_encryption():
    """Verify rằng tất cả sensitive data đã được encrypt"""
    db = SessionLocal()
    
    try:
        feedbacks = db.query(ConversationFeedback).all()
        
        unencrypted_comments = []
        unencrypted_corrections = []
        
        for fb in feedbacks:
            if fb.comment and not encryption_service.is_encrypted(fb.comment):
                unencrypted_comments.append(fb.id)
            
            if fb.user_correction and not encryption_service.is_encrypted(fb.user_correction):
                unencrypted_corrections.append(fb.id)
        
        if unencrypted_comments or unencrypted_corrections:
            print("WARNING: Found unencrypted data:")
            if unencrypted_comments:
                print(f"  - {len(unencrypted_comments)} comments: {unencrypted_comments[:10]}...")
            if unencrypted_corrections:
                print(f"  - {len(unencrypted_corrections)} corrections: {unencrypted_corrections[:10]}...")
            return False
        else:
            print("✓ All sensitive data is encrypted")
            return True
            
    except Exception as e:
        print(f"Error during verification: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Encrypt existing sensitive data in database")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - show what would be encrypted without actually encrypting"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify that all sensitive data is encrypted"
    )
    
    args = parser.parse_args()
    
    if args.verify:
        print("Verifying encryption status...")
        verify_encryption()
    else:
        dry_run = args.dry_run if args.dry_run else True
        
        if not dry_run:
            response = input(
                "WARNING: This will encrypt existing data. "
                "Make sure you have a backup and ENCRYPTION_KEY is set correctly. "
                "Continue? (yes/no): "
            )
            if response.lower() != "yes":
                print("Aborted.")
                sys.exit(0)
        
        print(f"Starting migration (dry_run={dry_run})...")
        encrypt_existing_data(dry_run=dry_run)
        
        if dry_run:
            print("\nTo actually encrypt the data, run:")
            print("  python migrations/encrypt_sensitive_fields.py --dry-run=false")