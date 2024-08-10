from django.urls import path
from .views import productos, cargar_productos, borrar_producto, editar_producto, info_editar_producto, exportar_productos, borrar_todos_productos


urlpatterns = [
    # Tabla productos
    path('', productos, name='productos'),
    # CRUD productos
    path('cargarProductos', cargar_productos, name='cargarProcutos'),
    # Borra un producto desde la tabla de productos.
    path('borrarProducto/<int:id>', borrar_producto, name='borrarProducto'),
    # Envía los datos al frontend para colaborar con el funcionamiento de un modal.
    path('infoEditarProducto', info_editar_producto, name='infoEditarProducto'),
    # Recibe los datos del modal y actualiza la información del producto si es que hubo cambios.
    path('editarProducto/<int:id>', editar_producto, name='editarProducto'),
    path('editarProducto', editar_producto, name='editarProducto'),
    # Genera un excel con la base de datos actual de los produtos.
    path('exportarProductos', exportar_productos, name='exportar_productos'),
    # Borra todos los productos de la base de datos.
    path('borrarProductos', borrar_todos_productos,
         name='borrar_todos_productos'),
]
