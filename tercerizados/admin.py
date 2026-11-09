from django.contrib import admin

from .models import (
    ImputacionPago, PagoTercerizado, PedidoTercerizado, RegistroAuditoria,
    TercerizadoPedido, TokenAgente,
)


class ImputacionInline(admin.TabularInline):
    model = ImputacionPago
    extra = 0


class VinculoPedidoInline(admin.TabularInline):
    """Pedidos de EasyPrint que entran en este encargue (pueden ser varios)."""

    model = TercerizadoPedido
    extra = 0
    autocomplete_fields = ()


@admin.register(PedidoTercerizado)
class PedidoTercerizadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'proveedor', 'descripcion', 'monto',
                    'monto_pagado', 'estado', 'origen', 'revisado')
    list_filter = ('estado', 'forma_pago', 'origen', 'revisado', 'proveedor')
    search_fields = ('descripcion', 'nota', 'referencia_externa')
    date_hierarchy = 'fecha'
    # monto_pagado lo calcula services.recalcular_tercerizado.
    readonly_fields = ('monto_pagado', 'created', 'updated')
    inlines = (VinculoPedidoInline,)


@admin.register(PagoTercerizado)
class PagoTercerizadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'proveedor', 'monto', 'medio',
                    'comprobante', 'usuario')
    list_filter = ('medio', 'proveedor')
    search_fields = ('comprobante', 'nota')
    date_hierarchy = 'fecha'
    inlines = (ImputacionInline,)


@admin.register(TokenAgente)
class TokenAgenteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'prefijo', 'activo', 'permite_crear',
                    'permite_editar', 'permite_borrar', 'permite_pagar',
                    'ultimo_uso')
    list_filter = ('activo',)
    # El token en claro no se guarda; el hash no se edita a mano.
    readonly_fields = ('token_hash', 'prefijo', 'creado', 'ultimo_uso')


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    """Solo lectura: el log es append-only (ver RegistroAuditoria.save)."""

    list_display = ('momento', 'actor_tipo', 'actor', 'accion', 'objeto',
                    'objeto_id', 'resumen')
    list_filter = ('actor_tipo', 'accion', 'objeto')
    search_fields = ('actor', 'resumen')
    date_hierarchy = 'momento'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
