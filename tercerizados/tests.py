"""Tests de pedidos tercerizados: imputación de pagos, permisos y API."""

import json
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.roles import ADMINISTRACION, GERENCIA, VENTAS
from productos.models import Proveedor

from . import services
from .models import (
    PagoTercerizado, PedidoTercerizado, RegistroAuditoria, TokenAgente,
)

CERO = Decimal('0.00')

# Igual que en caja/tests.py: en tests no hay manifest de staticfiles, así que
# las vistas que renderizan templates necesitan el storage simple.
STATIC = override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})


def D(valor):
    return Decimal(str(valor))


class BaseTercerizados(TestCase):
    def setUp(self):
        for nombre in (GERENCIA, ADMINISTRACION, VENTAS):
            Group.objects.get_or_create(name=nombre)
        self.gerencia = User.objects.create_user('gerente', password='x')
        self.gerencia.groups.add(Group.objects.get(name=GERENCIA))
        self.proveedor = Proveedor.objects.create(nombre='Lonas del Sur')
        self.otro = Proveedor.objects.create(nombre='Imprenta Vecina')

    def crear(self, monto, proveedor=None, **extra):
        pedido, _ = services.crear_pedido(
            proveedor=proveedor or self.proveedor,
            descripcion=extra.pop('descripcion', 'Trabajo de prueba'),
            monto=monto,
            **extra)
        return pedido


