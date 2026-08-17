from django.urls import path

from . import views

urlpatterns = [
    path(
        "contexto/<int:pedido_numero>",
        views.contexto_facturacion,
        name="contexto_facturacion",
    ),
    path("padron/<int:cuit>", views.consultar_padron, name="consultar_padron"),
    path("emitir", views.emitir_comprobante, name="emitir_comprobante"),
    path("comprobantes", views.lista_comprobantes, name="lista_comprobantes"),
    path(
        "comprobante/<int:comprobante_id>/pdf",
        views.comprobante_pdf,
        name="comprobante_pdf",
    ),
]
