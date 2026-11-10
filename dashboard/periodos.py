"""El período que filtra el bloque de actividad comercial del dashboard.

Fuente **única**: antes la resolución del período estaba escrita dos veces (en
``dashboard()`` y en ``exportar_excel()``), así que el Excel podía traer un
rango distinto del que mostraba la pantalla. Cualquier vista que filtre por
período llama a `resolver()` y usa lo que devuelve.

El rango personalizado llega como ``?periodo=personalizado&desde=…&hasta=…``
con fechas en ISO (es lo que manda un ``<input type="date">``). Si vienen mal,
se cae al período por defecto en silencio: un filtro mal tipeado no puede
dejar el dashboard sin dibujar.

Ojo: esto filtra **sólo el bloque 2**. El bloque de salud del mes (horas,
equilibrio, estructura) va siempre al mes calendario en curso, porque el costo
fijo está mensualizado y no tiene sentido preguntarse cuánto alquiler le toca a
"los últimos 17 días". Ver PLAN_v3.10.md §2.1.
"""
from datetime import date, timedelta

from django.utils import formats

PERSONALIZADO = 'personalizado'
POR_DEFECTO = 'mes'

# clave → (días hacia atrás, etiqueta para la pantalla)
PREDEFINIDOS = {
    'semana': (7, 'última semana'),
    'mes': (30, 'últimos 30 días'),
    'trimestre': (90, 'últimos 3 meses'),
}


class Periodo:
    """Un rango de fechas cerrado, con lo que hace falta para usarlo."""

    def __init__(self, clave, desde, hasta, etiqueta):
        self.clave = clave
        self.desde = desde
        self.hasta = hasta
        self.etiqueta = etiqueta

    @property
    def es_personalizado(self):
        return self.clave == PERSONALIZADO

    def filtro(self, campo='created__date'):
        """Kwargs para un ``filter()``: el rango completo, no sólo el inicio.

        El código viejo filtraba con ``created__date__gte=desde`` y sin tope.
        Daba igual mientras todos los períodos terminaran hoy; con un rango
        personalizado que termina en el pasado, no.
        """
        return {f'{campo}__range': (self.desde, self.hasta)}

    @property
    def querystring(self):
        """Para arrastrar el filtro a los links de exportar."""
        if self.es_personalizado:
            return (f'periodo={PERSONALIZADO}'
                    f'&desde={self.desde.isoformat()}'
                    f'&hasta={self.hasta.isoformat()}')
        return f'periodo={self.clave}'

    @property
    def sufijo_archivo(self):
        """Nombre de archivo del Excel, sin espacios ni barras."""
        if self.es_personalizado:
            return f'{self.desde.isoformat()}_a_{self.hasta.isoformat()}'
        return self.clave

    def __eq__(self, otro):
        return (isinstance(otro, Periodo) and self.clave == otro.clave
                and self.desde == otro.desde and self.hasta == otro.hasta)

    def __repr__(self):
        return f'<Periodo {self.clave} {self.desde}→{self.hasta}>'


def _fecha(texto):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return None


def _etiqueta_rango(desde, hasta):
    corto = 'SHORT_DATE_FORMAT'
    return (f'del {formats.date_format(desde, corto)} '
            f'al {formats.date_format(hasta, corto)}')


def predefinido(clave, hoy):
    dias, etiqueta = PREDEFINIDOS[clave]
    return Periodo(clave, hoy - timedelta(days=dias), hoy, etiqueta)


def resolver(request, hoy):
    """El período pedido por la query string, o el de 30 días si no se entiende."""
    clave = request.GET.get('periodo', POR_DEFECTO)

    if clave == PERSONALIZADO:
        desde = _fecha(request.GET.get('desde'))
        hasta = _fecha(request.GET.get('hasta'))
        if desde and hasta:
            # Al revés se arregla solo: es más útil que un error.
            if desde > hasta:
                desde, hasta = hasta, desde
            return Periodo(PERSONALIZADO, desde, hasta,
                           _etiqueta_rango(desde, hasta))
        clave = POR_DEFECTO

    if clave not in PREDEFINIDOS:
        clave = POR_DEFECTO
    return predefinido(clave, hoy)