class SaldosEImputacionTests(BaseTercerizados):
    def test_pedido_nuevo_debe_todo(self):
        pedido = self.crear(100000)
        self.assertEqual(pedido.monto_pagado, CERO)
        self.assertEqual(pedido.saldo, D('100000'))
        self.assertEqual(pedido.estado_pago, 'pendiente')
        self.assertFalse(pedido.pagado)

    def test_pago_parcial_deja_saldo(self):
        pedido = self.crear(100000)
        services.registrar_pago(
            proveedor=self.proveedor, monto=40000,
            imputaciones=[(pedido, 40000)])
        pedido.refresh_from_db()
        self.assertEqual(pedido.monto_pagado, D('40000.00'))
        self.assertEqual(pedido.saldo, D('60000.00'))
        self.assertEqual(pedido.estado_pago, 'parcial')

    def test_pago_total_cierra_el_pedido(self):
        pedido = self.crear(100000)
        services.registrar_pago(
            proveedor=self.proveedor, monto=100000,
            imputaciones=[(pedido, 100000)])
        pedido.refresh_from_db()
        self.assertEqual(pedido.saldo, CERO)
        self.assertEqual(pedido.estado_pago, 'pagado')
        self.assertTrue(pedido.pagado)

    def test_un_pago_cubre_varios_pedidos(self):
        """El caso del enunciado: el proveedor cobra el período completo."""
        a = self.crear(45000)
        b = self.crear(120000)
        c = self.crear(69500)
        services.registrar_pago(
            proveedor=self.proveedor, monto=95000,
            imputaciones=[(a, 45000), (b, 50000)])
        for p in (a, b, c):
            p.refresh_from_db()
        self.assertEqual(a.estado_pago, 'pagado')
        self.assertEqual(b.saldo, D('70000.00'))
        self.assertEqual(c.saldo, D('69500.00'))
        deuda = services.resumen_deuda(self.proveedor)[0]
        self.assertEqual(deuda['deuda'], D('139500.00'))

    def test_no_se_puede_imputar_mas_que_el_saldo(self):
        pedido = self.crear(50000)
        with self.assertRaises(services.ErrorTercerizado):
            services.registrar_pago(
                proveedor=self.proveedor, monto=60000,
                imputaciones=[(pedido, 60000)])
        pedido.refresh_from_db()
        self.assertEqual(pedido.monto_pagado, CERO)

    def test_no_se_puede_imputar_mas_que_el_pago(self):
        a = self.crear(50000)
        b = self.crear(50000)
        with self.assertRaises(services.ErrorTercerizado):
            services.registrar_pago(
                proveedor=self.proveedor, monto=60000,
                imputaciones=[(a, 50000), (b, 50000)])
        self.assertFalse(PagoTercerizado.objects.exists())

    def test_no_se_puede_imputar_a_pedido_de_otro_proveedor(self):
        ajeno = self.crear(50000, proveedor=self.otro)
        with self.assertRaises(services.ErrorTercerizado):
            services.registrar_pago(
                proveedor=self.proveedor, monto=50000,
                imputaciones=[(ajeno, 50000)])

    def test_reparto_automatico_va_del_mas_viejo_al_mas_nuevo(self):
        viejo = self.crear(30000, fecha=__import__('datetime').date(2026, 1, 10))
        nuevo = self.crear(30000, fecha=__import__('datetime').date(2026, 3, 10))
        services.registrar_pago(
            proveedor=self.proveedor, monto=40000, automatico=True)
        viejo.refresh_from_db()
        nuevo.refresh_from_db()
        self.assertEqual(viejo.monto_pagado, D('30000.00'))
        self.assertEqual(nuevo.monto_pagado, D('10000.00'))

    def test_lo_no_imputado_queda_a_cuenta(self):
        pedido = self.crear(10000)
        pago = services.registrar_pago(
            proveedor=self.proveedor, monto=25000,
            imputaciones=[(pedido, 10000)])
        self.assertEqual(pago.sin_imputar, D('15000.00'))
        deuda = services.resumen_deuda(self.proveedor)[0]
        self.assertEqual(deuda['deuda'], CERO)
        self.assertEqual(deuda['a_cuenta'], D('15000.00'))
        self.assertEqual(deuda['deuda_neta'], D('-15000.00'))

    def test_pago_repartido_no_deja_plata_a_cuenta_fantasma(self):
        """Regresión: sumar el pago y sus imputaciones en una sola consulta
        hacía un JOIN que repetía el monto del pago una vez por imputación, y
        aparecía plata "a cuenta" que no existía."""
        a = self.crear(48500)
        b = self.crear(72000)
        services.registrar_pago(
            proveedor=self.proveedor, monto=95000,
            imputaciones=[(a, 48500), (b, 46500)])
        deuda = services.resumen_deuda(self.proveedor)[0]
        self.assertEqual(deuda['a_cuenta'], CERO)
        self.assertEqual(deuda['pagado'], D('95000.00'))
        self.assertEqual(deuda['deuda'], D('25500.00'))
        self.assertEqual(deuda['deuda_neta'], D('25500.00'))

    def test_varios_pagos_a_un_proveedor_suman_una_vez(self):
        pedido = self.crear(100000)
        services.registrar_pago(
            proveedor=self.proveedor, monto=30000,
            imputaciones=[(pedido, 30000)])
        services.registrar_pago(
            proveedor=self.proveedor, monto=20000,
            imputaciones=[(pedido, 20000)])
        deuda = services.resumen_deuda(self.proveedor)[0]
        self.assertEqual(deuda['pagado'], D('50000.00'))
        self.assertEqual(deuda['deuda'], D('50000.00'))
        self.assertEqual(deuda['a_cuenta'], CERO)

    def test_anular_pago_devuelve_el_saldo(self):
        pedido = self.crear(80000)
        pago = services.registrar_pago(
            proveedor=self.proveedor, monto=80000,
            imputaciones=[(pedido, 80000)])
        services.anular_pago(pago)
        pedido.refresh_from_db()
        self.assertEqual(pedido.monto_pagado, CERO)
        self.assertEqual(pedido.saldo, D('80000.00'))
        self.assertFalse(PagoTercerizado.objects.filter(pk=pago.pk).exists())

    def test_pedido_cancelado_no_suma_deuda(self):
        pedido = self.crear(70000)
        services.editar_pedido(
            pedido, estado=PedidoTercerizado.Estado.CANCELADO)
        pedido.refresh_from_db()
        self.assertEqual(pedido.saldo, CERO)
        self.assertEqual(services.resumen_deuda(self.proveedor), [])

    def test_no_se_cancela_un_pedido_con_pagos(self):
        pedido = self.crear(70000)
        services.registrar_pago(
            proveedor=self.proveedor, monto=10000,
            imputaciones=[(pedido, 10000)])
        pedido.refresh_from_db()
        with self.assertRaises(services.ErrorTercerizado):
            services.editar_pedido(
                pedido, estado=PedidoTercerizado.Estado.CANCELADO)

    def test_el_monto_no_puede_bajar_de_lo_pagado(self):
        pedido = self.crear(70000)
        services.registrar_pago(
            proveedor=self.proveedor, monto=50000,
            imputaciones=[(pedido, 50000)])
        pedido.refresh_from_db()
        with self.assertRaises(services.ErrorTercerizado):
            services.editar_pedido(pedido, monto=30000)
        services.editar_pedido(pedido, monto=60000)
        pedido.refresh_from_db()
        self.assertEqual(pedido.saldo, D('10000.00'))

    def test_no_se_borra_un_pedido_con_pagos_imputados(self):
        pedido = self.crear(70000)
        services.registrar_pago(
            proveedor=self.proveedor, monto=10000,
            imputaciones=[(pedido, 10000)])
        pedido.refresh_from_db()
        with self.assertRaises(services.ErrorTercerizado):
            services.borrar_pedido(pedido)
        self.assertTrue(PedidoTercerizado.objects.filter(pk=pedido.pk).exists())


