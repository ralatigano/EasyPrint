"""Roles de usuario (grupos de Django) y permisos derivados.

- Gerencia: acceso total.
- Administración: funciones de gestión (ABMs, configuración, caja) salvo
  Dashboard, Usuaries y exportar la caja.
- Ventas: usuario operativo sin funciones de gestión.

Cualquier chequeo de permisos debe pasar por estas funciones en lugar de
consultar los grupos a mano, para que agregar un rol o mover un permiso no
obligue a tocar cada vista. Los superusuarios tienen todos los permisos.
"""

GERENCIA = 'Gerencia'
ADMINISTRACION = 'Administración'
VENTAS = 'Ventas'

GRUPOS_GESTION = (GERENCIA, ADMINISTRACION)

# Permiso → grupos que lo tienen. Para cambiar qué ve un rol, tocar solo acá.
PERMISOS = {
    'gestion': GRUPOS_GESTION,
    'dashboard': (GERENCIA,),
    'usuarios': (GERENCIA,),
    'caja': GRUPOS_GESTION,
    'caja_exportar': (GERENCIA,),
    'caja_eliminar': (GERENCIA,),
}


def _grupos(user):
    # Se cachea en el objeto user para no repetir la consulta en cada chequeo
    # del mismo request (navbar + vista + template).
    if not hasattr(user, '_grupos_cache'):
        user._grupos_cache = set(user.groups.values_list('name', flat=True))
    return user._grupos_cache


def tiene_permiso(user, permiso):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return bool(_grupos(user) & set(PERMISOS[permiso]))


def permisos_de(user):
    """Dict {permiso: bool} para usar en templates (`puede.caja`, etc.)."""
    return {p: tiene_permiso(user, p) for p in PERMISOS}


def es_gestion(user):
    """Gerencia o Administración: ABMs, configuración, etc."""
    return tiene_permiso(user, 'gestion')


def ve_dashboard(user):
    return tiene_permiso(user, 'dashboard')
