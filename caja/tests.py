import importlib
import json
from datetime import date
from decimal import Decimal

from django.apps import apps as django_apps
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from caja import services
from caja.models import Movimiento
from pedidos.estados import PedidoBloqueado, cambiar_estado_pedido
from pedidos.models import Pedido

STATIC = override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})


def _pedido(numero=1, precio=10000, estado='No iniciado', **extra):
    return Pedido.objects.create(
        numero=numero, descripcion='x', precio=precio, senia=0, saldo=precio,
        estado=estado, **extra)


def _usuario(username, grupo=None):
    user = User.objects.create_user(username=username, password='pw')
    if grupo:
        user.groups.add(Group.objects.get(name=grupo))
    return user


class ServiciosCajaTests(TestCase):

    def test_registrar_recalcula_cobrado_y_saldo(self):
        p = _pedido()
        services.registrar_movimiento(p, Decimal('4000'), 'efectivo', Movimiento.Tipo.SENIA)
        services.registrar_movimiento(p, Decimal('1500.50'), 'tarjeta', Movimiento.Tipo.PAGO)
        p.refresh_from_db()
        self.assertEqual(p.senia, 5500.50)
        self.assertEqual(p.saldo, 4499.50)

    def test_medio_obligatorio_y_monto_positivo(self):
        p = _pedido()
        with self.assertRaises(services.CobroInvalido):
            services.registrar_movimiento(p, 100, '', Movimiento.Tipo.SENIA)
        with self.assertRaises(services.CobroInvalido):
            services.registrar_movimiento(p, 100, 'sin_especificar', Movimiento.Tipo.SENIA)
        with self.assertRaises(services.CobroInvalido):
            services.registrar_movimiento(p, 0, 'efectivo', Movimiento.Tipo.SENIA)

    def test_devolucion_se_guarda_negativa(self):
        p = _pedido()
        services.registrar_movimiento(p, 3000, 'transferencia', Movimiento.Tipo.SENIA)
        mov = services.devolver_cobrado(p, 'efectivo')
        self.assertEqual(mov.monto, Decimal('-3000.00'))
        p.refresh_from_db()
        self.assertEqual(p.senia, 0)
        self.assertEqual(p.saldo, 10000)


class CambioEstadoTests(TestCase):

    def test_pagado_registra_el_saldo(self):
        p = _pedido(estado='Terminado (falta pago)')
        services.registrar_movimiento(p, 4000, 'efectivo', Movimiento.Tipo.SENIA)
        cambiar_estado_pedido(p, Pedido.PAGADO, accion='registrar', medio='transferencia')
        p.refresh_from_db()
        self.assertEqual(p.estado, Pedido.PAGADO)
        self.assertEqual(p.saldo, 0)
        ultimo = p.movimientos.order_by('-id').first()
        self.assertEqual((ultimo.medio, ultimo.monto), ('transferencia', Decimal('6000.00')))

    def test_pagado_sin_registrar_no_crea_movimiento(self):
        p = _pedido(estado='Terminado (falta pago)')
        cambiar_estado_pedido(p, Pedido.PAGADO, accion='omitir')
        self.assertFalse(p.movimientos.exists())

    def test_pagado_y_registrar_sin_medio_falla_sin_cambiar_estado(self):
        p = _pedido(estado='Terminado (falta pago)')
        with self.assertRaises(services.CobroInvalido):
            cambiar_estado_pedido(p, Pedido.PAGADO, accion='registrar', medio='')
        p.refresh_from_db()
        self.assertEqual(p.estado, 'Terminado (falta pago)')

    def test_cancelar_bloquea_el_pedido(self):
        p = _pedido()
        cambiar_estado_pedido(p, Pedido.CANCELADO, accion='retener')
        p.refresh_from_db()
        self.assertEqual(p.estado, Pedido.CANCELADO)
        self.assertTrue(p.bloqueado_cancelado)
        with self.assertRaises(PedidoBloqueado):
            cambiar_estado_pedido(p, 'En proceso')

    def test_cancelar_reteniendo_conserva_el_ingreso(self):
        p = _pedido()
        services.registrar_movimiento(p, 5000, 'efectivo', Movimiento.Tipo.SENIA)
        cambiar_estado_pedido(p, Pedido.CANCELADO, accion='retener')
        self.assertEqual(services.cobrado(p), Decimal('5000.00'))

    def test_cancelar_devolviendo_registra_devolucion(self):
        p = _pedido()
        services.registrar_movimiento(p, 5000, 'efectivo', Movimiento.Tipo.SENIA)
        cambiar_estado_pedido(p, Pedido.CANCELADO, accion='devolver', medio='transferencia')
        self.assertEqual(services.cobrado(p), 0)
        self.assertTrue(p.movimientos.filter(
            tipo='devolucion', medio='transferencia', monto=Decimal('-5000')).exists())


