"""Servicio de cálculo de la estructura de costos fijos y la tasa horaria.

Centraliza acá el cálculo para que no quede desparramado en las vistas. La tasa
horaria derivada de esta estructura es la base del "método nuevo" de costeo
(ver PLAN_ESTRUCTURA_COSTOS.md). En los cálculos se usa el Decimal completo;
redondear a 2 decimales solo para mostrar.
"""
from decimal import Decimal

from core.models import CostoFijo, ParametrosProduccion


def costo_fijo_mensual() -> Decimal:
    """Suma de todas las líneas activas, normalizadas a mensual."""
    total = Decimal("0")
    for costo in CostoFijo.objects.filter(activo=True):
        total += costo.monto_mensual
    return total


def horas_disponibles_mes() -> Decimal:
    """operarios * horas_dia * dias_mes."""
    p = ParametrosProduccion.load()
    return Decimal(p.operarios) * p.horas_dia * Decimal(p.dias_mes)


def horas_productivas_mes() -> Decimal:
    """horas_disponibles_mes() * ratio_productivas."""
    p = ParametrosProduccion.load()
    return horas_disponibles_mes() * p.ratio_productivas


def tasa_hora() -> Decimal:
    """costo_fijo_mensual() / horas_productivas_mes().

    Devuelve Decimal('0') si horas_productivas_mes() es 0 (no explotar).
    """
    horas = horas_productivas_mes()
    if horas == 0:
        return Decimal("0")
    return costo_fijo_mensual() / horas
