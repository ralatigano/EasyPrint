# Generated by Django 5.0.6 on 2024-07-23 20:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='cuit',
            field=models.IntegerField(blank=True, default=None, null=True),
        ),
    ]
