# Generated by Django 5.0.6 on 2024-06-30 15:47

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Cliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100)),
                ('negocio', models.CharField(blank=True, max_length=100)),
                ('telefono', models.CharField(blank=True, max_length=13)),
                ('direccion', models.CharField(blank=True, default=None, max_length=200, null=True)),
                ('email', models.EmailField(blank=True, max_length=100)),
                ('metodo_contacto', models.IntegerField(choices=[(0, 'Visita local'), (1, 'Whatsapp'), (2, 'Instagram'), (3, 'Facebook')], default=0)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
