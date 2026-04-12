from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from datetime import timedelta

from pedidos.models import Pedido
from presupuestos.models import Presupuesto
from productos.models import ProductoCotizado
from clientes.models import Cliente


@login_required
def dashboard(request):

    hoy = timezone.now().date()

    # ── Período seleccionado por el usuario ──────────────────────────────────
    # 'semana' | 'mes' | 'trimestre'
    periodo = request.GET.get('periodo', 'mes')
    if periodo == 'semana':
        fecha_desde = hoy - timedelta(days=7)
    elif periodo == 'trimestre':
        fecha_desde = hoy - timedelta(days=90)
    else:  # mes por defecto
        fecha_desde = hoy - timedelta(days=30)

    # ── Pedidos en curso ─────────────────────────────────────────────────────
    estados_en_curso = ['No iniciado', 'En proceso']
    pedidos_en_curso = Pedido.objects.filter(
        estado__in=estados_en_curso,
        bloqueado_cancelado=False
    )
    total_saldo_pendiente = pedidos_en_curso.aggregate(
        total=Sum('saldo')
    )['total'] or 0

    # ── Pedidos completados en el período ────────────────────────────────────
    estados_completados = ['Terminado (falta pago)', 'Terminado y pagado']
    pedidos_completados = Pedido.objects.filter(
        estado__in=estados_completados,
        updated__date__gte=fecha_desde
    )
    # Si saldo == 0, se cobró el precio completo; si no, se cobró la seña
    total_cobrado = 0
    for p in pedidos_completados:
        if p.saldo == 0:
            total_cobrado += p.precio
        elif p.senia:
            total_cobrado += p.senia

    # ── Ticket promedio del período ──────────────────────────────────────────
    ticket_promedio = (
        pedidos_completados.aggregate(avg=Avg('precio'))['avg'] or 0
    )

    # ── Pedidos por estado ───────────────────────────────────────────────────
    pedidos_por_estado = (
        Pedido.objects.filter(bloqueado_cancelado=False)
        .values('estado')
        .annotate(cantidad=Count('numero'))
        .order_by('estado')
    )

    # ── Presupuestos últimos 15 días y tasa de conversión ────────────────────
    hace_15_dias = hoy - timedelta(days=15)
    presupuestos_recientes = Presupuesto.objects.filter(
        created__date__gte=hace_15_dias
    )
    total_presupuestos = presupuestos_recientes.count()
    # Un presupuesto se convirtió en pedido si existe un Pedido con ese número de presupuesto
    numeros_presupuesto = presupuestos_recientes.values_list(
        'numero', flat=True)
    presupuestos_convertidos = Pedido.objects.filter(
        presupuesto__in=numeros_presupuesto
    ).count()
    tasa_conversion = (
        round((presupuestos_convertidos / total_presupuestos) * 100)
        if total_presupuestos > 0 else 0
    )

    # ── Producto más vendido en el período ───────────────────────────────────
    # ProductoCotizado -> Presupuesto -> Pedido (via pedido.presupuesto)
    presupuestos_con_pedido = Pedido.objects.filter(
        presupuesto__isnull=False,
        updated__date__gte=fecha_desde
    ).values_list('presupuesto', flat=True)

    productos_vendidos = (
        ProductoCotizado.objects
        .filter(presupuesto__numero__in=presupuestos_con_pedido)
        .values('insumo__nombre')
        .annotate(
            veces_vendido=Count('id'),
            total_unidades=Sum('cantidad'),
            total_facturado=Sum('resultado')
        )
        .order_by('-veces_vendido')[:5]
    )

    # ── Top 5 clientes últimos 6 meses ───────────────────────────────────────
    hace_6_meses = hoy - timedelta(days=180)
    top_clientes = (
        Pedido.objects
        .filter(
            cliente__isnull=False,
            bloqueado_cancelado=False,
            created__date__gte=hace_6_meses
        )
        .values('cliente__id', 'cliente__nombre', 'cliente__negocio')
        .annotate(
            cantidad_pedidos=Count('numero'),
            total_comprado=Sum('precio')
        )
        .order_by('-total_comprado')[:5]
    )

    # ── Próximos pedidos con fecha de entrega ────────────────────────────────
    proximos_pedidos = (
        Pedido.objects
        .filter(
            fecha_entrega__gte=hoy,
            bloqueado_cancelado=False,
            estado__in=estados_en_curso
        )
        .order_by('fecha_entrega')[:8]
    )

    context = {
        'autorizado': request.session.get('autorizado'),
        'usuario': request.session.get('usuario_nombre'),
        'img': request.session.get('img'),
        'periodo': periodo,
        # Pedidos en curso
        'pedidos_en_curso_count': pedidos_en_curso.count(),
        'total_saldo_pendiente': total_saldo_pendiente,
        # Completados
        'pedidos_completados_count': pedidos_completados.count(),
        'total_cobrado': total_cobrado,
        'ticket_promedio': ticket_promedio,
        # Estados
        'pedidos_por_estado': list(pedidos_por_estado),
        # Presupuestos
        'total_presupuestos': total_presupuestos,
        'presupuestos_convertidos': presupuestos_convertidos,
        'tasa_conversion': tasa_conversion,
        # Productos
        'productos_vendidos': list(productos_vendidos),
        # Clientes
        'top_clientes': list(top_clientes),
        # Próximos pedidos
        'proximos_pedidos': proximos_pedidos,
        'hoy': hoy,
    }
    return render(request, 'dashboard/dashboard.html', context)
