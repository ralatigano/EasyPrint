"""Tests de facturación que NO tocan la red (no llaman a ARCA).

Cubren la generación del PDF y del QR (FASE 3), armando un Comprobante
autorizado con un CAE ficticio directamente en la DB de test.
"""
import base64
import datetime
import json
from decimal import Decimal

from django.conf import settings
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

    def test_contexto_devuelve_identidad_desglosada(self):
        c = _comprobante_autorizado()
        cliente = c.pedido.cliente
        cliente.negocio = "Kiosco El Sol"
        cliente.razon_social = "PEREZ JUAN"
        cliente.save()

        resp = self.client.get(
            reverse("contexto_facturacion", args=[c.pedido.numero])
        )
        data = resp.json()["cliente"]
        self.assertEqual(data["nombre"], "Cliente Test")
        self.assertEqual(data["negocio"], "Kiosco El Sol")
        self.assertEqual(data["razon_social"], "PEREZ JUAN")


class RazonSocialTests(TestCase):
    def test_nombre_facturacion_prefiere_razon_social(self):
        cli = Cliente.objects.create(nombre="Juan", negocio="Kiosco")
        self.assertEqual(cli.nombre_facturacion, "Juan | Kiosco")
        cli.razon_social = "PEREZ JUAN CARLOS"
        self.assertEqual(cli.nombre_facturacion, "PEREZ JUAN CARLOS")

    def test_actualizar_cliente_desde_factura(self):
        from .views import _actualizar_cliente_desde_factura

        cli = Cliente.objects.create(nombre="Juan")
        data = {"razon_social": "PEREZ JUAN", "negocio": "Kiosco", "nombre": ""}
        _actualizar_cliente_desde_factura(cli, data, Comprobante.DocTipo.CUIT, 20111111112)
        cli.refresh_from_db()
        self.assertEqual(cli.razon_social, "PEREZ JUAN")
        self.assertEqual(cli.negocio, "Kiosco")
        self.assertEqual(cli.cuit, 20111111112)
        self.assertEqual(cli.nombre, "Juan")  # vacío no pisa

    def test_no_toca_consumidor_final(self):
        from .views import _actualizar_cliente_desde_factura

        cli = Cliente.objects.create(nombre="Consumidor final")
        _actualizar_cliente_desde_factura(
            cli, {"razon_social": "X"}, Comprobante.DocTipo.CUIT, 20111111112
        )
        cli.refresh_from_db()
        self.assertEqual(cli.razon_social, "")
        self.assertIsNone(cli.cuit)

    def test_dni_no_guarda_cuit(self):
        from .views import _actualizar_cliente_desde_factura

        cli = Cliente.objects.create(nombre="Juan")
        _actualizar_cliente_desde_factura(
            cli, {}, Comprobante.DocTipo.DNI, 30111222
        )
        cli.refresh_from_db()
        self.assertIsNone(cli.cuit)


class PadronDefensivoTests(TestCase):
    def test_consultar_cuit_invalido_ok_false_sin_red(self):
        from .services import padron

        r = padron.consultar("123")
        self.assertFalse(r["ok"])
        self.assertFalse(padron.consultar("")["ok"])

    def test_endpoint_padron_cuit_corto_ok_false(self):
        from django.contrib.auth.models import User

        User.objects.create_user("tester", password="x")
        self.client.login(username="tester", password="x")
        resp = self.client.get(reverse("consultar_padron", args=[123]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["ok"])


# ── Widget "Facturación vs. tope de categoría" (monotributo) ────────────────

class VentanaRecategorizacionTests(TestCase):
    """La ventana no es 12 meses móviles ni el año calendario: es la ventana de
    12 meses que evalúa la próxima recategorización. Se testean los bordes."""

    def _ventana(self, y, m, d):
        from .services.monotributo import ventana_recategorizacion

        return ventana_recategorizacion(datetime.date(y, m, d))

    def test_enero_evalua_el_anio_anterior_completo(self):
        # 1/1 y 31/1 caen en la recategorización de enero: mira el año anterior.
        self.assertEqual(
            self._ventana(2026, 1, 1),
            (datetime.date(2025, 1, 1), datetime.date(2025, 12, 31)),
        )
        self.assertEqual(
            self._ventana(2026, 1, 31),
            (datetime.date(2025, 1, 1), datetime.date(2025, 12, 31)),
        )

    def test_febrero_a_julio_ventana_semestral(self):
        semestral = (datetime.date(2025, 7, 1), datetime.date(2026, 6, 30))
        # 1/2: primer día de la ventana semestral.
        self.assertEqual(self._ventana(2026, 2, 1), semestral)
        # 30/6 y 1/7: el cambio de ventana NO ocurre acá, sigue siendo semestral.
        self.assertEqual(self._ventana(2026, 6, 30), semestral)
        self.assertEqual(self._ventana(2026, 7, 1), semestral)
        # 31/7: último día antes de pasar a la ventana anual.
        self.assertEqual(self._ventana(2026, 7, 31), semestral)

    def test_agosto_a_diciembre_ventana_anual(self):
        anual = (datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))
        # 1/8: primer día de la ventana anual.
        self.assertEqual(self._ventana(2026, 8, 1), anual)
        self.assertEqual(self._ventana(2026, 12, 31), anual)

    def test_fin_de_semestre_en_anio_bisiesto(self):
        # El 30/6 se calcula restando un día al 1/7, no hardcodeado.
        _, hasta = self._ventana(2024, 3, 15)
        self.assertEqual(hasta, datetime.date(2024, 6, 30))


