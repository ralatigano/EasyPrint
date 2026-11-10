from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from clientes.models import Cliente
from facturacion.models import Ambiente, Comprobante
from facturacion.services import config
from pedidos import views
from pedidos.models import Pedido
from presupuestos.models import Presupuesto


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class CalendarioEntregasTests(TestCase):
    """Fase 6: vista calendario (accesoria, solo lectura) de entregas."""

    def setUp(self):
        User.objects.create_user("v", password="pw12345")
        self.client.login(username="v", password="pw12345")

    def test_muestra_pedido_en_su_dia(self):
        Pedido.objects.create(
            numero=1, descripcion="x", precio=1000, saldo=500,
            producto="10 Tarjetas", fecha_entrega=date(2026, 6, 15))
        resp = self.client.get("/pedidos/calendario?anio=2026&mes=6")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "10 Tarjetas")
        self.assertContains(resp, "Debe $ 500")

    def test_excluye_cancelados(self):
        Pedido.objects.create(
            numero=2, descripcion="x", precio=1000, producto="Cancelado SA",
            fecha_entrega=date(2026, 6, 15), bloqueado_cancelado=True)
        resp = self.client.get("/pedidos/calendario?anio=2026&mes=6")
        self.assertNotContains(resp, "Cancelado SA")

    def test_navegacion_meses(self):
        # Enero -> anterior diciembre del año previo; siguiente febrero.
        resp = self.client.get("/pedidos/calendario?anio=2026&mes=1")
        self.assertEqual(resp.context["prev_mes"], 12)
        self.assertEqual(resp.context["prev_anio"], 2025)
        self.assertEqual(resp.context["next_mes"], 2)
        self.assertEqual(resp.context["next_anio"], 2026)


class CambiarClientePedidoTests(TestCase):
    """Regresión: el modal arma "<id>|<referencia>|<pedido>|<presupuesto>" y la
    referencia de un cliente con negocio trae '|' ("Apu | Kwik-E-Mart"), lo que
    corría los campos y hacía Pedido.objects.get(numero=" Kwik-E-Mart") → 500."""

    URL = '/pedidos/cambiarClientePedido'

    def setUp(self):
        self.client.force_login(User.objects.create_user('vendedor', password='x'))
        self.anterior = Cliente.objects.create(nombre='Homero')
        self.nuevo = Cliente.objects.create(nombre='Apu', negocio='Kwik-E-Mart')
        Presupuesto.objects.create(numero=500, cliente=self.anterior)
        self.pedido = Pedido.objects.create(
            numero=100, descripcion='x', precio=1000, cliente=self.anterior,
            presupuesto=500)

    def _post(self, pedido, presupuesto):
        return self.client.post(self.URL, {
            'pedidoNumero': pedido,
            'presupuestoNumero': presupuesto,
            'nuevoCliente': f'{self.nuevo.id}|{self.nuevo.referencia}',
        })

    def test_cambia_cliente_con_referencia_que_trae_barra(self):
        resp = self._post('100', '500')
        self.assertEqual(resp.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.cliente, self.nuevo)
        self.assertEqual(Presupuesto.objects.get(numero=500).cliente, self.nuevo)

    def test_numero_de_pedido_invalido_no_rompe(self):
        resp = self._post(' Kwik-E-Mart', '100')
        self.assertEqual(resp.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.cliente, self.anterior)

    def test_pedido_sin_presupuesto(self):
        self.pedido.presupuesto = None
        self.pedido.save()
        resp = self._post('100', 'None')
        self.assertEqual(resp.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.cliente, self.nuevo)


STATIC = override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})

OTRO_AMBIENTE = {
    Ambiente.PRODUCCION: Ambiente.HOMOLOGACION,
    Ambiente.HOMOLOGACION: Ambiente.PRODUCCION,
}


def _comprobante(pedido, estado, tipo=Comprobante.Tipo.FACTURA_C, ambiente=None):
    return Comprobante.objects.create(
        pedido=pedido,
        ambiente=ambiente or config.ambiente_actual(),
        tipo_cbte=tipo,
        punto_venta=1,
        numero=1,
        fecha_emision=date(2026, 11, 10),
        importe_total=Decimal("1000"),
        estado=estado,
    )


