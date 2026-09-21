# productos/stock.py
"""
Lógica de stock de insumos y faltantes, centralizada.

Modelo mental:
- `Insumo.stock` es lo disponible (en unidad de compra) después de reservar lo
  que piden los pedidos cargados.
- Cuando un pedido necesita más de lo disponible, el stock queda en 0 y la
  diferencia se registra como `FaltanteInsumo` (en unidad de uso).
- Invariante: si un insumo tiene stock > 0 no debería tener faltantes abiertos
  (todo ingreso de material cubre primero los faltantes).

Orden de prioridad para cubrir faltantes (el mismo que usa el simulador de la
vista de faltantes, para que la simulación prediga lo que después pasa de
verdad): fecha de entrega más cercana primero; sin fecha, al final; a igual
fecha, el faltante registrado antes.

Al registrar una compra desde la vista de faltantes se puede alterar ese orden
por pedido: los "priorizados" van primero y los "postergados" al final (dentro
de cada grupo se mantiene el orden por fecha). Postergar no excluye: si sobra
material después de cubrir al resto, también cubre a los postergados.
"""
from collections import defaultdict

from django.db.models import F
from django.utils import timezone

from .models import ComponenteProducto, FaltanteInsumo, ProductoCotizado

ESTADOS_FINALES = ('Terminado (falta pago)', 'Terminado y pagado')

# Tolerancia para comparar cantidades float (evita faltantes de 0,0000001).
EPS = 1e-6


def ordenar_por_prioridad(qs):
    return qs.order_by(
        F('pedido__fecha_entrega').asc(nulls_last=True), 'registrado_en', 'id')


def faltantes_abiertos():
    return FaltanteInsumo.objects.filter(resuelto=False)


def _factor(insumo):
    return float(insumo.factor_conversion or 1) or 1


def _stock_real(insumo):
    # No se usa insumo.stock_real(): en guardar_insumo el factor todavía es el
    # string del POST y la multiplicación no daría un número.
    return float(insumo.stock or 0) * _factor(insumo)


def _marcar_modificacion(insumo, usuario):
    if usuario is not None:
        insumo.ultima_modificacion = timezone.now()
        insumo.modificado_por = usuario


# ---------------------------------------------------------------------------
# Ingresos de material
# ---------------------------------------------------------------------------

def aplicar_ingreso(insumo, cantidad_uso, usuario=None,
                    priorizados=(), postergados=()):
    """
    Ingresa `cantidad_uso` (unidad de uso) del insumo: primero cubre los
    faltantes abiertos por orden de prioridad y lo que sobra se suma al stock.
    `priorizados` / `postergados` son números de pedido que se adelantan o se
    mandan al final de la cola. Guarda el insumo. Devuelve dict con los pedidos
    cubiertos por completo y lo que fue a stock.
    """
    disponible = max(float(cantidad_uso or 0), 0.0)
    cubiertos = []

    abiertos = list(ordenar_por_prioridad(
        FaltanteInsumo.objects.filter(insumo=insumo, resuelto=False)))
    if priorizados or postergados:
        adelante, atras = set(priorizados), set(postergados)
        # sort es estable: dentro de cada grupo se conserva el orden por fecha.
        abiertos.sort(key=lambda f: 0 if f.pedido_id in adelante
                      else 2 if f.pedido_id in atras else 1)
    for f in abiertos:
        if disponible <= EPS:
            break
        if disponible >= f.cantidad_faltante - EPS:
            disponible -= f.cantidad_faltante
            f.resuelto = True
            f.motivo_cierre = FaltanteInsumo.MOTIVO_STOCK
            f.save(update_fields=['resuelto', 'motivo_cierre'])
            cubiertos.append(f.pedido_id)
        else:
            f.cantidad_faltante -= disponible
            disponible = 0
            f.save(update_fields=['cantidad_faltante'])

    disponible = max(disponible, 0.0)
    if disponible > EPS:
        insumo.stock = (insumo.stock or 0) + disponible / _factor(insumo)
    _marcar_modificacion(insumo, usuario)
    insumo.save()
    return {'pedidos_cubiertos': cubiertos, 'a_stock': disponible}


def faltante_abierto_total(insumo):
    return sum(f.cantidad_faltante for f in
               FaltanteInsumo.objects.filter(insumo=insumo, resuelto=False))


def reemplazar_stock(insumo, nuevo_stock_real, usuario=None):
    """
    El usuario informa el stock real contado (unidad de uso). Ese material
    compensa primero los faltantes abiertos y el resto queda como stock.
    Devuelve el mensaje para mostrar.
    """
    nuevo_stock_real = max(float(nuevo_stock_real or 0), 0.0)
    unidad = insumo.unidad_composicion
    insumo.stock = 0
    aplicar_ingreso(insumo, nuevo_stock_real, usuario)

    restante = faltante_abierto_total(insumo)
    base = (f"Se ha actualizado el stock de {insumo.nombre} a "
            f"{nuevo_stock_real:.2f} {unidad}.")
    if restante > EPS:
        return (f"{base} Aún faltan {restante:.2f} {unidad} para compensar "
                f"los pedidos pendientes.")
    return f"{base} Stock disponible: {_stock_real(insumo):.2f} {unidad}."


