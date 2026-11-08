"""Vistas de la sección Pedidos tercerizados (solo Gerencia).

Toda la escritura delega en `services.py`, que es lo mismo que usa la API del
agente: así las dos vías validan igual y quedan auditadas igual.
"""

import json
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from openpyxl import Workbook
from openpyxl.styles import Font

from core.decorators import requiere_permiso
from core.utils import format_ar, parse_ar
from productos.models import Proveedor

from . import services
from .models import (
    ImputacionPago, PagoTercerizado, PedidoTercerizado, RegistroAuditoria,
    TokenAgente,
)

CERO = Decimal('0.00')


def _fecha(valor, default=None):
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return default


def _contexto_base(request):
    """Datos que el layout espera en todas las vistas del proyecto."""
    return {
        'usuario': request.session.get('usuario_nombre'),
        'img': request.session.get('img'),
        'autorizado': request.session.get('autorizado'),
    }


def _filtros(request):
    """Filtros de la tabla de pedidos. Por defecto: todo lo que debe plata."""
    desde = _fecha(request.GET.get('desde'))
    hasta = _fecha(request.GET.get('hasta'))
    proveedor_id = request.GET.get('proveedor', '')
    estado = request.GET.get('estado', '')
    estado_pago = request.GET.get('estado_pago', '')
    forma_pago = request.GET.get('forma_pago', '')
    buscar = request.GET.get('buscar', '').strip()

    qs = (PedidoTercerizado.objects
          .select_related('proveedor', 'pedido', 'pedido__cliente',
                          'creado_por', 'creado_por_token')
          .prefetch_related(
              Prefetch('imputaciones',
                       queryset=ImputacionPago.objects.select_related('pago'))))

    if desde:
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)
    if proveedor_id.isdigit():
        qs = qs.filter(proveedor_id=int(proveedor_id))
    if estado in PedidoTercerizado.Estado.values:
        qs = qs.filter(estado=estado)
    if forma_pago in PedidoTercerizado.FormaPago.values:
        qs = qs.filter(forma_pago=forma_pago)
    if buscar:
        qs = qs.filter(
            Q(descripcion__icontains=buscar) | Q(nota__icontains=buscar)
            | Q(proveedor__nombre__icontains=buscar))

    filtros = {
        'desde': desde, 'hasta': hasta, 'proveedor': proveedor_id,
        'estado': estado, 'estado_pago': estado_pago,
        'forma_pago': forma_pago, 'buscar': buscar,
    }
    return qs, filtros, estado_pago


def _aplicar_estado_pago(pedidos, estado_pago):
    """El estado de pago es derivado, así que se filtra en Python."""
    if estado_pago in ('pendiente', 'parcial', 'pagado', 'cancelado'):
        return [p for p in pedidos if p.estado_pago == estado_pago]
    if estado_pago == 'con_deuda':
        return [p for p in pedidos if p.saldo > CERO]
    return list(pedidos)


@login_required
@requiere_permiso('tercerizados')
def control_tercerizados(request):
    qs, filtros, estado_pago = _filtros(request)
    pedidos = _aplicar_estado_pago(qs, estado_pago)

    deuda = services.resumen_deuda()
    if filtros['proveedor'].isdigit():
        deuda = [d for d in deuda
                 if d['proveedor_id'] == int(filtros['proveedor'])]

    pagos = (PagoTercerizado.objects
             .select_related('proveedor', 'usuario', 'creado_por_token')
             .prefetch_related(
                 Prefetch('imputaciones',
                          queryset=ImputacionPago.objects.select_related('pedido'))))
    if filtros['desde']:
        pagos = pagos.filter(fecha__gte=filtros['desde'])
    if filtros['hasta']:
        pagos = pagos.filter(fecha__lte=filtros['hasta'])
    if filtros['proveedor'].isdigit():
        pagos = pagos.filter(proveedor_id=int(filtros['proveedor']))

    sin_revisar = PedidoTercerizado.objects.filter(
        origen=PedidoTercerizado.Origen.AGENTE, revisado=False).count()

    contexto = _contexto_base(request)
    contexto.update({
        'pedidos': pedidos,
        'pagos': pagos[:200],
        'deuda': deuda,
        'deuda_total': sum((d['deuda'] for d in deuda), CERO),
        'a_cuenta_total': sum((d['a_cuenta'] for d in deuda), CERO),
        'total_listado': sum((p.monto for p in pedidos), CERO),
        'saldo_listado': sum((p.saldo for p in pedidos), CERO),
        'filtros': filtros,
        'proveedores': Proveedor.objects.all(),
        'estados': PedidoTercerizado.Estado.choices,
        'formas_pago': PedidoTercerizado.FormaPago.choices,
        'medios': PagoTercerizado.Medio.choices,
        'sin_revisar': sin_revisar,
        'hoy': timezone.localdate(),
        'query': request.GET.urlencode(),
    })
    return render(request, 'tercerizados/control_tercerizados.html', contexto)


