from django.contrib import admin
from .models import Cliente
# Register your models here.


class AdminCLientes(admin.ModelAdmin):
    list_display = ["nombre", "negocio", "telefono",
                    "email", "metodo_contacto", "created"]
    search_fields = ["nombre"]
    list_filter = ["created", "metodo_contacto"]
    list_per_page = 25
    readonly_fields = ["created", "updated"]


admin.site.register(Cliente, AdminCLientes)
