import logging
import smtplib
import os
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import Count

from .models import Campaign, EmailLog, Recipient
from .utils import get_gmail_oauth2_credentials

# Setup logger
logger = logging.getLogger(__name__)

@shared_task
def send_campaign_emails(campaign_id):
    """
    Send emails for a campaign to all recipients in the associated list
    """
    try:
        campaign = Campaign.objects.get(pk=campaign_id)
        
        # Check if campaign should be active
        if campaign.status not in ['active', 'scheduled']:
            logger.warning(f"Campaign {campaign.name} is not active or scheduled. Status: {campaign.status}")
            return f"Campaign {campaign.name} is not active or scheduled."
        
        # Update campaign status to active
        campaign.status = 'active'
        campaign.save()
        
        # Get recipients who haven't received this campaign yet
        recipient_ids = campaign.recipient_list.recipients.exclude(
            email_logs__campaign=campaign
        ).values_list('id', flat=True)
        
        # If all emails sent, mark campaign as completed
        if not recipient_ids:
            campaign.status = 'completed'
            campaign.save()
            return f"Campaign {campaign.name} completed. All emails sent."
        
        # Check daily quota
        today_sent_count = EmailLog.objects.filter(
            status='sent',
            sent_at__date=timezone.now().date()
        ).count()
        
        remaining_quota = settings.DAILY_EMAIL_LIMIT - today_sent_count
        if remaining_quota <= 0:
            logger.warning(f"Daily email quota exceeded. Sent {today_sent_count} emails today.")
            return "Daily email quota exceeded."
        
        # Limit batch size to remaining quota
        batch_size = min(50, remaining_quota)  # Process in small batches
        recipients_batch = Recipient.objects.filter(id__in=recipient_ids[:batch_size])
        
        # Setup email connection
        if hasattr(settings, 'GOOGLE_REFRESH_TOKEN') and settings.GOOGLE_REFRESH_TOKEN:
            # Use OAuth2 if configured
            try:
                smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
                smtp_server.ehlo()
                smtp_server.starttls()
                
                creds = get_gmail_oauth2_credentials()
                auth_string = f'user={settings.EMAIL_HOST_USER}\1auth=Bearer {creds["access_token"]}\1\1'
                smtp_server.docmd('AUTH', f'XOAUTH2 {auth_string}')
                
                logger.info("Connected to Gmail SMTP using OAuth2")
            except Exception as e:
                logger.error(f"OAuth2 authentication failed: {str(e)}")
                # Fallback to basic auth
                smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
                smtp_server.ehlo()
                smtp_server.starttls()
                smtp_server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
                logger.info("Fallback to basic auth successful")
        else:
            # Use basic authentication
            smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
            smtp_server.ehlo()
            smtp_server.starttls()
            smtp_server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            logger.info("Connected to Gmail SMTP using basic auth")
        
        sent_count = 0
        error_count = 0
        
        try:
            for recipient in recipients_batch:
                try:
                    # Replace template variables in content
                    content_template = Template(campaign.content)
                    personalized_content = content_template.safe_substitute(
                        name=recipient.name,
                        email=recipient.email
                    )
                    
                    # Create email message
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = campaign.subject
                    from_header = f"{campaign.from_name} <{settings.EMAIL_HOST_USER}>" if campaign.from_name else settings.EMAIL_HOST_USER
                    msg['From'] = from_header
                    msg['To'] = recipient.email
                    
                    # Attach HTML content
                    html_part = MIMEText(personalized_content, 'html')
                    msg.attach(html_part)
                    
                    # Send email
                    smtp_server.send_message(msg)
                    
                    # Log success
                    with transaction.atomic():
                        EmailLog.objects.create(
                            campaign=campaign,
                            recipient=recipient,
                            status='sent',
                            sent_at=timezone.now()
                        )
                    
                    sent_count += 1
                    
                except Exception as e:
                    # Log error
                    logger.error(f"Error sending to {recipient.email}: {str(e)}")
                    with transaction.atomic():
                        EmailLog.objects.create(
                            campaign=campaign,
                            recipient=recipient,
                            status='error',
                            error_message=str(e),
                            sent_at=timezone.now()
                        )
                    error_count += 1
        
        finally:
            # Close SMTP connection
            smtp_server.quit()
        
        # Schedule next batch if needed
        remaining_recipients = recipient_ids.count() - batch_size
        if remaining_recipients > 0:
            send_campaign_emails.apply_async(
                args=[campaign_id],
                countdown=300  # 5 minutes between batches to avoid rate limits
            )
        elif campaign.schedule_type == 'recurring' and campaign.recurring_days:
            # Schedule next run for recurring campaigns
            next_run = timezone.now() + timedelta(days=campaign.recurring_days)
            campaign.scheduled_time = next_run
            campaign.save()
            
            # Schedule the next recurring task
            send_campaign_emails.apply_async(
                args=[campaign_id],
                eta=next_run
            )
        else:
            # Mark one-time campaign as completed if all emails sent
            campaign.status = 'completed'
            campaign.save()
        
        return f"Campaign '{campaign.name}' processed. Sent: {sent_count}, Errors: {error_count}, Remaining: {remaining_recipients}"
    
    except Campaign.DoesNotExist:
        logger.error(f"Campaign with ID {campaign_id} does not exist")
        return f"Campaign with ID {campaign_id} does not exist"
    except Exception as e:
        logger.error(f"Error in send_campaign_emails task: {str(e)}")
        return f"Error: {str(e)}"

