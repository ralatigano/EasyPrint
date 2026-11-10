"""Hasta dónde puede moverse la fecha de un comprobante (`CbteFch`).

Fuente única de la regla: la usan el endpoint que arma el modal (para los
`min`/`max` del campo de fecha), la vista que emite (para validar antes de
viajar a ARCA) y los tests. Si el día de mañana se emite con otro concepto, se
toca sólo este módulo.

La regla sale del manual del desarrollador de WSFEv1:

- Concepto 1 (Productos): la fecha puede estar hasta **5 días** antes o después
  de la fecha de envío del pedido de autorización.
- Conceptos 2 y 3 (Servicios / Productos y Servicios): **10 días**.
- Una nota de crédito o débito, además, no puede ser anterior a la factura que
  corrige.

Importante: **la última palabra la tiene ARCA**, no este módulo. La validación
local existe para no hacer un viaje al pedo y para poder explicar el error en
castellano; si ARCA rechaza igual, su observación se muestra tal cual. Por eso
el rango se refleja tal como está documentado, sin agregarle restricciones
propias: el cotizador no decide por el usuario qué fechas son razonables.
"""
import datetime

from django.utils import timezone

from ..models import Comprobante

# Días hacia atrás y hacia adelante que ARCA acepta, por concepto.
DIAS_POR_CONCEPTO = {
    Comprobante.Concepto.PRODUCTOS: 5,
    Comprobante.Concepto.SERVICIOS: 10,
    Comprobante.Concepto.PRODUCTOS_Y_SERVICIOS: 10,
}
DIAS_POR_DEFECTO = 5


class FechaInvalida(ValueError):
    """La fecha pedida cae fuera de lo que ARCA acepta."""


def margen(concepto):
    """Días hacia cada lado para ese concepto."""
    try:
        return DIAS_POR_CONCEPTO[int(concepto)]
    except (KeyError, TypeError, ValueError):
        # Un concepto desconocido usa el margen más corto: equivocarse para el
        # lado restrictivo sólo cuesta un rechazo evitado, no una factura mal
        # fechada.
        return DIAS_POR_DEFECTO


def rango(concepto, hoy=None, fecha_asociado=None):
    """``(minimo, maximo)`` de fechas aceptables, ambos inclusive."""
    hoy = hoy or timezone.localdate()
    dias = datetime.timedelta(days=margen(concepto))
    minimo, maximo = hoy - dias, hoy + dias
    if fecha_asociado and fecha_asociado > minimo:
        # Una nota no puede ser anterior al comprobante que corrige.
        minimo = fecha_asociado
    return minimo, maximo


def validar(fecha, concepto, hoy=None, fecha_asociado=None):
    """Devuelve la fecha si es emitible; si no, levanta `FechaInvalida`.

    El mensaje está escrito para mostrárselo al usuario tal cual.
    """
    minimo, maximo = rango(concepto, hoy=hoy, fecha_asociado=fecha_asociado)
    if fecha < minimo:
        if fecha_asociado and minimo == fecha_asociado:
            raise FechaInvalida(
                "La nota no puede tener una fecha anterior a la factura que "
                f"corrige ({_ar(fecha_asociado)})."
            )
        raise FechaInvalida(
            f"ARCA no acepta comprobantes con fecha anterior al "
            f"{_ar(minimo)} ({margen(concepto)} días hacia atrás)."
        )
    if fecha > maximo:
        raise FechaInvalida(
            f"ARCA no acepta comprobantes con fecha posterior al "
            f"{_ar(maximo)} ({margen(concepto)} días hacia adelante)."
        )
    return fecha


def parsear(texto, por_defecto=None):
    """La fecha que mandó el navegador (ISO), o la de hoy si no vino.

    Un texto ilegible es un error del usuario, no un motivo para facturar
    silenciosamente con otra fecha: por eso levanta en lugar de caer al default.
    """
    if texto in (None, ""):
        return por_defecto or timezone.localdate()
    if isinstance(texto, datetime.date):
        return texto
    try:
        return datetime.date.fromisoformat(str(texto))
    except ValueError:
        raise FechaInvalida("La fecha del comprobante no es válida.")


def _ar(fecha):
    return fecha.strftime("%d/%m/%Y")
