"""Lógica de pedidos tercerizados: imputación de pagos, deuda y auditoría.

Toda la escritura pasa por acá (la UI y la API solo llaman a estas funciones),
así que las dos vías comparten validaciones y las dos quedan auditadas. Las
reglas:

- `PedidoTercerizado.monto_pagado` nunca se escribe a mano: se recalcula desde
  las imputaciones con `recalcular_tercerizado`.
- Un pago se imputa a pedidos del mismo proveedor, nunca por encima del saldo
  de cada pedido ni del monto del pago. Lo que sobra queda "a cuenta".
- Un pedido cancelado no suma deuda y no admite imputaciones nuevas.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, F, Min, Q, Sum
from django.utils import timezone

from core.utils import format_ar

from .models import (
    ImputacionPago, PagoTercerizado, PedidoTercerizado, RegistroAuditoria,
)

CERO = Decimal('0.00')


class ErrorTercerizado(Exception):
    """Dato inválido al registrar o pagar. El llamador lo traduce a mensaje
    (UI) o a un 400 con detalle (API)."""


# ---------------------------------------------------------------- Actor


@dataclass
class Actor:
    """Quién hace el cambio, para el registro de auditoría."""

    tipo: str = RegistroAuditoria.Actor.SISTEMA
    nombre: str = 'sistema'
    usuario: object = None
    token: object = None
    ip: str = None
    extra: dict = field(default_factory=dict)


def actor_de_request(request):
    """Actor a partir de la sesión de Django (UI de gerencia)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return Actor()
    nombre = user.get_full_name() or user.get_username()
    return Actor(
        tipo=RegistroAuditoria.Actor.USUARIO,
        nombre=nombre,
        usuario=user,
        ip=_ip(request),
    )


def actor_de_token(token, request=None):
    """Actor a partir de un `TokenAgente` (API del agente LLM)."""
    return Actor(
        tipo=RegistroAuditoria.Actor.AGENTE,
        nombre=token.nombre,
        token=token,
        ip=_ip(request) if request is not None else None,
    )


def _ip(request):
    adelantada = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if adelantada:
        return adelantada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def auditar(actor, accion, objeto, objeto_id, resumen, detalle=None):
    """Escribe una entrada en el log append-only."""
    actor = actor or Actor()
    return RegistroAuditoria.objects.create(
        actor_tipo=actor.tipo,
        actor=actor.nombre[:150],
        usuario=actor.usuario,
        token=actor.token,
        accion=accion,
        objeto=objeto,
        objeto_id=objeto_id,
        resumen=resumen[:300],
        detalle=detalle or {},
        ip=actor.ip,
    )


# ---------------------------------------------------------------- Helpers


def _decimal(valor, campo):
    """Decimal con 2 decimales. Acepta Decimal/int/float/str ya normalizado."""
    try:
        return Decimal(str(valor)).quantize(Decimal('0.01'))
    except Exception:
        raise ErrorTercerizado(f'El valor de "{campo}" no es un número válido.')


def snapshot(pedido):
    """Foto serializable de un pedido, para el detalle de auditoría."""
    return {
        'fecha': pedido.fecha.isoformat() if pedido.fecha else None,
        'proveedor': pedido.proveedor.nombre if pedido.proveedor_id else None,
        'descripcion': pedido.descripcion,
        'pedido_interno': pedido.pedido_id,
        'monto': str(pedido.monto),
        'forma_pago': pedido.forma_pago,
        'estado': pedido.estado,
        'nota': pedido.nota,
        'revisado': pedido.revisado,
        'referencia_externa': pedido.referencia_externa,
    }


def diferencias(antes, despues):
    """Solo los campos que cambiaron, como {campo: [antes, despues]}."""
    return {k: [antes.get(k), despues.get(k)]
            for k in despues if antes.get(k) != despues.get(k)}


# ---------------------------------------------------------------- Saldos


def recalcular_tercerizado(pedido):
    """Reescribe `monto_pagado` desde las imputaciones. Única vía válida."""
    total = pedido.imputaciones.aggregate(t=Sum('monto'))['t'] or CERO
    if pedido.monto_pagado != total:
        pedido.monto_pagado = total
        pedido.save(update_fields=['monto_pagado', 'updated'])
    return pedido


