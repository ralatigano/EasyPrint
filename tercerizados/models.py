"""Pedidos tercerizados: lo que EasyPrint le encarga a un proveedor.

El problema que resuelve: varios proveedores se pagan por **cuenta corriente**,
así que la deuda crece pedido a pedido y recién se discute cuando el proveedor
quiere cobrar. Acá cada encargue queda registrado con su monto, y los pagos se
**imputan** a pedidos concretos, de modo que en cualquier momento se sabe la
deuda viva por proveedor y qué pedido quedó cubierto por qué pago.

Modelos:

- `PedidoTercerizado`: un encargue. `monto_pagado` es denormalizado (se
  recalcula desde las imputaciones, ver `services.recalcular_tercerizado`).
- `PagoTercerizado` + `ImputacionPago`: un pago a un proveedor y cómo se
  reparte entre sus pedidos. Un pago puede quedar parcialmente sin imputar
  (plata a cuenta).
- `TokenAgente`: credencial de la API para el agente LLM de gerencia. Solo
  habilita el CRUD de esta app, nunca una sesión de Django.
- `RegistroAuditoria`: log append-only de quién tocó qué. Ni el agente ni la
  UI pueden editarlo o borrarlo (ver `save`/`delete`).
"""

import hashlib
import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

CERO = Decimal('0.00')


