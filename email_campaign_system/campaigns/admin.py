from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Campaign, Recipient, EmailLog, RecipientList

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'status', 'schedule_type', 'scheduled_time', 'created_at')
    list_filter = ('status', 'schedule_type', 'created_at')
    search_fields = ('name', 'subject')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')

@admin.register(RecipientList)
class RecipientListAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'recipient_count')
    search_fields = ('name',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    
    def recipient_count(self, obj):
        return obj.recipients.count()
    recipient_count.short_description = 'Number of Recipients'

@admin.register(Recipient)
class RecipientAdmin(ImportExportModelAdmin):
    list_display = ('email', 'name', 'recipient_list', 'created_at')
    list_filter = ('recipient_list', 'created_at')
    search_fields = ('email', 'name')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)

@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'recipient', 'status', 'sent_at')
    list_filter = ('status', 'sent_at')
    search_fields = ('campaign__name', 'recipient__email')
    date_hierarchy = 'sent_at'
    readonly_fields = ('campaign', 'recipient', 'status', 'error_message', 'sent_at')
