"""Control de capacidad vs. fechas de entrega (Fase 6).

Calcula, para una fecha de entrega F, si hay tiempo físico de producción entre
hoy y F dado todo lo ya comprometido. Es un aviso, NO un planificador ni un
bloqueo: solo la curva de carga comprometida por fecha. Ver
PLAN_ESTRUCTURA_COSTOS.md, Fase 6.

Días hábiles: lunes a viernes menos los Feriado cargados en la DB (nunca se
consulta una API en tiempo real).
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from core.models import ParametrosProduccion, Feriado

# Pedidos que todavía ocupan taller (no terminados ni cancelados).
ESTADOS_NO_TERMINADOS = ['No iniciado', 'En proceso']


def dias_habiles(desde, hasta):
    """Cantidad de días hábiles (lun-vie, sin feriados) en [desde, hasta] inclusive.

    Devuelve 0 si ``hasta`` es anterior a ``desde``.
    """
    if hasta < desde:
        return 0
    feriados = set(
        Feriado.objects.filter(fecha__gte=desde, fecha__lte=hasta)
        .values_list('fecha', flat=True)
    )
    total = 0
    dia = desde
    un_dia = timedelta(days=1)
    while dia <= hasta:
        if dia.weekday() < 5 and dia not in feriados:  # 0-4 = lun-vie
            total += 1
        dia += un_dia
    return total


def capacidad_hasta(fecha, hoy=None):
    """Horas-persona productivas disponibles entre hoy y ``fecha`` inclusive:

        dias_habiles(hoy, fecha) * horas_dia * operarios * ratio_productivas
    """
    hoy = hoy or timezone.localdate()
    p = ParametrosProduccion.load()
    dh = dias_habiles(hoy, fecha)
    return Decimal(dh) * p.horas_dia * Decimal(p.operarios) * p.ratio_productivas


def carga_comprometida(fecha):
    """Horas ya comprometidas con entrega hasta ``fecha`` inclusive: suma de
    t_produccion de los ítems de pedidos NO terminados con fecha_entrega <= fecha.

    Import local de Pedido para evitar dependencias circulares a nivel módulo.
    """
    from pedidos.models import Pedido
    from productos.models import ProductoCotizado

    numeros = list(
        Pedido.objects.filter(
            estado__in=ESTADOS_NO_TERMINADOS,
            bloqueado_cancelado=False,
            fecha_entrega__isnull=False,
            fecha_entrega__lte=fecha,
            presupuesto__isnull=False,
        ).values_list('presupuesto', flat=True)
    )
    total = ProductoCotizado.objects.filter(
        presupuesto__numero__in=numeros
    ).aggregate(s=Sum('t_produccion'))['s']
    return total if total is not None else Decimal('0')


def margen_libre(fecha, hoy=None):
    """Capacidad disponible menos carga comprometida hasta ``fecha``."""
    return capacidad_hasta(fecha, hoy=hoy) - carga_comprometida(fecha)


def evaluar_entrega(fecha, horas_nuevas, hoy=None):
    """Evalúa si un pedido nuevo de ``horas_nuevas`` entra para la fecha ``fecha``.

    Es acumulativo sobre el backlog (no un chequeo local "¿entran 6 h antes del
    viernes?"). Devuelve un dict con los números y una bandera ``alcanza``.
    NUNCA bloquea: el llamador decide qué hacer con el aviso.
    """
    horas_nuevas = Decimal(str(horas_nuevas or 0))
    capacidad = capacidad_hasta(fecha, hoy=hoy)
    carga = carga_comprometida(fecha)
    libre = capacidad - carga
    return {
        'fecha': fecha,
        'capacidad': capacidad,
        'carga_comprometida': carga,
        'margen_libre': libre,
        'horas_nuevas': horas_nuevas,
        # Si las horas del pedido nuevo superan el margen libre, no hay lugar.
        'alcanza': horas_nuevas <= libre,
        'faltante': (horas_nuevas - libre) if horas_nuevas > libre else Decimal('0'),
    }
