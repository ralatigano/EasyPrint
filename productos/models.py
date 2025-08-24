from django.db import models
from presupuestos.models import Presupuesto
from pedidos.models import Pedido
from django.contrib.auth.models import User
# Create your models here.


class Categoria(models.Model):
    id = models.AutoField(primary_key=True)  # Agregar un campo id
    nombre = models.CharField(max_length=50, blank=True, default=None)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now_add=True)

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
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    presupuesto = models.ForeignKey(
        Presupuesto, on_delete=models.PROTECT, null=True, blank=True)
    cantidad = models.FloatField(default=1)

    desc_plata = models.DecimalField(
        max_digits=8, decimal_places=2, default=0)  # Descuento fijo en pesos
    desc_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=0)  # Descuento porcentual
    # Tiempo estimado de producción en minutos
    t_produccion = models.IntegerField(default=0)
    empaquetado = models.BooleanField(default=False)
    vendedor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    resultado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cliente = models.CharField(max_length=200, null=True, blank=True)
    info_adic = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad} - ${self.resultado}"

    @property
    def precio_bruto(self):
        return self.resultado + self.desc_plata


class FaltanteInsumo(models.Model):
    insumo = models.ForeignKey('Insumo', on_delete=models.CASCADE)
    pedido = models.ForeignKey(
        Pedido, on_delete=models.CASCADE, null=True, blank=True)
    cantidad_faltante = models.FloatField()
    registrado_en = models.DateTimeField(auto_now_add=True)
    resuelto = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.insumo.nombre} - Faltan {self.cantidad_faltante:.2f} ({self.pedido.numero})"
