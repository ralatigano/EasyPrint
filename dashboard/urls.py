from django.urls import path
from . import views


urlpatterns = [
    # Tabla clientes
    path('', views.dashboard, name='dashboard'),
    path('guardar-objetivo/', views.guardar_objetivo, name='guardar_objetivo'),
    path('eliminar-objetivo/<int:pk>/',
         views.eliminar_objetivo, name='eliminar_objetivo'),
    path('exportar/<str:tipo>/', views.exportar_excel, name='exportar_excel'),
]
