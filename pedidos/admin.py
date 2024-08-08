from django.contrib import admin
from .models import Pedido
# Register your models here.


class AdminPedidos(admin.ModelAdmin):
    list_display = ["numero", "producto", "descripcion", "precio",
                    "senia", "saldo", "estado", "cliente", "presupuesto", "created"]
    search_fields = ["cliente", "producto", "estado"]
    list_filter = ["created", "producto", "cliente", "estado"]
    list_per_page = 25
    readonly_fields = ["created", "updated"]


admin.site.register(Pedido, AdminPedidos)
