from django.db import models
from django.contrib.auth import authenticate, get_user_model

User=get_user_model()


class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    datetime = models.DateTimeField()
    source = models.CharField(max_length=50)  # gmail / whatsapp
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
