"""Prueba la consulta al padrón de ARCA (ws_sr_padron_a13) por CUIT.

NO emite comprobantes; sólo consulta datos del padrón. Sirve para validar la
adhesión del web service y el parseo de la respuesta desde la CLI, sin pasar por
el navegador.

Uso:
  ../env/Scripts/python.exe manage.py probar_padron 20111111112
  ../env/Scripts/python.exe manage.py probar_padron 20111111112 --raw
"""
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET

from django.core.management.base import BaseCommand

from facturacion.services import config, padron
from facturacion.services._soap import find_text, post_soap
from facturacion.services.wsaa import obtener_ta


class Command(BaseCommand):
    help = "Consulta la razón social de un CUIT en el padrón de ARCA (ws_sr_padron_a13)."

    def add_arguments(self, parser):
        parser.add_argument("cuit", help="CUIT a consultar (11 dígitos, sin guiones).")
        parser.add_argument(
            "--raw",
            action="store_true",
            help="Imprime el XML crudo de la respuesta (para depurar el parseo).",
        )

    def handle(self, *args, **options):
        cuit = "".join(ch for ch in str(options["cuit"]) if ch.isdigit())
        self.stdout.write(
            f"Ambiente: {config.ambiente_actual()}  ·  "
            f"CUIT emisor: {config.cuit()}  ·  Servicio: {padron.SERVICIO}"
        )
        self.stdout.write(f"Endpoint: {padron._url()}")

        if len(cuit) != 11:
            self.stderr.write(self.style.ERROR("El CUIT debe tener 11 dígitos."))
            return

        # 1) Ticket de acceso para el servicio de padrón (falla claro si no está adherido).
        self.stdout.write("\n[WSAA] Obteniendo ticket de acceso para padrón...")
        try:
            ta = obtener_ta(padron.SERVICIO)
            self.stdout.write(self.style.SUCCESS(f"  OK (vence {ta.expiracion})"))
        except Exception as e:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f"  ERROR: {e}"))
            self.stderr.write(
                "  → Verificá que el CUIT tenga adherido 'ws_sr_padron_a13' "
                "(homologación: WSASS; producción: Administrador de Relaciones)."
            )
            return

        # 2) Consulta al padrón (llamada de bajo nivel para poder mostrar el XML).
        soap = (
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
            f' xmlns:a13="{padron.NS}">'
            "<soapenv:Body><a13:getPersona>"
            f"<token>{ta.token}</token>"
            f"<sign>{ta.sign}</sign>"
            f"<cuitRepresentada>{config.cuit()}</cuitRepresentada>"
            f"<idPersona>{cuit}</idPersona>"
            "</a13:getPersona></soapenv:Body></soapenv:Envelope>"
        )
        self.stdout.write(f"\n[getPersona] Consultando CUIT {cuit}...")
        try:
            root = post_soap(padron._url(), soap, soap_action="")
        except Exception as e:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f"  ERROR de red/SOAP: {e}"))
            return

        if options["raw"]:
            xml_str = ET.tostring(root, encoding="unicode")
            self.stdout.write("\n--- XML crudo ---")
            self.stdout.write(minidom.parseString(xml_str).toprettyxml(indent="  "))
            self.stdout.write("--- fin XML ---\n")

        fault = find_text(root, "faultstring")
        if fault:
            self.stderr.write(self.style.ERROR(f"  SOAP fault: {fault}"))
            return

        razon = padron._razon_social_desde_persona(root)
        tipo = find_text(root, "tipoPersona")
        if razon:
            self.stdout.write(
                self.style.SUCCESS(f"  Razón social: {razon}  (tipoPersona={tipo})")
            )
        else:
            self.stderr.write(
                "  No se encontró razón social en la respuesta "
                "(corré con --raw para ver el XML)."
            )
