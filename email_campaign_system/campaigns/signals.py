import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Campaign, EmailLog
from .tasks import send_campaign_emails
from celery import current_app

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Campaign)
def handle_campaign_status_change(sender, instance, created, **kwargs):
    """
    Signal handler to schedule or cancel celery tasks when a campaign's status changes
    """
    if created and instance.status == 'scheduled' and instance.scheduled_time:
        # New campaign that is scheduled - create celery task
        logger.info(f"Scheduling new campaign: {instance.name} (ID: {instance.id}) for {instance.scheduled_time}")
        
        # Schedule the task
        result = send_campaign_emails.apply_async(
            args=[str(instance.id)],
            eta=instance.scheduled_time
        )
        
        # Store the task ID
        Campaign.objects.filter(id=instance.id).update(celery_task_id=result.id)
        logger.info(f"Created celery task {result.id} for campaign {instance.id}")
        
    elif not created:
        # Existing campaign - handle status updates
        if instance.status == 'cancelled' and instance.celery_task_id:
            # Cancel any scheduled tasks
            current_app.control.revoke(instance.celery_task_id, terminate=True)
            
            # Clear the task ID
            Campaign.objects.filter(id=instance.id).update(celery_task_id=None)
            logger.info(f"Cancelled celery task for campaign {instance.id}")
            
        elif instance.status == 'draft' and instance.celery_task_id:
            # Draft campaigns should not have scheduled tasks
            current_app.control.revoke(instance.celery_task_id, terminate=True)
            
            # Clear the task ID
            Campaign.objects.filter(id=instance.id).update(celery_task_id=None)
            logger.info(f"Removed scheduled task for draft campaign {instance.id}")

@receiver(post_save, sender=EmailLog)
def update_campaign_status_on_completion(sender, instance, created, **kwargs):
    """
    Signal handler to update campaign status when all emails are sent
    """
    if created and instance.status == 'sent':
        campaign = instance.campaign
        
        # Check if all recipients have received this campaign
        recipient_count = campaign.recipient_list.recipients.count()
        email_sent_count = EmailLog.objects.filter(campaign=campaign).count()
        
        # If all emails sent, mark campaign as completed
        if email_sent_count >= recipient_count and campaign.status in ['active', 'scheduled']:
            logger.info(f"All emails sent for campaign {campaign.id}. Marking as completed.")
            Campaign.objects.filter(id=campaign.id).update(
                status='completed',
                updated_at=timezone.now()
            )

@receiver(pre_delete, sender=Campaign)
def cancel_campaign_tasks_on_delete(sender, instance, **kwargs):
    """
    Signal handler to cancel any scheduled tasks when a campaign is deleted
    """
    if instance.celery_task_id:
        try:
            current_app.control.revoke(instance.celery_task_id, terminate=True)
            logger.info(f"Cancelled celery task {instance.celery_task_id} for deleted campaign {instance.id}")
        except Exception as e:
            logger.error(f"Error revoking task for campaign {instance.id}: {str(e)}")
