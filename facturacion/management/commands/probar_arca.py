"""Prueba de conectividad/lectura contra ARCA. NO emite comprobantes.

Reemplaza al script temporal `wsaa_test.py`, usando ya la capa de servicio real.
Uso:  ../env/Scripts/python.exe manage.py probar_arca
"""
from django.core.management.base import BaseCommand

from facturacion.models import Comprobante
from facturacion.services import config, wsfev1


class Command(BaseCommand):
    help = "Prueba lecturas contra ARCA (dummy, puntos de venta, último autorizado)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--emitir",
            action="store_true",
            help=(
                "Además de las lecturas, solicita un CAE de prueba "
                "(Factura C a Consumidor Final, importe chico). Sólo homologación."
            ),
        )
        parser.add_argument(
            "--importe",
            type=float,
            default=100.0,
            help="Importe total del comprobante de prueba (default: 100.00).",
        )

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

        if options["emitir"]:
            self._emitir_prueba(pv, tipo, options["importe"])

    def _emitir_prueba(self, pv, tipo, importe):
        """Solicita un CAE de prueba (FECAESolicitar) — el camino nunca validado."""
        if config.ambiente_actual() != "homologacion":
            self.stderr.write(
                self.style.ERROR(
                    "\n[FECAESolicitar] ABORTADO: --emitir sólo se permite en "
                    f"homologación (ambiente actual: {config.ambiente_actual()})."
                )
            )
            return

        self.stdout.write(
            f"\n[FECAESolicitar] Emitiendo Factura C de prueba a Consumidor Final "
            f"por ${importe:.2f} (PV={pv})..."
        )
        try:
            resp = wsfev1.solicitar_cae(
                punto_venta=pv,
                tipo_cbte=tipo,
                concepto=Comprobante.Concepto.PRODUCTOS,
                doc_tipo=Comprobante.DocTipo.CONSUMIDOR_FINAL,  # 99
                doc_nro=0,
                cond_iva_receptor=5,  # Consumidor Final
                importe_total=importe,
            )
        except Exception as e:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f"  ERROR: {e}"))
            return

        if resp["observaciones"]:
            self.stdout.write("  Observaciones:")
            for obs in resp["observaciones"]:
                self.stdout.write(f"    - {obs}")

        if resp["resultado"] == "A":
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [OK] APROBADO - Nro {pv:04d}-{resp['numero']:08d} - "
                    f"CAE {resp['cae']} (vto {resp['cae_vto']})"
                )
            )
        else:
            self.stderr.write(
                self.style.ERROR(
                    f"  [X] RECHAZADO (Resultado={resp['resultado']}). "
                    "Ver observaciones arriba."
                )
            )
