"""Métricas del dashboard.

Dos bloques que se leen distinto (PLAN_v3.10.md §2.1):

- `panel_horas()` → **salud del mes**: horas, punto de equilibrio y qué falta
  para cubrir la estructura. Siempre del día 1 del mes a hoy, **sin** el filtro
  de período, porque la estructura de costos está mensualizada.
- `ranking_contribucion_hora()` y `dinero_por_entrar()` → **actividad
  comercial**: el primero sigue el filtro de período (la contribución de un
  ítem es un snapshot propio, así que es comparable en cualquier ventana); el
  segundo es una foto de hoy.

Ojo con el join: ``Pedido.presupuesto`` es un IntegerField con el *número* del
presupuesto (no una FK). ``ProductoCotizado.presupuesto`` sí es FK a
Presupuesto. El cruce va por ``presupuesto__numero__in=[...]``.
"""
from decimal import Decimal

from django.db.models import F, Sum
from django.utils import timezone

from core import costos
from pedidos.models import Pedido
from presupuestos.models import Presupuesto
from productos.models import ProductoCotizado

EN_CURSO = ['No iniciado', 'En proceso']
ENTREGADO_SIN_PAGAR = 'Terminado (falta pago)'


def _dec(v):
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


def _suma(qs, campo):
    return _dec(qs.aggregate(s=Sum(campo))['s'])


