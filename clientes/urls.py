from django.urls import path
from .views import clientes, editar_cliente


urlpatterns = [
    # Tabla clientes
    path('', clientes, name='clientes'),
    # CRUD clientes
    path('editarCliente', editar_cliente, name='editar_clientes'),
]
