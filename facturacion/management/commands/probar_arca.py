"""Prueba de conectividad/lectura contra ARCA. NO emite comprobantes.

Reemplaza al script temporal `wsaa_test.py`, usando ya la capa de servicio real.
Uso:  ../env/Scripts/python.exe manage.py probar_arca
"""
from django.core.management.base import BaseCommand

from facturacion.models import Comprobante
from facturacion.services import config, wsfev1


class Command(BaseCommand):
    help = "Prueba lecturas contra ARCA (dummy, puntos de venta, último autorizado)."

    def handle(self, *args, **options):
        self.stdout.write(
            f"Ambiente: {config.ambiente_actual()}  ·  CUIT: {config.cuit()}  ·  "
            f"PV por defecto: {config.punto_venta()}"
        )

        self.stdout.write("\n[FEDummy] estado del servidor de facturación:")
        try:
            for k, v in wsfev1.dummy().items():
                self.stdout.write(f"  {k}: {v}")
        except Exception as e:  # noqa: BLE001 - queremos ver cualquier fallo
            self.stderr.write(f"  ERROR: {e}")

        self.stdout.write("\n[FEParamGetPtosVenta] puntos de venta del ambiente:")
        try:
            pvs = wsfev1.puntos_de_venta()
            if not pvs:
                self.stdout.write("  (ninguno configurado)")
            for pv in pvs:
                self.stdout.write(
                    f"  PV {pv['nro']} | emision={pv['emision']} | bloqueado={pv['bloqueado']}"
                )
        except Exception as e:  # noqa: BLE001
            self.stderr.write(f"  ERROR: {e}")

        pv = config.punto_venta()
        tipo = Comprobante.Tipo.FACTURA_C
        self.stdout.write(f"\n[FECompUltimoAutorizado] PV={pv}, Factura C (tipo {tipo}):")
        try:
            ultimo = wsfev1.ultimo_autorizado(pv, tipo)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Último autorizado: {ultimo}  (el próximo sería {ultimo + 1})"
                )
            )
        except Exception as e:  # noqa: BLE001
            self.stderr.write(f"  ERROR: {e}")
