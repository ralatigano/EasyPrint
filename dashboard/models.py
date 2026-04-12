from django.db import models

# Create your models here.
class ObjetivoVentas(models.Model):
    nombre = models.CharField(max_length=100)
    monto_objetivo = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_desde = models.DateField()
    fecha_hasta = models.DateField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_desde']
        verbose_name = "Objetivo de ventas"
        verbose_name_plural = "Objetivos de ventas"

    def __str__(self):
        return f"{self.nombre} (${self.monto_objetivo})"