from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Campaign management
    path('campaigns/', views.campaign_list, name='campaign_list'),
    path('campaigns/create/', views.campaign_create, name='campaign_create'),
    path('campaigns/<uuid:campaign_id>/', views.campaign_detail, name='campaign_detail'),
    path('campaigns/<uuid:campaign_id>/edit/', views.campaign_edit, name='campaign_edit'),
    path('campaigns/<uuid:campaign_id>/delete/', views.campaign_delete, name='campaign_delete'),
    path('campaigns/<uuid:campaign_id>/pause/', views.campaign_pause, name='campaign_pause'),
    path('campaigns/<uuid:campaign_id>/activate/', views.campaign_activate, name='campaign_activate'),
    
    # Recipient management
    path('recipients/', views.recipient_list, name='recipient_list'),
    path('recipients/lists/', views.recipient_list_create, name='recipient_list_create'),
    path('recipients/lists/<uuid:list_id>/', views.recipient_list_detail, name='recipient_list_detail'),
    path('recipients/upload/', views.recipient_upload, name='recipient_upload'),
    path('recipients/lists/<uuid:list_id>/delete/', views.recipient_list_delete, name='recipient_list_delete'),
    
    # Logs and analytics
    path('logs/', views.email_logs, name='email_logs'),
    path('analytics/', views.analytics_view, name='analytics'),
    
    # API endpoints for charts
    path('api/campaign-stats/<uuid:campaign_id>/', views.campaign_stats, name='campaign_stats'),
    path('api/daily-stats/', views.daily_stats, name='daily_stats'),
]
