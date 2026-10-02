"""Registro de cobros de pedidos.

Toda alta de dinero pasa por acá para que `Pedido.senia` (lo cobrado) y
`Pedido.saldo` queden siempre iguales a la suma de los movimientos.
"""
from decimal import Decimal

from django.db.models import Sum

from .models import Movimiento

CENTAVO = Decimal('0.01')


class CobroInvalido(ValueError):
    """Datos de cobro inválidos; el mensaje se muestra tal cual al usuario."""


def _dec(valor):
    return Decimal(str(valor or 0)).quantize(CENTAVO)


def referencia_pedido(pedido):
    cliente = pedido.cliente.nombre if pedido.cliente_id else 'Sin cliente'
    return f'Pedido {pedido.numero} — {cliente}'[:200]


def cobrado(pedido):
    total = pedido.movimientos.aggregate(t=Sum('monto'))['t']
    return _dec(total)


def saldo(pedido):
    return _dec(pedido.precio) - cobrado(pedido)


def recalcular_pedido(pedido):
    """Sincroniza `senia` (cobrado) y `saldo` del pedido con sus movimientos."""
    total = cobrado(pedido)
    pedido.senia = float(total)
    pedido.saldo = float(_dec(pedido.precio) - total)
    pedido.save(update_fields=['senia', 'saldo', 'updated'])


def validar_medio(medio):
    if medio not in Movimiento.MEDIOS_ACTIVOS:
        raise CobroInvalido('Elegí el medio de pago (efectivo, transferencia o tarjeta).')
    return medio


def registrar_movimiento(pedido, monto, medio, tipo, usuario=None, fecha=None, nota=''):
    """Crea un movimiento y recalcula el pedido. `monto` se pasa siempre
    positivo; las devoluciones se guardan con signo negativo."""
    monto = _dec(monto)
    if monto <= 0:
        raise CobroInvalido('El monto tiene que ser mayor a cero.')
    validar_medio(medio)
    if tipo == Movimiento.Tipo.DEVOLUCION:
        monto = -monto
    datos = dict(
        pedido=pedido, referencia=referencia_pedido(pedido), tipo=tipo,
        medio=medio, monto=monto, nota=(nota or '')[:255], usuario=usuario,
    )
    if fecha:
        datos['fecha'] = fecha
    mov = Movimiento.objects.create(**datos)
    recalcular_pedido(pedido)
    return mov


def registrar_saldo(pedido, medio, usuario=None):
    """Registra como cobrado todo el saldo pendiente. Devuelve el movimiento
    o None si no había saldo."""
    pendiente = saldo(pedido)
    if pendiente <= 0:
        return None
    return registrar_movimiento(
        pedido, pendiente, medio, Movimiento.Tipo.PAGO, usuario=usuario,
        nota='Saldo cobrado al marcar el pedido como pagado')


def devolver_cobrado(pedido, medio, usuario=None):
    """Devuelve todo lo cobrado (al cancelar). Devuelve el movimiento o None."""
    total = cobrado(pedido)
    if total <= 0:
        return None
    return registrar_movimiento(
        pedido, total, medio, Movimiento.Tipo.DEVOLUCION, usuario=usuario,
        nota='Devolución por cancelación del pedido')