class AuditoriaTests(BaseTercerizados):
    def test_cada_escritura_deja_rastro(self):
        pedido = self.crear(50000)
        services.editar_pedido(pedido, monto=55000)
        pago = services.registrar_pago(
            proveedor=self.proveedor, monto=55000,
            imputaciones=[(pedido, 55000)])
        services.anular_pago(pago)
        acciones = list(
            RegistroAuditoria.objects.values_list('accion', flat=True))
        self.assertIn('crear', acciones)
        self.assertIn('editar', acciones)
        self.assertIn('pagar', acciones)
        self.assertIn('anular_pago', acciones)

    def test_el_log_es_inmutable(self):
        self.crear(1000)
        registro = RegistroAuditoria.objects.first()
        registro.resumen = 'otra cosa'
        with self.assertRaises(ValueError):
            registro.save()
        with self.assertRaises(ValueError):
            registro.delete()
        registro.refresh_from_db()
        self.assertNotEqual(registro.resumen, 'otra cosa')

    def test_la_edicion_guarda_que_cambio(self):
        pedido = self.crear(50000)
        services.editar_pedido(pedido, monto=80000)
        registro = RegistroAuditoria.objects.filter(accion='editar').first()
        self.assertIn('monto', registro.detalle['cambios'])
        self.assertEqual(
            registro.detalle['cambios']['monto'], ['50000.00', '80000.00'])


