#!/bin/bash
set -e

# 1. Start Celery in background (&)
# Using standard prefork. If it acts up in Cloud Run, we might switch to -P gevent later.
celery -A app.celery worker --loglevel=info --concurrency=2 &

# 2. Start Gunicorn (Production Flask Server) in foreground
# It listens on the $PORT provided by Google
exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app