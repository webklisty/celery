#!/usr/bin/env python
"""
Test script to verify email functionality in the campaign system
"""
import os
import sys
import django
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'email_campaign_system.settings')
django.setup()

from django.conf import settings
from campaigns.models import Campaign, Recipient, EmailLog, RecipientList
from campaigns.tasks import send_campaign_emails

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def test_smtp_connection():
    """Test direct connection to Gmail SMTP server"""
    logger.info("Testing SMTP connection to Gmail...")
    
    try:
        # Get email settings
        email_host = settings.EMAIL_HOST
        email_port = settings.EMAIL_PORT
        email_user = settings.EMAIL_HOST_USER
        email_password = settings.EMAIL_HOST_PASSWORD
        
        logger.info(f"Connecting to {email_host}:{email_port} as {email_user}")
        
        # Connect to SMTP server
        smtp = smtplib.SMTP(email_host, email_port)
        smtp.ehlo()
        smtp.starttls()
        
        # Log in
        smtp.login(email_user, email_password)
        logger.info("SMTP login successful!")
        
        # Close connection
        smtp.quit()
        return True
    except Exception as e:
        logger.error(f"SMTP connection failed: {str(e)}")
        return False

def send_test_email(recipient_email):
    """Send a test email to verify email functionality"""
    logger.info(f"Sending test email to {recipient_email}")
    
    try:
        # Get email settings
        email_host = settings.EMAIL_HOST
        email_port = settings.EMAIL_PORT
        email_user = settings.EMAIL_HOST_USER
        email_password = settings.EMAIL_HOST_PASSWORD
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Test Email from Campaign System'
        msg['From'] = f"Email Campaign System <{email_user}>"
        msg['To'] = recipient_email
        
        # Create email content
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ padding: 20px; max-width: 600px; margin: 0 auto; }}
                .header {{ background-color: #4A6FDC; color: white; padding: 10px 20px; }}
                .content {{ padding: 20px; border: 1px solid #ddd; }}
                .footer {{ font-size: 12px; color: #666; padding-top: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Email Campaign System Test</h2>
                </div>
                <div class="content">
                    <h3>This is a test email</h3>
                    <p>This email was sent from the Email Campaign System to verify that email functionality is working correctly.</p>
                    <p>Current server time: <strong>{current_time}</strong></p>
                    <p>If you're receiving this, the email system is configured correctly!</p>
                </div>
                <div class="footer">
                    <p>This is an automated test message. Please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Attach HTML content
        part = MIMEText(html_content, 'html')
        msg.attach(part)
        
        # Connect to SMTP server
        smtp = smtplib.SMTP(email_host, email_port)
        smtp.ehlo()
        smtp.starttls()
        smtp.login(email_user, email_password)
        
        # Send email
        smtp.send_message(msg)
        smtp.quit()
        
        logger.info("Test email sent successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to send test email: {str(e)}")
        return False

def check_active_campaigns():
    """Check for active campaigns in the system and their status"""
    logger.info("Checking active campaigns in the system...")
    
    # Get all campaigns
    campaigns = Campaign.objects.all()
    logger.info(f"Total campaigns: {campaigns.count()}")
    
    for campaign in campaigns:
        logger.info(f"Campaign: {campaign.name} (ID: {campaign.id})")
        logger.info(f"  Status: {campaign.status}")
        logger.info(f"  Schedule: {campaign.schedule_type}")
        logger.info(f"  Scheduled time: {campaign.scheduled_time}")
        
        # Check recipient list
        recipients = campaign.recipient_list.recipients.all()
        logger.info(f"  Recipients: {recipients.count()}")
        
        # Check if there are any logs
        logs = EmailLog.objects.filter(campaign=campaign)
        logger.info(f"  Email logs: {logs.count()}")
        
        # Check task ID
        if campaign.celery_task_id:
            logger.info(f"  Celery task ID: {campaign.celery_task_id}")
        else:
            logger.info("  No Celery task ID found")

def trigger_campaign_manually(campaign_id):
    """Manually trigger a campaign to send emails"""
    logger.info(f"Manually triggering campaign with ID: {campaign_id}")
    
    try:
        # Get the campaign
        campaign = Campaign.objects.get(pk=campaign_id)
        logger.info(f"Found campaign: {campaign.name}")
        
        # Set status to active if not already
        if campaign.status != 'active':
            logger.info(f"Changing status from {campaign.status} to 'active'")
            campaign.status = 'active'
            campaign.save()
        
        # Trigger the task
        logger.info("Triggering email sending task...")
        result = send_campaign_emails(str(campaign.id))
        logger.info(f"Task result: {result}")
        
        return True
    except Campaign.DoesNotExist:
        logger.error(f"Campaign with ID {campaign_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error triggering campaign: {str(e)}")
        return False

def create_test_data():
    """Create test data for the email system"""
    logger.info("Creating test data...")
    
    try:
        # Create recipient list
        recipient_list = RecipientList.objects.create(name="Test List")
        logger.info(f"Created recipient list: {recipient_list.name} (ID: {recipient_list.id})")
        
        # Create a recipient
        recipient = Recipient.objects.create(
            email="test@example.com",
            name="Test User",
            recipient_list=recipient_list
        )
        logger.info(f"Created recipient: {recipient.name} <{recipient.email}>")
        
        # Create a campaign
        campaign = Campaign.objects.create(
            name="Test Campaign",
            subject="Test Email",
            content="<p>This is a test email from the campaign system.</p>",
            from_name="Email Campaign System",
            status="scheduled",
            schedule_type="one_time",
            scheduled_time=datetime.now(),
            recipient_list=recipient_list
        )
        logger.info(f"Created campaign: {campaign.name} (ID: {campaign.id})")
        
        return campaign.id
    except Exception as e:
        logger.error(f"Error creating test data: {str(e)}")
        return None

if __name__ == "__main__":
    """Main function"""
    logger.info("Email Campaign System Test")
    logger.info("========================")
    
    # Check command line arguments
    if len(sys.argv) < 2:
        logger.info("Usage: python test_email.py <command> [<args>]")
        logger.info("Commands:")
        logger.info("  smtp - Test SMTP connection")
        logger.info("  send <email> - Send test email to <email>")
        logger.info("  check - Check active campaigns")
        logger.info("  trigger <campaign_id> - Trigger campaign manually")
        logger.info("  create - Create test data")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "smtp":
        test_smtp_connection()
    
    elif command == "send":
        if len(sys.argv) < 3:
            logger.error("Missing recipient email")
            logger.info("Usage: python test_email.py send <email>")
            sys.exit(1)
        
        recipient_email = sys.argv[2]
        send_test_email(recipient_email)
    
    elif command == "check":
        check_active_campaigns()
    
    elif command == "trigger":
        if len(sys.argv) < 3:
            logger.error("Missing campaign ID")
            logger.info("Usage: python test_email.py trigger <campaign_id>")
            sys.exit(1)
        
        campaign_id = sys.argv[2]
        trigger_campaign_manually(campaign_id)
    
    elif command == "create":
        create_test_data()
    
    else:
        logger.error(f"Unknown command: {command}")
        sys.exit(1)
    
    logger.info("Test completed")