def compensar_con_stock(insumo):
    """Si hay stock y faltantes abiertos a la vez, usa el stock para cubrirlos."""
    if (insumo.stock or 0) <= 0:
        return
    if not FaltanteInsumo.objects.filter(insumo=insumo, resuelto=False).exists():
        return
    disponible = _stock_real(insumo)
    insumo.stock = 0
    aplicar_ingreso(insumo, disponible)


# ---------------------------------------------------------------------------
# Pedidos
# ---------------------------------------------------------------------------

def _productos_del_pedido(pedido):
    return ProductoCotizado.objects.filter(
        presupuesto=pedido.presupuesto).select_related('insumo')


def necesidades_pedido(pedido):
    """{insumo: cantidad en unidad de uso} que consume el pedido."""
    necesidades = defaultdict(float)
    for p in _productos_del_pedido(pedido):
        if p.insumo.tercerizado:
            continue
        componentes = ComponenteProducto.objects.filter(
            producto=p.insumo, alternativo=False).select_related('insumo')
        for comp in componentes:
            necesidades[comp.insumo] += comp.cantidad * p.cantidad
    return necesidades


def descontar_producto(producto, cantidad, pedido=None):
    """
    Reserva los insumos de `cantidad` unidades del producto. Si no alcanza,
    deja el stock en 0 y registra el faltante. Devuelve advertencias (texto).
    """
    advertencias = []
    componentes = ComponenteProducto.objects.filter(
        producto=producto, alternativo=False).select_related('insumo')

    for comp in componentes:
        insumo = comp.insumo
        necesario = comp.cantidad * cantidad
        stock_real = _stock_real(insumo)

        if stock_real >= necesario:
            insumo.stock = (stock_real - necesario) / _factor(insumo)
        else:
            faltante = necesario - stock_real
            insumo.stock = 0
            advertencias.append(
                f'Necesitarás comprar {faltante:.2f} {insumo.unidad_composicion} '
                f'de {insumo.nombre} para completar este pedido.')
            FaltanteInsumo.objects.create(
                insumo=insumo, cantidad_faltante=faltante, pedido=pedido)
        insumo.save()
    return advertencias


def cerrar_faltantes_pedido(pedido):
    """Pedido terminado: sus faltantes dejan de alertar. Devuelve cuántos cerró."""
    return FaltanteInsumo.objects.filter(pedido=pedido, resuelto=False).update(
        resuelto=True, motivo_cierre=FaltanteInsumo.MOTIVO_PEDIDO)


def reabrir_faltantes_pedido(pedido):
    """
    El pedido volvió a abrirse: se reactivan los faltantes que se habían cerrado
    por terminarlo (no los cubiertos con stock real). Si hay stock disponible se
    usa para cubrirlos. Devuelve cuántos quedaron abiertos.
    """
    qs = FaltanteInsumo.objects.filter(
        pedido=pedido, resuelto=True,
        motivo_cierre=FaltanteInsumo.MOTIVO_PEDIDO).select_related('insumo')
    insumos = {f.insumo for f in qs}
    if not insumos:
        return 0
    qs.update(resuelto=False, motivo_cierre='')
    for insumo in insumos:
        compensar_con_stock(insumo)
    return FaltanteInsumo.objects.filter(pedido=pedido, resuelto=False).count()


def aplicar_cambio_estado(pedido, estado_anterior):
    """
    Ajusta los faltantes según la transición de estado. Devuelve un mensaje de
    advertencia si se reactivaron faltantes, o None.
    """
    era_final = estado_anterior in ESTADOS_FINALES
    es_final = pedido.estado in ESTADOS_FINALES
    if es_final and not era_final:
        cerrar_faltantes_pedido(pedido)
    elif era_final and not es_final:
        abiertos = reabrir_faltantes_pedido(pedido)
        if abiertos:
            return (f'El pedido {pedido.numero} volvió a abrirse: se reactivaron '
                    f'{abiertos} faltante(s) de insumos. Si ya tenés el material, '
                    f'corregí el stock desde Stock.')
    return None


def reponer_pedido(pedido):
    """
    Devuelve al stock el material de un pedido que se borra o cancela.

    Solo vuelve lo que realmente se descontó: si el pedido entró en falta, la
    parte que nunca se cubrió no existe y no se repone. Los faltantes propios
    del pedido se eliminan antes, para que el material devuelto no los "cubra".
    Un pedido terminado ya consumió su material, así que no repone nada.
    """
    faltantes_pedido = FaltanteInsumo.objects.filter(pedido=pedido)
    if pedido.estado in ESTADOS_FINALES:
        faltantes_pedido.delete()
        return

    no_cubierto = defaultdict(float)
    for f in faltantes_pedido:
        if not f.resuelto or f.motivo_cierre == FaltanteInsumo.MOTIVO_PEDIDO:
            no_cubierto[f.insumo_id] += f.cantidad_faltante
    faltantes_pedido.delete()

    for insumo, necesario in necesidades_pedido(pedido).items():
        real = necesario - no_cubierto.get(insumo.id, 0)
        if real > EPS:
            aplicar_ingreso(insumo, real)
