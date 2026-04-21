from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'datetime', 'source', 'status', 'created_at')
    list_filter = ('source', 'status', 'created_at')
    search_fields = ('title', 'description', 'user__username', 'user__email')
    ordering = ('-created_at',)
