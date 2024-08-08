from django.contrib import admin
from .models import Producto, Categoria

# Register your models here.


class AdminProductos(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "precio",
                    "categoria", "ancho", "alto", "created"]
    search_fields = ["nombre", "categoria"]
    list_filter = ["created", "categoria", "nombre",
                   "presupuesto", 'cantidad', 'resultado']
    list_per_page = 25
    readonly_fields = ["created", "updated"]


admin.site.register(Producto, AdminProductos)


class AdminCategoria(admin.ModelAdmin):
    list_display = ["nombre", "created"]
    search_fields = ["nombre"]
    list_filter = ["nombre"]
    list_per_page = 25
    readonly_fields = ["created", "updated"]


admin.site.register(Categoria, AdminCategoria)
