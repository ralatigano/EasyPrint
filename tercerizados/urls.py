from django.urls import path

from . import views

urlpatterns = [
    path('', views.control_tercerizados, name='control_tercerizados'),
    path('guardar', views.guardar_tercerizado, name='guardar_tercerizado'),
    path('info/<int:pedido_id>', views.info_tercerizado,
         name='info_tercerizado'),
    path('borrar/<int:pedido_id>', views.borrar_tercerizado,
         name='borrar_tercerizado'),
    path('revisados', views.marcar_revisados, name='marcar_revisados'),
    # Pagos
    path('pagar', views.registrar_pago, name='registrar_pago_tercerizado'),
    path('pagos/anular/<int:pago_id>', views.anular_pago,
         name='anular_pago_tercerizado'),
    path('pendientes/<int:proveedor_id>', views.pendientes_proveedor,
         name='pendientes_proveedor'),
    # Log y credenciales
    path('auditoria', views.auditoria, name='auditoria_tercerizados'),
    path('tokens', views.tokens_agente, name='tercerizados_tokens'),
    path('tokens/crear', views.crear_token, name='crear_token_agente'),
    path('tokens/alternar/<int:token_id>', views.alternar_token,
         name='alternar_token_agente'),
    path('tokens/borrar/<int:token_id>', views.borrar_token,
         name='borrar_token_agente'),
    # Exportar
    path('exportar', views.exportar_tercerizados,
         name='exportar_tercerizados'),
]
