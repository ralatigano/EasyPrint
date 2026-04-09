def rol_usuario(request):
    if not request.user.is_authenticated:
        return {'es_gerencia': False, 'es_ventas': False, 'es_super': False}

    es_super = request.user.is_superuser
    es_gerencia = es_super or request.user.groups.filter(
        name='Gerencia').exists()
    es_ventas = request.user.groups.filter(name='Ventas').exists()

    return {
        'es_super':    es_super,
        'es_gerencia': es_gerencia,
        'es_ventas':   es_ventas,
    }
