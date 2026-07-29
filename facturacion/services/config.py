"""Acceso centralizado a la configuración de ARCA (settings.AFIP)."""
from django.conf import settings


def ambiente_actual():
    return settings.AFIP["ENV"]


def url(servicio, ambiente=None):
    """URL del web service (`wsaa` | `wsfev1`) según el ambiente activo."""
    amb = ambiente or ambiente_actual()
    return settings.AFIP_URLS[amb][servicio]


def cuit():
    return settings.AFIP["CUIT"]


def punto_venta():
    return settings.AFIP["PUNTO_VENTA"]


def cert_path():
    return settings.AFIP["CERT_PATH"]


def key_path():
    return settings.AFIP["KEY_PATH"]
