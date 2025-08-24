from django.contrib import admin
from .models import Pedido, ViajeCadete

# Register your models here.


class AdminPedidos(admin.ModelAdmin):
    list_display = ["numero", "producto", "descripcion", "precio",
                    "senia", "saldo", "estado", "cliente", "presupuesto", "created"]
    search_fields = ["cliente", "producto", "estado"]
    list_filter = ["created", "producto", "cliente", "estado"]
    list_per_page = 25
    readonly_fields = ["created", "updated"]


admin.site.register(Pedido, AdminPedidos)


class ViajeCadeteAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'origen', 'destino',
                    'precio', 'pagado', 'fecha_pago')
    list_filter = ('pagado', 'fecha')
    search_fields = ('origen', 'destino')
    date_hierarchy = 'fecha'
    ordering = ('-fecha',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related()