def panel_horas(hoy=None):
    """Las métricas del mes en curso.

    Números clave:
      - ``resultado_mes``: contribución acumulada − costo fijo. Es lo que el
        card muestra: negativo = falta plata para cubrir la estructura. Cruza
        el cero **exactamente** cuando las horas vendidas llegan al punto de
        equilibrio, así que los dos cards del bloque dicen lo mismo en
        unidades distintas (horas a la izquierda, pesos a la derecha).
      - ``punto_equilibrio_hs``: horas que hay que vender para cubrir el costo
        fijo, dado el aporte promedio por hora del mes. Es el número grande.
      - ``absorcion_recuperada``: las horas vendidas valuadas a la tasa. **No
        mira el precio cobrado**, así que no se muestra como indicador propio
        (sería la barra de horas convertida a pesos). Se usa como referencia:
        es lo que la contribución tendría que haber alcanzado.
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

    horas_vendidas = _suma(items_vendidos, 't_produccion')
    contribucion_mes = _dec(items_vendidos.aggregate(
        s=Sum(F('resultado') - F('piso_absoluto')))['s'])
    cobrado_mes = _suma(items_vendidos, 'resultado')

    # --- Conversión: la MISMA cohorte en el numerador y el denominador ---
    # Antes se comparaba "lo vendido este mes" (viniera de cuando viniera)
    # contra "lo cotizado este mes": cohortes distintas, y el cociente podía
    # pasar del 100 % (daba 217 %). Ahora se mira una sola camada: de las horas
    # que se presupuestaron este mes, cuántas terminaron en un pedido.
    presupuestos_mes = Presupuesto.objects.filter(
        created__date__gte=inicio_mes, created__date__lte=hoy)
    items_cotizados = ProductoCotizado.objects.filter(
        presupuesto__in=presupuestos_mes, piso_absorcion__gt=0)
    horas_cotizadas = _suma(items_cotizados, 't_produccion')

    numeros_con_pedido = Pedido.objects.filter(
        bloqueado_cancelado=False, presupuesto__isnull=False,
    ).values_list('presupuesto', flat=True)
    horas_cotizadas_vendidas = _suma(
        items_cotizados.filter(presupuesto__numero__in=numeros_con_pedido),
        't_produccion')
    conversion = (
        horas_cotizadas_vendidas / horas_cotizadas * 100
        if horas_cotizadas else Decimal('0'))

    # --- Estructura ---
    horas_objetivo = costos.horas_productivas_mes()
    tasa = costos.tasa_hora()
    costo_fijo = costos.costo_fijo_mensual()

    absorcion_recuperada = horas_vendidas * tasa
    sub_absorcion = absorcion_recuperada - costo_fijo

    # Lo que de verdad dejó lo vendido, contra lo que hay que pagar.
    resultado_mes = contribucion_mes - costo_fijo
    falta_cubrir = -resultado_mes if resultado_mes < 0 else Decimal('0')

    contrib_prom_por_hora = (
        contribucion_mes / horas_vendidas if horas_vendidas else Decimal('0'))
    # Punto de equilibrio en horas: costo fijo / aporte promedio por hora. Si no
    # hay ventas todavía no se puede estimar (None → se muestra "sin datos").
    punto_equilibrio_hs = (
        costo_fijo / contrib_prom_por_hora if contrib_prom_por_hora else None)

    # ¿Entra el equilibrio en la capacidad? Si no entra, ni vendiendo el 100 %
    # de las horas cierra el mes, y la salida no es vender más.
    equilibrio_entra = (
        punto_equilibrio_hs is not None and horas_objetivo
        and punto_equilibrio_hs <= horas_objetivo)
    horas_restantes = (
        punto_equilibrio_hs - horas_vendidas
        if punto_equilibrio_hs is not None else None)
    if horas_restantes is not None and horas_restantes < 0:
        horas_restantes = Decimal('0')

    # Cuánto precio falta para que el equilibrio entre en la capacidad. El
    # equilibrio cae dentro de la capacidad exactamente cuando la contribución
    # llega a la absorción recuperada (contrib/hora ≥ tasa), así que lo que
    # falta es esa diferencia, medida sobre lo que se cobró.
    falta_precio_pct = None
    if not equilibrio_entra and cobrado_mes > 0:
        faltante = absorcion_recuperada - contribucion_mes
        if faltante > 0:
            falta_precio_pct = faltante / cobrado_mes * 100

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
        'horas_cotizadas_vendidas': horas_cotizadas_vendidas,
        'tasa_hora': tasa,
        'costo_fijo_mensual': costo_fijo,
        'absorcion_recuperada': absorcion_recuperada,
        'sub_absorcion': sub_absorcion,
        'contribucion_mes': contribucion_mes,
        'cobrado_mes': cobrado_mes,
        'resultado_mes': resultado_mes,
        'falta_cubrir': falta_cubrir,
        'contrib_prom_por_hora': contrib_prom_por_hora,
        'punto_equilibrio_hs': punto_equilibrio_hs,
        'equilibrio_entra': bool(equilibrio_entra),
        'horas_restantes': horas_restantes,
        'falta_precio_pct': falta_precio_pct,
        'conversion': conversion,
        'pct_vendidas': pct_vendidas,
        'pct_equilibrio': pct_equilibrio,
    }


def ranking_contribucion_hora(desde, hasta, limite=5):
    """Ranking de productos por contribución POR HORA (no por margen %).

    El recurso escaso es el tiempo, así que un producto de margen chico pero
    rápido puede rendir más que uno de margen grande que ocupa la máquina todo
    el día.

    Sigue el filtro de período a propósito: la contribución de un ítem es
    ``resultado − piso_absoluto``, los dos snapshots del momento de cotizar, y
    no depende de la mensualización del costo fijo. Es comparable en cualquier
    ventana de tiempo, a diferencia de la absorción.
    """
    numeros = list(
        Pedido.objects.filter(
            created__date__range=(desde, hasta),
            bloqueado_cancelado=False, presupuesto__isnull=False,
        ).values_list('presupuesto', flat=True)
    )
    filas = (
        ProductoCotizado.objects
        .filter(presupuesto__numero__in=numeros, piso_absorcion__gt=0)
        .values('insumo__nombre')
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


def dinero_por_entrar():
    """La plata que falta cobrar, partida en las dos cosas distintas que es.

    No sigue el filtro de período: es una foto de hoy, no la actividad de una
    ventana. Y se parte porque las dos mitades piden acciones distintas —una es
    trabajo por hacer, la otra es plata para ir a reclamar.
    """
    en_curso = Pedido.objects.filter(
        estado__in=EN_CURSO, bloqueado_cancelado=False)
    entregados = Pedido.objects.filter(
        estado=ENTREGADO_SIN_PAGAR, bloqueado_cancelado=False)

    saldo_en_curso = _suma(en_curso, 'saldo')
    saldo_entregado = _suma(entregados, 'saldo')
    return {
        'total': saldo_en_curso + saldo_entregado,
        'en_curso': saldo_en_curso,
        'en_curso_count': en_curso.count(),
        'entregado': saldo_entregado,
        'entregado_count': entregados.count(),
        'estados_en_curso': EN_CURSO,
        'estado_entregado': ENTREGADO_SIN_PAGAR,
    }