# ---------------------------------------------------------------- Pedidos


@login_required
@requiere_permiso('tercerizados')
@require_POST
def guardar_tercerizado(request):
    """Alta y edición desde el modal."""
    pedido_id = request.POST.get('pedidoId') or '0'
    actor = services.actor_de_request(request)

    proveedor_id = request.POST.get('proveedor')
    proveedor = (Proveedor.objects.filter(pk=proveedor_id).first()
                 if proveedor_id else None)
    interno_numero = request.POST.get('pedido_interno') or ''
    interno = None
    if interno_numero.strip():
        from pedidos.models import Pedido
        interno = Pedido.objects.filter(numero=interno_numero.strip()).first()
        if interno is None:
            messages.warning(
                request,
                f'No existe el pedido interno #{interno_numero}; se guardó sin vincular.')

    datos = {
        'fecha': _fecha(request.POST.get('fecha'), timezone.localdate()),
        'proveedor': proveedor,
        'descripcion': request.POST.get('descripcion', ''),
        'pedido': interno,
        'monto': parse_ar(request.POST.get('monto')),
        'forma_pago': request.POST.get('forma_pago'),
        'estado': request.POST.get('estado'),
        'nota': request.POST.get('nota', ''),
    }

    try:
        if pedido_id and pedido_id != '0':
            pedido = get_object_or_404(PedidoTercerizado, pk=pedido_id)
            # Editar desde la UI implica que gerencia lo miró.
            datos['revisado'] = True
            services.editar_pedido(pedido, actor=actor, **datos)
            messages.success(
                request, f'Pedido tercerizado #{pedido.pk} actualizado.')
        else:
            nuevo, creado = services.crear_pedido(actor=actor, **datos)
            messages.success(
                request,
                f'Pedido tercerizado #{nuevo.pk} registrado.' if creado
                else f'Ese pedido ya estaba registrado (#{nuevo.pk}).')
    except services.ErrorTercerizado as e:
        messages.error(request, str(e))

    return redirect(_volver(request))


@login_required
@requiere_permiso('tercerizados')
def info_tercerizado(request, pedido_id):
    """JSON para precargar el modal de edición."""
    pedido = get_object_or_404(
        PedidoTercerizado.objects.select_related('proveedor', 'pedido'),
        pk=pedido_id)
    return JsonResponse({
        'id': pedido.pk,
        'fecha': pedido.fecha.strftime('%Y-%m-%d'),
        'proveedor': pedido.proveedor_id,
        'proveedor_nombre': pedido.proveedor.nombre,
        'descripcion': pedido.descripcion,
        'pedido_interno': pedido.pedido_id,
        'monto': float(pedido.monto),
        'monto_pagado': float(pedido.monto_pagado),
        'saldo': float(pedido.saldo),
        'forma_pago': pedido.forma_pago,
        'estado': pedido.estado,
        'estado_pago': pedido.estado_pago,
        'nota': pedido.nota,
        'origen': pedido.origen,
        'revisado': pedido.revisado,
        # Lo usa el modal de eliminación genérico (core/js/eliminar.js).
        'mensaje': (
            f'Vas a eliminar el pedido tercerizado #{pedido.pk}: '
            f'"{pedido.descripcion}" de {pedido.proveedor.nombre} por '
            f'$ {pedido.monto}.'),
    })


