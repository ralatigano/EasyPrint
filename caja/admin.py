from django.contrib import admin

from .models import Movimiento


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'referencia', 'tipo', 'medio', 'monto', 'usuario')
    list_filter = ('medio', 'tipo')
    search_fields = ('referencia', 'nota')
