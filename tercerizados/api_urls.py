"""Rutas de la API del agente (ver tercerizados/api.py).

Van montadas en /api/tercerizados/ y son las únicas vistas del proyecto que
aceptan un TokenAgente. Una ruta por recurso; el método HTTP elige la acción
(y cada acción pide su propio permiso en el token).
"""

from django.urls import path

from . import api

urlpatterns = [
    path('ping', api.ping, name='api_tercerizados_ping'),
    path('esquema', api.esquema, name='api_tercerizados_esquema'),
    path('proveedores', api.proveedores, name='api_tercerizados_proveedores'),
    path('deuda', api.deuda, name='api_tercerizados_deuda'),
    # GET lista · POST crea
    path('pedidos', api.pedidos_coleccion, name='api_tercerizados_pedidos'),
    # GET ve · PATCH/PUT/POST edita · DELETE borra
    path('pedidos/<int:pedido_id>', api.pedidos_detalle,
         name='api_tercerizados_pedido'),
    # GET lista · POST registra
    path('pagos', api.pagos_coleccion, name='api_tercerizados_pagos'),
    # DELETE anula
    path('pagos/<int:pago_id>', api.pagos_detalle, name='api_tercerizados_pago'),
]
