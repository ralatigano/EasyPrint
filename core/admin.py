from django.contrib import admin
from .models import Usuario
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
# Register your models here.


class UsuarioInline(admin.StackedInline):
    model = Usuario
    can_delete = False
    verbose_name_plural = "usuarios"

# Define a new User admin


class UserAdmin(BaseUserAdmin):
    inlines = [UsuarioInline]


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
