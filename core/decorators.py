from django.shortcuts import redirect
from django.contrib import messages

from core.roles import tiene_permiso


def requiere_permiso(permiso):
    """Restringe una vista a los usuarios con `permiso` (ver core/roles.py)."""
    def decorador(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('/login')
            if tiene_permiso(request.user, permiso):
                return view_func(request, *args, **kwargs)
            messages.error(
                request, 'No tenés permiso para acceder a esta sección.')
            return redirect('/')
        wrapper.__name__ = view_func.__name__
        wrapper.__doc__ = view_func.__doc__
        return wrapper
    return decorador


# Gerencia o Administración.
solo_gerencia = requiere_permiso('gestion')

# Solo Gerencia.
solo_dashboard = requiere_permiso('dashboard')
solo_usuarios = requiere_permiso('usuarios')
