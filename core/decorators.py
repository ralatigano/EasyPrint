from django.shortcuts import redirect
from django.contrib import messages


def solo_gerencia(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login')
        if request.user.is_superuser or request.user.groups.filter(name='Gerencia').exists():
            return view_func(request, *args, **kwargs)
        messages.error(
            request, 'No tenés permiso para acceder a esta sección.')
        return redirect('/')
    return wrapper
