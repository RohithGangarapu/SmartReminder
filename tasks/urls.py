from django.urls import path

from . import views

urlpatterns = [
    path('', views.tasks_collection, name='tasks-collection'),
    path('<int:id>', views.task_detail, name='task-detail'),
]
