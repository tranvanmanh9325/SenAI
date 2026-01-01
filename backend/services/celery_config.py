"""
Celery Configuration for Background Tasks
Cung cấp task queue cho các background operations
"""
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Redis configuration for Celery broker
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "").strip()
if '#' in REDIS_PASSWORD:
    REDIS_PASSWORD = REDIS_PASSWORD.split('#')[0].strip()
if not REDIS_PASSWORD:
    REDIS_PASSWORD = None

# Build Redis URL for Celery
if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Celery configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Create Celery app
celery_app = Celery(
    "ai_agent_backend",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=['services.celery_tasks']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,  # Results expire after 1 hour
)

# Task routes
celery_app.conf.task_routes = {
    'services.celery_tasks.*': {'queue': 'default'},
    'services.celery_tasks.index_conversation': {'queue': 'indexing'},
    'services.celery_tasks.batch_process': {'queue': 'batch'},
}