@login_required
@requiere_permiso('tercerizados')
@require_POST
def borrar_tercerizado(request, pedido_id):
    pedido = get_object_or_404(PedidoTercerizado, pk=pedido_id)
    descripcion = pedido.descripcion
    try:
        services.borrar_pedido(
            pedido, actor=services.actor_de_request(request))
        messages.success(
            request, f'Se eliminó el pedido tercerizado "{descripcion}".')
    except services.ErrorTercerizado as e:
        messages.error(request, str(e))
    return redirect(_volver(request))


@login_required
@requiere_permiso('tercerizados')
@require_POST
def marcar_revisados(request):
    ids = request.POST.getlist('ids')
    revisado = request.POST.get('revisado', '1') != '0'
    cantidad = services.marcar_revisados(
        ids, actor=services.actor_de_request(request), revisado=revisado)
    if cantidad:
        messages.success(
            request,
            f'{cantidad} pedido(s) marcados como '
            f'{"revisados" if revisado else "no revisados"}.')
    else:
        messages.error(request, 'No seleccionaste ningún pedido.')
    return redirect(_volver(request))


# ---------------------------------------------------------------- Pagos


@login_required
@requiere_permiso('tercerizados')
@require_POST
def registrar_pago(request):
    """Registra un pago y lo imputa a los pedidos marcados en el modal.

    El modal manda `imputacion_<pedido_id>` con el monto a aplicar a cada
    pedido; si no viene ninguno y se pidió reparto automático, el monto se
    aplica del pedido más viejo al más nuevo.
    """
    proveedor = Proveedor.objects.filter(
        pk=request.POST.get('proveedor')).first()
    monto = parse_ar(request.POST.get('monto'))
    automatico = request.POST.get('automatico') == 'on'

    imputaciones = []
    for clave, valor in request.POST.items():
        if not clave.startswith('imputacion_'):
            continue
        parte = parse_ar(valor)
        if parte > CERO:
            imputaciones.append((clave.removeprefix('imputacion_'), parte))

    try:
        pago = services.registrar_pago(
            proveedor=proveedor,
            monto=monto,
            medio=request.POST.get('medio'),
            fecha=_fecha(request.POST.get('fecha'), timezone.localdate()),
            imputaciones=imputaciones,
            automatico=automatico,
            nota=request.POST.get('nota', ''),
            comprobante=request.POST.get('comprobante', ''),
            actor=services.actor_de_request(request),
        )
        sobrante = pago.sin_imputar
        texto = (f'Pago de $ {format_ar(pago.monto)} a '
                 f'{pago.proveedor.nombre} registrado.')
        if sobrante > CERO:
            texto += (f' Quedaron $ {format_ar(sobrante)} a cuenta del '
                      f'proveedor.')
        messages.success(request, texto)
    except services.ErrorTercerizado as e:
        messages.error(request, str(e))
    return redirect(_volver(request))


@login_required
@requiere_permiso('tercerizados')
@require_POST
def anular_pago(request, pago_id):
    pago = get_object_or_404(PagoTercerizado, pk=pago_id)
    monto = pago.monto
    try:
        services.anular_pago(pago, actor=services.actor_de_request(request))
        messages.success(
            request,
            f'Se anuló el pago de $ {format_ar(monto)} y los pedidos '
            f'volvieron a quedar con saldo.')
    except services.ErrorTercerizado as e:
        messages.error(request, str(e))
    return redirect(_volver(request))


@login_required
@requiere_permiso('tercerizados')
def pendientes_proveedor(request, proveedor_id):
    """Pedidos con saldo de un proveedor, para armar la imputación del pago."""
    proveedor = get_object_or_404(Proveedor, pk=proveedor_id)
    pedidos = services.pedidos_con_saldo(proveedor)
    return JsonResponse({
        'proveedor': proveedor.nombre,
        'pedidos': [{
            'id': p.pk,
            'fecha': p.fecha.strftime('%d/%m/%Y'),
            'descripcion': p.descripcion,
            'monto': float(p.monto),
            'pagado': float(p.monto_pagado),
            'saldo': float(p.saldo),
        } for p in pedidos],
        'deuda': float(sum((p.saldo for p in pedidos), CERO)),
    })


# ---------------------------------------------------------------- Auditoría


