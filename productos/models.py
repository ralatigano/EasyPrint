from django.db import models
from django.db.models.functions import Lower
from presupuestos.models import Presupuesto
from pedidos.models import Pedido
from django.contrib.auth.models import User
# Create your models here.


class Categoria(models.Model):
    id = models.AutoField(primary_key=True)  # Agregar un campo id
    nombre = models.CharField(max_length=50, blank=True, default=None)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    class META():
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"


class Insumo(models.Model):
    nombre = models.CharField(max_length=100)
    unidad_medida = models.CharField(max_length=20)  # "resma", "rollo", etc.
    # "hoja", "cm", etc.
    unidad_composicion = models.CharField(max_length=20, default="unidad")
    # cuántas unidades de composición hay por unidad de stock
    factor_conversion = models.PositiveIntegerField(default=1)

    stock = models.FloatField(default=0)  # stock en unidad_medida
    precio = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    ultima_modificacion = models.DateTimeField(
        null=True,
        blank=True,
        default=None
    )
    modificado_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name='insumos_modificados'
    )

    def stock_real(self):
        return self.stock * self.factor_conversion

    def __str__(self):
        return f"{self.nombre} ({self.stock} {self.unidad_medida})"

    class Meta:
        constraints = [
            # Evita insumos duplicados por nombre ignorando mayúsculas/minúsculas.
            models.UniqueConstraint(
                Lower('nombre'),
                name='uniq_insumo_nombre_ci',
            ),
        ]


class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    tercerizado = models.BooleanField(default=False)
    ancho = models.FloatField(null=True, blank=True, default=0)
    alto = models.FloatField(null=True, blank=True, default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio_proveedor = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    factor = models.DecimalField(max_digits=6, decimal_places=2, default=1.00)
    categoria = models.ForeignKey(
        'Categoria', on_delete=models.SET_NULL, null=True, blank=True)
    activo = models.BooleanField(default=True)

    # --- Tiempos de producción (Fase 2) ---
    # Alimentan la precarga del tiempo estimado al cotizar. Si ambos son 0, el
    # producto no tiene tiempos configurados y el cotizador cae al default de 1h
    # (neutro, como antes de la Fase 2). Ver PLAN_ESTRUCTURA_COSTOS.md.
    tiempo_setup = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text="Horas de preparación por trabajo, independientes de la cantidad "
                  "(armar el archivo, calibrar, arranque, primera prueba).")
    tiempo_unitario = models.DecimalField(
        max_digits=8, decimal_places=4, default=0,
        help_text="Horas por unidad producida. La unidad es la misma que la del precio "
                  "del producto: por hoja (tipo A), por m² (tipo B), por metro lineal "
                  "(tipo C) o por unidad (tipo D).")

    insumos = models.ManyToManyField(
        'Insumo',
        through='ComponenteProducto',
        related_name='productos'
    )

    def __str__(self):
        return self.nombre


class ComponenteProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad = models.FloatField(
        help_text="Cantidad en unidad de composición, ej: hojas")
    unidad = models.CharField(max_length=20, null=True, blank=True)
    alternativo = models.BooleanField(default=False)

    class Meta:
        unique_together = ('producto', 'insumo')

    def __str__(self):
        alt = " (alternativo)" if self.alternativo else ""
        return f"{self.cantidad} x {self.insumo.nombre} para {self.producto.nombre}{alt}"


class ProductoCotizado(models.Model):
    insumo = models.ForeignKey(Producto, on_delete=models.PROTECT)
    presupuesto = models.ForeignKey(
        Presupuesto, on_delete=models.PROTECT, null=True, blank=True)
    # Lo que se entrega al cliente
    producto_final = models.CharField(max_length=255, null=True, blank=True)

    # Descripción generada automáticamente
    descripcion = models.TextField(null=True, blank=True)

    cantidad = models.FloatField(default=1)

    desc_plata = models.DecimalField(
        max_digits=8, decimal_places=2, default=0)  # Descuento fijo en pesos
    desc_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=0)  # Descuento porcentual
    # Tiempo estimado de producción, en HORAS
    t_produccion = models.DecimalField(
        max_digits=8, decimal_places=2, default=0)
    empaquetado = models.BooleanField(default=False)
    vendedor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    resultado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cliente = models.CharField(max_length=200, null=True, blank=True)
    info_adic = models.TextField(null=True, blank=True)

    # --- Snapshots del momento de la cotización (Fase 3) ---
    # Congelan los insumos del cálculo para poder reconstruir y comparar los dos
    # métodos después, sin que actualizar los costos reescriba la historia.
    # NO recalcular nunca: son fotos del momento de cotizar.
    costo_insumos_snap = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    costo_empaquetado_snap = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    margen_snap = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    tasa_hora_snap = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    precio_hora_legacy_snap = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)

    precio_sugerido = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    piso_absoluto = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    piso_absorcion = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)

    # True si el precio final se editó a mano (distinto del calculado). Permite
    # reportar después cuánto margen se resignó. Se setea en la Fase 4.
    precio_manual = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.insumo.nombre} x {self.cantidad} - ${self.resultado}"

    @property
    def precio_bruto(self):
        return self.resultado + self.desc_plata

    @property
    def contribucion(self):
        """Precio efectivamente cobrado menos costo variable."""
        return self.resultado - self.piso_absoluto

    @property
    def contribucion_por_hora(self):
        return self.contribucion / self.t_produccion if self.t_produccion else None


class FaltanteInsumo(models.Model):
    insumo = models.ForeignKey('Insumo', on_delete=models.CASCADE)
    pedido = models.ForeignKey(
        Pedido, on_delete=models.CASCADE, null=True, blank=True)
    cantidad_faltante = models.FloatField()
    registrado_en = models.DateTimeField(auto_now_add=True)
    resuelto = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.insumo.nombre} - Faltan {self.cantidad_faltante:.2f} ({self.pedido.numero})"
