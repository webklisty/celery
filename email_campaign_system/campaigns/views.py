import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_celery_beat.models import PeriodicTask, CrontabSchedule

from .models import Campaign, RecipientList, Recipient, EmailLog
from .forms import CustomAuthenticationForm, CampaignForm, RecipientListForm, CSVUploadForm
from .tasks import send_campaign_emails
from .utils import process_csv_file, get_campaign_stats, get_daily_stats

logger = logging.getLogger(__name__)

# Authentication views
def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password. Please try again.")
            form = CustomAuthenticationForm()
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'campaigns/login.html', {'form': form})

# Dashboard views
@login_required
def dashboard_view(request):
    """Display dashboard with campaign statistics"""
    # Get recent campaigns
    recent_campaigns = Campaign.objects.all().order_by('-created_at')[:5]
    
    # Get today's email statistics
    today = timezone.now().date()
    today_sent = EmailLog.objects.filter(
        sent_at__date=today, 
        status='sent'
    ).count()
    today_errors = EmailLog.objects.filter(
        sent_at__date=today, 
        status='error'
    ).count()
    
    # Get total statistics
    total_campaigns = Campaign.objects.count()
    total_recipients = Recipient.objects.count()
    total_sent = EmailLog.objects.filter(status='sent').count()
    
    # Get campaign counts by status
    status_counts = {
        'draft': Campaign.objects.filter(status='draft').count(),
        'scheduled': Campaign.objects.filter(status='scheduled').count(),
        'active': Campaign.objects.filter(status='active').count(),
        'completed': Campaign.objects.filter(status='completed').count(),
        'paused': Campaign.objects.filter(status='paused').count(),
    }
    
    context = {
        'recent_campaigns': recent_campaigns,
        'today_sent': today_sent,
        'today_errors': today_errors,
        'total_campaigns': total_campaigns,
        'total_recipients': total_recipients,
        'total_sent': total_sent,
        'status_counts': status_counts,
    }
    
    return render(request, 'campaigns/dashboard.html', context)

# Campaign management views
@login_required
def campaign_list(request):
    """Display list of all campaigns"""
    campaigns = Campaign.objects.all().order_by('-created_at')
    return render(request, 'campaigns/campaign_list.html', {'campaigns': campaigns})

@login_required
def campaign_create(request):
    """Create a new campaign"""
    if request.method == 'POST':
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save()
            
            # Schedule the campaign if it's set to scheduled status
            if campaign.status == 'scheduled' and campaign.scheduled_time:
                # Schedule the task
                result = send_campaign_emails.apply_async(
                    args=[str(campaign.id)],
                    eta=campaign.scheduled_time
                )
                campaign.celery_task_id = result.id
                campaign.save()
                
            messages.success(request, f"Campaign '{campaign.name}' created successfully!")
            return redirect('campaign_detail', campaign_id=campaign.id)
    else:
        form = CampaignForm()
    
    return render(request, 'campaigns/campaign_create.html', {'form': form})

@login_required
def campaign_detail(request, campaign_id):
    """Display campaign details"""
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    stats = get_campaign_stats(campaign)
    
    # Get recent logs for this campaign
    logs = EmailLog.objects.filter(campaign=campaign).order_by('-sent_at')[:50]
    
    context = {
        'campaign': campaign,
        'stats': stats,
        'logs': logs,
    }
    
    return render(request, 'campaigns/campaign_detail.html', context)

@login_required
def campaign_edit(request, campaign_id):
    """Edit an existing campaign"""
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, instance=campaign)
        if form.is_valid():
            updated_campaign = form.save()
            
            # Update scheduling if needed
            if updated_campaign.status == 'scheduled' and updated_campaign.scheduled_time:
                # Cancel existing task if any
                if updated_campaign.celery_task_id:
                    # Attempt to revoke the task if it exists
                    from celery import current_app
                    current_app.control.revoke(updated_campaign.celery_task_id, terminate=True)
                
                # Schedule new task
                result = send_campaign_emails.apply_async(
                    args=[str(updated_campaign.id)],
                    eta=updated_campaign.scheduled_time
                )
                updated_campaign.celery_task_id = result.id
                updated_campaign.save()
            
            messages.success(request, f"Campaign '{updated_campaign.name}' updated successfully!")
            return redirect('campaign_detail', campaign_id=campaign.id)
    else:
        form = CampaignForm(instance=campaign)
    
    return render(request, 'campaigns/campaign_edit.html', {'form': form, 'campaign': campaign})

@login_required
def campaign_delete(request, campaign_id):
    """Delete a campaign"""
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    
    if request.method == 'POST':
        campaign_name = campaign.name
        
        # Cancel any scheduled tasks
        if campaign.celery_task_id:
            from celery.task.control import revoke
            revoke(campaign.celery_task_id, terminate=True)
        
        # Delete the campaign
        campaign.delete()
        messages.success(request, f"Campaign '{campaign_name}' deleted successfully!")
        return redirect('campaign_list')
    
    return render(request, 'campaigns/campaign_detail.html', {
        'campaign': campaign,
        'confirm_delete': True
    })

