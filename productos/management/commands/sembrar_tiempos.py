"""Siembra los tiempos de producción (setup / unitario) de una categoría en lote.

La dueña estima una vez por categoría y después refina a mano los productos que
se desvían. Ver PLAN_ESTRUCTURA_COSTOS.md, Fase 2.4.

Ejemplos:
    manage.py sembrar_tiempos --categoria "Tarjetas" --setup 0.5 --unitario 0.002
    manage.py sembrar_tiempos --categoria-id 3 --setup 1 --unitario 0 --dry-run
    manage.py sembrar_tiempos --categoria "Lonas" --unitario 0.05 --solo-vacios

Nota: desde el DESACOPLE de la Fase 2, el precio COBRADO usa `horas_legacy`
(constante de config), así que sembrar tiempos NO mueve lo que se cobra: solo
alimenta el precio SUGERIDO (informativo). Ver PLAN_ESTRUCTURA_COSTOS.md.
"""
import sys
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from productos.models import Categoria, Producto


class Command(BaseCommand):
    help = ("Aplica tiempo_setup y/o tiempo_unitario a todos los productos de una "
            "categoría. Alimenta el precio sugerido (no mueve el cobrado, que usa "
            "horas_legacy).")

    def add_arguments(self, parser):
        grupo = parser.add_mutually_exclusive_group(required=True)
        grupo.add_argument("--categoria", help="Nombre de la categoría (case-insensitive).")
        grupo.add_argument("--categoria-id", type=int, help="ID de la categoría.")

        parser.add_argument(
            "--setup", help="Horas de setup por trabajo (decimal). Ej: 0.5")
        parser.add_argument(
            "--unitario", help="Horas por unidad producida (decimal). Ej: 0.002")
        parser.add_argument(
            "--solo-vacios", action="store_true",
            help="Aplicar solo a productos que hoy tienen ambos tiempos en 0.")
        parser.add_argument(
            "--tercerizado", choices=["si", "no"],
            help="Filtrar por tercerización. Útil porque los tercerizados suelen "
                 "llevar solo setup (diseño) y unitario 0, y los propios ambos.")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Mostrar qué se cambiaría sin escribir en la base.")

    def _parse_decimal(self, valor, etiqueta):
        if valor is None:
            return None
        try:
            d = Decimal(str(valor).replace(",", "."))
        except InvalidOperation:
            raise CommandError(f"Valor inválido para --{etiqueta}: '{valor}'")
        if d < 0:
            raise CommandError(f"--{etiqueta} no puede ser negativo.")
        return d

    def handle(self, *args, **opts):
        # La consola de Windows suele ser cp1252 y revienta con nombres de
        # producto acentuados o con flechas/guiones largos. Forzar UTF-8.
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

        setup = self._parse_decimal(opts.get("setup"), "setup")
        unitario = self._parse_decimal(opts.get("unitario"), "unitario")
        if setup is None and unitario is None:
            raise CommandError("Indicá al menos --setup o --unitario.")

        # Resolver categoría
        if opts.get("categoria_id") is not None:
            try:
                categoria = Categoria.objects.get(id=opts["categoria_id"])
            except Categoria.DoesNotExist:
                raise CommandError(f"No existe la categoría con id {opts['categoria_id']}.")
        else:
            categoria = Categoria.objects.filter(
                nombre__iexact=opts["categoria"].strip()).first()
            if not categoria:
                raise CommandError(f"No existe la categoría '{opts['categoria']}'.")

        productos = Producto.objects.filter(categoria=categoria, activo=True)
        if opts.get("solo_vacios"):
            productos = productos.filter(tiempo_setup=0, tiempo_unitario=0)
        if opts.get("tercerizado"):
            productos = productos.filter(
                tercerizado=(opts["tercerizado"] == "si"))

        total = productos.count()
        if total == 0:
            self.stdout.write(self.style.WARNING(
                f"No hay productos activos que coincidan en la categoría '{categoria.nombre}'."))
            return

        campos = []
        if setup is not None:
            campos.append("tiempo_setup")
        if unitario is not None:
            campos.append("tiempo_unitario")

        self.stdout.write(
            f"Categoria: {categoria.nombre} - {total} producto(s) a actualizar "
            f"({', '.join(campos)}).")

        if opts.get("dry_run"):
            for p in productos.order_by("nombre"):
                nuevo_setup = setup if setup is not None else p.tiempo_setup
                nuevo_unit = unitario if unitario is not None else p.tiempo_unitario
                self.stdout.write(
                    f"  [dry-run] {p.nombre}: setup {p.tiempo_setup} -> {nuevo_setup}, "
                    f"unitario {p.tiempo_unitario} -> {nuevo_unit}")
            self.stdout.write(self.style.WARNING("Dry-run: no se escribió nada."))
            return

        # Escribir. Se recorre y guarda uno por uno para no depender de que ambos
        # valores estén presentes (update() global no serviría si solo vino uno).
        for p in productos:
            if setup is not None:
                p.tiempo_setup = setup
            if unitario is not None:
                p.tiempo_unitario = unitario
            p.save(update_fields=campos)

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {total} producto(s) de '{categoria.nombre}' actualizados. "
            f"Solo afecta el precio sugerido; el cobrado no se mueve (usa horas_legacy)."))