@STATIC
class VistasPedidosCobrosTests(TestCase):

    def setUp(self):
        _usuario('v', 'Ventas')
        self.client.login(username='v', password='pw')

    def test_registrar_pago_formato_ar(self):
        """Regresión: "15.000" se guardaba como 15 (float con replace)."""
        p = _pedido(precio=40000)
        self.client.post('/pedidos/registrarPago', {
            'pedido': p.numero, 'monto': '15.000', 'medio': 'efectivo',
            'fecha': '2026-10-01'})
        p.refresh_from_db()
        self.assertEqual(p.senia, 15000)
        mov = p.movimientos.get()
        self.assertEqual((mov.fecha, mov.tipo), (date(2026, 10, 1), 'senia'))

    def test_pago_que_completa_pasa_a_pagado(self):
        p = _pedido(precio=1000, estado='Terminado (falta pago)')
        self.client.post('/pedidos/registrarPago', {
            'pedido': p.numero, 'monto': '1.000,00', 'medio': 'tarjeta'})
        p.refresh_from_db()
        self.assertEqual(p.estado, Pedido.PAGADO)
        self.assertEqual(p.movimientos.get().tipo, 'pago')

    def test_no_se_registran_pagos_en_cancelados(self):
        p = _pedido(estado=Pedido.CANCELADO, bloqueado_cancelado=True)
        self.client.post('/pedidos/registrarPago', {
            'pedido': p.numero, 'monto': '100', 'medio': 'efectivo'})
        self.assertFalse(p.movimientos.exists())

    def test_cambiar_estado_cancelado_desde_el_form(self):
        p = _pedido()
        self.client.post('/pedidos/cambiarEstado', {
            'cambiarPedido_estado': p.numero, 'estado': 'Cancelado',
            'cobro_accion': 'retener'})
        p.refresh_from_db()
        self.assertTrue(p.bloqueado_cancelado)

    def test_bulk_pagado_registra_saldos(self):
        p1 = _pedido(1, precio=1000, estado='Terminado (falta pago)')
        p2 = _pedido(2, precio=2000, estado='Terminado (falta pago)')
        self.client.post('/pedidos/cambiarEstadoBulk', json.dumps({
            'ids': [1, 2], 'estado': Pedido.PAGADO,
            'cobro_accion': 'registrar', 'cobro_medio': 'efectivo'}),
            content_type='application/json')
        for p in (p1, p2):
            p.refresh_from_db()
            self.assertEqual((p.estado, p.saldo), (Pedido.PAGADO, 0))

    def test_bulk_salta_cancelados(self):
        _pedido(1, estado=Pedido.CANCELADO, bloqueado_cancelado=True)
        self.client.post('/pedidos/cambiarEstadoBulk', json.dumps({
            'ids': [1], 'estado': 'En proceso'}), content_type='application/json')
        self.assertEqual(Pedido.objects.get(numero=1).estado, Pedido.CANCELADO)


@STATIC
class VistaCajaTests(TestCase):

    def setUp(self):
        p = _pedido()
        services.registrar_movimiento(p, 3000, 'efectivo', Movimiento.Tipo.SENIA,
                                      fecha=date(2026, 9, 10))
        services.registrar_movimiento(p, 2000, 'transferencia', Movimiento.Tipo.PAGO,
                                      fecha=date(2026, 9, 12))
        self.pedido = p

    def _login(self, grupo):
        _usuario(grupo.lower(), grupo)
        self.client.login(username=grupo.lower(), password='pw')

    def test_totales_por_medio(self):
        self._login('Administración')
        resp = self.client.get('/caja/?desde=2026-09-01&hasta=2026-09-30')
        self.assertEqual(resp.status_code, 200)
        totales = {t['medio']: t['neto'] for t in resp.context['totales']}
        self.assertEqual(totales['efectivo'], Decimal('3000'))
        self.assertEqual(totales['transferencia'], Decimal('2000'))
        self.assertNotIn('sin_especificar', totales)
        self.assertEqual(resp.context['total_neto'], Decimal('5000'))

    def test_ventas_no_accede(self):
        self._login('Ventas')
        self.assertEqual(self.client.get('/caja/').status_code, 302)

    def test_exportar_solo_gerencia(self):
        self._login('Administración')
        self.assertEqual(self.client.get('/caja/exportar').status_code, 302)
        self.assertNotContains(self.client.get('/caja/'), '/caja/exportar')
        self.client.logout()
        self._login('Gerencia')
        resp = self.client.get('/caja/exportar?desde=2026-09-01&hasta=2026-09-30')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])

    def test_eliminar_movimiento_recalcula(self):
        self._login('Gerencia')
        mov = self.pedido.movimientos.get(medio='transferencia')
        self.client.post(f'/caja/eliminar/{mov.id}')
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.senia, 3000)
        self.assertEqual(self.pedido.saldo, 7000)


class MigracionCobrosHistoricosTests(TestCase):

    def test_carga_senias_y_saldos_de_pagados(self):
        Pedido.objects.create(numero=1, descripcion='x', precio=1000, senia=400,
                              saldo=600, estado='En proceso')
        Pedido.objects.create(numero=2, descripcion='x', precio=2000, senia=500,
                              saldo=1500, estado=Pedido.PAGADO)
        Pedido.objects.create(numero=3, descripcion='x', precio=300, senia=0,
                              saldo=300, estado='No iniciado')
        mig = importlib.import_module('caja.migrations.0002_cobros_historicos')
        mig.cargar(django_apps, None)

        p1, p2, p3 = (Pedido.objects.get(numero=n) for n in (1, 2, 3))
        self.assertEqual((p1.senia, p1.saldo), (400, 600))
        self.assertEqual((p2.senia, p2.saldo), (2000, 0))
        self.assertEqual(list(p2.movimientos.order_by('id').values_list('tipo', 'monto')),
                         [('senia', Decimal('500.00')), ('pago', Decimal('1500.00'))])
        self.assertFalse(p3.movimientos.exists())
        self.assertFalse(Movimiento.objects.exclude(medio='sin_especificar').exists())