class PedidoTercerizado(models.Model):
    """Un trabajo encargado a un proveedor externo."""

    class FormaPago(models.TextChoices):
        CUENTA_CORRIENTE = 'cuenta_corriente', 'Cuenta corriente'
        CONTADO = 'contado', 'Contado'

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente de entrega'
        RECIBIDO = 'recibido', 'Recibido'
        # Un pedido cancelado no suma a la deuda (ver services.resumen_deuda).
        CANCELADO = 'cancelado', 'Cancelado'

    class Origen(models.TextChoices):
        MANUAL = 'manual', 'Carga manual'
        AGENTE = 'agente', 'Agente (correo)'

    fecha = models.DateField(
        default=timezone.localdate,
        help_text='Fecha del encargue / de la aprobación del proveedor.')
    proveedor = models.ForeignKey(
        'productos.Proveedor', on_delete=models.PROTECT,
        related_name='pedidos_tercerizados')
    # Por convención arranca con los identificadores del proveedor entre
    # corchetes, para poder conciliar contra su resumen de cuenta:
    # "[FA-A 00005-00078221 · S42352] - 200 lonas 3x2". Ver
    # tercerizados/instrucciones.py, que es lo que se le pega al agente.
    descripcion = models.CharField(max_length=200)
    # Pedidos nuestros a los que corresponde el gasto, si aplica. Es M2M y no
    # FK porque un encargue al proveedor puede cubrir VARIOS pedidos nuestros
    # (la plancha de stickers que junta trabajos de dos clientes para
    # aprovechar el material), y a la vez un pedido nuestro puede repartirse
    # en varios proveedores o en varios encargues al mismo proveedor.
    pedidos = models.ManyToManyField(
        'pedidos.Pedido', through='TercerizadoPedido', blank=True,
        related_name='tercerizados')
    monto = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    forma_pago = models.CharField(
        max_length=20, choices=FormaPago.choices,
        default=FormaPago.CUENTA_CORRIENTE)
    estado = models.CharField(
        max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)

    # Total imputado por pagos. NO escribir a mano: lo recalcula
    # services.recalcular_tercerizado() desde las imputaciones.
    monto_pagado = models.DecimalField(
        max_digits=12, decimal_places=2, default=CERO)

    nota = models.TextField(blank=True, default='')

    # --- Trazabilidad del origen del registro ---
    origen = models.CharField(
        max_length=10, choices=Origen.choices, default=Origen.MANUAL)
    # Identificador del correo / mensaje que originó el registro. Hace
    # idempotente el alta por API: si el agente reprocesa el mismo correo, no
    # duplica el pedido.
    referencia_externa = models.CharField(max_length=200, blank=True, default='')
    # Los registros que carga el agente arrancan sin revisar, para que
    # gerencia los valide contra el correo.
    revisado = models.BooleanField(default=False)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    creado_por_token = models.ForeignKey(
        'TokenAgente', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-fecha', '-id')
        verbose_name = 'Pedido tercerizado'
        verbose_name_plural = 'Pedidos tercerizados'
        constraints = [
            # Idempotencia del alta por API. Los registros manuales quedan con
            # referencia vacía, así que la condición excluye ''.
            models.UniqueConstraint(
                'referencia_externa',
                condition=~models.Q(referencia_externa=''),
                name='uniq_tercerizado_referencia_externa',
            ),
        ]

    def __str__(self):
        return f'#{self.pk} {self.descripcion}'

    # --- Estado de pago (derivado de monto_pagado) ---

    @property
    def saldo(self):
        """Lo que falta pagar. Un pedido cancelado no debe nada."""
        if self.estado == self.Estado.CANCELADO:
            return CERO
        return self.monto - self.monto_pagado

    @property
    def pagado(self):
        return self.saldo <= CERO

    @property
    def estado_pago(self):
        if self.estado == self.Estado.CANCELADO:
            return 'cancelado'
        if self.monto_pagado <= CERO:
            return 'pendiente'
        if self.monto - self.monto_pagado <= CERO:
            return 'pagado'
        return 'parcial'

    @property
    def estado_pago_display(self):
        return {
            'cancelado': 'Cancelado',
            'pendiente': 'Pendiente',
            'pagado': 'Pagado',
            'parcial': 'Pago parcial',
        }[self.estado_pago]


class TercerizadoPedido(models.Model):
    """Vínculo entre un pedido tercerizado y un pedido de EasyPrint.

    Solo relaciona: no reparte el costo. Si hace falta saber cuánto de un
    encargue compartido le toca a cada pedido nuestro, habrá que agregarlo
    acá como un monto opcional.
    """

    tercerizado = models.ForeignKey(
        PedidoTercerizado, on_delete=models.CASCADE, related_name='vinculos')
    # Si se borra el pedido nuestro desaparece el vínculo, pero el registro
    # del gasto con el proveedor queda: la deuda existe igual.
    pedido = models.ForeignKey(
        'pedidos.Pedido', on_delete=models.CASCADE,
        related_name='vinculos_tercerizados')

    class Meta:
        ordering = ('pedido_id',)
        verbose_name = 'Vínculo con pedido de EasyPrint'
        verbose_name_plural = 'Vínculos con pedidos de EasyPrint'
        constraints = [
            models.UniqueConstraint(
                fields=('tercerizado', 'pedido'),
                name='uniq_tercerizado_pedido'),
        ]

    def __str__(self):
        return f'Tercerizado {self.tercerizado_id} <-> pedido {self.pedido_id}'


class PagoTercerizado(models.Model):
    """Un pago a un proveedor, que se reparte entre sus pedidos.

    `monto` es lo que efectivamente se le pagó; las `imputaciones` dicen a qué
    pedidos se aplicó. Si se imputa menos que el monto, el resto queda como
    plata a cuenta del proveedor (ver `sin_imputar`).
    """

    class Medio(models.TextChoices):
        EFECTIVO = 'efectivo', 'Efectivo'
        TRANSFERENCIA = 'transferencia', 'Transferencia'
        TARJETA = 'tarjeta', 'Tarjeta'
        CHEQUE = 'cheque', 'Cheque'

    fecha = models.DateField(default=timezone.localdate)
    proveedor = models.ForeignKey(
        'productos.Proveedor', on_delete=models.PROTECT,
        related_name='pagos_tercerizados')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    medio = models.CharField(
        max_length=20, choices=Medio.choices, default=Medio.TRANSFERENCIA)
    nota = models.CharField(max_length=255, blank=True, default='')
    comprobante = models.CharField(
        max_length=120, blank=True, default='',
        help_text='Nº de comprobante / factura del proveedor, si lo hay.')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    creado_por_token = models.ForeignKey(
        'TokenAgente', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-fecha', '-created', '-id')
        verbose_name = 'Pago a proveedor tercerizado'
        verbose_name_plural = 'Pagos a proveedores tercerizados'

    def __str__(self):
        return f'Pago {self.pk} del {self.fecha} $ {self.monto}'

    @property
    def imputado(self):
        total = self.imputaciones.aggregate(t=models.Sum('monto'))['t']
        return total or CERO

    @property
    def sin_imputar(self):
        return self.monto - self.imputado


class ImputacionPago(models.Model):
    """Cuánto de un pago se aplicó a un pedido tercerizado."""

    pago = models.ForeignKey(
        PagoTercerizado, on_delete=models.CASCADE, related_name='imputaciones')
    pedido = models.ForeignKey(
        PedidoTercerizado, on_delete=models.CASCADE,
        related_name='imputaciones')
    monto = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Imputación de pago'
        verbose_name_plural = 'Imputaciones de pago'
        constraints = [
            models.UniqueConstraint(
                fields=('pago', 'pedido'), name='uniq_imputacion_pago_pedido'),
        ]

    def __str__(self):
        return f'Pago {self.pago_id} -> pedido {self.pedido_id}: $ {self.monto}'


class TokenAgente(models.Model):
    """Credencial para que el agente LLM de gerencia use la API de esta app.

    El token se muestra **una sola vez** al crearlo: en la base queda solo el
    hash SHA-256. No es un usuario de Django y no abre sesión: autentica
    únicamente las vistas de `tercerizados/api.py`, así que su alcance es el
    CRUD de pedidos tercerizados y nada más.
    """

    nombre = models.CharField(max_length=80)
    token_hash = models.CharField(max_length=64, unique=True)
    # Primeros caracteres del token, para reconocerlo en la UI sin guardarlo.
    prefijo = models.CharField(max_length=12)
    activo = models.BooleanField(default=True)

    # Permisos del token. El alta/edición/borrado de pedidos es lo que el
    # agente necesita para seguir las confirmaciones por correo; registrar
    # pagos queda apagado por defecto porque los paga gerencia.
    permite_leer = models.BooleanField(default=True)
    permite_crear = models.BooleanField(default=True)
    permite_editar = models.BooleanField(default=True)
    permite_borrar = models.BooleanField(default=True)
    permite_pagar = models.BooleanField(default=False)

    creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    ultimo_uso = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-activo', 'nombre')
        verbose_name = 'Token de agente'
        verbose_name_plural = 'Tokens de agente'
        constraints = [
            models.UniqueConstraint(
                Lower('nombre'), name='uniq_token_agente_nombre_ci'),
        ]

    def __str__(self):
        return f'{self.nombre}' if self.activo else f'{self.nombre} (inactivo)'

    @staticmethod
    def hashear(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    @classmethod
    def generar(cls, nombre, creado_por=None, **permisos):
        """Crea el token y devuelve `(instancia, token_en_claro)`.

        El token en claro no vuelve a estar disponible después de esta llamada.
        """
        token = secrets.token_urlsafe(32)
        obj = cls.objects.create(
            nombre=nombre,
            token_hash=cls.hashear(token),
            prefijo=token[:8],
            creado_por=creado_por,
            **permisos,
        )
        return obj, token

    def permite(self, accion):
        """`accion` en {leer, crear, editar, borrar, pagar}."""
        return bool(self.activo and getattr(self, f'permite_{accion}', False))


class RegistroAuditoria(models.Model):
    """Log append-only: quién tocó qué, cuándo y cómo quedó.

    Existe justamente para que el agente no pueda tapar sus propios cambios:
    `save()` rechaza modificar una entrada ya escrita y `delete()` rechaza
    borrarla, así que ni la API ni la UI pueden alterar el historial. Para
    purgarlo haría falta entrar a la base a mano, a propósito.
    """

    class Actor(models.TextChoices):
        USUARIO = 'usuario', 'Usuario'
        AGENTE = 'agente', 'Agente'
        SISTEMA = 'sistema', 'Sistema'

    class Accion(models.TextChoices):
        CREAR = 'crear', 'Creó'
        EDITAR = 'editar', 'Editó'
        BORRAR = 'borrar', 'Borró'
        PAGAR = 'pagar', 'Registró pago'
        ANULAR_PAGO = 'anular_pago', 'Anuló pago'
        REVISAR = 'revisar', 'Marcó revisado'

    momento = models.DateTimeField(auto_now_add=True)
    actor_tipo = models.CharField(
        max_length=10, choices=Actor.choices, default=Actor.USUARIO)
    # Nombre copiado al momento del hecho: sobrevive al borrado del usuario
    # o del token.
    actor = models.CharField(max_length=150)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    token = models.ForeignKey(
        TokenAgente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+')

    accion = models.CharField(max_length=15, choices=Accion.choices)
    objeto = models.CharField(max_length=30, help_text="'pedido' o 'pago'.")
    objeto_id = models.IntegerField(null=True, blank=True)
    resumen = models.CharField(max_length=300)
    # {'antes': {...}, 'despues': {...}} con los campos que cambiaron.
    detalle = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ('-momento', '-id')
        verbose_name = 'Registro de auditoría'
        verbose_name_plural = 'Registros de auditoría'

    def __str__(self):
        return f'{self.momento} {self.actor} {self.accion} {self.objeto} {self.objeto_id}'

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError(
                'El registro de auditoría es inmutable: no se puede modificar '
                'una entrada ya escrita.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(
            'El registro de auditoría es inmutable: no se puede borrar.')