# ---------------------------------------------------------------- Pedidos


def crear_pedido(*, proveedor, descripcion, monto, fecha=None, pedido=None,
                 forma_pago=None, estado=None, nota='', referencia_externa='',
                 origen=None, actor=None):
    """Alta de un pedido tercerizado (desde la UI o desde la API)."""
    actor = actor or Actor()
    descripcion = (descripcion or '').strip()
    if not descripcion:
        raise ErrorTercerizado('La descripción del trabajo es obligatoria.')
    if proveedor is None:
        raise ErrorTercerizado('Hay que indicar el proveedor.')
    monto = _decimal(monto, 'monto')
    if monto < CERO:
        raise ErrorTercerizado('El monto no puede ser negativo.')

    referencia_externa = (referencia_externa or '').strip()
    if referencia_externa:
        ya = PedidoTercerizado.objects.filter(
            referencia_externa=referencia_externa).first()
        if ya is not None:
            # Idempotencia: el agente reprocesó el mismo correo.
            return ya, False

    with transaction.atomic():
        nuevo = PedidoTercerizado.objects.create(
            fecha=fecha or timezone.localdate(),
            proveedor=proveedor,
            descripcion=descripcion,
            pedido=pedido,
            monto=monto,
            forma_pago=forma_pago or PedidoTercerizado.FormaPago.CUENTA_CORRIENTE,
            estado=estado or PedidoTercerizado.Estado.PENDIENTE,
            nota=nota or '',
            referencia_externa=referencia_externa,
            origen=origen or PedidoTercerizado.Origen.MANUAL,
            # Lo que carga el agente queda sin revisar para que gerencia lo
            # valide contra el correo; lo que carga una persona ya está visto.
            revisado=(origen != PedidoTercerizado.Origen.AGENTE),
            creado_por=actor.usuario,
            creado_por_token=actor.token,
        )
        auditar(
            actor, RegistroAuditoria.Accion.CREAR, 'pedido', nuevo.pk,
            f'Alta de "{nuevo.descripcion}" a {nuevo.proveedor.nombre} por '
            f'$ {format_ar(nuevo.monto)}',
            {'despues': snapshot(nuevo)},
        )
    return nuevo, True


CAMPOS_EDITABLES = (
    'fecha', 'proveedor', 'descripcion', 'pedido', 'monto', 'forma_pago',
    'estado', 'nota', 'revisado',
)


def editar_pedido(pedido_tercerizado, *, actor=None, **cambios):
    """Edición parcial: solo los campos presentes en `cambios`."""
    actor = actor or Actor()
    antes = snapshot(pedido_tercerizado)

    desconocidos = set(cambios) - set(CAMPOS_EDITABLES)
    if desconocidos:
        raise ErrorTercerizado(
            'No se pueden editar estos campos: ' + ', '.join(sorted(desconocidos)))

    if 'monto' in cambios:
        monto = _decimal(cambios['monto'], 'monto')
        if monto < CERO:
            raise ErrorTercerizado('El monto no puede ser negativo.')
        if monto < pedido_tercerizado.monto_pagado:
            raise ErrorTercerizado(
                f'El monto no puede quedar por debajo de lo ya pagado '
                f'($ {format_ar(pedido_tercerizado.monto_pagado)}). Anulá el pago '
                f'primero.')
        cambios['monto'] = monto

    if 'descripcion' in cambios:
        descripcion = (cambios['descripcion'] or '').strip()
        if not descripcion:
            raise ErrorTercerizado('La descripción del trabajo es obligatoria.')
        cambios['descripcion'] = descripcion

    if cambios.get('estado') == PedidoTercerizado.Estado.CANCELADO \
            and pedido_tercerizado.monto_pagado > CERO:
        raise ErrorTercerizado(
            'No se puede cancelar un pedido que ya tiene pagos imputados. '
            'Anulá el pago primero.')

    if 'proveedor' in cambios and cambios['proveedor'] is not None \
            and cambios['proveedor'].pk != pedido_tercerizado.proveedor_id \
            and pedido_tercerizado.imputaciones.exists():
        raise ErrorTercerizado(
            'No se puede cambiar el proveedor de un pedido con pagos '
            'imputados. Anulá el pago primero.')

    with transaction.atomic():
        for campo, valor in cambios.items():
            setattr(pedido_tercerizado, campo, valor)
        pedido_tercerizado.save()
        despues = snapshot(pedido_tercerizado)
        auditar(
            actor, RegistroAuditoria.Accion.EDITAR, 'pedido',
            pedido_tercerizado.pk,
            f'Editó el pedido #{pedido_tercerizado.pk} ({pedido_tercerizado.descripcion})',
            {'antes': antes, 'despues': despues,
             'cambios': diferencias(antes, despues)},
        )
    return pedido_tercerizado


