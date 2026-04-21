from django.urls import path

from . import views

urlpatterns = [
    path('gmail/connect', views.gmail_connect, name='gmail-connect'),
    path('gmail/fetch', views.gmail_fetch, name='gmail-fetch'),
    path('google-calendar/sync-tasks', views.google_calendar_sync_tasks, name='google-calendar-sync-tasks'),
    path('whatsapp/connect', views.whatsapp_connect, name='whatsapp-connect'),
    path('whatsapp/webhook', views.whatsapp_webhook, name='whatsapp-webhook'),
    path('whatsapp/fetch', views.whatsapp_fetch, name='whatsapp-fetch'),
]
