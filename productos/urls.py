from django.urls import path
from .views import (
    productos, importar_productos_excel, borrar_producto, guardar_producto, datos_insumo, insumos_select, categorias_select, info_editar_producto, obtener_producto,
    exportar_productos_excel, borrar_todos_productos, obtener_dimensiones_producto, obtener_productos_categoria,
    categorias, guardar_categoria, borrar_categoria, obtener_categoria, listar_categorias,
    insumos, guardar_insumo, borrar_insumo, info_insumo, importar_insumos_excel, exportar_insumos_excel, borrar_todos_insumos,
)

urlpatterns = [
    # Tabla productos
    path('', productos, name='productos'),
    # CRUD productos
    path('guardarProducto', guardar_producto, name='guardarProducto'),
    # Borra un producto desde la tabla de productos.
    path('borrarProducto/<int:producto_id>',
         borrar_producto, name='borrarProducto'),
    # Borra todos los productos de la base de datos.
    path('borrarProductos', borrar_todos_productos,
         name='borrar_todos_productos'),
    # Importar o exportar productos desde o hacia un archivo excel
    path('importarProductos/', importar_productos_excel, name='importarProcutos'),
    path('exportarProductos', exportar_productos_excel, name='exportar_productos'),
    # Envía los datos de productos al frontend para colaborar con distitnas funciones.
    path('infoEditarProducto', info_editar_producto, name='infoEditarProducto'),
    path('obtenerProducto/<int:producto_id>',
         obtener_producto, name='obtenerProducto'),
    path('obtenerDimensiones/<int:producto_id>',
         obtener_dimensiones_producto, name='obtenerDimensiones'),
    path('obtenerInsumos', insumos_select, name='obtener_insumos'),
    path('datosInsumo/<int:id>', datos_insumo, name='datos_insumo'),
    path('obtenerCategorias', categorias_select, name='obtener_categorias'),
    path('productosPorCategoria/<int:categoria_id>',
         obtener_productos_categoria, name='obtener_productos_categoria'),
    # Tabla categorias
    path('categorias/', categorias, name='categorias'),
    # CRUD categorias
    path('guardarCategoria/', guardar_categoria, name='guardar_categoria'),
    path('borrarCategoria/<int:categoria_id>',
         borrar_categoria, name='borrar_categoria'),
    # Envía los datos de categorías al frontend para colaborar con distitnas funciones.
    path('obtenerCategoria/<int:categoria_id>/',
         obtener_categoria, name='obtener_categoria'),
    path('listarCategorias/', listar_categorias, name='listar_categorias'),
    # Tabla insumos
    path('insumos/', insumos, name='insumos'),
    # CRUD insumos
    path('guardarInsumo/', guardar_insumo, name='guardar_insumo'),
    path('borrarInsumo/<int:insumo_id>', borrar_insumo, name='borrar_insumo'),
    path('borrarTodosInsumos/', borrar_todos_insumos,
         name='borrarTodosInsumos'),
    # Envía los datos de insumos al frontend para colaborar con distitnas funciones.
    path('infoInsumo/<int:insumo_id>', info_insumo, name='info_insumo'),
    # Importar o exportar insumos desde o hacia un archivo excel
    path('importarInsumos/', importar_insumos_excel,
         name='importarInsumos'),
    path('exportarInsumos/', exportar_insumos_excel,
         name='exportarInsumos'),
]
