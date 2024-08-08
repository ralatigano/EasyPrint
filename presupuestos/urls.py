from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    Inicio, presupuestos,  calcular_cantidad_por_hoja, agregar_descartar_producto,
    borrar_imagen_generada, obtener_productos, calculo_rapido, delete_calc_presupuesto,
    destroy_calc_presupuesto, edit_producto_cotizado, guardar_presupuesto, editar_presupuesto,
    generar_presupuesto_pdf,
)


urlpatterns = [
    # Home
    path('inicio/', Inicio, name="inicio"),
    # Tabla presupuestos
    path('', presupuestos, name='presupuestos'),
    # vista llamada desde el frontend para obtener los productos pertenecientes a una categoría.
    path('obtenerProductos', obtener_productos, name='obtenerProductos'),
    # vista que hace cálculos y se comunica con el frontend para mostrar los resultados en un modal.
    path('calcularCantHojas', calcular_cantidad_por_hoja,
         name='calcularCantHojas'),
    # vista que es llamada desde el frontend y borra la imagen que se genera con los cálculos.
    path('borrarImagenGenerada', borrar_imagen_generada,
         name='borrarImagenGenerada'),
    # vista que realiza los cálculos y los pasa al frontend para mostrarlos en un modal.
    path('calculoRapido', calculo_rapido, name='calculoRapido'),
    # vista que permite agregar o descartar un producto desde el modal de cálculo de costos.
    path('agregarDescartarProducto/<str:str>',
         agregar_descartar_producto, name='agregarDescartarProducto'),
    # vista que permite borrar un producto del presupuesto que se está armando.
    path('deleteCalc_Presupuesto/<str:r>/',
         delete_calc_presupuesto, name='deleteCalc_Presupuesto'),
    # vista que permite borrar todos los items del presupuesto que se está armando.
    path('borrarTodo', destroy_calc_presupuesto, name='borrarTodo'),
    # vista que permite editar algunos datos deun producto de la cotización actual.
    path('editarProductoCotizado',
         edit_producto_cotizado, name='editarProductoCotizado'),
    path('guardarPresupuesto', guardar_presupuesto, name='guardarPresupuesto'),
    path('verPresupuesto/<int:np>', editar_presupuesto, name='verPresupuesto'),
    path('descargarPresupuesto/<int:np>',
         generar_presupuesto_pdf, name='descargarPresupuestoPDF'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
