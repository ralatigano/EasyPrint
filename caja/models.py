from django.conf import settings
from django.db import models
from django.utils import timezone


class Movimiento(models.Model):
    """Dinero que entra (o se devuelve) por un pedido.

    Es el registro de cobros: cada seña, pago parcial, saldo o devolución queda
    con su fecha y medio de pago. `Pedido.senia` (cobrado) y `Pedido.saldo` se
    recalculan a partir de estos movimientos (ver caja/services.py).

    `monto` lleva signo: positivo = ingreso, negativo = devolución. Así los
    totales por caja son un simple Sum('monto').
    """

    class Medio(models.TextChoices):
        EFECTIVO = 'efectivo', 'Efectivo'
        TRANSFERENCIA = 'transferencia', 'Transferencia'
        TARJETA = 'tarjeta', 'Tarjeta'
        # Solo para los cobros cargados antes del control de caja.
        SIN_ESPECIFICAR = 'sin_especificar', 'Sin especificar'

    class Tipo(models.TextChoices):
        SENIA = 'senia', 'Seña'
        PAGO = 'pago', 'Pago'
        DEVOLUCION = 'devolucion', 'Devolución'

    # Medios elegibles al registrar un cobro nuevo.
    MEDIOS_ACTIVOS = [Medio.EFECTIVO, Medio.TRANSFERENCIA, Medio.TARJETA]

    fecha = models.DateField(default=timezone.localdate)
    pedido = models.ForeignKey(
        'pedidos.Pedido', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='movimientos')
    # Copia del pedido/cliente al momento del cobro: si el pedido se borra, el
    # movimiento conserva a qué correspondía.
    referencia = models.CharField(max_length=200, blank=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    medio = models.CharField(max_length=20, choices=Medio.choices)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    nota = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    registrado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-fecha', '-registrado_en', '-id')
        verbose_name = 'Movimiento de caja'
        verbose_name_plural = 'Movimientos de caja'

    def __str__(self):
        return f'{self.fecha} {self.get_tipo_display()} {self.monto} ({self.get_medio_display()})'