@login_required
@requiere_permiso('tercerizados')
def auditoria(request):
    """Log de quién tocó qué. Solo lectura: nadie puede editarlo ni borrarlo."""
    qs = RegistroAuditoria.objects.select_related('usuario', 'token')
    actor_tipo = request.GET.get('actor_tipo', '')
    accion = request.GET.get('accion', '')
    buscar = request.GET.get('buscar', '').strip()
    if actor_tipo in RegistroAuditoria.Actor.values:
        qs = qs.filter(actor_tipo=actor_tipo)
    if accion in RegistroAuditoria.Accion.values:
        qs = qs.filter(accion=accion)
    if buscar:
        qs = qs.filter(Q(resumen__icontains=buscar) | Q(actor__icontains=buscar))

    contexto = _contexto_base(request)
    contexto.update({
        'registros': qs[:500],
        'actores': RegistroAuditoria.Actor.choices,
        'acciones': RegistroAuditoria.Accion.choices,
        'filtros': {'actor_tipo': actor_tipo, 'accion': accion, 'buscar': buscar},
    })
    return render(request, 'tercerizados/auditoria.html', contexto)


# ---------------------------------------------------------------- Tokens


@login_required
@requiere_permiso('tercerizados_tokens')
def tokens_agente(request):
    contexto = _contexto_base(request)
    contexto.update({
        'tokens': TokenAgente.objects.select_related('creado_por'),
        # El token recién creado se muestra una sola vez, vía sesión.
        'token_nuevo': request.session.pop('token_agente_nuevo', None),
    })
    return render(request, 'tercerizados/tokens.html', contexto)


@login_required
@requiere_permiso('tercerizados_tokens')
@require_POST
def crear_token(request):
    nombre = request.POST.get('nombre', '').strip()
    if not nombre:
        messages.error(request, 'El token necesita un nombre.')
        return redirect('tercerizados_tokens')
    if TokenAgente.objects.filter(nombre__iexact=nombre).exists():
        messages.error(request, f'Ya existe un token llamado "{nombre}".')
        return redirect('tercerizados_tokens')

    permisos = {
        'permite_leer': True,
        'permite_crear': request.POST.get('permite_crear') == 'on',
        'permite_editar': request.POST.get('permite_editar') == 'on',
        'permite_borrar': request.POST.get('permite_borrar') == 'on',
        'permite_pagar': request.POST.get('permite_pagar') == 'on',
    }
    token, en_claro = TokenAgente.generar(
        nombre, creado_por=request.user, **permisos)
    # Se muestra una única vez en la próxima carga de la página.
    request.session['token_agente_nuevo'] = {
        'nombre': token.nombre, 'token': en_claro}
    services.auditar(
        services.actor_de_request(request), RegistroAuditoria.Accion.CREAR,
        'token', token.pk, f'Creó el token de agente "{token.nombre}"',
        {'permisos': permisos})
    messages.success(request, f'Token "{token.nombre}" creado.')
    return redirect('tercerizados_tokens')


@login_required
@requiere_permiso('tercerizados_tokens')
@require_POST
def alternar_token(request, token_id):
    token = get_object_or_404(TokenAgente, pk=token_id)
    token.activo = not token.activo
    token.save(update_fields=['activo'])
    services.auditar(
        services.actor_de_request(request), RegistroAuditoria.Accion.EDITAR,
        'token', token.pk,
        f'{"Activó" if token.activo else "Desactivó"} el token "{token.nombre}"',
        {'activo': token.activo})
    messages.success(
        request,
        f'Token "{token.nombre}" {"activado" if token.activo else "desactivado"}.')
    return redirect('tercerizados_tokens')


@login_required
@requiere_permiso('tercerizados_tokens')
@require_POST
def borrar_token(request, token_id):
    token = get_object_or_404(TokenAgente, pk=token_id)
    nombre = token.nombre
    token.delete()
    services.auditar(
        services.actor_de_request(request), RegistroAuditoria.Accion.BORRAR,
        'token', token_id, f'Borró el token de agente "{nombre}"')
    messages.success(request, f'Token "{nombre}" eliminado.')
    return redirect('tercerizados_tokens')


# ---------------------------------------------------------------- Exportar