@STATIC
class PermisosTests(BaseTercerizados):
    def test_gerencia_entra(self):
        self.client.force_login(self.gerencia)
        respuesta = self.client.get(reverse('control_tercerizados'))
        self.assertEqual(respuesta.status_code, 200)

    def test_administracion_no_entra(self):
        """La sección es solo de Gerencia: Administración no la ve."""
        admin = User.objects.create_user('admin', password='x')
        admin.groups.add(Group.objects.get(name=ADMINISTRACION))
        self.client.force_login(admin)
        respuesta = self.client.get(reverse('control_tercerizados'))
        self.assertEqual(respuesta.status_code, 302)

    def test_ventas_no_entra(self):
        vendedor = User.objects.create_user('vendedor', password='x')
        vendedor.groups.add(Group.objects.get(name=VENTAS))
        self.client.force_login(vendedor)
        respuesta = self.client.get(reverse('control_tercerizados'))
        self.assertEqual(respuesta.status_code, 302)

    def test_anonimo_va_al_login(self):
        respuesta = self.client.get(reverse('control_tercerizados'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('next=/tercerizados/', respuesta.url)

    def test_navbar_no_muestra_la_seccion_a_administracion(self):
        admin = User.objects.create_user('admin2', password='x')
        admin.groups.add(Group.objects.get(name=ADMINISTRACION))
        self.client.force_login(admin)
        respuesta = self.client.get('/caja/')
        self.assertNotContains(respuesta, 'nav_item_tercerizados')

    def test_navbar_muestra_la_seccion_a_gerencia(self):
        self.client.force_login(self.gerencia)
        respuesta = self.client.get(reverse('control_tercerizados'))
        self.assertContains(respuesta, 'nav_item_tercerizados')


@STATIC
class VistasUITests(BaseTercerizados):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.gerencia)

    def test_alta_desde_el_modal_con_monto_en_formato_ar(self):
        respuesta = self.client.post(reverse('guardar_tercerizado'), {
            'pedidoId': '0',
            'fecha': '2026-11-08',
            'proveedor': self.proveedor.pk,
            'descripcion': '200 lonas 3x2',
            'monto': '145.000,50',
            'forma_pago': 'cuenta_corriente',
            'estado': 'pendiente',
        })
        self.assertEqual(respuesta.status_code, 302)
        pedido = PedidoTercerizado.objects.get()
        # Formato argentino: el punto es separador de miles.
        self.assertEqual(pedido.monto, D('145000.50'))
        self.assertEqual(pedido.origen, 'manual')
        self.assertTrue(pedido.revisado)

    def test_pago_desde_el_modal_imputa_a_los_pedidos_marcados(self):
        a = self.crear(45000)
        b = self.crear(120000)
        respuesta = self.client.post(reverse('registrar_pago_tercerizado'), {
            'proveedor': self.proveedor.pk,
            'fecha': '2026-11-08',
            'monto': '95.000,00',
            'medio': 'transferencia',
            f'imputacion_{a.pk}': '45.000,00',
            f'imputacion_{b.pk}': '50.000,00',
        })
        self.assertEqual(respuesta.status_code, 302)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.saldo, CERO)
        self.assertEqual(b.saldo, D('70000.00'))

    def test_pendientes_proveedor_devuelve_los_que_deben(self):
        con_saldo = self.crear(45000)
        pagado = self.crear(20000)
        services.registrar_pago(
            proveedor=self.proveedor, monto=20000,
            imputaciones=[(pagado, 20000)])
        respuesta = self.client.get(
            reverse('pendientes_proveedor', args=[self.proveedor.pk]))
        datos = respuesta.json()
        self.assertEqual([p['id'] for p in datos['pedidos']], [con_saldo.pk])
        self.assertEqual(datos['deuda'], 45000.0)

    def test_marcar_revisados(self):
        pedido = self.crear(
            1000, origen=PedidoTercerizado.Origen.AGENTE)
        self.assertFalse(pedido.revisado)
        self.client.post(reverse('marcar_revisados'),
                         {'ids': [pedido.pk], 'revisado': '1'})
        pedido.refresh_from_db()
        self.assertTrue(pedido.revisado)

    def test_exportar_devuelve_un_excel(self):
        self.crear(1000)
        respuesta = self.client.get(reverse('exportar_tercerizados'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('spreadsheet', respuesta['Content-Type'])

    def test_borrar_pedido_sin_pagos(self):
        pedido = self.crear(1000)
        self.client.post(reverse('borrar_tercerizado', args=[pedido.pk]))
        self.assertFalse(PedidoTercerizado.objects.filter(pk=pedido.pk).exists())

    def test_borrar_no_acepta_get(self):
        pedido = self.crear(1000)
        respuesta = self.client.get(
            reverse('borrar_tercerizado', args=[pedido.pk]))
        self.assertEqual(respuesta.status_code, 405)
        self.assertTrue(PedidoTercerizado.objects.filter(pk=pedido.pk).exists())


@STATIC
class ApiAgenteTests(BaseTercerizados):
    def setUp(self):
        super().setUp()
        self.token_obj, self.token = TokenAgente.generar(
            'agente-correo', creado_por=self.gerencia)

    def cabeceras(self, token=None):
        return {'HTTP_AUTHORIZATION': f'Bearer {token or self.token}'}

    def post_json(self, url, cuerpo, token=None, metodo='post'):
        return getattr(self.client, metodo)(
            url, data=json.dumps(cuerpo), content_type='application/json',
            **self.cabeceras(token))

    # --- Autenticación y alcance ---

    def test_sin_token_rechaza(self):
        respuesta = self.client.get('/api/tercerizados/ping')
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json()['codigo'], 'sin_token')

    def test_token_invalido_rechaza(self):
        respuesta = self.client.get(
            '/api/tercerizados/ping', **self.cabeceras('no-es-un-token'))
        self.assertEqual(respuesta.status_code, 401)

    def test_token_desactivado_rechaza(self):
        self.token_obj.activo = False
        self.token_obj.save()
        respuesta = self.client.get('/api/tercerizados/ping', **self.cabeceras())
        self.assertEqual(respuesta.status_code, 403)

    def test_ping_informa_permisos_y_registra_uso(self):
        respuesta = self.client.get('/api/tercerizados/ping', **self.cabeceras())
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()['datos']
        self.assertTrue(datos['permisos']['crear'])
        # Pagar viene apagado por defecto.
        self.assertFalse(datos['permisos']['pagar'])
        self.token_obj.refresh_from_db()
        self.assertIsNotNone(self.token_obj.ultimo_uso)

    def test_el_token_no_sirve_para_el_resto_del_cotizador(self):
        """El alcance del token es solo la API de tercerizados."""
        for url in ('/tercerizados/', '/caja/', '/pedidos/v2',
                    '/productos/insumos', '/presupuestos', '/clientes',
                    '/dashboard', '/usuarios'):
            respuesta = self.client.get(url, follow=True, **self.cabeceras())
            # Termina en el login: el token no vale como sesión en ninguna
            # vista del cotizador.
            self.assertTrue(
                respuesta.redirect_chain,
                f'{url} no debería contestar con un token de agente')
            self.assertIn(
                'next=', respuesta.redirect_chain[-1][0],
                f'{url} debería mandar al login con un token de agente')

    def test_el_token_no_puede_tocar_la_auditoria(self):
        self.crear(1000)
        respuesta = self.client.get(
            '/tercerizados/auditoria', **self.cabeceras())
        self.assertEqual(respuesta.status_code, 302)

    # --- Alta ---

    def test_crear_pedido(self):
        respuesta = self.post_json('/api/tercerizados/pedidos', {
            'proveedor': 'Lonas del Sur',
            'descripcion': '200 lonas 3x2 con ojalillos',
            'monto': 145000.50,
            'fecha': '2026-11-08',
            'forma_pago': 'cuenta_corriente',
            'referencia_externa': '<CAF123@mail.gmail.com>',
        })
        self.assertEqual(respuesta.status_code, 201)
        pedido = PedidoTercerizado.objects.get()
        self.assertEqual(pedido.monto, D('145000.50'))
        self.assertEqual(pedido.origen, 'agente')
        # Lo que carga el agente queda para que gerencia lo valide.
        self.assertFalse(pedido.revisado)
        self.assertEqual(pedido.creado_por_token, self.token_obj)

    def test_alta_es_idempotente_por_referencia_externa(self):
        cuerpo = {
            'proveedor': self.proveedor.pk,
            'descripcion': 'Lonas',
            'monto': 1000,
            'referencia_externa': '<mismo-correo@gmail.com>',
        }
        primera = self.post_json('/api/tercerizados/pedidos', cuerpo)
        segunda = self.post_json('/api/tercerizados/pedidos', cuerpo)
        self.assertEqual(primera.status_code, 201)
        self.assertEqual(segunda.status_code, 200)
        self.assertTrue(segunda.json()['duplicado'])
        self.assertEqual(PedidoTercerizado.objects.count(), 1)

    def test_proveedor_inexistente_devuelve_los_cargados(self):
        respuesta = self.post_json('/api/tercerizados/pedidos', {
            'proveedor': 'Proveedor Que No Existe',
            'descripcion': 'Algo', 'monto': 1000,
        })
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('Lonas del Sur', respuesta.json()['error'])

    def test_monto_en_formato_argentino(self):
        respuesta = self.post_json('/api/tercerizados/pedidos', {
            'proveedor': self.proveedor.pk, 'descripcion': 'Lonas',
            'monto': '145.000,50',
        })
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(PedidoTercerizado.objects.get().monto, D('145000.50'))

    def test_monto_decimal_plano_no_se_lee_como_miles(self):
        """Un string "45000.50" es decimal, no 4500050."""
        respuesta = self.post_json('/api/tercerizados/pedidos', {
            'proveedor': self.proveedor.pk, 'descripcion': 'Lonas',
            'monto': '45000.50',
        })
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(PedidoTercerizado.objects.get().monto, D('45000.50'))

    def test_monto_basura_da_error_claro(self):
        respuesta = self.post_json('/api/tercerizados/pedidos', {
            'proveedor': self.proveedor.pk, 'descripcion': 'Lonas',
            'monto': 'como cien mil',
        })
        self.assertEqual(respuesta.status_code, 400)

    def test_fecha_mal_formada_da_error_claro(self):
        respuesta = self.post_json('/api/tercerizados/pedidos', {
            'proveedor': self.proveedor.pk, 'descripcion': 'Lonas',
            'monto': 1000, 'fecha': '08/11/2026',
        })
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('YYYY-MM-DD', respuesta.json()['error'])

    def test_estado_invalido_lista_los_validos(self):
        respuesta = self.post_json('/api/tercerizados/pedidos', {
            'proveedor': self.proveedor.pk, 'descripcion': 'Lonas',
            'monto': 1000, 'estado': 'entregadisimo',
        })
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('pendiente', respuesta.json()['error'])

    # --- Lectura / edición / borrado ---

    def test_listar_y_filtrar(self):
        self.crear(1000, descripcion='Lonas grandes')
        self.crear(2000, proveedor=self.otro, descripcion='Folletos')
        respuesta = self.client.get(
            '/api/tercerizados/pedidos?proveedor=Lonas del Sur',
            **self.cabeceras())
        datos = respuesta.json()
        self.assertEqual(datos['cantidad'], 1)
        self.assertEqual(datos['datos'][0]['descripcion'], 'Lonas grandes')

    def test_editar_pedido(self):
        pedido = self.crear(1000)
        respuesta = self.post_json(
            f'/api/tercerizados/pedidos/{pedido.pk}',
            {'monto': 1500, 'estado': 'recibido'}, metodo='patch')
        self.assertEqual(respuesta.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.monto, D('1500.00'))
        self.assertEqual(pedido.estado, 'recibido')

    def test_cancelar_un_trabajo_por_api(self):
        """Los trabajos se cancelan: el agente lo refleja con PATCH."""
        pedido = self.crear(1000)
        self.post_json(f'/api/tercerizados/pedidos/{pedido.pk}',
                       {'estado': 'cancelado'}, metodo='patch')
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'cancelado')
        self.assertEqual(pedido.saldo, CERO)

    def test_editar_campo_no_permitido(self):
        pedido = self.crear(1000, origen=PedidoTercerizado.Origen.AGENTE)
        respuesta = self.post_json(
            f'/api/tercerizados/pedidos/{pedido.pk}',
            {'revisado': True}, metodo='patch')
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()['codigo'], 'campo_no_editable')
        pedido.refresh_from_db()
        self.assertFalse(pedido.revisado)

    def test_borrar_pedido(self):
        pedido = self.crear(1000)
        respuesta = self.client.delete(
            f'/api/tercerizados/pedidos/{pedido.pk}', **self.cabeceras())
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(PedidoTercerizado.objects.exists())

    def test_pedido_inexistente_da_404(self):
        respuesta = self.client.get(
            '/api/tercerizados/pedidos/9999', **self.cabeceras())
        self.assertEqual(respuesta.status_code, 404)

    def test_deuda(self):
        pedido = self.crear(100000)
        services.registrar_pago(
            proveedor=self.proveedor, monto=30000,
            imputaciones=[(pedido, 30000)])
        respuesta = self.client.get(
            '/api/tercerizados/deuda', **self.cabeceras())
        fila = respuesta.json()['datos'][0]
        self.assertEqual(fila['proveedor'], 'Lonas del Sur')
        self.assertEqual(fila['deuda'], '70000.00')

    # --- Permisos por token ---

    def test_token_sin_permiso_de_pagar_no_registra_pagos(self):
        pedido = self.crear(1000)
        respuesta = self.post_json('/api/tercerizados/pagos', {
            'proveedor': self.proveedor.pk, 'monto': 1000,
            'imputaciones': [{'pedido': pedido.pk, 'monto': 1000}],
        })
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()['codigo'], 'sin_permiso')
        self.assertFalse(PagoTercerizado.objects.exists())

    def test_token_con_permiso_de_pagar_registra(self):
        self.token_obj.permite_pagar = True
        self.token_obj.save()
        pedido = self.crear(1000)
        respuesta = self.post_json('/api/tercerizados/pagos', {
            'proveedor': self.proveedor.pk, 'monto': 1000,
            'imputaciones': [{'pedido': pedido.pk, 'monto': 1000}],
        })
        self.assertEqual(respuesta.status_code, 201)
        pedido.refresh_from_db()
        self.assertEqual(pedido.saldo, CERO)

    def test_token_solo_lectura_no_crea(self):
        solo_lectura, clave = TokenAgente.generar(
            'solo-lectura', permite_crear=False, permite_editar=False,
            permite_borrar=False)
        respuesta = self.post_json('/api/tercerizados/pedidos', {
            'proveedor': self.proveedor.pk, 'descripcion': 'x', 'monto': 1,
        }, token=clave)
        self.assertEqual(respuesta.status_code, 403)
        # Pero leer sí puede.
        respuesta = self.client.get(
            '/api/tercerizados/pedidos', **self.cabeceras(clave))
        self.assertEqual(respuesta.status_code, 200)

    def test_metodo_no_permitido(self):
        respuesta = self.client.delete(
            '/api/tercerizados/deuda', **self.cabeceras())
        self.assertEqual(respuesta.status_code, 405)

    # --- Auditoría de lo que hace el agente ---

    def test_lo_que_hace_el_agente_queda_firmado(self):
        self.post_json('/api/tercerizados/pedidos', {
            'proveedor': self.proveedor.pk, 'descripcion': 'Lonas',
            'monto': 1000,
        })
        registro = RegistroAuditoria.objects.get(accion='crear', objeto='pedido')
        self.assertEqual(registro.actor_tipo, 'agente')
        self.assertEqual(registro.actor, 'agente-correo')
        self.assertEqual(registro.token, self.token_obj)

    def test_el_esquema_se_describe_solo(self):
        respuesta = self.client.get(
            '/api/tercerizados/esquema', **self.cabeceras())
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()['datos']
        self.assertIn('endpoints', datos)
        self.assertTrue(any(e['ruta'].endswith('/pedidos')
                            for e in datos['endpoints']))


