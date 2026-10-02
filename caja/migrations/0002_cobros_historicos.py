"""Carga como movimientos los cobros registrados antes del control de caja.

- Cada pedido con seña > 0 → un movimiento 'Seña' por ese total, fechado el día
  en que se creó el pedido.
- Cada pedido 'Terminado y pagado' que todavía tenía saldo (el cobro final nunca
  se registraba) → un movimiento 'Pago' por ese saldo, fechado en su última
  modificación.

El medio queda 'Sin especificar' porque no se conocía. Después recalcula
`senia`/`saldo` igual que caja/services.py.
"""
from decimal import Decimal

from django.db import migrations
from django.utils import timezone

NOTA_SENIA = 'Cobro registrado antes del control de caja'
NOTA_SALDO = 'Saldo de pedido marcado como pagado antes del control de caja'


def _dec(v):
    return Decimal(str(v or 0)).quantize(Decimal('0.01'))


def _fecha(dt):
    return timezone.localtime(dt).date() if timezone.is_aware(dt) else dt.date()


def cargar(apps, schema_editor):
    Pedido = apps.get_model('pedidos', 'Pedido')
    Movimiento = apps.get_model('caja', 'Movimiento')
    for p in Pedido.objects.select_related('cliente').iterator():
        cliente = p.cliente.nombre if p.cliente_id else 'Sin cliente'
        ref = f'Pedido {p.numero} — {cliente}'[:200]
        senia = _dec(p.senia)
        cobrado = Decimal('0')
        if senia > 0:
            Movimiento.objects.create(
                pedido=p, referencia=ref, tipo='senia', medio='sin_especificar',
                monto=senia, nota=NOTA_SENIA, fecha=_fecha(p.created))
            cobrado += senia
        pendiente = _dec(p.precio) - cobrado
        if p.estado == 'Terminado y pagado' and pendiente > 0:
            Movimiento.objects.create(
                pedido=p, referencia=ref, tipo='pago', medio='sin_especificar',
                monto=pendiente, nota=NOTA_SALDO, fecha=_fecha(p.updated))
            cobrado += pendiente
        Pedido.objects.filter(pk=p.pk).update(
            senia=float(cobrado), saldo=float(_dec(p.precio) - cobrado))


def deshacer(apps, schema_editor):
    Movimiento = apps.get_model('caja', 'Movimiento')
    Pedido = apps.get_model('pedidos', 'Pedido')
    for m in Movimiento.objects.filter(nota=NOTA_SALDO).select_related('pedido'):
        if m.pedido:
            Pedido.objects.filter(pk=m.pedido.pk).update(saldo=m.pedido.saldo + float(m.monto))
    Movimiento.objects.filter(nota__in=(NOTA_SENIA, NOTA_SALDO)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('caja', '0001_initial'),
        ('pedidos', '0007_alter_pedido_estado'),
    ]

    operations = [migrations.RunPython(cargar, deshacer)]
