@echo off
REM Start Celery Worker for Windows
REM Usage: start_celery.bat

cd /d %~dp0
call venv\Scripts\activate
celery -A services.celery_config worker --loglevel=info --pool=solo


