from django.urls import path
from .views import dashboard


urlpatterns = [
    # Tabla clientes
    path('', dashboard, name='dashboard'),

]
