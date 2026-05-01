from django.urls import path

from . import views

urlpatterns = [
    path('status', views.integrations_status, name='integrations-status'),
    path('sync-now', views.integrations_sync_now, name='integrations-sync-now'),
    path('gmail/connect', views.gmail_connect, name='gmail-connect'),
    path('gmail/fetch', views.gmail_fetch, name='gmail-fetch'),
    path('google/start', views.google_oauth_start, name='google-oauth-start'),
    path('google/callback', views.google_oauth_callback, name='google-oauth-callback'),
    path('google-calendar/auth-url', views.google_calendar_auth_url, name='google-calendar-auth-url'),
    path('google-calendar/connect', views.google_calendar_connect, name='google-calendar-connect'),
    path('google-calendar/sync-tasks', views.google_calendar_sync_tasks, name='google-calendar-sync-tasks'),
    path('google-calendar/sync-task/<int:task_id>', views.google_calendar_sync_task, name='google-calendar-sync-task'),
    path('google-calendar/sync-task/<int:task_id>/remove', views.google_calendar_unsync_task, name='google-calendar-unsync-task'),
    path('whatsapp/connect', views.whatsapp_connect, name='whatsapp-connect'),
    path('whatsapp/webhook', views.whatsapp_webhook, name='whatsapp-webhook'),
    path('whatsapp/fetch', views.whatsapp_fetch, name='whatsapp-fetch'),
]
