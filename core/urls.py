from django.urls import path, include
from .views import (
    iniciar_sesion, cerrar_sesion, registrar_usuario,
    editar_perfil, cambiar_contrasena, restablecer_contrasena,
    correo_contrasena, dark_mode, get_dark_mode,
    obtener_usuarios, usuarios,
    info_grupos, usuario_info,
    crear_editar_usuario, validar_username, borrar_usuario,
)

urlpatterns = [
    # Login y Logout
    path('', iniciar_sesion, name="login"),
    path('logout', cerrar_sesion, name='logout'),
    # Creación de usuario
    path('registrar', registrar_usuario, name='registrarUsuario'),
    # Edición de perfil - cambio de contraseña
    path('perfil', editar_perfil, name='perfil'),
    path('cambiarContrasena', cambiar_contrasena, name='cambiarContrasena'),
    # Restablecer contraseña - enviar correo con contraseña temporal
    path('restablecerContrasena', restablecer_contrasena,
         name='restablecerContrasena'),
    path('correoContrasena', correo_contrasena, name='correoContrasena'),
    # Preferencia de tema oscuro/claro
    path('valorDarkMode/<str:tema>', dark_mode, name='valorDarkMode'),
    path('getDarkMode', get_dark_mode, name='getDarkMode'),
    # Envía una lista con los nombres de los usuarios al frontend
    path('obtenerUsuarios', obtener_usuarios, name='obtenerUsuarios'),
    path('usuarios', usuarios, name='usuarios'),
    # Tabla usuarios
    path('usuarios', usuarios, name='usuarios'),
    # CRUD usuario
    path('usuarios/guardar', crear_editar_usuario, name='crear_editar_usuario'),
    path('usuarios/info/<int:user_id>', usuario_info, name='usuario_info'),
    path('usuarios/validar-username', validar_username, name='validar_username'),
    path('infoGrupos', info_grupos, name='infoGrupos'),
    # Eliminar usuario
    path('borrarUsuario/<int:usuario_id>',
         borrar_usuario, name='borrarUsuario'),
]