def borrar_pedido(pedido_tercerizado, *, actor=None):
    """Borra el pedido. Si tiene pagos imputados, no se borra: se cancela."""
    actor = actor or Actor()
    if pedido_tercerizado.imputaciones.exists():
        raise ErrorTercerizado(
            'Este pedido tiene pagos imputados, así que no se borra (se '
            'perdería el rastro del pago). Anulá el pago, o marcalo como '
            'cancelado.')
    antes = snapshot(pedido_tercerizado)
    pk = pedido_tercerizado.pk
    with transaction.atomic():
        pedido_tercerizado.delete()
        auditar(
            actor, RegistroAuditoria.Accion.BORRAR, 'pedido', pk,
            f'Borró el pedido #{pk} ({antes["descripcion"]}) de '
            f'{antes["proveedor"]} por $ {format_ar(Decimal(antes["monto"]))}',
            {'antes': antes},
        )
    return pk


def marcar_revisados(ids, *, actor=None, revisado=True):
    """Gerencia valida (o desmarca) los registros que cargó el agente."""
    actor = actor or Actor()
    pedidos = list(PedidoTercerizado.objects.filter(pk__in=ids))
    for p in pedidos:
        p.revisado = revisado
        p.save(update_fields=['revisado', 'updated'])
    if pedidos:
        auditar(
            actor, RegistroAuditoria.Accion.REVISAR, 'pedido',
            pedidos[0].pk if len(pedidos) == 1 else None,
            f'Marcó {len(pedidos)} pedido(s) como '
            f'{"revisado" if revisado else "no revisado"}',
            {'ids': [p.pk for p in pedidos], 'revisado': revisado},
        )
    return len(pedidos)


# ---------------------------------------------------------------- Pagos


def pedidos_con_saldo(proveedor):
    """Pedidos del proveedor que todavía deben plata, del más viejo al más
    nuevo (así se paga primero lo más antiguo)."""
    return (PedidoTercerizado.objects
            .filter(proveedor=proveedor)
            .exclude(estado=PedidoTercerizado.Estado.CANCELADO)
            .filter(monto__gt=F('monto_pagado'))
            .order_by('fecha', 'id'))


def _imputaciones_automaticas(proveedor, monto):
    """Reparte `monto` sobre los pedidos con saldo, del más viejo al más nuevo."""
    repartidas = []
    restante = monto
    for pedido in pedidos_con_saldo(proveedor):
        if restante <= CERO:
            break
        aplicar = min(restante, pedido.saldo)
        if aplicar > CERO:
            repartidas.append((pedido, aplicar))
            restante -= aplicar
    return repartidas


