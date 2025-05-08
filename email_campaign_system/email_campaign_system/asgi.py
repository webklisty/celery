"""
ASGI config for email_campaign_system project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'email_campaign_system.settings')

application = get_asgi_application()
