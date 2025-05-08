import csv
import io
import logging
import base64
import json
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

def process_csv_file(csv_file, recipient_list):
    """
    Process uploaded CSV file and create recipients
    
    Args:
        csv_file: File object containing CSV data
        recipient_list: RecipientList object to associate recipients with
        
    Returns:
        tuple: (success_count, error_count, error_messages)
    """
    from .models import Recipient
    
    success_count = 0
    error_count = 0
    error_messages = []
    
    try:
        # Read CSV file
        csv_data = csv_file.read().decode('utf-8')
        csv_io = io.StringIO(csv_data)
        reader = csv.DictReader(csv_io)
        
        with transaction.atomic():
            for row in reader:
                try:
                    email = row.get('email', '').strip()
                    name = row.get('name', '').strip()
                    
                    # Validate data
                    if not email:
                        error_count += 1
                        error_messages.append(f"Row {reader.line_num}: Email is required")
                        continue
                    
                    # Create or update recipient
                    recipient, created = Recipient.objects.update_or_create(
                        email=email,
                        recipient_list=recipient_list,
                        defaults={'name': name or email.split('@')[0]}
                    )
                    
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    error_messages.append(f"Row {reader.line_num}: {str(e)}")
                    
        return success_count, error_count, error_messages
        
    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        return 0, 1, [f"Error processing CSV: {str(e)}"]

def get_gmail_oauth2_credentials():
    """
    Get Gmail OAuth2 credentials using the refresh token
    
    Returns:
        dict: Dictionary containing access token
    """
    try:
        # If no refresh token, return empty dict
        if not settings.GOOGLE_REFRESH_TOKEN:
            return {}
            
        # Create credentials object
        credentials = Credentials(
            None,  # No access token initially
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            token_uri='https://oauth2.googleapis.com/token',
            scopes=['https://mail.google.com/']
        )
        
        # Refresh the token
        credentials.refresh(Request())
        
        return {
            'access_token': credentials.token,
            'expires_in': credentials.expiry.timestamp() if credentials.expiry else None
        }
        
    except Exception as e:
        logger.error(f"Error getting Gmail OAuth2 credentials: {str(e)}")
        return {}

def format_template_content(content, recipient):
    """
    Format email content by replacing template variables
    
    Args:
        content: Email content with template variables
        recipient: Recipient object
    
    Returns:
        str: Formatted content
    """
    from string import Template
    template = Template(content)
    context = {
        'name': recipient.name,
        'email': recipient.email,
    }
    return template.safe_substitute(context)

def get_campaign_stats(campaign):
    """
    Get statistics for a specific campaign
    
    Args:
        campaign: Campaign object
    
    Returns:
        dict: Campaign statistics
    """
    from .models import EmailLog
    
    sent_count = EmailLog.objects.filter(campaign=campaign, status='sent').count()
    error_count = EmailLog.objects.filter(campaign=campaign, status='error').count()
    total_recipients = campaign.recipient_list.recipients.count()
    remaining = total_recipients - (sent_count + error_count)
    
    return {
        'sent': sent_count,
        'errors': error_count,
        'total': total_recipients,
        'remaining': remaining,
        'completion_percentage': int((sent_count / total_recipients) * 100) if total_recipients > 0 else 0
    }

def get_daily_stats(days=7):
    """
    Get email statistics for the last n days
    
    Args:
        days: Number of days to include in statistics
    
    Returns:
        dict: Daily statistics
    """
    from .models import EmailLog
    from django.db.models import Count
    from django.utils import timezone
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days-1)
    
    # Initialize result with all dates
    result = {
        'labels': [],
        'sent': [],
        'errors': []
    }
    
    # Create a dictionary for each date
    current_date = start_date
    while current_date <= end_date:
        result['labels'].append(current_date.strftime('%b %d'))
        
        # Get logs for this date
        day_logs = EmailLog.objects.filter(sent_at__date=current_date)
        result['sent'].append(day_logs.filter(status='sent').count())
        result['errors'].append(day_logs.filter(status='error').count())
        
        current_date += timedelta(days=1)
    
    return result