def registrar_pago(*, proveedor, monto, medio=None, fecha=None,
                   imputaciones=None, automatico=False, nota='',
                   comprobante='', actor=None):
    """Registra un pago a un proveedor y lo imputa a sus pedidos.

    `imputaciones` es una lista de `(PedidoTercerizado | id, monto)`. Si se
    pasa `automatico=True` y no hay imputaciones explícitas, el monto se
    reparte del pedido más viejo al más nuevo. Lo que no se impute queda como
    plata a cuenta del proveedor.
    """
    actor = actor or Actor()
    if proveedor is None:
        raise ErrorTercerizado('Hay que indicar el proveedor.')
    monto = _decimal(monto, 'monto')
    if monto <= CERO:
        raise ErrorTercerizado('El monto del pago tiene que ser mayor a cero.')

    detalle = _normalizar_imputaciones(proveedor, imputaciones)
    if not detalle and automatico:
        detalle = _imputaciones_automaticas(proveedor, monto)

    total_imputado = sum((m for _, m in detalle), CERO)
    if total_imputado > monto:
        raise ErrorTercerizado(
            f'Se está imputando $ {format_ar(total_imputado)} pero el pago es '
            f'de $ {format_ar(monto)}.')

    with transaction.atomic():
        pago = PagoTercerizado.objects.create(
            fecha=fecha or timezone.localdate(),
            proveedor=proveedor,
            monto=monto,
            medio=medio or PagoTercerizado.Medio.TRANSFERENCIA,
            nota=nota or '',
            comprobante=comprobante or '',
            usuario=actor.usuario,
            creado_por_token=actor.token,
        )
        for pedido, parte in detalle:
            ImputacionPago.objects.create(pago=pago, pedido=pedido, monto=parte)
            recalcular_tercerizado(pedido)

        auditar(
            actor, RegistroAuditoria.Accion.PAGAR, 'pago', pago.pk,
            f'Pago de $ {format_ar(pago.monto)} a {proveedor.nombre} '
            f'({pago.get_medio_display()}), imputado a {len(detalle)} pedido(s)',
            {
                'pago': {
                    'fecha': pago.fecha.isoformat(),
                    'proveedor': proveedor.nombre,
                    'monto': str(pago.monto),
                    'medio': pago.medio,
                    'comprobante': pago.comprobante,
                    'nota': pago.nota,
                },
                'imputaciones': [
                    {'pedido': p.pk, 'descripcion': p.descripcion,
                     'monto': str(m)} for p, m in detalle
                ],
                'sin_imputar': str(monto - total_imputado),
            },
        )
    return pago


def _normalizar_imputaciones(proveedor, imputaciones):
    """Valida la lista de imputaciones y la devuelve como [(pedido, monto)]."""
    if not imputaciones:
        return []

    normalizadas = []
    acumulado_por_pedido = {}
    for item in imputaciones:
        referencia, bruto = item
        parte = _decimal(bruto, 'imputación')
        if parte <= CERO:
            continue
        pedido = _resolver_pedido(referencia)
        if pedido.proveedor_id != proveedor.pk:
            raise ErrorTercerizado(
                f'El pedido #{pedido.pk} es de {pedido.proveedor.nombre}, no de '
                f'{proveedor.nombre}: no se le puede imputar este pago.')
        if pedido.estado == PedidoTercerizado.Estado.CANCELADO:
            raise ErrorTercerizado(
                f'El pedido #{pedido.pk} está cancelado: no admite pagos.')
        if pedido.pk in acumulado_por_pedido:
            raise ErrorTercerizado(
                f'El pedido #{pedido.pk} aparece dos veces en la imputación.')
        if parte > pedido.saldo:
            raise ErrorTercerizado(
                f'Al pedido #{pedido.pk} ({pedido.descripcion}) se le quiere '
                f'imputar $ {format_ar(parte)} pero su saldo es '
                f'$ {format_ar(pedido.saldo)}.')
        acumulado_por_pedido[pedido.pk] = parte
        normalizadas.append((pedido, parte))
    return normalizadas


def _resolver_pedido(referencia):
    if isinstance(referencia, PedidoTercerizado):
        return referencia
    try:
        return PedidoTercerizado.objects.get(pk=int(referencia))
    except (PedidoTercerizado.DoesNotExist, TypeError, ValueError):
        raise ErrorTercerizado(f'No existe el pedido tercerizado #{referencia}.')


