from django.db import models

# Create your models here.

metodo_contacto = [(0, 'Visita local'), (1, 'Whatsapp'),
                   (2, 'Instagram'), (3, 'Facebook')]


class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    negocio = models.CharField(max_length=100, blank=True)
    cuit = models.IntegerField(null=True, blank=True, default=None)
    telefono = models.CharField(max_length=13, blank=True)
    direccion = models.CharField(
        max_length=200, blank=True, null=True, default=None)
    email = models.EmailField(max_length=100, blank=True)
    metodo_contacto = models.IntegerField(
        null=False, blank=False, choices=metodo_contacto, default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    class META():
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
