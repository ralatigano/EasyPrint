from django.urls import path
from .views import (
    pedidos, cambiar_estado, cambiar_enc, agregar_descripcion,
    agregar_senia, completar_pedido, confirmar_pedido, get_productos_info,
    eliminar_pedido, preparar_completar_pedido,
    viajes_cadete, guardar_viaje_cadete, borrar_viaje_cadete, info_viaje_cadete, actualizar_estado_viajes, exportar_viajes_cadete
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
    path('eliminarPedido/<int:pedido_id>',
         eliminar_pedido, name='eliminarPedido'),
    # responde a una petición ajax para cargar un modal con información de los productos de un pedido
    path('obtenerDatosProductos', get_productos_info,
         name='obtenerDatosProductos'),
    path('prepararCompletarPedido/<int:presupuesto_numero>',
         preparar_completar_pedido, name='prepararCompletarPedido'),
    # Tabla viajes de cadete
    path('viajesCadete', viajes_cadete, name='viajesCadete'),
    path('guardarViajeCadete', guardar_viaje_cadete, name='guardarViajeCadete'),
    path('borrarViajeCadete/<int:viaje_id>',
         borrar_viaje_cadete, name='borrarViajeCadete'),
    path('infoViajeCadete/<int:viaje_id>',
         info_viaje_cadete, name='infoViajeCadete'),
    path('actualizarEstadoViajes', actualizar_estado_viajes,
         name='actualizarEstadoViajes'),
    path('exportarViajesCadete', exportar_viajes_cadete,
         name='exportar_viajes_cadete'),
]
