import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SmartReminder.settings')

app = Celery('SmartReminder')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'integrations-periodic-sync': {
        'task': 'integrations.tasks.periodic_integrations_sync',
        'schedule': crontab(minute='*/10'),
    }
}