class AcumuladoFacturadoTests(TestCase):
    """El acumulado suma facturas y notas de débito, y resta notas de crédito.
    Sólo cuenta comprobantes autorizados del ambiente activo."""

    def setUp(self):
        cliente = Cliente.objects.create(nombre="Cliente Acum")
        self.pedido = Pedido.objects.create(
            numero=999500,
            producto="Volantes",
            descripcion="A5",
            precio=1000,
            cliente=cliente,
        )

    def _cbte(self, importe, fecha, tipo=Comprobante.Tipo.FACTURA_C,
              estado=Comprobante.Estado.AUTORIZADO, ambiente="homologacion"):
        return Comprobante.objects.create(
            pedido=self.pedido,
            ambiente=ambiente,
            tipo_cbte=tipo,
            punto_venta=1,
            numero=1,
            fecha_emision=fecha,
            importe_total=Decimal(importe),
            estado=estado,
        )

    def test_suma_facturas_y_notas_de_debito_resta_notas_de_credito(self):
        from .services.monotributo import acumulado_facturado

        f = datetime.date(2026, 3, 10)
        self._cbte("1000.00", f)
        self._cbte("500.00", f, tipo=Comprobante.Tipo.NOTA_DEBITO_C)
        self._cbte("300.00", f, tipo=Comprobante.Tipo.NOTA_CREDITO_C)

        total = acumulado_facturado(
            datetime.date(2026, 1, 1), datetime.date(2026, 12, 31),
            ambiente="homologacion",
        )
        self.assertEqual(total, Decimal("1200.00"))

    def test_ignora_no_autorizados_otro_ambiente_y_fuera_de_ventana(self):
        from .services.monotributo import acumulado_facturado

        dentro = datetime.date(2026, 3, 10)
        self._cbte("100.00", dentro)                                        # cuenta
        self._cbte("50.00", dentro, estado=Comprobante.Estado.BORRADOR)     # no
        self._cbte("50.00", dentro, estado=Comprobante.Estado.ANULADO)      # no
        self._cbte("50.00", dentro, estado=Comprobante.Estado.ERROR)        # no
        self._cbte("50.00", dentro, ambiente="produccion")                  # no
        self._cbte("50.00", datetime.date(2025, 12, 31))                    # no

        total = acumulado_facturado(
            datetime.date(2026, 1, 1), datetime.date(2026, 12, 31),
            ambiente="homologacion",
        )
        self.assertEqual(total, Decimal("100.00"))

    def test_sin_comprobantes_devuelve_cero(self):
        from .services.monotributo import acumulado_facturado

        total = acumulado_facturado(
            datetime.date(2026, 1, 1), datetime.date(2026, 12, 31),
            ambiente="homologacion",
        )
        self.assertEqual(total, Decimal("0.00"))

    def test_bordes_de_la_ventana_son_inclusivos(self):
        from .services.monotributo import acumulado_facturado

        self._cbte("10.00", datetime.date(2026, 1, 1))
        self._cbte("10.00", datetime.date(2026, 12, 31))
        total = acumulado_facturado(
            datetime.date(2026, 1, 1), datetime.date(2026, 12, 31),
            ambiente="homologacion",
        )
        self.assertEqual(total, Decimal("20.00"))


