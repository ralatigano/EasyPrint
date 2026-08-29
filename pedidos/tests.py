from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from pedidos.models import Pedido


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
