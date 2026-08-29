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


def margen_objetivo() -> Decimal:
    """Margen del método nuevo sobre el costo total (config, distinto del factor
    del producto). Ver PLAN_ESTRUCTURA_COSTOS.md, hallazgo de la Fase 3."""
    return ParametrosProduccion.load().margen_objetivo


def horas_legacy() -> Decimal:
    """Horas fijas de mano de obra del método viejo (el que se cobra hoy).

    Desacopla el tiempo de los dos métodos (Fase 2): el método viejo cobra con
    estas horas constantes (congelando el precio cobrado), mientras el tiempo
    estructural de cada producto alimenta solo el precio sugerido. Ver
    PLAN_ESTRUCTURA_COSTOS.md (supera D3). Andamio temporal.
    """
    return ParametrosProduccion.load().horas_legacy


def factor_correccion_tiempos() -> Decimal:
    """Multiplicador global sobre los tiempos estimados de cada producto (Fase 2).

    Arranca en 1,00. Corrige un sesgo sistemático de estimación sin medir trabajo
    por trabajo (D5 del plan). Se aplica UNA sola vez, al precargar el tiempo en el
    cotizador; el cálculo de la cotización usa ese valor ya corregido tal cual.
    """
    return ParametrosProduccion.load().factor_correccion_tiempos


def tiempo_estimado(setup, unitario, cantidad_producto, factor) -> Decimal:
    """Horas estimadas de producción de un trabajo (Fase 2, fórmula 2.2).

        tiempo_estimado = (setup + unitario * cantidad_producto) * factor

    ``cantidad_producto`` es la magnitud a la que convergen los cuatro tipos de
    cálculo (hojas/m²/metros/unidades), la misma que multiplica al precio del
    insumo, no la cantidad de elementos. Función pura (sin DB) para poder testearla.
    """
    setup = Decimal(str(setup))
    unitario = Decimal(str(unitario))
    cantidad_producto = Decimal(str(cantidad_producto))
    factor = Decimal(str(factor))
    return (setup + unitario * cantidad_producto) * factor
