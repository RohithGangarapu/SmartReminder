from django.urls import path

from . import views

urlpatterns = [
    path('extract-task', views.extract_task, name='ai-extract-task'),
]
