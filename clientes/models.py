from django.db import models

# Create your models here.


class Cliente(models.Model):
    CONTACTO = [(0, 'Visita local'), (1, 'Whatsapp'),
                (2, 'Instagram'), (3, 'Facebook'),
                (4, 'Ticktok'), (5, 'Otro')]
    # Condición frente al IVA (códigos de ARCA). Se usa para la facturación:
    # define el CondicionIVAReceptorId del comprobante.
    CONDICIONES_IVA = [
        (5, 'Consumidor Final'),
        (1, 'IVA Responsable Inscripto'),
        (6, 'Responsable Monotributo'),
        (4, 'IVA Sujeto Exento'),
        (13, 'Monotributista Social'),
        (7, 'Sujeto No Categorizado'),
    ]
    nombre = models.CharField(max_length=100)
    negocio = models.CharField(max_length=100, blank=True, null=True)
    cuit = models.IntegerField(null=True, blank=True, default=None)
    condicion_iva = models.IntegerField(
        choices=CONDICIONES_IVA, null=True, blank=True, default=None)
    telefono = models.CharField(max_length=13, blank=True)
    direccion = models.CharField(
        max_length=200, blank=True, null=True, default=None)
    email = models.EmailField(max_length=100, blank=True)
    metodo_contacto = models.IntegerField(
        null=False, blank=False, choices=CONTACTO, default=0)
    frecuencia = models.IntegerField(default=0, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    @property
    def referencia(self):
        if self.negocio:
            return f"{self.nombre} | {self.negocio}"
        return self.nombre

    def __str__(self):
        return self.nombre

    class META():
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
