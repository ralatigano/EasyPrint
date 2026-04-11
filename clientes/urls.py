from django.urls import path
from .views import clientes, editar_cliente, obtener_cliente, borrar_cliente, info_adicional_cliente


urlpatterns = [
    # Tabla clientes
    path('', clientes, name='clientes'),
    # CRUD clientes
    path('editarCliente', editar_cliente, name='editar_clientes'),
    path('obtenerCliente/<int:cliente_id>',
         obtener_cliente, name='obtenerCliente'),
    path('borrarCliente/<int:cliente_id>',
         borrar_cliente, name='borrarCliente'),
    path('infoCliente/<int:cliente_id>',
         info_adicional_cliente, name='infoCliente'),
]
