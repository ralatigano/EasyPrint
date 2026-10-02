from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from openpyxl import Workbook
from openpyxl.styles import Font

from core.decorators import requiere_permiso
from core.utils import format_ar

from .models import Movimiento
from .services import recalcular_pedido


def _fecha(valor, default):
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return default


def _filtros(request):
    hoy = timezone.localdate()
    desde = _fecha(request.GET.get('desde'), hoy.replace(day=1))
    hasta = _fecha(request.GET.get('hasta'), hoy)
    medio = request.GET.get('medio', '')
    tipo = request.GET.get('tipo', '')
    buscar = request.GET.get('buscar', '').strip()

    qs = (Movimiento.objects.filter(fecha__range=(desde, hasta))
          .select_related('usuario', 'pedido__cliente'))
    if medio in Movimiento.Medio.values:
        qs = qs.filter(medio=medio)
    if tipo in Movimiento.Tipo.values:
        qs = qs.filter(tipo=tipo)
    if buscar:
        qs = qs.filter(Q(referencia__icontains=buscar) | Q(nota__icontains=buscar))
    filtros = {'desde': desde, 'hasta': hasta, 'medio': medio,
               'tipo': tipo, 'buscar': buscar}
    return qs, filtros


def _totales_por_medio(qs):
    """[{medio, etiqueta, ingresos, devoluciones, neto}] para los medios con
    movimientos, más 'sin especificar' solo si aparece (cobros históricos)."""
    filas = []
    for medio, etiqueta in Movimiento.Medio.choices:
        del_medio = qs.filter(medio=medio)
        ingresos = del_medio.filter(monto__gt=0).aggregate(t=Sum('monto'))['t'] or 0
        devoluciones = -(del_medio.filter(monto__lt=0).aggregate(t=Sum('monto'))['t'] or 0)
        if medio == Movimiento.Medio.SIN_ESPECIFICAR and not (ingresos or devoluciones):
            continue
        filas.append({'medio': medio, 'etiqueta': etiqueta, 'ingresos': ingresos,
                      'devoluciones': devoluciones, 'neto': ingresos - devoluciones})
    return filas


@login_required
@requiere_permiso('caja')
def control_caja(request):
    qs, filtros = _filtros(request)
    totales = _totales_por_medio(qs)
    return render(request, 'caja/control_caja.html', {
        'movimientos': qs,
        'totales': totales,
        'total_neto': sum(t['neto'] for t in totales),
        'filtros': filtros,
        'medios': Movimiento.Medio.choices,
        'tipos': Movimiento.Tipo.choices,
        'query': request.GET.urlencode(),
        'usuario': request.session.get('usuario_nombre'),
        'img': request.session.get('img'),
        'autorizado': request.session.get('autorizado'),
    })


@login_required
@requiere_permiso('caja_exportar')
def exportar_caja(request):
    qs, filtros = _filtros(request)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Movimientos'
    encabezado = ['Fecha', 'Pedido', 'Tipo', 'Medio', 'Monto', 'Registró', 'Nota']
    ws.append(encabezado)
    for celda in ws[1]:
        celda.font = Font(bold=True)
    for m in qs:
        ws.append([
            m.fecha, m.referencia, m.get_tipo_display(), m.get_medio_display(),
            float(m.monto), m.usuario.get_full_name() if m.usuario else '', m.nota,
        ])
    for fila in ws.iter_rows(min_row=2, min_col=1, max_col=1):
        fila[0].number_format = 'DD/MM/YYYY'
    for fila in ws.iter_rows(min_row=2, min_col=5, max_col=5):
        fila[0].number_format = '#,##0.00'
    for col, ancho in zip('ABCDEFG', (12, 45, 12, 15, 14, 20, 40)):
        ws.column_dimensions[col].width = ancho

    resumen = wb.create_sheet('Resumen por medio')
    resumen.append(['Medio', 'Ingresos', 'Devoluciones', 'Neto'])
    for celda in resumen[1]:
        celda.font = Font(bold=True)
    for t in _totales_por_medio(qs):
        resumen.append([t['etiqueta'], float(t['ingresos']),
                        float(t['devoluciones']), float(t['neto'])])
    resumen.column_dimensions['A'].width = 18

    nombre = f"caja_{filtros['desde']:%Y%m%d}_{filtros['hasta']:%Y%m%d}.xlsx"
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename={nombre}'
    wb.save(response)
    return response


@login_required
@requiere_permiso('caja_eliminar')
@require_POST
@transaction.atomic
def eliminar_movimiento(request, movimiento_id):
    """Corrige un cobro mal cargado: lo borra y recalcula el saldo del pedido."""
    mov = get_object_or_404(Movimiento, pk=movimiento_id)
    pedido = mov.pedido
    mov.delete()
    if pedido:
        recalcular_pedido(pedido)
    messages.success(
        request, f'Se eliminó el movimiento de $ {format_ar(abs(mov.monto))} ({mov.referencia}).')
    volver = request.POST.get('volver', '')
    # Solo se vuelve a la propia vista de caja (con sus filtros).
    return redirect(volver if volver.startswith('/caja/') else 'control_caja')