class ResumenMonotributoTests(TestCase):
    def _pedido(self, numero, nombre):
        cliente = Cliente.objects.create(nombre=nombre)
        return Pedido.objects.create(
            numero=numero, producto="X", descripcion="X",
            precio=1, cliente=cliente,
        )

    def test_sin_configurar_no_calcula_porcentaje(self):
        from .services.monotributo import resumen

        r = resumen(datetime.date(2026, 3, 10))
        self.assertFalse(r["configurado"])
        self.assertEqual(r["porcentaje"], 0)

    def test_semaforo_y_restante(self):
        from .models import ConfiguracionMonotributo
        from .services.monotributo import resumen

        cfg = ConfiguracionMonotributo.load()
        cfg.categoria = "C"
        cfg.tope_anual = Decimal("1000.00")
        cfg.save()

        pedido = self._pedido(999501, "Cliente Res")
        ambiente = settings.AFIP["ENV"]

        def facturar(importe):
            Comprobante.objects.create(
                pedido=pedido, ambiente=ambiente,
                tipo_cbte=Comprobante.Tipo.FACTURA_C, punto_venta=1, numero=1,
                fecha_emision=datetime.date(2026, 3, 10),
                importe_total=Decimal(importe),
                estado=Comprobante.Estado.AUTORIZADO,
            )

        facturar("500.00")
        r = resumen(datetime.date(2026, 3, 10))
        self.assertTrue(r["configurado"])
        self.assertEqual(r["nivel"], "ok")
        self.assertEqual(r["porcentaje"], 50.0)
        self.assertEqual(r["restante"], Decimal("500.00"))
        self.assertFalse(r["excedido"])

        facturar("250.00")  # 75% → alerta
        self.assertEqual(resumen(datetime.date(2026, 3, 10))["nivel"], "alerta")

        facturar("200.00")  # 95% → crítico
        self.assertEqual(resumen(datetime.date(2026, 3, 10))["nivel"], "critico")

        facturar("100.00")  # 105% → excedido, la barra se recorta en 100
        r = resumen(datetime.date(2026, 3, 10))
        self.assertTrue(r["excedido"])
        self.assertEqual(r["porcentaje_barra"], "100.00")
        self.assertEqual(r["restante_fmt"], "50,00")

    def test_no_cuenta_comprobantes_posteriores_a_hoy(self):
        """El acumulado corre hasta hoy, no hasta el fin de la ventana."""
        from .services.monotributo import resumen

        pedido = self._pedido(999502, "Cliente Futuro")
        Comprobante.objects.create(
            pedido=pedido, ambiente=settings.AFIP["ENV"],
            tipo_cbte=Comprobante.Tipo.FACTURA_C, punto_venta=1, numero=1,
            fecha_emision=datetime.date(2026, 5, 1),
            importe_total=Decimal("999.00"),
            estado=Comprobante.Estado.AUTORIZADO,
        )
        r = resumen(datetime.date(2026, 3, 10))
        self.assertEqual(r["hasta_efectivo"], datetime.date(2026, 3, 10))
        self.assertEqual(r["facturado"], Decimal("0.00"))


@_STATIC_SIMPLE
class ConfigMonotributoViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group, User

        self.gerente = User.objects.create_user("gerente", password="x")
        self.gerente.groups.add(Group.objects.create(name="Gerencia"))
        self.raso = User.objects.create_user("raso", password="x")

    def _login_gerencia(self):
        """Login + el flag `autorizado` que normalmente deja la vista de login
        en la sesión (self.client.login() no pasa por esa vista)."""
        self.client.login(username="gerente", password="x")
        sesion = self.client.session
        sesion["autorizado"] = True
        sesion.save()

    def test_gerencia_guarda_categoria_y_tope_en_formato_ar(self):
        from .models import ConfiguracionMonotributo

        self.client.login(username="gerente", password="x")
        resp = self.client.post(
            reverse("guardar_config_monotributo"),
            {"categoria": "c", "tope_anual": "$ 24.670.494,31"},
        )
        self.assertEqual(resp.status_code, 302)
        cfg = ConfiguracionMonotributo.load()
        self.assertEqual(cfg.categoria, "C")
        self.assertEqual(cfg.tope_anual, Decimal("24670494.31"))

    def test_categoria_invalida_no_guarda(self):
        from .models import ConfiguracionMonotributo

        self.client.login(username="gerente", password="x")
        self.client.post(
            reverse("guardar_config_monotributo"),
            {"categoria": "Z", "tope_anual": "1.000,00"},
        )
        self.assertFalse(ConfiguracionMonotributo.load().configurado)

    def test_tope_cero_no_guarda(self):
        from .models import ConfiguracionMonotributo

        self.client.login(username="gerente", password="x")
        self.client.post(
            reverse("guardar_config_monotributo"),
            {"categoria": "C", "tope_anual": "0"},
        )
        self.assertFalse(ConfiguracionMonotributo.load().configurado)

    def test_usuario_sin_gerencia_no_puede_configurar(self):
        from .models import ConfiguracionMonotributo

        self.client.login(username="raso", password="x")
        self.client.post(
            reverse("guardar_config_monotributo"),
            {"categoria": "C", "tope_anual": "1.000,00"},
        )
        self.assertFalse(ConfiguracionMonotributo.load().configurado)

    def test_lista_comprobantes_muestra_el_widget(self):
        from .models import ConfiguracionMonotributo

        cfg = ConfiguracionMonotributo.load()
        cfg.categoria = "C"
        cfg.tope_anual = Decimal("24670494.31")
        cfg.save()

        self._login_gerencia()
        resp = self.client.get(reverse("lista_comprobantes"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Facturación electrónica")
        self.assertContains(resp, "Tope categoría C")
        self.assertContains(resp, "24.670.494,31")

    def test_widget_sin_configurar_ofrece_cargar_la_categoria(self):
        self._login_gerencia()
        resp = self.client.get(reverse("lista_comprobantes"))
        self.assertContains(resp, "Configurar categoría")
        self.assertContains(resp, "modalMonotributo")
