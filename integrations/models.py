from django.db import models
from django.conf import settings


class GmailIntegration(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gmail_integration',
    )
    gmail_email = models.EmailField()
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_expiry = models.DateTimeField(null=True, blank=True)
    scope = models.TextField(blank=True, default='')
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user_id}:{self.gmail_email}'


class GoogleCalendarIntegration(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='google_calendar_integration',
    )
    google_email = models.EmailField()
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_expiry = models.DateTimeField(null=True, blank=True)
    scope = models.TextField(blank=True, default='')
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user_id}:{self.google_email}'


class GmailSyncedMessage(models.Model):
    STATUS_CREATED = 'created'
    STATUS_SKIPPED = 'skipped'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_SKIPPED, 'Skipped'),
        (STATUS_FAILED, 'Failed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gmail_synced_messages',
    )
    integration = models.ForeignKey(
        GmailIntegration,
        on_delete=models.CASCADE,
        related_name='synced_messages',
    )
    gmail_message_id = models.CharField(max_length=255)
    subject = models.TextField(blank=True, default='')
    snippet = models.TextField(blank=True, default='')
    task = models.ForeignKey(
        'tasks.Task',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='gmail_source_messages',
    )
    extraction_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CREATED,
    )
    error_message = models.TextField(blank=True, default='')
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'gmail_message_id'],
                name='unique_gmail_message_per_user',
            )
        ]

    def __str__(self):
        return f'{self.user_id}:{self.gmail_message_id}:{self.extraction_status}'


class WhatsAppIntegration(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='whatsapp_integration',
    )
    phone_number_id = models.CharField(max_length=255, unique=True)
    business_phone_number = models.CharField(max_length=32, blank=True, default='')
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user_id}:{self.phone_number_id}'


class WhatsAppSyncedMessage(models.Model):
    STATUS_CREATED = 'created'
    STATUS_SKIPPED = 'skipped'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_SKIPPED, 'Skipped'),
        (STATUS_FAILED, 'Failed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='whatsapp_synced_messages',
    )
    integration = models.ForeignKey(
        WhatsAppIntegration,
        on_delete=models.CASCADE,
        related_name='synced_messages',
    )
    whatsapp_message_id = models.CharField(max_length=255)
    from_number = models.CharField(max_length=32, blank=True, default='')
    message_type = models.CharField(max_length=50, blank=True, default='')
    text_body = models.TextField(blank=True, default='')
    raw_payload = models.JSONField(default=dict, blank=True)
    task = models.ForeignKey(
        'tasks.Task',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='whatsapp_source_messages',
    )
    extraction_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CREATED,
    )
    error_message = models.TextField(blank=True, default='')
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'whatsapp_message_id'],
                name='unique_whatsapp_message_per_user',
            )
        ]

    def __str__(self):
        return f'{self.user_id}:{self.whatsapp_message_id}:{self.extraction_status}'


class GoogleCalendarTaskSync(models.Model):
    STATUS_SYNCED = 'synced'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_SYNCED, 'Synced'),
        (STATUS_FAILED, 'Failed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='google_calendar_task_syncs',
    )
    integration = models.ForeignKey(
        GoogleCalendarIntegration,
        on_delete=models.CASCADE,
        related_name='google_calendar_task_syncs',
    )
    task = models.OneToOneField(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='google_calendar_sync',
    )
    calendar_id = models.CharField(max_length=255, default='primary')
    calendar_event_id = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SYNCED)
    error_message = models.TextField(blank=True, default='')
    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'calendar_event_id'],
                name='unique_google_calendar_event_per_user',
            )
        ]

    def __str__(self):
        return f'{self.user_id}:{self.task_id}:{self.status}'
