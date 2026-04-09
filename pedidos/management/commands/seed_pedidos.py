import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from clientes.models import Cliente
from pedidos.models import Pedido
# ajustar app si DetalleSugerido está en otro módulo
from presupuestos.models import Presupuesto, DetalleSugerido


PRODUCTOS = [
    "Remeras personalizadas",
    "Tarjetas personales",
    "Stickers",
    "Tazas personalizadas",
    "Bolsas con logo",
    "Banderas",
    "Flyers A5",
    "Folletos A4",
    "Carteles vinílicos",
    "Etiquetas autoadhesivas",
]

DESCRIPCIONES = [
    "Cliente urgente, coordinar entrega",
    "Diseño a confirmar",
    "Señado, esperar aprobación",
    "Muestra enviada por WhatsApp",
    "Revisar colores antes de imprimir",
    "Sin observaciones",
    "Retira en local",
    "Envío a domicilio",
    "Presupuesto cerrado con descuento",
    "Repetición de pedido anterior",
]

ESTADOS = [
    'No iniciado',
    'En proceso',
    'Terminado (falta pago)',
    'Terminado y pagado',
]

NOMBRES = [
    ("Ana", "Flores del Sur"),
    ("Carlos", None),
    ("Lucía", "Estudio Creativo"),
    ("Martín", "Ferretería El Clavo"),
    ("Sofía", None),
    ("Diego", "Panadería La Espiga"),
    ("Valentina", "Salón Belleza VIP"),
    ("Tomás", None),
    ("Camila", "Gym FitLife"),
    ("Rodrigo", "Constructora RB"),
]


class Command(BaseCommand):
    help = "Crea pedidos de prueba. Uso: manage.py seed_pedidos [--cantidad N] [--limpiar]"

    def add_arguments(self, parser):
        parser.add_argument(
            '--cantidad',
            type=int,
            default=None,
            help='Cantidad de pedidos a crear (si no se pasa, se pregunta interactivamente)',
        )
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Eliminar pedidos, presupuestos de prueba y DetalleSugerido antes de crear',
        )

    def handle(self, *args, **options):
        cantidad = options['cantidad']

        if cantidad is None:
            try:
                cantidad = int(
                    input("¿Cuántos pedidos querés crear? [50]: ").strip() or "50")
            except ValueError:
                self.stderr.write("Valor inválido. Usando 50.")
                cantidad = 50

        if cantidad <= 0:
            self.stderr.write("La cantidad debe ser mayor a 0.")
            return

        if options['limpiar']:
            eliminados = Pedido.objects.filter(
                descripcion__in=DESCRIPCIONES).count()
            Pedido.objects.filter(descripcion__in=DESCRIPCIONES).delete()
            self.stdout.write(
                f"  Eliminados {eliminados} pedidos de prueba anteriores.")
            DetalleSugerido.objects.all().delete()
            self.stdout.write("  DetalleSugerido limpiado.")

        # Sincronizar DetalleSugerido con PRODUCTOS del seed
        sugerencias_creadas = 0
        for texto in PRODUCTOS:
            _, creado = DetalleSugerido.objects.get_or_create(texto=texto)
            if creado:
                sugerencias_creadas += 1
        if sugerencias_creadas:
            self.stdout.write(
                f"  Creados {sugerencias_creadas} registros en DetalleSugerido.")

        # Obtener o crear usuarios para asignar como encargados
        usuarios = list(User.objects.all())
        if not usuarios:
            self.stderr.write(
                "No hay usuarios en el sistema. Creá al menos uno antes de correr el seed.")
            return

        # Crear clientes de prueba si no alcanzan
        clientes = list(Cliente.objects.all())
        clientes_creados = 0
        while len(clientes) < len(NOMBRES):
            nombre, negocio = NOMBRES[len(clientes) % len(NOMBRES)]
            if not Cliente.objects.filter(nombre=nombre, negocio=negocio).exists():
                c = Cliente.objects.create(
                    nombre=nombre,
                    negocio=negocio,
                    telefono=f"387{random.randint(1000000, 9999999)}",
                    metodo_contacto=random.randint(0, 5),
                )
                clientes.append(c)
                clientes_creados += 1
            else:
                clientes = list(Cliente.objects.all())
                break

        if clientes_creados:
            self.stdout.write(
                f"  Creados {clientes_creados} clientes de prueba.")

        # Determinar el próximo número disponible
        ultimo_pedido = Pedido.objects.order_by('-numero').first()
        ultimo_presupuesto = Presupuesto.objects.order_by('-numero').first()
        siguiente_numero = max(
            (ultimo_pedido.numero if ultimo_pedido else 0),
            (ultimo_presupuesto.numero if ultimo_presupuesto else 0),
        ) + 1

        pedidos_creados = 0
        for i in range(cantidad):
            numero = siguiente_numero + i
            cliente = random.choice(clientes)
            estado = random.choice(ESTADOS)
            precio = round(random.uniform(2000, 80000), 2)
            senia = round(precio * random.choice([0, 0.3, 0.5]), 2)
            saldo = round(precio - senia,
                          2) if estado != 'Terminado y pagado' else 0.0
            encargado = random.choice(
                usuarios + [None, None])  # ~33% sin asignar
            fecha_entrega = (
                date.today() + timedelta(days=random.randint(-10, 60))
                if random.random() > 0.2 else None
            )
            # Usar solo productos que existen en DetalleSugerido
            producto = random.choice(PRODUCTOS)
            if random.random() > 0.6:
                otro = random.choice([p for p in PRODUCTOS if p != producto])
                producto += f", {otro}"

            Presupuesto.objects.create(
                numero=numero,
                total=precio,
                seña=senia,
                saldo=saldo,
                cliente=cliente,
            )

            Pedido.objects.create(
                numero=numero,
                producto=producto,
                descripcion=random.choice(DESCRIPCIONES),
                precio=precio,
                senia=senia if senia > 0 else None,
                saldo=saldo if saldo > 0 else None,
                estado=estado,
                cliente=cliente,
                presupuesto=numero,
                encargado=encargado,
                fecha_entrega=fecha_entrega,
            )
            pedidos_creados += 1

        self.stdout.write(self.style.SUCCESS(
            f"✓ {pedidos_creados} pedidos creados correctamente (números {siguiente_numero}–{siguiente_numero + pedidos_creados - 1})."
        ))