@login_required
@require_POST
def campaign_pause(request, campaign_id):
    """Pause an active campaign"""
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    
    if campaign.status in ['active', 'scheduled']:
        # Update status
        campaign.status = 'paused'
        campaign.save()
        
        # Cancel any scheduled tasks
        if campaign.celery_task_id:
            from celery.task.control import revoke
            revoke(campaign.celery_task_id, terminate=True)
            campaign.celery_task_id = None
            campaign.save()
        
        messages.success(request, f"Campaign '{campaign.name}' paused successfully!")
    else:
        messages.error(request, f"Campaign '{campaign.name}' is not active or scheduled!")
    
    return redirect('campaign_detail', campaign_id=campaign_id)

@login_required
@require_POST
def campaign_activate(request, campaign_id):
    """Activate a paused campaign"""
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    
    if campaign.status == 'paused':
        # Update status
        campaign.status = 'scheduled'
        campaign.save()
        
        # Schedule new task if scheduled time is in the future
        if campaign.scheduled_time and campaign.scheduled_time > timezone.now():
            result = send_campaign_emails.apply_async(
                args=[str(campaign.id)],
                eta=campaign.scheduled_time
            )
            campaign.celery_task_id = result.id
            campaign.save()
        else:
            # Schedule immediately
            result = send_campaign_emails.apply_async(args=[str(campaign.id)])
            campaign.celery_task_id = result.id
            campaign.save()
        
        messages.success(request, f"Campaign '{campaign.name}' activated successfully!")
    else:
        messages.error(request, f"Campaign '{campaign.name}' is not paused!")
    
    return redirect('campaign_detail', campaign_id=campaign_id)

# Recipient management views
@login_required
def recipient_list(request):
    """Display all recipient lists"""
    lists = RecipientList.objects.all().order_by('-created_at')
    
    # Add recipient count to each list
    for recipient_list in lists:
        recipient_list.count = recipient_list.recipients.count()
    
    return render(request, 'campaigns/recipient_list.html', {'lists': lists})

@login_required
def recipient_list_create(request):
    """Create a new recipient list"""
    if request.method == 'POST':
        form = RecipientListForm(request.POST)
        if form.is_valid():
            recipient_list = form.save()
            messages.success(request, f"Recipient list '{recipient_list.name}' created successfully!")
            return redirect('recipient_list_detail', list_id=recipient_list.id)
    else:
        form = RecipientListForm()
    
    lists = RecipientList.objects.all().order_by('-created_at')
    
    return render(request, 'campaigns/recipient_list.html', {
        'form': form,
        'lists': lists
    })

@login_required
def recipient_list_detail(request, list_id):
    """Display details of a recipient list"""
    recipient_list = get_object_or_404(RecipientList, pk=list_id)
    recipients = recipient_list.recipients.all().order_by('email')
    
    return render(request, 'campaigns/recipient_list_detail.html', {
        'recipient_list': recipient_list,
        'recipients': recipients
    })

@login_required
def recipient_list_delete(request, list_id):
    """Delete a recipient list"""
    recipient_list = get_object_or_404(RecipientList, pk=list_id)
    
    if request.method == 'POST':
        list_name = recipient_list.name
        recipient_list.delete()
        messages.success(request, f"Recipient list '{list_name}' deleted successfully!")
        return redirect('recipient_list')
    
    return render(request, 'campaigns/recipient_list_detail.html', {
        'recipient_list': recipient_list,
        'confirm_delete': True
    })

@login_required
def recipient_upload(request):
    """Upload recipients from CSV file"""
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            recipient_list = form.cleaned_data['recipient_list']
            
            # Process the CSV file
            success_count, error_count, error_messages = process_csv_file(csv_file, recipient_list)
            
            if success_count > 0:
                messages.success(request, f"Successfully imported {success_count} recipients!")
            
            if error_count > 0:
                messages.error(request, f"Failed to import {error_count} recipients! See below for details.")
                for error in error_messages:
                    messages.warning(request, error)
                    
            return redirect('recipient_list_detail', list_id=recipient_list.id)
    else:
        form = CSVUploadForm()
    
    return render(request, 'campaigns/recipient_upload.html', {'form': form})

# Logs and analytics views
@login_required
def email_logs(request):
    """Display email sending logs"""
    campaign_id = request.GET.get('campaign_id')
    status = request.GET.get('status')
    
    logs = EmailLog.objects.all().order_by('-sent_at')
    
    # Apply filters if provided
    if campaign_id:
        logs = logs.filter(campaign_id=campaign_id)
    
    if status:
        logs = logs.filter(status=status)
    
    # Get all campaigns for filter dropdown
    campaigns = Campaign.objects.all().order_by('name')
    
    return render(request, 'campaigns/logs.html', {
        'logs': logs[:1000],  # Limit to 1000 for performance
        'campaigns': campaigns,
        'selected_campaign': campaign_id,
        'selected_status': status
    })

@login_required
def analytics_view(request):
    """Display analytics dashboard"""
    # Get all campaigns for statistics
    campaigns = Campaign.objects.all().order_by('-created_at')
    
    # Get daily stats for chart
    daily_stats = get_daily_stats(days=14)
    
    return render(request, 'campaigns/analytics.html', {
        'campaigns': campaigns,
        'daily_stats': json.dumps(daily_stats)
    })

# API endpoints for charts
@login_required
def campaign_stats(request, campaign_id):
    """Get statistics for a specific campaign as JSON"""
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    stats = get_campaign_stats(campaign)
    return JsonResponse(stats)

@login_required
def daily_stats(request):
    """Get daily email statistics as JSON"""
    days = int(request.GET.get('days', 7))
    stats = get_daily_stats(days=days)
    return JsonResponse(stats)