@shared_task
def check_scheduled_campaigns():
    """
    Check for campaigns that need to be sent based on their scheduled time
    """
    now = timezone.now()
    logger.info(f"Checking for scheduled campaigns at {now}")
    
    # Find campaigns that are scheduled and their scheduled time has passed
    scheduled_campaigns = Campaign.objects.filter(
        status='scheduled',
        scheduled_time__lte=now
    )
    
    logger.info(f"Found {scheduled_campaigns.count()} campaigns due for sending")
    
    for campaign in scheduled_campaigns:
        # Schedule the send_campaign_emails task for this campaign
        logger.info(f"Processing scheduled campaign: {campaign.name} (ID: {campaign.id})")
        logger.info(f"  Scheduled for: {campaign.scheduled_time}, Current time: {now}")
        logger.info(f"  Schedule type: {campaign.schedule_type}, Recipients: {campaign.recipient_list.recipients.count()}")
        
        # Explicitly mark as active to ensure it's processed
        campaign.status = 'active'
        campaign.save()
        
        # Directly trigger the email task
        result = send_campaign_emails.apply_async(
            args=[str(campaign.id)],
            countdown=5  # Start in 5 seconds to allow the status change to be saved
        )
        
        # Update the task ID
        campaign.celery_task_id = result.id
        campaign.save()
        
        # Log that we've scheduled this campaign
        logger.info(f"Scheduled campaign '{campaign.name}' (ID: {campaign.id}) for immediate sending with task ID {result.id}")
    
    # Check for draft campaigns that have scheduled times in the past
    draft_campaigns_due = Campaign.objects.filter(
        status='draft',
        scheduled_time__lte=now,
        scheduled_time__isnull=False
    )
    
    if draft_campaigns_due.count() > 0:
        logger.warning(f"Found {draft_campaigns_due.count()} draft campaigns with past scheduled times that were not sent")
        for campaign in draft_campaigns_due:
            logger.warning(f"Draft campaign not sent: {campaign.name} (ID: {campaign.id}), scheduled for {campaign.scheduled_time}")
    
    return f"Checked for scheduled campaigns. Found {scheduled_campaigns.count()} to process."

@shared_task
def generate_daily_report():
    """
    Generate a daily report of email sending activity
    """
    yesterday = timezone.now().date() - timedelta(days=1)
    
    # Get statistics for yesterday
    logs = EmailLog.objects.filter(sent_at__date=yesterday)
    sent_count = logs.filter(status='sent').count()
    error_count = logs.filter(status='error').count()
    
    # Campaign performance
    campaign_stats = logs.values('campaign__name').annotate(
        sent=Count('id', filter={'status': 'sent'}),
        errors=Count('id', filter={'status': 'error'})
    ).order_by('-sent')
    
    # Create report message
    report = f"Daily Email Report for {yesterday}\n\n"
    report += f"Total emails sent: {sent_count}\n"
    report += f"Total errors: {error_count}\n\n"
    
    report += "Campaign Performance:\n"
    for stat in campaign_stats:
        report += f"- {stat['campaign__name']}: Sent {stat['sent']}, Errors {stat['errors']}\n"
    
    logger.info(report)
    return report
