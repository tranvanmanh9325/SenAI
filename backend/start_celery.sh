#!/bin/bash
# Start Celery Worker for Linux/Mac
# Usage: ./start_celery.sh

cd "$(dirname "$0")"
source venv/bin/activate
celery -A services.celery_config worker --loglevel=info