def anular_pago(pago, *, actor=None):
    """Borra un pago y devuelve el saldo a los pedidos que tenía imputados."""
    actor = actor or Actor()
    afectados = list(pago.imputaciones.select_related('pedido'))
    detalle = {
        'pago': {
            'fecha': pago.fecha.isoformat(),
            'proveedor': pago.proveedor.nombre,
            'monto': str(pago.monto),
            'medio': pago.medio,
            'comprobante': pago.comprobante,
            'nota': pago.nota,
        },
        'imputaciones': [
            {'pedido': i.pedido_id, 'descripcion': i.pedido.descripcion,
             'monto': str(i.monto)} for i in afectados
        ],
    }
    pedidos = [i.pedido for i in afectados]
    pk = pago.pk
    proveedor = pago.proveedor
    monto = pago.monto
    with transaction.atomic():
        pago.delete()
        for pedido in pedidos:
            recalcular_tercerizado(pedido)
        auditar(
            actor, RegistroAuditoria.Accion.ANULAR_PAGO, 'pago', pk,
            f'Anuló el pago #{pk} de $ {format_ar(monto)} a {proveedor.nombre}',
            detalle,
        )
    return pk


# ---------------------------------------------------------------- Deuda


def resumen_deuda(proveedor=None):
    """Deuda viva por proveedor.

    Devuelve una lista de dicts con, por proveedor: lo encargado, lo pagado,
    la deuda (suma de saldos de pedidos no cancelados), la plata a cuenta
    (pagos no imputados) y la deuda neta. Ordenada de mayor a menor deuda.
    """
    pedidos = (PedidoTercerizado.objects
               .exclude(estado=PedidoTercerizado.Estado.CANCELADO))
    pagos = PagoTercerizado.objects.all()
    if proveedor is not None:
        pedidos = pedidos.filter(proveedor=proveedor)
        pagos = pagos.filter(proveedor=proveedor)

    por_proveedor = {}
    agregado = (pedidos
                .values('proveedor_id', 'proveedor__nombre')
                .annotate(
                    encargado=Sum('monto'),
                    pagado=Sum('monto_pagado'),
                    cantidad=Count('id'),
                    pendientes=Count('id', filter=Q(monto__gt=F('monto_pagado'))),
                    desde=Min('fecha', filter=Q(monto__gt=F('monto_pagado'))),
                ))
    for fila in agregado:
        encargado = fila['encargado'] or CERO
        pagado = fila['pagado'] or CERO
        por_proveedor[fila['proveedor_id']] = {
            'proveedor_id': fila['proveedor_id'],
            'proveedor': fila['proveedor__nombre'],
            'encargado': encargado,
            'pagado': pagado,
            'deuda': encargado - pagado,
            'cantidad': fila['cantidad'],
            'pendientes': fila['pendientes'],
            'desde': fila['desde'],
            'a_cuenta': CERO,
        }

    # Plata a cuenta: lo pagado al proveedor que no se imputó a ningún pedido.
    # Los dos totales se piden por separado a propósito: sumar monto y
    # imputaciones__monto en la misma consulta hace un JOIN que repite el pago
    # una vez por imputación e infla el total.
    imputado_por_proveedor = {
        fila['pago__proveedor_id']: fila['total'] or CERO
        for fila in (ImputacionPago.objects
                     .filter(pago__in=pagos)
                     .values('pago__proveedor_id')
                     .annotate(total=Sum('monto')))
    }
    for fila in (pagos
                 .values('proveedor_id', 'proveedor__nombre')
                 .annotate(total=Sum('monto'))):
        total = fila['total'] or CERO
        imputado = imputado_por_proveedor.get(fila['proveedor_id'], CERO)
        a_cuenta = total - imputado
        entrada = por_proveedor.get(fila['proveedor_id'])
        if entrada is None:
            entrada = por_proveedor[fila['proveedor_id']] = {
                'proveedor_id': fila['proveedor_id'],
                'proveedor': fila['proveedor__nombre'],
                'encargado': CERO, 'pagado': CERO, 'deuda': CERO,
                'cantidad': 0, 'pendientes': 0, 'desde': None,
                'a_cuenta': CERO,
            }
        entrada['a_cuenta'] = a_cuenta

    filas = []
    for entrada in por_proveedor.values():
        entrada['deuda_neta'] = entrada['deuda'] - entrada['a_cuenta']
        filas.append(entrada)
    filas.sort(key=lambda f: (-f['deuda'], f['proveedor'] or ''))
    return filas
