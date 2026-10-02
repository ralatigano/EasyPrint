from core.roles import VENTAS, permisos_de


def rol_usuario(request):
    if not request.user.is_authenticated:
        return {'es_gerencia': False, 'es_ventas': False, 'es_super': False,
                'puede': {}}

    puede = permisos_de(request.user)
    return {
        'es_super':    request.user.is_superuser,
        # `es_gerencia` incluye a Administración: habilita las funciones de gestión.
        'es_gerencia': puede['gestion'],
        'es_ventas':   request.user.groups.filter(name=VENTAS).exists(),
        # Permisos finos (core/roles.py): `{% if puede.dashboard %}`, etc.
        'puede':       puede,
    }
