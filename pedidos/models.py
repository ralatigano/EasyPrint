from django.db import models
from django.contrib.auth.models import User
from clientes.models import Cliente
from django.utils import timezone

# Create your models here


class Pedido(models.Model):

    ESTADOS = [('No iniciado', 'No iniciado'),
               ('En proceso', 'En proceso'),
               ('Terminado (falta pago)', 'Terminado (falta pago)'),
               ('Terminado y pagado', 'Terminado y pagado'),
               ]

    numero = models.IntegerField(primary_key=True)
    producto = models.TextField(blank=True, null=True)
    descripcion = models.CharField(max_length=200)
    precio = models.FloatField()
    senia = models.FloatField(null=True, blank=True)
    saldo = models.FloatField(null=True, blank=True)
    estado = models.TextField(choices=ESTADOS,
                              default='No iniciado', max_length=100)
    bloqueado_cancelado = models.BooleanField(default=False)
    cliente = models.ForeignKey(
        on_delete=models.SET_NULL, to=Cliente, default=None, blank=True, null=True)
    presupuesto = models.IntegerField(null=True, blank=True)
    encargado = models.ForeignKey(
        on_delete=models.SET_NULL, to=User, default=None, blank=True, null=True)
    fecha_entrega = models.DateField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now_add=True)

    @property
    def nombre_encargado(self):
        if self.encargado != None:
            return self.encargado.first_name
        else:
            return 'Sin asignar'

    @property
    def saldo_real(self):
        if self.saldo is not None:
            return self.saldo
        return round(self.precio - (self.senia or 0), 2)

    def __str__(self):
        return str(self.numero)

    class META():
        ordering = ["-created"]
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"


class ViajeCadete(models.Model):
    fecha = models.DateField(default=timezone.now)
    origen = models.CharField(max_length=255)
    destino = models.CharField(max_length=255)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pagado = models.BooleanField(default=False)
    fecha_pago = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = "Viaje de cadete"
        verbose_name_plural = "Viajes de cadete"

    def __str__(self):
        return f"{self.fecha} | {self.origen} → {self.destino} | ${self.precio:.2f}"
