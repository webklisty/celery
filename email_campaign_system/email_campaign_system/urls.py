"""
URL configuration for email_campaign_system project.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='dashboard/'), name='home'),
    path('', include('campaigns.urls')),
]
