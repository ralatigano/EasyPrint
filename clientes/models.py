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
    # Razón social oficial (según ARCA). Campo propio porque puede ser una persona
    # física o jurídica; se prefiere como nombre del receptor al facturar.
    razon_social = models.CharField(max_length=200, blank=True)
    # BigIntegerField (no IntegerField): un CUIT de 11 dígitos supera int32 y
    # desbordaría en Postgres. Se guarda como entero (11 dígitos, sin guiones).
    cuit = models.BigIntegerField(null=True, blank=True, default=None)
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

    @property
    def nombre_facturacion(self):
        """Nombre del receptor para el comprobante: razón social si existe,
        si no la referencia (nombre | negocio)."""
        return self.razon_social or self.referencia

    def __str__(self):
        return self.nombre

    class META():
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
