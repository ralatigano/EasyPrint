from django.urls import path

from .views import indice, capitulo, manual_pdf

urlpatterns = [
    path('', indice, name='ayuda_indice'),
    path('pdf', manual_pdf, name='ayuda_pdf'),
    # Después del PDF para que "pdf" no se lea como un slug de capítulo.
    path('<slug:slug>', capitulo, name='ayuda_capitulo'),
]
