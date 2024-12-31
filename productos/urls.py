from django.urls import path
from .views import (
    productos, cargar_productos, borrar_producto, guardar_producto, info_editar_producto, obtener_producto, exportar_productos, borrar_todos_productos,
    categorias, guardar_categoria, borrar_categoria, obtener_categoria,
)

urlpatterns = [
    # Tabla productos
    path('', productos, name='productos'),
    # CRUD productos
    path('cargarProductos', cargar_productos, name='cargarProcutos'),
    # Borra un producto desde la tabla de productos.
    path('borrarProducto/<int:producto_id>',
         borrar_producto, name='borrarProducto'),
    # Envía los datos al frontend para colaborar con el funcionamiento de un modal.
    path('infoEditarProducto', info_editar_producto, name='infoEditarProducto'),
    path('obtenerProducto/<int:producto_id>',
         obtener_producto, name='obtenerProducto'),
    path('guardarProducto', guardar_producto, name='guardarProducto'),
    # Genera un excel con la base de datos actual de los produtos.
    path('exportarProductos', exportar_productos, name='exportar_productos'),
    # Borra todos los productos de la base de datos.
    path('borrarProductos', borrar_todos_productos,
         name='borrar_todos_productos'),
    path('categorias/', categorias, name='categorias'),
    path('obtenerCategoria/<int:categoria_id>/',
         obtener_categoria, name='obtener_categoria'),
    path('guardarCategoria/', guardar_categoria, name='guardar_categoria'),
    path('borrarCategoria/<int:categoria_id>',
         borrar_categoria, name='borrar_categoria'),
]