@STATIC
class TokensUITests(BaseTercerizados):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.gerencia)

    def test_crear_token_lo_muestra_una_sola_vez(self):
        self.client.post(reverse('crear_token_agente'), {
            'nombre': 'agente-correo', 'permite_crear': 'on'})
        # Primera carga: se ve el token en claro.
        primera = self.client.get(reverse('tercerizados_tokens'))
        self.assertContains(primera, 'no se vuelve a mostrar')
        # Segunda carga: ya no está.
        segunda = self.client.get(reverse('tercerizados_tokens'))
        self.assertNotContains(segunda, 'no se vuelve a mostrar')

    def test_el_token_en_claro_no_se_guarda(self):
        self.client.post(reverse('crear_token_agente'), {'nombre': 'ag'})
        token = TokenAgente.objects.get()
        self.assertEqual(len(token.token_hash), 64)
        self.assertEqual(len(token.prefijo), 8)

    def test_desactivar_token(self):
        token, _ = TokenAgente.generar('ag')
        self.client.post(reverse('alternar_token_agente', args=[token.pk]))
        token.refresh_from_db()
        self.assertFalse(token.activo)

    def test_ventas_no_puede_crear_tokens(self):
        vendedor = User.objects.create_user('v', password='x')
        vendedor.groups.add(Group.objects.get(name=VENTAS))
        self.client.force_login(vendedor)
        respuesta = self.client.post(
            reverse('crear_token_agente'), {'nombre': 'mio'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(TokenAgente.objects.exists())
