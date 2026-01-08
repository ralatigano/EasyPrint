from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    Inicio, presupuestos, guardar_presupuesto, editar_presupuesto, editar_producto_cotizado, generar_presupuesto_pdf,
    obtener_cliente, cambiar_cliente, productos_por_presupuesto,
    borrar_imagen_generada, generar_grafico, calcular_cotizacion_final, agregar_producto, descartar_producto, delete_calc_presupuesto,
    destroy_calc_presupuesto, info_prod_cotizado, actualizar_detalle, set_cliente_session
)


urlpatterns = [
    # Home
    path('inicio/', Inicio, name="inicio"),
    # Tabla presupuestos
    path('', presupuestos, name='presupuestos'),
    path('generarGrafico/', generar_grafico, name='generarGrafico'),
    # vista que es llamada desde el frontend y borra la imagen que se genera con los cálculos.
    path('borrarImagenGenerada', borrar_imagen_generada,
         name='borrarImagenGenerada'),
    path('calcularCotizacionFinal', calcular_cotizacion_final,
         name='calcularCotizacionFinal'),
    path("actualizarDetalle", actualizar_detalle, name="actualizarDetalle"),
    path('agregarProducto', agregar_producto, name='agregarProducto'),
    path('descartarProducto', descartar_producto, name='descartarProducto'),
    # vista que permite borrar un producto del presupuesto que se está armando.
    path('deleteCalc_Presupuesto/<str:r>/',
         delete_calc_presupuesto, name='deleteCalc_Presupuesto'),
    # vista que permite borrar todos los items del presupuesto que se está armando.
    path('borrarTodo', destroy_calc_presupuesto, name='borrarTodo'),
    # vista consultada desde el frontend para obtener información para el modal de editar un producto cotizado.
    path('infoProductoCotizado/<int:producto_id>/',
         info_prod_cotizado, name='infoProductoCotizado'),
    # vista que permite editar algunos datos de un producto de la cotización actual.
    path('editarProductoCotizado/', editar_producto_cotizado,
         name='editarProductoCotizado'),
    path('guardarPresupuesto', guardar_presupuesto, name='guardarPresupuesto'),
    path('verPresupuesto/<int:np>', editar_presupuesto, name='verPresupuesto'),
    path('descargarPresupuesto/<int:np>',
         generar_presupuesto_pdf, name='descargarPresupuestoPDF'),
    # Vista auxiliar para guardar el cliente en la sesión para poder usarlo en el flujo de guardar presupuesto o confirmar pedido.
    path('setClienteSession', set_cliente_session, name='setClienteSession'),
    # Funcionalidad para editar el cliente desde la vista de presupuestos.
    path('obtenerCliente/', obtener_cliente, name='obtenerCliente'),
    path('cambiarCliente/', cambiar_cliente, name='cambiarCliente'),
    path('productosPorPresupuesto/<int:presupuesto_numero>', productos_por_presupuesto,
         name='productosPorPresupuesto'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
