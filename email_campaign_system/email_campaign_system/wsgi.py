"""
WSGI config for email_campaign_system project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'email_campaign_system.settings')

application = get_wsgi_application()
