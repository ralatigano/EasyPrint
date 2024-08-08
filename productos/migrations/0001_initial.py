# Generated by Django 5.0.6 on 2024-06-30 15:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('presupuestos', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Categoria',
            fields=[
                ('nombre', models.CharField(blank=True, default=None, max_length=50, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Producto',
            fields=[
                ('codigo', models.IntegerField(primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=50)),
                ('precio', models.FloatField()),
                ('ancho', models.FloatField(blank=True, default=0, null=True)),
                ('alto', models.FloatField(blank=True, default=0, null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.CharField(blank=True, default=None, max_length=200, null=True)),
                ('info_adic', models.CharField(blank=True, default=None, max_length=200, null=True)),
                ('cantidad', models.IntegerField(blank=True, default=None, null=True)),
                ('desc_plata', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=10, null=True)),
                ('desc_porcentaje', models.IntegerField(blank=True, default=0, null=True)),
                ('resultado', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=10, null=True)),
                ('caso_part', models.BooleanField(default=False)),
                ('categoria', models.ForeignKey(blank=True, default=None, on_delete=django.db.models.deletion.CASCADE, to='productos.categoria')),
                ('presupuesto', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='presupuestos.presupuesto')),
            ],
        ),
    ]