class MarcaFacturadoTests(TestCase):
    """La marca de facturado se anota en la queryset, no se consulta por fila.

    La tabla trae todos los pedidos: una consulta por fila serían cientos.
    """

    def setUp(self):
        self.pedido = Pedido.objects.create(
            numero=1, descripcion="x", precio=1000, producto="Tarjetas")

    def _anotado(self, numero=1):
        return views._pedidos_con_facturacion().get(numero=numero)

    def test_sin_comprobantes_no_esta_facturado(self):
        p = self._anotado()
        self.assertFalse(p.facturado)
        self.assertFalse(p.error_facturacion)

    def test_una_factura_autorizada_lo_marca(self):
        _comprobante(self.pedido, Comprobante.Estado.AUTORIZADO)
        self.assertTrue(self._anotado().facturado)

    def test_un_borrador_no_lo_marca(self):
        _comprobante(self.pedido, Comprobante.Estado.BORRADOR)
        p = self._anotado()
        self.assertFalse(p.facturado)
        self.assertFalse(p.error_facturacion)

    def test_un_intento_con_error_se_distingue_de_sin_facturar(self):
        _comprobante(self.pedido, Comprobante.Estado.ERROR)
        p = self._anotado()
        self.assertFalse(p.facturado)
        self.assertTrue(p.error_facturacion)

    def test_un_comprobante_de_otro_ambiente_no_cuenta(self):
        """Una factura de homologación no es una factura real."""
        _comprobante(self.pedido, Comprobante.Estado.AUTORIZADO,
                     ambiente=OTRO_AMBIENTE[config.ambiente_actual()])
        self.assertFalse(self._anotado().facturado)

    def test_una_nota_de_credito_sola_no_marca_facturado(self):
        _comprobante(self.pedido, Comprobante.Estado.AUTORIZADO,
                     tipo=Comprobante.Tipo.NOTA_CREDITO_C)
        self.assertFalse(self._anotado().facturado)

    def test_facturado_le_gana_a_un_intento_fallido_previo(self):
        """Se reintentó y salió: el pedido está facturado."""
        _comprobante(self.pedido, Comprobante.Estado.ERROR)
        _comprobante(self.pedido, Comprobante.Estado.AUTORIZADO)
        p = self._anotado()
        self.assertTrue(p.facturado)

    def test_no_consulta_una_vez_por_pedido(self):
        for n in range(2, 12):
            Pedido.objects.create(numero=n, descripcion="x", precio=1,
                                  producto="p")
        _comprobante(self.pedido, Comprobante.Estado.AUTORIZADO)
        with self.assertNumQueries(1):
            list(views._pedidos_con_facturacion().values("numero", "facturado"))


@STATIC
class TablaPedidosTests(TestCase):
    def setUp(self):
        User.objects.create_user("v", password="pw12345")
        self.client.login(username="v", password="pw12345")
        self.pedido = Pedido.objects.create(
            numero=1, descripcion="x", precio=1000, producto="Tarjetas",
            fecha_entrega=date(2026, 6, 15))

    # Se busca el icono completo y no solo la clase: el nombre de la clase
    # tambien aparece en el bloque <style> del template, asi que buscarlo
    # suelto daria positivo siempre.
    ICONO_OK = 'fa-receipt marca-facturado'
    ICONO_ERROR = 'fa-triangle-exclamation marca-factura-error'

    def test_la_marca_aparece_cuando_hay_factura(self):
        _comprobante(self.pedido, Comprobante.Estado.AUTORIZADO)
        resp = self.client.get("/pedidos/v2")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.ICONO_OK)
        self.assertNotContains(resp, self.ICONO_ERROR)

    def test_un_intento_fallido_muestra_otra_marca(self):
        _comprobante(self.pedido, Comprobante.Estado.ERROR)
        resp = self.client.get("/pedidos/v2")
        self.assertContains(resp, self.ICONO_ERROR)
        self.assertNotContains(resp, self.ICONO_OK)

    def test_sin_factura_no_hay_marca(self):
        resp = self.client.get("/pedidos/v2")
        self.assertNotContains(resp, self.ICONO_OK)
        self.assertNotContains(resp, self.ICONO_ERROR)

    def test_la_fecha_de_entrega_va_en_iso_para_el_filtro(self):
        """El filtro de rango compara texto: la celda visible va en formato AR."""
        resp = self.client.get("/pedidos/v2")
        self.assertContains(resp, 'data-entrega="2026-06-15"')

    def test_estan_los_campos_del_rango(self):
        resp = self.client.get("/pedidos/v2")
        self.assertContains(resp, 'id="filtroDesde"')
        self.assertContains(resp, 'id="filtroHasta"')
