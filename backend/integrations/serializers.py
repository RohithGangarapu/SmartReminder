from rest_framework import serializers


class GmailConnectRequestSerializer(serializers.Serializer):
    authorization_code = serializers.CharField()
    redirect_uri = serializers.URLField()


class GoogleCalendarConnectRequestSerializer(serializers.Serializer):
    authorization_code = serializers.CharField()
    redirect_uri = serializers.URLField()


class GmailConnectResponseSerializer(serializers.Serializer):
    connected = serializers.BooleanField()
    gmail_email = serializers.EmailField()
    token_expiry = serializers.DateTimeField(allow_null=True)
    scope = serializers.CharField()


class GoogleCalendarConnectResponseSerializer(serializers.Serializer):
    connected = serializers.BooleanField()
    google_email = serializers.EmailField()
    token_expiry = serializers.DateTimeField(allow_null=True)
    scope = serializers.CharField()


class GoogleCalendarAuthUrlResponseSerializer(serializers.Serializer):
    auth_url = serializers.URLField()
    redirect_uri = serializers.URLField()
    scope = serializers.CharField()


class GmailFetchResponseSerializer(serializers.Serializer):
    fetched = serializers.IntegerField()
    created = serializers.IntegerField()
    skipped = serializers.IntegerField()
    failed = serializers.IntegerField()
    tasks = serializers.ListField(child=serializers.DictField(), required=False)


class WhatsAppConnectRequestSerializer(serializers.Serializer):
    phone_number_id = serializers.CharField()
    business_phone_number = serializers.CharField(required=False, allow_blank=True)


class WhatsAppConnectResponseSerializer(serializers.Serializer):
    connected = serializers.BooleanField()
    phone_number_id = serializers.CharField()
    business_phone_number = serializers.CharField()


class WhatsAppFetchResponseSerializer(serializers.Serializer):
    fetched = serializers.IntegerField()
    created = serializers.IntegerField()
    skipped = serializers.IntegerField()
    failed = serializers.IntegerField()
    tasks = serializers.ListField(child=serializers.DictField(), required=False)
    messages = serializers.ListField(child=serializers.DictField(), required=False)


class GoogleCalendarSyncRequestSerializer(serializers.Serializer):
    task_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=False,
    )
    calendar_id = serializers.CharField(required=False, allow_blank=False, default='primary')


class GoogleCalendarSyncResponseSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    synced = serializers.IntegerField()
    failed = serializers.IntegerField()
    results = serializers.ListField(child=serializers.DictField(), required=False)


class GoogleCalendarTaskSyncResultSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()
    title = serializers.CharField()
    status = serializers.CharField()
    calendar_id = serializers.CharField(required=False)
    calendar_event_id = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class IntegrationsStatusResponseSerializer(serializers.Serializer):
    gmail_connected = serializers.BooleanField()
    gmail_email = serializers.CharField(allow_blank=True, required=False)
    whatsapp_connected = serializers.BooleanField()
    whatsapp_phone_number_id = serializers.CharField(allow_blank=True, required=False)
    google_calendar_connected = serializers.BooleanField()
    google_calendar_email = serializers.CharField(allow_blank=True, required=False)
    total_tasks = serializers.IntegerField()
    pending_tasks = serializers.IntegerField()
    synced_tasks = serializers.IntegerField()


class SyncNowRequestSerializer(serializers.Serializer):
    gmail_max_results = serializers.IntegerField(required=False, min_value=1, max_value=50, default=10)
    calendar_id = serializers.CharField(required=False, allow_blank=False, default='primary')


class SyncNowResponseSerializer(serializers.Serializer):
    gmail = serializers.DictField(required=False)
    google_calendar = serializers.DictField(required=False)
