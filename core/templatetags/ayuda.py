"""Tag `{% ayuda 'clave' %}`: el botón "(i)" con la explicación del concepto.

Uso en un template, después de `{% load ayuda %}`:

    <label class="form-label">Ratio productivas {% ayuda 'ratio_productivas' %}</label>

El texto sale de `core/glosario.py`. Si la clave no existe el tag no dibuja
nada (en DEBUG además avisa por consola), para que una clave mal escrita no
rompa la página.
"""

from django import template
from django.conf import settings

from core.glosario import GLOSARIO

register = template.Library()


@register.inclusion_tag('core/partials/ayuda.html')
def ayuda(clave, posicion='top'):
    texto = GLOSARIO.get(clave)
    if texto is None and settings.DEBUG:
        print(f'[ayuda] No existe la clave "{clave}" en core/glosario.py')
    return {'texto': texto, 'posicion': posicion}
