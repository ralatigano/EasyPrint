"""Crea los grupos de roles (Gerencia, Administración, Ventas) si no existen.

Vive en la app `caja` y no en `core` para no depender de la historia de
migraciones de `core`, que difiere entre `main` y la rama de estructura de
costos.
"""
from django.db import migrations

GRUPOS = ('Gerencia', 'Administración', 'Ventas')


def crear_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for nombre in GRUPOS:
        Group.objects.get_or_create(name=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ('caja', '0002_cobros_historicos'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(crear_grupos, migrations.RunPython.noop),
    ]
