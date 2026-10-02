from django.urls import path

from . import views

urlpatterns = [
    path('', views.control_caja, name='control_caja'),
    path('exportar', views.exportar_caja, name='exportar_caja'),
    path('eliminar/<int:movimiento_id>', views.eliminar_movimiento,
         name='eliminar_movimiento_caja'),
]
