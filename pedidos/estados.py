"""Cambio de estado de un pedido con sus efectos en stock y caja.

Lo usan el cambio individual y el masivo, para que ambos se comporten igual.
"""
from django.db import transaction

from caja import services as caja
from core.utils import format_ar
from productos.stock import aplicar_cambio_estado, reponer_pedido

from .models import Pedido

# Qué hacer con el dinero al cambiar de estado (`cobro_accion`):
#   → 'Terminado y pagado' con saldo: 'registrar' (cobra el saldo con `medio`) u 'omitir'.
#   → 'Cancelado' con dinero cobrado: 'retener' (queda como ingreso) o 'devolver' (con `medio`).
REGISTRAR, OMITIR, RETENER, DEVOLVER = 'registrar', 'omitir', 'retener', 'devolver'


class PedidoBloqueado(Exception):
    pass


@transaction.atomic
def cambiar_estado_pedido(pedido, nuevo_estado, usuario=None, accion=None, medio=None):
    """Aplica el cambio y devuelve una lista de avisos para mostrar.

    Lanza PedidoBloqueado si el pedido ya fue cancelado y caja.CobroInvalido si
    falta el medio de pago para registrar/devolver dinero.
    """
    if pedido.bloqueado_cancelado:
        raise PedidoBloqueado(
            f'El pedido {pedido.numero} fue cancelado y no puede modificarse.')
    if nuevo_estado not in dict(Pedido.ESTADOS):
        raise ValueError(f'Estado inválido: {nuevo_estado}')

    if nuevo_estado == Pedido.CANCELADO:
        return _cancelar(pedido, usuario, accion, medio)

    if nuevo_estado == Pedido.PAGADO and accion == REGISTRAR:
        caja.registrar_saldo(pedido, caja.validar_medio(medio), usuario)

    estado_anterior = pedido.estado
    pedido.estado = nuevo_estado
    pedido.save()
    # Terminar un pedido cierra sus faltantes; reabrirlo los reactiva.
    aviso = aplicar_cambio_estado(pedido, estado_anterior)
    return [aviso] if aviso else []


def _cancelar(pedido, usuario, accion, medio):
    # Se repone antes de cambiar el estado: reponer_pedido mira el estado
    # actual para saber si el material ya se consumió (pedido terminado).
    reponer_pedido(pedido)
    avisos = []
    if accion == DEVOLVER:
        mov = caja.devolver_cobrado(pedido, caja.validar_medio(medio), usuario)
        if mov:
            avisos.append(f'Se registró la devolución de $ {format_ar(-mov.monto)} del pedido {pedido.numero}.')
    pedido.estado = Pedido.CANCELADO
    pedido.bloqueado_cancelado = True
    pedido.save()
    return avisos