@login_required
@requiere_permiso('tercerizados')
def exportar_tercerizados(request):
    """Excel con el detalle filtrado, los pagos y la deuda por proveedor.

    Es lo que se le muestra al proveedor cuando las cuentas no coinciden.
    """
    qs, filtros, estado_pago = _filtros(request)
    pedidos = _aplicar_estado_pago(qs, estado_pago)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Pedidos'
    ws.append(['Fecha', 'Proveedor', 'Trabajo', 'Pedido interno', 'Monto',
               'Pagado', 'Saldo', 'Forma de pago', 'Estado', 'Estado de pago',
               'Origen', 'Revisado', 'Nota'])
    for celda in ws[1]:
        celda.font = Font(bold=True)
    for p in pedidos:
        ws.append([
            p.fecha, p.proveedor.nombre, p.descripcion,
            p.pedido_id or '', float(p.monto), float(p.monto_pagado),
            float(p.saldo), p.get_forma_pago_display(), p.get_estado_display(),
            p.estado_pago_display, p.get_origen_display(),
            'Sí' if p.revisado else 'No', p.nota,
        ])
    ws.append(['', '', 'TOTAL', '', float(sum((p.monto for p in pedidos), CERO)),
               float(sum((p.monto_pagado for p in pedidos), CERO)),
               float(sum((p.saldo for p in pedidos), CERO))])
    for celda in ws[ws.max_row]:
        celda.font = Font(bold=True)
    for fila in ws.iter_rows(min_row=2, min_col=1, max_col=1):
        fila[0].number_format = 'DD/MM/YYYY'
    for col in ('E', 'F', 'G'):
        for fila in ws.iter_rows(min_row=2, min_col=ws[col][0].column,
                                 max_col=ws[col][0].column):
            fila[0].number_format = '#,##0.00'
    for col, ancho in zip('ABCDEFGHIJKLM',
                          (12, 24, 40, 14, 14, 14, 14, 18, 20, 16, 16, 10, 40)):
        ws.column_dimensions[col].width = ancho

    hoja_pagos = wb.create_sheet('Pagos')
    hoja_pagos.append(['Fecha', 'Proveedor', 'Monto', 'Medio', 'Comprobante',
                       'Imputado', 'A cuenta', 'Registró', 'Nota'])
    for celda in hoja_pagos[1]:
        celda.font = Font(bold=True)
    pagos = PagoTercerizado.objects.select_related('proveedor', 'usuario')
    if filtros['desde']:
        pagos = pagos.filter(fecha__gte=filtros['desde'])
    if filtros['hasta']:
        pagos = pagos.filter(fecha__lte=filtros['hasta'])
    if filtros['proveedor'].isdigit():
        pagos = pagos.filter(proveedor_id=int(filtros['proveedor']))
    for pago in pagos:
        hoja_pagos.append([
            pago.fecha, pago.proveedor.nombre, float(pago.monto),
            pago.get_medio_display(), pago.comprobante, float(pago.imputado),
            float(pago.sin_imputar),
            pago.usuario.get_full_name() if pago.usuario else
            (pago.creado_por_token.nombre if pago.creado_por_token_id else ''),
            pago.nota,
        ])
    for col, ancho in zip('ABCDEFGHI', (12, 24, 14, 16, 18, 14, 14, 20, 40)):
        hoja_pagos.column_dimensions[col].width = ancho

    hoja_deuda = wb.create_sheet('Deuda por proveedor')
    hoja_deuda.append(['Proveedor', 'Encargado', 'Pagado', 'Deuda',
                       'A cuenta', 'Deuda neta', 'Pedidos con saldo',
                       'Más antiguo'])
    for celda in hoja_deuda[1]:
        celda.font = Font(bold=True)
    for d in services.resumen_deuda():
        hoja_deuda.append([
            d['proveedor'], float(d['encargado']), float(d['pagado']),
            float(d['deuda']), float(d['a_cuenta']), float(d['deuda_neta']),
            d['pendientes'], d['desde'],
        ])
    for col, ancho in zip('ABCDEFGH', (24, 14, 14, 14, 14, 14, 18, 14)):
        hoja_deuda.column_dimensions[col].width = ancho

    hoy = timezone.localdate()
    nombre = f'tercerizados_{hoy:%Y%m%d}.xlsx'
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename={nombre}'
    wb.save(response)
    return response


def _volver(request):
    """Vuelve a la vista de tercerizados conservando los filtros."""
    destino = request.POST.get('volver', '')
    if destino.startswith('/tercerizados/'):
        return destino
    return '/tercerizados/'
