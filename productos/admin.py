from django.contrib import admin
from .models import (Insumo, Producto,
                     ComponenteProducto, ProductoCotizado,
                     FaltanteInsumo, Categoria)

# Register your models here.


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'unidad_medida', 'stock',
                    'precio', 'activo')
    search_fields = ('nombre',)
    list_filter = ('unidad_medida', 'activo')
    ordering = ('nombre',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tercerizado', 'factor', 'activo')
    search_fields = ('nombre',)
    list_filter = ('tercerizado', 'activo')
    ordering = ('nombre',)
    inlines = []  # Podés sumar el inline de ComponenteProducto si querés editar en la misma vista


class ComponenteProductoInline(admin.TabularInline):
    model = ComponenteProducto
    extra = 1


@admin.register(ComponenteProducto)
class ComponenteProductoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'insumo', 'cantidad', 'unidad', 'alternativo')
    list_filter = ('alternativo', 'unidad')
    search_fields = ('producto__nombre', 'insumo__nombre')
    raw_id_fields = ('producto', 'insumo')


@admin.register(ProductoCotizado)
class ProductoCotizadoAdmin(admin.ModelAdmin):
    list_display = (
        'producto',
        'producto__tercerizado',
        'producto__factor',
        'producto__categoria',
        'producto__activo',
        'cantidad',
        'empaquetado',
        'resultado'
    )
    list_filter = (
        'producto__tercerizado',
        'producto__activo',
        'producto__categoria',
        'empaquetado'
    )
    search_fields = ('producto__nombre', 'cliente')
    readonly_fields = ('resultado',)
    ordering = ('-id',)


class AdminCategoria(admin.ModelAdmin):
    list_display = ["nombre", "created"]
    search_fields = ["nombre"]
    list_filter = ["nombre"]
    list_per_page = 25
    readonly_fields = ["created", "updated"]


admin.site.register(Categoria, AdminCategoria)


@admin.register(FaltanteInsumo)
class FaltanteInsumoAdmin(admin.ModelAdmin):
    list_display = ('insumo', 'pedido', 'cantidad_faltante',
                    'registrado_en', 'resuelto')
    list_filter = ('resuelto', 'registrado_en')
    search_fields = ('insumo__nombre', 'pedido__numero')
