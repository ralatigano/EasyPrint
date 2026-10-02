from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.utils import format_ar, parse_ar


class ParseArTests(TestCase):
    """Regresión del bug: el precio del insumo se guardaba en 0 al editar
    desde el modal, porque el campo llegaba con formato "$ 1.234,56" y
    parse_ar no toleraba el símbolo de moneda ni los espacios."""

    def test_formato_moneda_con_simbolo(self):
        # El modal manda el precio con prefijo "$ " (ver Insumos.js).
        self.assertEqual(parse_ar("$ 350,50"), Decimal("350.50"))
        self.assertEqual(parse_ar("$ 1.234,56"), Decimal("1234.56"))
        self.assertEqual(parse_ar("  $  2.000,00  "), Decimal("2000.00"))

    def test_formato_ar_sin_simbolo(self):
        self.assertEqual(parse_ar("350,50"), Decimal("350.50"))
        self.assertEqual(parse_ar("1.234,56"), Decimal("1234.56"))

    def test_negativos(self):
        self.assertEqual(parse_ar("-1.500,25"), Decimal("-1500.25"))

    def test_valores_numericos(self):
        # Si ya es numérico no se reinterpretan separadores.
        self.assertEqual(parse_ar(1234.56), Decimal("1234.56"))
        self.assertEqual(parse_ar(350), Decimal("350"))

    def test_vacios_e_invalidos(self):
        self.assertEqual(parse_ar(""), Decimal("0.00"))
        self.assertEqual(parse_ar(None), Decimal("0.00"))
        self.assertEqual(parse_ar("abc"), Decimal("0.00"))

    def test_roundtrip_format_parse(self):
        # format_ar y parse_ar deben ser inversos entre sí.
        self.assertEqual(parse_ar(format_ar(1234.56)), Decimal("1234.56"))


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class RolesTests(TestCase):
    """Administración tiene las funciones de Gerencia salvo el Dashboard."""

    def _usuario(self, username, grupo=None):
        from django.contrib.auth.models import Group
        user = User.objects.create_user(username=username, password='x')
        if grupo:
            user.groups.add(Group.objects.get(name=grupo))
        return user

    def test_grupos_creados_por_migracion(self):
        from django.contrib.auth.models import Group
        nombres = set(Group.objects.values_list('name', flat=True))
        self.assertTrue({'Gerencia', 'Administración', 'Ventas'} <= nombres)

    def test_permisos_por_rol(self):
        from core.roles import es_gestion, ve_dashboard
        casos = {
            'Gerencia': (True, True),
            'Administración': (True, False),
            'Ventas': (False, False),
        }
        for grupo, (gestion, dashboard) in casos.items():
            user = self._usuario(f'u_{grupo}', grupo)
            self.assertEqual(es_gestion(user), gestion, grupo)
            self.assertEqual(ve_dashboard(user), dashboard, grupo)

    def test_administracion_entra_a_gestion_pero_no_al_dashboard(self):
        self._usuario('admin1', 'Administración')
        self.client.login(username='admin1', password='x')
        self.assertEqual(self.client.get('/configuracion/pagos').status_code, 200)
        resp = self.client.get('/dashboard/')
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get('/productos/insumos/')
        self.assertContains(resp, 'Configuración')
        self.assertNotContains(resp, 'id="nav_item_dashboard"')

    def test_administracion_no_accede_a_usuarios(self):
        self._usuario('admin2', 'Administración')
        self.client.login(username='admin2', password='x')
        self.assertEqual(self.client.get('/usuarios').status_code, 302)
        resp = self.client.get('/productos/insumos/')
        self.assertNotContains(resp, 'id="nav_item_usuarios"')
        self.assertContains(resp, 'id="nav_item_caja"')

    def test_ventas_no_ve_caja_pero_si_comprobantes(self):
        self._usuario('ven1', 'Ventas')
        self.client.login(username='ven1', password='x')
        resp = self.client.get('/productos/insumos/')
        self.assertNotContains(resp, 'id="nav_item_caja"')
        self.assertContains(resp, 'id="nav_item_comprobantes"')

    def test_gerencia_ve_el_dashboard(self):
        self._usuario('ger1', 'Gerencia')
        self.client.login(username='ger1', password='x')
        resp = self.client.get('/productos/insumos/')
        self.assertContains(resp, 'id="nav_item_dashboard"')
