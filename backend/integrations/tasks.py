import os

from celery import shared_task

from .models import GmailIntegration, GoogleCalendarIntegration
from .views import _run_gmail_fetch_for_user, _run_google_calendar_sync_for_user


@shared_task
def periodic_integrations_sync():
    gmail_max_results = int(os.getenv('INTEGRATIONS_GMAIL_MAX_RESULTS', '10'))
    calendar_id = os.getenv('GOOGLE_CALENDAR_ID', 'primary')

    for integration in GmailIntegration.objects.select_related('user').all():
        try:
            _run_gmail_fetch_for_user(integration.user, max_results=gmail_max_results)
        except ValueError:
            continue

    for integration in GoogleCalendarIntegration.objects.select_related('user').all():
        try:
            _run_google_calendar_sync_for_user(integration.user, calendar_id=calendar_id)
        except ValueError:
            continue
