#!/bin/bash

# Set environment variables for the admin password
export DJANGO_SUPERUSER_PASSWORD=admin123

# Run migrations and start the server
python manage.py migrate
python manage.py createsuperuser --username admin --email admin@example.com --noinput 2>/dev/null || true
echo "Admin credentials: username=admin, password=admin123"
python manage.py runserver 0.0.0.0:5000