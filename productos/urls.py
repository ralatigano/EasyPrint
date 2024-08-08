from django.urls import path
from .views import productos, cargar_productos, borrar_producto, editar_producto, info_editar_producto, exportar_productos, borrar_todos_productos


urlpatterns = [
    # Tabla productos
    path('', productos, name='productos'),
    # CRUD productos
    path('cargarProductos', cargar_productos, name='cargarProcutos'),
    path('borrarProducto/<int:id>', borrar_producto, name='borrarProducto'),
    path('infoEditarProducto', info_editar_producto, name='infoEditarProducto'),
    path('editarProducto/<int:id>', editar_producto, name='editarProducto'),
    path('editarProducto', editar_producto, name='editarProducto'),
    path('exportarProductos', exportar_productos, name='exportar_productos'),
    path('borrarProductos', borrar_todos_productos,
         name='borrar_todos_productos'),
]
