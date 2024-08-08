from django.urls import path
from .views import clientes, editar_cliente


urlpatterns = [
    # Tabla productos
    path('', clientes, name='clientes'),
    # CRUD productos
    path('editarCliente', editar_cliente, name='editar_clientes'),
]
