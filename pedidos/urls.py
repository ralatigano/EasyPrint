from django.urls import path
from .views import (
    pedidos, cambiar_estado, cambiar_enc, agregar_descripcion,
    agregar_senia, completar_pedido, confirmar_pedido, get_productos_info
)


urlpatterns = [
    # Tabla pedidos
    path('', pedidos, name='pedidos'),
    # Vista para completar el pedido en función de un presupuesto.
    path('completarPedido', completar_pedido, name='completarPedido'),
    path('confirmarPedido', confirmar_pedido, name='confirmarPedido'),
    # Editar atributos específicos de un pedido
    path('cambiarEstado', cambiar_estado, name='cambiarEstado'),
    path('cambiarEncargado', cambiar_enc, name='cambiarEncargado'),
    path('agregarDescripcion', agregar_descripcion, name='agregar_descripcion'),
    path('agregarSenia', agregar_senia, name='agregar_senia'),
    # responde a una petición ajax para cargar un modal con información de los productos de un pedido
    path('obtenerDatosProductos', get_productos_info,
         name='obtenerDatosProductos'),
]
