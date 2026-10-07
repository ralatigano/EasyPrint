from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from clientes.models import Cliente
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
