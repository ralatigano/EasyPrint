"""
Comando de management para renumerar presupuestos con números "sucios"
(aquellos que no siguen el formato 3000001090+).

Uso:
    python manage.py renumerar_presupuestos           # dry-run, solo muestra qué haría
    python manage.py renumerar_presupuestos --aplicar # ejecuta los cambios

Ubicación: <tu_app_presupuestos>/management/commands/renumerar_presupuestos.py
(crear las carpetas management/ y commands/ con __init__.py vacíos si no existen)
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max

from presupuestos.models import Presupuesto
from pedidos.models import Pedido

BASE = 3000001090   # límite inferior válido
BASE_MAX = 3000009999  # límite superior válido (10 dígitos, prefijo 3000)


class Command(BaseCommand):
    help = "Renumera presupuestos con números fuera del formato 3000001090+."

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar',
            action='store_true',
            default=False,
            help='Sin este flag el comando solo muestra los cambios (dry-run).',
        )
        parser.add_argument(
            '--desde',
            type=int,
            default=BASE + 1,
            help='Número desde el que arrancar si no hay presupuestos limpios en BD (default: BASE+1).',
        )

    def handle(self, *args, **options):
        aplicar = options['aplicar']

        # 1. Identificar presupuestos sucios: fuera del rango [BASE, BASE_MAX]
        #    Cubre tanto números pequeños (< BASE) como timestamps (> BASE_MAX)
        sucios = list(
            Presupuesto.objects.exclude(
                numero__gte=BASE, numero__lte=BASE_MAX
            ).order_by('numero')
        )

        if not sucios:
            self.stdout.write(self.style.SUCCESS(
                "No se encontraron presupuestos con números fuera de formato. Nada que hacer."
            ))
            return

        self.stdout.write(
            f"Presupuestos fuera de formato encontrados: {len(sucios)}")

        # 2. Calcular el próximo número válido a partir del máximo limpio existente
        ultimo_limpio = Presupuesto.objects.filter(
            numero__gte=BASE, numero__lte=BASE_MAX
        ).aggregate(Max('numero'))['numero__max']

        # Si no hay ningún presupuesto limpio, arrancar desde el valor pasado por
        # --desde (default BASE+1). Útil cuando la BD de pruebas no tiene limpios.
        siguiente = (ultimo_limpio + 1) if ultimo_limpio else options['desde']

        self.stdout.write(
            f"Último presupuesto con formato correcto: {ultimo_limpio}")
        self.stdout.write(
            f"Los presupuestos sucios se renumerarán desde: {siguiente}\n")

        # 3. Construir el plan de renumeración
        plan = []
        for presup in sucios:
            plan.append((presup, siguiente))
            siguiente += 1

        # 4. Mostrar plan
        self.stdout.write(
            f"{'Número actual':<25} {'Número nuevo':<15} {'Cliente'}")
        self.stdout.write("-" * 60)
        for presup, nuevo in plan:
            cliente = presup.cliente.referencia if presup.cliente else "Sin cliente"
            self.stdout.write(f"{presup.numero:<25} {nuevo:<15} {cliente}")

        if not aplicar:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry-run: no se aplicaron cambios. "
                    "Corré con --aplicar para ejecutar."
                )
            )
            return

        # 5. Aplicar con transacción atómica
        #    Problema: numero es PK, Django no permite cambiar PKs directamente con .save()
        #    en todos los backends. Usamos update() por queryset o recreamos el objeto.
        #    Para evitar violaciones de FK (Pedido.presupuesto → numero del presupuesto),
        #    también actualizamos el campo presupuesto en Pedido.

        errores = 0
        renumerados = 0

        with transaction.atomic():
            for presup, nuevo_numero in plan:
                viejo_numero = presup.numero
                try:
                    # Crear presupuesto con el número nuevo copiando todos los campos
                    Presupuesto.objects.create(
                        numero=nuevo_numero,
                        desc_plata=presup.desc_plata,
                        total=presup.total,
                        seña=presup.seña,
                        saldo=presup.saldo,
                        cliente=presup.cliente,
                        # created/updated son auto_now_add, se generan solos
                    )

                    # Actualizar la FK en Pedido si existe un pedido asociado
                    pedidos_afectados = Pedido.objects.filter(
                        presupuesto=viejo_numero)
                    cantidad_pedidos = pedidos_afectados.count()
                    if cantidad_pedidos:
                        pedidos_afectados.update(presupuesto=nuevo_numero)
                        self.stdout.write(
                            f"  {viejo_numero} → {nuevo_numero}: "
                            f"{cantidad_pedidos} pedido(s) actualizado(s)."
                        )
                    else:
                        self.stdout.write(
                            f"  {viejo_numero} → {nuevo_numero}: sin pedidos asociados.")

                    # Borrar el presupuesto viejo
                    presup.delete()
                    renumerados += 1

                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"  ERROR al renumerar {viejo_numero} → {nuevo_numero}: {e}"
                        )
                    )
                    errores += 1
                    # Reraise para que la transacción atómica haga rollback completo
                    raise

        if errores == 0:
            self.stdout.write(self.style.SUCCESS(
                f"\n✓ {renumerados} presupuesto(s) renumerados correctamente."
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f"\n✗ Se produjeron {errores} errores. Se hizo rollback de todos los cambios."
            ))
