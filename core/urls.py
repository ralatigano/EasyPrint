from django.urls import path, include
from .views import (
    iniciar_sesion, cerrar_sesion, registrar_usuario,
    editar_perfil, cambiar_contrasena, restablecer_contrasena,
    correo_contrasena, dark_mode, get_dark_mode, obtener_usuarios, prueba
)

urlpatterns = [
    # Login y Logout
    path('', iniciar_sesion, name="login"),
    path('logout', cerrar_sesion, name='logout'),
    # Creación de usuario
    path('registrar', registrar_usuario, name='registrarUsuario'),
    # Edición de perfil
    path('perfil', editar_perfil, name='perfil'),
    path('cambiarContrasena', cambiar_contrasena, name='cambiarContrasena'),
    # Restablecer contraseña
    path('restablecerContrasena', restablecer_contrasena,
         name='restablecerContrasena'),
    path('correoContrasena', correo_contrasena, name='correoContrasena'),
    # Preferencia de tema oscuro/claro
    path('valorDarkMode/<str:tema>', dark_mode, name='valorDarkMode'),
    path('getDarkMode', get_dark_mode, name='getDarkMode'),
    # Envía una lista con los nombres de los usuarios al frontend
    path('obtenerUsuarios', obtener_usuarios, name='obtenerUsuarios'),
    path('prueba', prueba, name='prueba'),
]
