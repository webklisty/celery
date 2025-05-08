from django.db import models
from django.utils import timezone
from django.utils.text import slugify
import uuid

class RecipientList(models.Model):
    """Model for storing lists of email recipients"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class Recipient(models.Model):
    """Model for storing information about individual email recipients"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255)
    name = models.CharField(max_length=255)
    recipient_list = models.ForeignKey(
        RecipientList, 
        on_delete=models.CASCADE, 
        related_name='recipients'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['email', 'recipient_list']
    
    def __str__(self):
        return f"{self.name} <{self.email}>"

class Campaign(models.Model):
    """Model for storing email campaign information"""
    SCHEDULE_TYPES = (
        ('one_time', 'One Time'),
        ('recurring', 'Recurring'),
    )
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    content = models.TextField()
    from_name = models.CharField(max_length=255, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPES, default='one_time')
    scheduled_time = models.DateTimeField(null=True, blank=True)
    recurring_days = models.PositiveIntegerField(null=True, blank=True, help_text="Repeat campaign every X days")
    recipient_list = models.ForeignKey(
        RecipientList, 
        on_delete=models.CASCADE, 
        related_name='campaigns'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    celery_task_id = models.CharField(max_length=50, blank=True, null=True)
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return f"/campaigns/{self.id}/"
    
    @property
    def sent_count(self):
        return self.email_logs.filter(status='sent').count()
    
    @property
    def error_count(self):
        return self.email_logs.filter(status='error').count()
    
    @property
    def total_recipients(self):
        return self.recipient_list.recipients.count()
    
    @property
    def completion_percentage(self):
        if self.total_recipients == 0:
            return 0
        return int((self.sent_count / self.total_recipients) * 100)

class EmailLog(models.Model):
    """Model for logging email sending status and errors"""
    STATUS_CHOICES = (
        ('sent', 'Sent'),
        ('error', 'Error'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign, 
        on_delete=models.CASCADE, 
        related_name='email_logs'
    )
    recipient = models.ForeignKey(
        Recipient, 
        on_delete=models.CASCADE, 
        related_name='email_logs'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['campaign', 'recipient']
        
    def __str__(self):
        return f"{self.campaign.name} - {self.recipient.email} - {self.status}"
