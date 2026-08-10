"""Tests de facturación que NO tocan la red (no llaman a ARCA).

Cubren la generación del PDF y del QR (FASE 3), armando un Comprobante
autorizado con un CAE ficticio directamente en la DB de test.
"""
import base64
import datetime
import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

# En tests no se corre collectstatic, así que el ManifestStaticFilesStorage de
# producción rompe al renderizar plantillas (busca el manifest). Para los tests
# que renderizan una página completa usamos el storage simple.
_STATIC_SIMPLE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)

from clientes.models import Cliente
from pedidos.models import Pedido

from .models import Comprobante
from .services import pdf


def _comprobante_autorizado(**extra):
    cliente = Cliente.objects.create(nombre="Cliente Test")
    pedido = Pedido.objects.create(
        numero=999001,
        producto="Tarjetas personales x1000",
        descripcion="Impresión full color",
        precio=12500.50,
        cliente=cliente,
    )
    defaults = dict(
        pedido=pedido,
        ambiente="homologacion",
        tipo_cbte=Comprobante.Tipo.FACTURA_C,
        punto_venta=1,
        numero=4,
        concepto=Comprobante.Concepto.PRODUCTOS,
        fecha_emision=datetime.date(2026, 8, 10),
        importe_total=Decimal("12500.50"),
        doc_tipo=Comprobante.DocTipo.CONSUMIDOR_FINAL,
        doc_nro=0,
        cond_iva_receptor=5,
        receptor_nombre="Consumidor Final",
        cae="86320751141599",
        cae_vencimiento=datetime.date(2026, 8, 20),
        estado=Comprobante.Estado.AUTORIZADO,
    )
    defaults.update(extra)
    return Comprobante.objects.create(**defaults)


class QrTests(TestCase):
    def test_qr_url_estructura_arca(self):
        c = _comprobante_autorizado()
        url = pdf._qr_url(c)
        self.assertTrue(url.startswith("https://www.afip.gob.ar/fe/qr/?p="))
        datos = json.loads(base64.b64decode(url.split("p=")[1]))
        self.assertEqual(datos["ver"], 1)
        self.assertEqual(datos["tipoCmp"], 11)
        self.assertEqual(datos["ptoVta"], 1)
        self.assertEqual(datos["nroCmp"], 4)
        self.assertEqual(datos["importe"], 12500.50)
        self.assertEqual(datos["moneda"], "PES")
        self.assertEqual(datos["tipoCodAut"], "E")
        self.assertEqual(datos["codAut"], 86320751141599)
        # codAut e importe deben ser numéricos, no strings.
        self.assertIsInstance(datos["codAut"], int)
        self.assertIsInstance(datos["importe"], float)


class PdfTests(TestCase):
    def test_render_pdf_devuelve_pdf(self):
        c = _comprobante_autorizado()
        contenido = pdf.render_pdf(c)
        self.assertTrue(contenido.startswith(b"%PDF"))
        self.assertGreater(len(contenido), 1000)

    def test_render_pdf_receptor_identificado(self):
        c = _comprobante_autorizado(
            doc_tipo=Comprobante.DocTipo.CUIT,
            doc_nro=20111111112,
            cond_iva_receptor=6,
            receptor_nombre="Otro Contribuyente",
        )
        contenido = pdf.render_pdf(c)
        self.assertTrue(contenido.startswith(b"%PDF"))


class PdfViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        User.objects.create_user("tester", password="x")
        self.client.login(username="tester", password="x")

    def test_pdf_autorizado_200(self):
        c = _comprobante_autorizado()
        resp = self.client.get(reverse("comprobante_pdf", args=[c.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_pdf_borrador_rechazado(self):
        c = _comprobante_autorizado(
            estado=Comprobante.Estado.BORRADOR, cae="", numero=None
        )
        resp = self.client.get(reverse("comprobante_pdf", args=[c.id]))
        self.assertEqual(resp.status_code, 400)


@_STATIC_SIMPLE
class ListaComprobantesTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        User.objects.create_user("tester", password="x")
        self.client.login(username="tester", password="x")

    def test_lista_200_con_comprobante(self):
        c = _comprobante_autorizado()
        resp = self.client.get(reverse("lista_comprobantes"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, c.numero_formateado)


class ContextoFacturacionTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        User.objects.create_user("tester", password="x")
        self.client.login(username="tester", password="x")

    def test_contexto_devuelve_condicion_iva_del_cliente(self):
        c = _comprobante_autorizado()
        cliente = c.pedido.cliente
        cliente.cuit = 20111111112
        cliente.condicion_iva = 6  # Responsable Monotributo
        cliente.save()

        resp = self.client.get(
            reverse("contexto_facturacion", args=[c.pedido.numero])
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["cliente"]["condicion_iva"], 6)
        self.assertEqual(data["cliente"]["cuit"], 20111111112)
