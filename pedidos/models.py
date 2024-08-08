from django.db import models
from django.contrib.auth.models import User
from clientes.models import Cliente

# Create your models here.
estado_pedido = [('Sin seña', 'Sin seña'), ('Señado', 'Señado'),
                 ('En proceso', 'En proceso'), ('Para retirar', 'Para retirar'),
                 ('Entregado', 'Entregado'), ('Pagado', 'Pagado'), ('Cancelado', 'Cancelado')]


class Pedido(models.Model):
    numero = models.IntegerField(primary_key=True)
    producto = models.TextField(blank=True, null=True)
    descripcion = models.CharField(max_length=200)
    precio = models.FloatField()
    senia = models.FloatField(null=True, blank=True)
    saldo = models.FloatField(null=True, blank=True)
    estado = models.TextField(choices=estado_pedido,
                              default='Sin seña', max_length=100)
    cliente = models.ForeignKey(
        on_delete=models.CASCADE, to=Cliente, default=None, blank=True)
    presupuesto = models.IntegerField(null=True, blank=True)
    encargado = models.ForeignKey(
        on_delete=models.CASCADE, to=User, default=None, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now_add=True)

    @property
    def nombre_encargado(self):
        if self.encargado != None:
            return self.encargado.first_name
        else:
            return 'Sin asignar'

    def __str__(self):
        return str(self.numero)

    class META():
        ordering = ["-created"]
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
