from django.urls import path
from .views import (
    pedidos, pedidos_v2, cambiar_estado, cambiar_enc, agregar_descripcion, cambiar_cliente_pedido,
    agregar_senia, completar_pedido, confirmar_pedido, get_productos_info,
    eliminar_pedido, preparar_completar_pedido, evaluar_entrega_fecha,
    viajes_cadete, guardar_viaje_cadete, borrar_viaje_cadete, info_viaje_cadete, actualizar_estado_viajes, exportar_viajes_cadete,
    cambiar_estado_bulk, cambiar_enc_bulk,
)


urlpatterns = [
    # Tabla pedidos
    # La tabla vieja (path '') quedó deshabilitada: la v2 ya está probada y en uso.
    # Se comenta la ruta para evitar confusiones. La vista `pedidos` y su template
    # `pedidos/pedidos.html` siguen existiendo por si hiciera falta reactivarla.
    # path('', pedidos, name='pedidos'),
    path('v2', pedidos_v2, name='pedidos_v2'),
    # Vista para completar el pedido en función de un presupuesto.
    path('completarPedido', completar_pedido, name='completarPedido'),
    path('confirmarPedido', confirmar_pedido, name='confirmarPedido'),
    path('evaluarEntrega', evaluar_entrega_fecha, name='evaluarEntrega'),
    # Editar atributos específicos de un pedido
    path('cambiarEstado', cambiar_estado, name='cambiarEstado'),
    path('cambiarEncargado', cambiar_enc, name='cambiarEncargado'),
    path('agregarDescripcion', agregar_descripcion, name='agregar_descripcion'),
    path('agregarSenia', agregar_senia, name='agregar_senia'),
    path('eliminarPedido/<int:pedido_id>',
         eliminar_pedido, name='eliminarPedido'),
    path('cambiarClientePedido',
         cambiar_cliente_pedido, name='cambiar_cliente_pedido'),
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
    path('cambiarEstadoBulk', cambiar_estado_bulk, name='cambiarEstadoBulk'),
    path('cambiarEncargadoBulk', cambiar_enc_bulk, name='cambiarEncargadoBulk'),
]
