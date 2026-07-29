from datetime import timedelta

from django.db import models
from django.utils import timezone


class Ambiente(models.TextChoices):
    HOMOLOGACION = "homologacion", "Homologación"
    PRODUCCION = "produccion", "Producción"


class TokenAcceso(models.Model):
    """Cache del Ticket de Acceso (Token + Sign) de WSAA.

    ARCA sólo entrega un TA válido por (CUIT, servicio) y lo mantiene vigente
    ~12 h; hay que reusarlo, no pedir uno nuevo en cada llamada. Se cachea en DB
    (una fila por ambiente+servicio) en vez de en archivo para funcionar bien en
    entornos multiproceso.
    """

    ambiente = models.CharField(max_length=20, choices=Ambiente.choices)
    servicio = models.CharField(max_length=20, default="wsfe")
    token = models.TextField()
    sign = models.TextField()
    generado = models.DateTimeField(auto_now=True)
    expiracion = models.DateTimeField()

    class Meta:
        unique_together = ("ambiente", "servicio")
        verbose_name = "Token de acceso ARCA"
        verbose_name_plural = "Tokens de acceso ARCA"

    def __str__(self):
        return f"TA {self.servicio}/{self.ambiente} (vence {self.expiracion:%Y-%m-%d %H:%M})"

    def vigente(self, margen_minutos=10):
        """True si el TA sigue válido con un margen de seguridad."""
        return self.expiracion > timezone.now() + timedelta(minutes=margen_minutos)


class Comprobante(models.Model):
    """Comprobante electrónico emitido (o intento de emisión) contra ARCA."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        AUTORIZADO = "autorizado", "Autorizado"
        ERROR = "error", "Error"
        ANULADO = "anulado", "Anulado"

    class Tipo(models.IntegerChoices):
        # Tipos AFIP para monotributo (Factura C y sus notas)
        FACTURA_C = 11, "Factura C"
        NOTA_DEBITO_C = 12, "Nota de Débito C"
        NOTA_CREDITO_C = 13, "Nota de Crédito C"

    class DocTipo(models.IntegerChoices):
        CUIT = 80, "CUIT"
        CUIL = 86, "CUIL"
        DNI = 96, "DNI"
        CONSUMIDOR_FINAL = 99, "Consumidor Final"

    class Concepto(models.IntegerChoices):
        PRODUCTOS = 1, "Productos"
        SERVICIOS = 2, "Servicios"
        PRODUCTOS_Y_SERVICIOS = 3, "Productos y Servicios"

    pedido = models.ForeignKey(
        "pedidos.Pedido",
        on_delete=models.PROTECT,
        related_name="comprobantes",
    )
    # Para NC/ND: la factura original que se referencia (CbteAsoc en ARCA).
    comprobante_asociado = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="notas",
        help_text="Factura original referenciada por una nota de crédito/débito.",
    )

    ambiente = models.CharField(max_length=20, choices=Ambiente.choices)
    tipo_cbte = models.IntegerField(choices=Tipo.choices, default=Tipo.FACTURA_C)
    punto_venta = models.IntegerField()
    numero = models.IntegerField(null=True, blank=True)  # lo asigna ARCA

    concepto = models.IntegerField(choices=Concepto.choices, default=Concepto.PRODUCTOS)
    fecha_emision = models.DateField(null=True, blank=True)
    importe_total = models.DecimalField(max_digits=15, decimal_places=2)

    # Receptor
    doc_tipo = models.IntegerField(
        choices=DocTipo.choices, default=DocTipo.CONSUMIDOR_FINAL
    )
    doc_nro = models.BigIntegerField(default=0)
    # Condición frente al IVA del receptor: obligatorio en ARCA desde 2024.
    cond_iva_receptor = models.IntegerField(null=True, blank=True)
    receptor_nombre = models.CharField(max_length=200, blank=True)

    # Resultado de ARCA
    cae = models.CharField(max_length=20, blank=True)
    cae_vencimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.BORRADOR
    )
    respuesta_afip = models.JSONField(null=True, blank=True)  # respuesta cruda (auditoría)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Comprobante"
        verbose_name_plural = "Comprobantes"
        ordering = ("-created",)

    def __str__(self):
        etiqueta = self.get_tipo_cbte_display()
        if self.numero:
            return f"{etiqueta} {self.punto_venta:04d}-{self.numero:08d}"
        return f"{etiqueta} (sin autorizar) · pedido {self.pedido_id}"

    @property
    def numero_formateado(self):
        if not self.numero:
            return "—"
        return f"{self.punto_venta:04d}-{self.numero:08d}"

    @property
    def es_nota(self):
        return self.tipo_cbte in (self.Tipo.NOTA_DEBITO_C, self.Tipo.NOTA_CREDITO_C)
