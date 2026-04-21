from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

User = get_user_model()


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


try:
    admin.site.register(User, UserAdmin)
except admin.sites.AlreadyRegistered:
    pass
