from django.db import models
from django.conf import settings
import uuid
import os
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import random

# Generar un nombre aleatorio usando la librería uuid


def profile_picture_path(instance, filename):
    random_filename = str(uuid.uuid4())
    # recupero la extensión del archivo de imagen
    extension = os.path.splitext(filename)[1]
    return 'users/{0}/{1}{2}'.format(instance.user.username, random_filename, extension)


class Usuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to=profile_picture_path, blank=True)
    birthday = models.DateField(null=True, blank=True)
    dark_mode = models.BooleanField(default=False)
    telefono = models.CharField(
        max_length=20, null=True, blank=True, default=None)

    def save(self, *args, **kwargs):
        if self.pk and self.image != None:
            old_profile = Usuario.objects.get(pk=self.pk) if self.pk else None
            if old_profile.image and old_profile.image.path != self.image.path:
                default_storage.delete(old_profile.image.path)
        super(Usuario, self).save(*args, **kwargs)

        if self.image and os.path.exists(self.image.path):
            self.resize_image()

    def resize_image(self):
        with Image.open(self.image.path) as img:
            ancho, alto = img.size
            if ancho > alto:
                nuevo_alto = 300
                nuevo_ancho = int((ancho/alto)*nuevo_alto)
                img = img.resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)
                img.save(self.image.path)
            if alto > ancho:
                nuevo_ancho = 300
                nuevo_alto = int((alto/ancho)*nuevo_ancho)
                img = img.resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)
                img.save(self.image.path)
            else:
                img.thumbnail((300, 300), Image.LANCZOS)
                img.save(self.image.path)
        with Image.open(self.image.path) as img:
            ancho, alto = img.size
            if ancho > alto:
                left = (ancho-alto)/2
                top = 0
                right = (ancho + alto)/2
                bottom = alto
            else:
                left = 0
                top = (alto-ancho)/2
                right = ancho
                bottom = (alto+ancho)/2
            img = img.crop((left, top, right, bottom))
            img.save(self.image.path)

    @property
    def nombre_completo(self):
        return f"{self.user.first_name} {self.user.last_name}"


def generate_random_color_image(base_image_path, size=(300, 300)):
    color = tuple(random.randint(0, 255) for _ in range(3))
    background = Image.new('RGBA', size, color)

    base_image = Image.open(base_image_path).convert('RGBA')
    base_image.thumbnail(size, Image.LANCZOS)

    background.paste(base_image, (0, 0), base_image)
    return background


@receiver(post_save, sender=User)
def create_usuario(sender, instance, created, **kwargs):
    if created:
        usuario = Usuario.objects.create(user=instance)
        # Generar una imagen de perfil aleatoria con la imagen base
        base_image_path = os.path.join(settings.MEDIA_ROOT, 'default.png')
        random_image = generate_random_color_image(base_image_path)
        image_path = profile_picture_path(usuario, 'profile.png')
        full_image_path = os.path.join(settings.MEDIA_ROOT, image_path)

        # Crear el directorio si no existe
        os.makedirs(os.path.dirname(full_image_path), exist_ok=True)

        random_image.save(full_image_path)
        usuario.image = image_path
        usuario.save()
