from django.contrib import admin

from .models import (
    GmailIntegration,
    GmailSyncedMessage,
    GoogleCalendarIntegration,
    GoogleCalendarTaskSync,
    WhatsAppIntegration,
    WhatsAppSyncedMessage,
)


@admin.register(GmailIntegration)
class GmailIntegrationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'gmail_email', 'connected_at', 'updated_at')
    search_fields = ('gmail_email', 'user__username', 'user__email')
    ordering = ('-connected_at',)


@admin.register(GmailSyncedMessage)
class GmailSyncedMessageAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'gmail_message_id',
        'extraction_status',
        'task',
        'fetched_at',
    )
    list_filter = ('extraction_status', 'fetched_at')
    search_fields = (
        'gmail_message_id',
        'subject',
        'snippet',
        'user__username',
        'user__email',
    )
    ordering = ('-fetched_at',)


@admin.register(GoogleCalendarIntegration)
class GoogleCalendarIntegrationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'google_email', 'connected_at', 'updated_at')
    search_fields = ('google_email', 'user__username', 'user__email')
    ordering = ('-connected_at',)


@admin.register(WhatsAppIntegration)
class WhatsAppIntegrationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'phone_number_id', 'business_phone_number', 'connected_at')
    search_fields = ('phone_number_id', 'business_phone_number', 'user__username', 'user__email')
    ordering = ('-connected_at',)


@admin.register(WhatsAppSyncedMessage)
class WhatsAppSyncedMessageAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'whatsapp_message_id',
        'from_number',
        'message_type',
        'extraction_status',
        'task',
        'received_at',
    )
    list_filter = ('message_type', 'extraction_status', 'received_at')
    search_fields = (
        'whatsapp_message_id',
        'from_number',
        'text_body',
        'user__username',
        'user__email',
    )
    ordering = ('-received_at',)


@admin.register(GoogleCalendarTaskSync)
class GoogleCalendarTaskSyncAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'task',
        'calendar_id',
        'calendar_event_id',
        'status',
        'synced_at',
    )
    list_filter = ('status', 'calendar_id', 'synced_at')
    search_fields = (
        'calendar_event_id',
        'task__title',
        'user__username',
        'user__email',
    )
    ordering = ('-synced_at',)
