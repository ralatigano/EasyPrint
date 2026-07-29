from django.contrib import admin

from .models import Comprobante, TokenAcceso


@admin.register(Comprobante)
class ComprobanteAdmin(admin.ModelAdmin):
    list_display = (
        "numero_formateado",
        "get_tipo_cbte_display",
        "estado",
        "ambiente",
        "importe_total",
        "pedido",
        "fecha_emision",
    )
    list_filter = ("estado", "ambiente", "tipo_cbte")
    search_fields = ("numero", "cae", "receptor_nombre", "pedido__numero")
    readonly_fields = ("cae", "cae_vencimiento", "numero", "respuesta_afip", "created", "updated")


@admin.register(TokenAcceso)
class TokenAccesoAdmin(admin.ModelAdmin):
    list_display = ("servicio", "ambiente", "expiracion", "generado")
    readonly_fields = ("token", "sign", "generado")
