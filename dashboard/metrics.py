"""Métricas del panel de horas del dashboard (Fase 5).

Todo se calcula sobre el MES EN CURSO (del día 1 a hoy), independiente del filtro
de período (semana/30 días/trimestre) del resto del dashboard. Ver
PLAN_ESTRUCTURA_COSTOS.md, Fase 5.

Ojo con el join: ``Pedido.presupuesto`` es un IntegerField con el *número* del
presupuesto (no una FK). ``ProductoCotizado.presupuesto`` sí es FK a Presupuesto.
El cruce va por ``presupuesto__numero__in=[...]``.
"""
from decimal import Decimal

from django.db.models import Sum, F
from django.utils import timezone

from core import costos
from pedidos.models import Pedido
from presupuestos.models import Presupuesto
from productos.models import ProductoCotizado


def _dec(v):
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


def panel_horas(hoy=None):
    """Devuelve las métricas del panel de horas del mes en curso.

    Números clave (ver glosario del plan):
      - punto_equilibrio_hs: horas que hay que vender para cubrir el costo fijo,
        dado el aporte promedio por hora del mes. Es el número grande a mostrar.
      - sub_absorcion: absorción recuperada − costo fijo (negativo = falta cubrir).
    """
    hoy = hoy or timezone.localdate()
    inicio_mes = hoy.replace(day=1)

    # --- Ventas del mes: presupuestos convertidos en pedido este mes ---
    numeros_vendidos = list(
        Pedido.objects.filter(
            created__date__gte=inicio_mes, created__date__lte=hoy,
            bloqueado_cancelado=False, presupuesto__isnull=False,
        ).values_list('presupuesto', flat=True)
    )
    # Solo ítems cotizados CON la estructura de costos (snapshots de la Fase 3).
    # Los ítems viejos tienen piso_absorcion=0 y su "contribución" sería el precio
    # entero (piso_absoluto=0), lo que distorsionaría el panel. A medida que todas
    # las cotizaciones usen la estructura nueva, el panel se completa solo.
    items_vendidos = ProductoCotizado.objects.filter(
        presupuesto__numero__in=numeros_vendidos, piso_absorcion__gt=0)

    horas_vendidas = _dec(items_vendidos.aggregate(s=Sum('t_produccion'))['s'])
    contribucion_mes = _dec(items_vendidos.aggregate(
        s=Sum(F('resultado') - F('piso_absoluto')))['s'])

    # --- Cotizado del mes: presupuestos creados este mes (con estructura) ---
    presupuestos_mes = Presupuesto.objects.filter(
        created__date__gte=inicio_mes, created__date__lte=hoy)
    horas_cotizadas = _dec(
        ProductoCotizado.objects.filter(
            presupuesto__in=presupuestos_mes, piso_absorcion__gt=0)
        .aggregate(s=Sum('t_produccion'))['s'])

    # --- Estructura ---
    horas_objetivo = costos.horas_productivas_mes()
    tasa = costos.tasa_hora()
    costo_fijo = costos.costo_fijo_mensual()

    absorcion_recuperada = horas_vendidas * tasa
    sub_absorcion = absorcion_recuperada - costo_fijo

    contrib_prom_por_hora = (
        contribucion_mes / horas_vendidas if horas_vendidas else Decimal('0'))
    # Punto de equilibrio en horas: costo fijo / aporte promedio por hora. Si no
    # hay ventas todavía no se puede estimar (None → se muestra "sin datos").
    punto_equilibrio_hs = (
        costo_fijo / contrib_prom_por_hora if contrib_prom_por_hora else None)
    conversion = (
        horas_vendidas / horas_cotizadas * 100 if horas_cotizadas else Decimal('0'))

    # Porcentajes para la barra de progreso (Django no divide en el template).
    pct_vendidas = (
        min(horas_vendidas / horas_objetivo * 100, Decimal('100'))
        if horas_objetivo else Decimal('0'))
    pct_equilibrio = (
        min(punto_equilibrio_hs / horas_objetivo * 100, Decimal('100'))
        if horas_objetivo and punto_equilibrio_hs else None)

    return {
        'inicio_mes': inicio_mes,
        'hoy': hoy,
        'horas_objetivo': horas_objetivo,
        'horas_vendidas': horas_vendidas,
        'horas_cotizadas': horas_cotizadas,
        'tasa_hora': tasa,
        'costo_fijo_mensual': costo_fijo,
        'absorcion_recuperada': absorcion_recuperada,
        'sub_absorcion': sub_absorcion,
        'contribucion_mes': contribucion_mes,
        'contrib_prom_por_hora': contrib_prom_por_hora,
        'punto_equilibrio_hs': punto_equilibrio_hs,
        'conversion': conversion,
        'pct_vendidas': pct_vendidas,
        'pct_equilibrio': pct_equilibrio,
        'ranking_contrib_hora': _ranking_contribucion_hora(items_vendidos),
    }


def _ranking_contribucion_hora(items_vendidos, limite=5):
    """Ranking de productos por contribución POR HORA (no por margen %): el
    recurso escaso es el tiempo. Ver glosario del plan."""
    filas = (
        items_vendidos.values('insumo__nombre')
        .annotate(
            contrib=Sum(F('resultado') - F('piso_absoluto')),
            horas=Sum('t_produccion'),
        )
    )
    ranking = []
    for f in filas:
        horas = _dec(f['horas'])
        if horas > 0:
            f['horas'] = horas
            f['contrib'] = _dec(f['contrib'])
            f['contrib_por_hora'] = f['contrib'] / horas
            ranking.append(f)
    ranking.sort(key=lambda x: x['contrib_por_hora'], reverse=True)
    return ranking[:limite]
