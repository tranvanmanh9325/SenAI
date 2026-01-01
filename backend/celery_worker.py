"""
Celery Worker Startup Script
Chạy Celery worker để xử lý background tasks

Usage:
    python celery_worker.py
    hoặc
    celery -A celery_worker worker --loglevel=info
"""
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.celery_config import celery_app

if __name__ == "__main__":
    # Start Celery worker
    celery_app.start()


