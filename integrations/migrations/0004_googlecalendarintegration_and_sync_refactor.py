from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_google_calendar_integrations(apps, schema_editor):
    GmailIntegration = apps.get_model('integrations', 'GmailIntegration')
    GoogleCalendarIntegration = apps.get_model('integrations', 'GoogleCalendarIntegration')
    GoogleCalendarTaskSync = apps.get_model('integrations', 'GoogleCalendarTaskSync')

    users_with_syncs = set(
        GoogleCalendarTaskSync.objects.values_list('user_id', flat=True).distinct()
    )

    for gmail_integration in GmailIntegration.objects.all():
        if gmail_integration.user_id not in users_with_syncs:
            continue

        GoogleCalendarIntegration.objects.update_or_create(
            user_id=gmail_integration.user_id,
            defaults={
                'google_email': gmail_integration.gmail_email,
                'access_token': gmail_integration.access_token,
                'refresh_token': gmail_integration.refresh_token,
                'token_expiry': gmail_integration.token_expiry,
                'scope': gmail_integration.scope,
            },
        )

    for sync in GoogleCalendarTaskSync.objects.all():
        calendar_integration = GoogleCalendarIntegration.objects.filter(user_id=sync.user_id).first()
        if calendar_integration:
            sync.calendar_integration_id = calendar_integration.id
            sync.save(update_fields=['calendar_integration'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('integrations', '0003_googlecalendartasksync_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='GoogleCalendarIntegration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('google_email', models.EmailField(max_length=254)),
                ('access_token', models.TextField()),
                ('refresh_token', models.TextField()),
                ('token_expiry', models.DateTimeField(blank=True, null=True)),
                ('scope', models.TextField(blank=True, default='')),
                ('connected_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='google_calendar_integration', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='googlecalendartasksync',
            name='calendar_integration',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='google_calendar_task_syncs_temp',
                to='integrations.googlecalendarintegration',
            ),
        ),
        migrations.RunPython(copy_google_calendar_integrations, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='googlecalendartasksync',
            name='integration',
        ),
        migrations.RenameField(
            model_name='googlecalendartasksync',
            old_name='calendar_integration',
            new_name='integration',
        ),
        migrations.AlterField(
            model_name='googlecalendartasksync',
            name='integration',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='google_calendar_task_syncs',
                to='integrations.googlecalendarintegration',
            ),
        ),
    ]
