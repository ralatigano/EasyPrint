from django.contrib import admin
from .models import Presupuesto
# Register your models here.


class AdminPresupuesto(admin.ModelAdmin):
    list_display = ["numero", "total", "saldo",
                    "cliente", "created", "updated"]
    search_fields = ["cliente", "numero", "created", "total", "senia", "saldo"]
    list_filter = ["created", "cliente", "updated", "total"]
    list_per_page = 25
    readonly_fields = ["numero", "created", "updated"]


admin.site.register(Presupuesto, AdminPresupuesto)
