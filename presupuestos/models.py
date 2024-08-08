from django.db import models
from clientes.models import Cliente
# Create your models here.


class Presupuesto(models.Model):
    numero = models.IntegerField(primary_key=True)
    desc_plata = models.DecimalField(
        decimal_places=2, max_digits=10, default=0)
    total = models.DecimalField(decimal_places=2, max_digits=10, default=0)
    seña = models.FloatField(null=True, blank=True)
    saldo = models.FloatField(null=True, blank=True)
    cliente = models.ForeignKey(
        on_delete=models.CASCADE, to='clientes.Cliente', default=None, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.numero)

    class META():
        ordering = ["-created"]
        verbose_name = "Presupuesto"
        verbose_name_plural = "Presupuestos"
