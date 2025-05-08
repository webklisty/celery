#!/bin/bash

# Start Redis server in the background
redis-server --daemonize yes --protected-mode no &
sleep 2
echo "Redis server started"

# Start Celery worker
celery -A email_campaign_system worker --loglevel=info --concurrency=2 &
sleep 2
echo "Celery worker started"

# Start Celery beat scheduler
celery -A email_campaign_system beat --loglevel=info &
sleep 2
echo "Celery beat scheduler started"

# Keep the script running
tail -f /dev/null