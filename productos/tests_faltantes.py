import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from pedidos.models import Pedido
from presupuestos.models import Presupuesto

from .models import (ComponenteProducto, FaltanteInsumo, Insumo, Producto,
                     ProductoCotizado, Proveedor)
from .stock import (aplicar_cambio_estado, aplicar_ingreso, descontar_producto,
                    reemplazar_stock, reponer_pedido)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class BaseStock(TestCase):
    """Papel: 1 resma = 500 hojas. Un 'Flyer' usa 1 hoja por unidad."""

    def setUp(self):
        self.papel = Insumo.objects.create(
            nombre="Papel obra", unidad_medida="resma", unidad_composicion="hoja",
            factor_conversion=500, precio=Decimal("10000"), stock=0)
        self.flyer = Producto.objects.create(nombre="Flyer", tercerizado=False)
        ComponenteProducto.objects.create(
            producto=self.flyer, insumo=self.papel, cantidad=1)

    def crear_pedido(self, numero, hojas, fecha=None, estado='No iniciado'):
        """Crea pedido + presupuesto y descuenta el stock como confirmar_pedido."""
        Presupuesto.objects.create(numero=numero)
        ProductoCotizado.objects.create(
            insumo=self.flyer, presupuesto_id=numero, cantidad=hojas)
        pedido = Pedido.objects.create(
            numero=numero, descripcion='', precio=0, estado=estado,
            presupuesto=numero, fecha_entrega=fecha)
        descontar_producto(self.flyer, hojas, pedido=pedido)
        return pedido

    def stock_hojas(self):
        self.papel.refresh_from_db()
        return round(self.papel.stock_real(), 6)

    def abierto(self, pedido):
        return sum(f.cantidad_faltante for f in
                   FaltanteInsumo.objects.filter(pedido=pedido, resuelto=False))

    def cambiar_estado(self, pedido, estado):
        anterior = pedido.estado
        pedido.estado = estado
        pedido.save()
        return aplicar_cambio_estado(pedido, anterior)


# ---------------------------------------------------------------------------
# Tests: cierre y reapertura de faltantes por estado del pedido
# ---------------------------------------------------------------------------

class EstadoPedidoFaltantesTest(BaseStock):

    def test_terminar_pedido_cierra_sus_faltantes(self):
        pedido = self.crear_pedido(1, 100)
        self.assertEqual(self.abierto(pedido), 100)
        self.cambiar_estado(pedido, 'Terminado (falta pago)')
        self.assertEqual(self.abierto(pedido), 0)
        f = FaltanteInsumo.objects.get(pedido=pedido)
        self.assertEqual(f.motivo_cierre, FaltanteInsumo.MOTIVO_PEDIDO)

    def test_pasar_entre_estados_finales_no_reabre(self):
        pedido = self.crear_pedido(1, 100)
        self.cambiar_estado(pedido, 'Terminado (falta pago)')
        aviso = self.cambiar_estado(pedido, 'Terminado y pagado')
        self.assertIsNone(aviso)
        self.assertEqual(self.abierto(pedido), 0)

    def test_reabrir_pedido_reactiva_faltantes_y_avisa(self):
        pedido = self.crear_pedido(1, 100)
        self.cambiar_estado(pedido, 'Terminado y pagado')
        aviso = self.cambiar_estado(pedido, 'En proceso')
        self.assertEqual(self.abierto(pedido), 100)
        self.assertIn('reactivaron', aviso)

    def test_reabrir_no_reactiva_lo_cubierto_con_stock(self):
        pedido = self.crear_pedido(1, 100)
        aplicar_ingreso(self.papel, 100)          # llegó el material
        self.cambiar_estado(pedido, 'Terminado y pagado')
        aviso = self.cambiar_estado(pedido, 'En proceso')
        self.assertIsNone(aviso)
        self.assertEqual(self.abierto(pedido), 0)

    def test_reabrir_usa_stock_disponible(self):
        pedido = self.crear_pedido(1, 100)
        self.cambiar_estado(pedido, 'Terminado y pagado')
        reemplazar_stock(self.papel, 60)          # se cargaron 60 hojas
        self.cambiar_estado(pedido, 'En proceso')
        self.assertAlmostEqual(self.abierto(pedido), 40)
        self.assertAlmostEqual(self.stock_hojas(), 0)

    def test_vista_cambiar_estado_cierra_y_reabre(self):
        user = User.objects.create_user(username="u", password="x")
        self.client.force_login(user)
        pedido = self.crear_pedido(1, 100)
        self.client.post('/pedidos/cambiarEstado', {
            'estado': 'Terminado y pagado', 'cambiarPedido_estado': 1})
        self.assertEqual(self.abierto(pedido), 0)
        self.client.post('/pedidos/cambiarEstado', {
            'estado': 'En proceso', 'cambiarPedido_estado': 1})
        self.assertEqual(self.abierto(pedido), 100)


# ---------------------------------------------------------------------------
# Tests: devolver stock al borrar un pedido
# ---------------------------------------------------------------------------

class ReponerPedidoTest(BaseStock):

    def test_pedido_sin_faltante_devuelve_todo(self):
        reemplazar_stock(self.papel, 100)
        a = self.crear_pedido(1, 50)
        self.assertAlmostEqual(self.stock_hojas(), 50)
        reponer_pedido(a)
        self.assertAlmostEqual(self.stock_hojas(), 100)

    def test_pedido_en_falta_solo_devuelve_lo_descontado(self):
        """Había 30, pedía 50: se descontaron 30 y faltan 20. Borrar devuelve 30."""
        reemplazar_stock(self.papel, 30)
        a = self.crear_pedido(1, 50)
        reponer_pedido(a)
        a.delete()
        self.assertAlmostEqual(self.stock_hojas(), 30)
        self.assertFalse(FaltanteInsumo.objects.exists())

    def test_no_cubre_faltantes_ajenos_con_material_inexistente(self):
        """Devolver las 50 hojas completas cubriría 30 hojas de D que no existen."""
        reemplazar_stock(self.papel, 20)
        a = self.crear_pedido(1, 50, fecha=date(2026, 12, 1))  # usa 20, faltan 30
        d = self.crear_pedido(2, 100, fecha=date(2026, 10, 1))  # faltan 100
        reponer_pedido(a)
        a.delete()
        # A devuelve solo las 20 hojas reales, que van a D (más urgente).
        self.assertAlmostEqual(self.abierto(d), 80)
        self.assertAlmostEqual(self.stock_hojas(), 0)

    def test_pedido_terminado_no_devuelve_material(self):
        reemplazar_stock(self.papel, 100)
        a = self.crear_pedido(1, 50)
        self.cambiar_estado(a, 'Terminado y pagado')
        reponer_pedido(a)
        self.assertAlmostEqual(self.stock_hojas(), 50)

    def test_vista_eliminar_pedido(self):
        user = User.objects.create_user(username="g", password="x")
        user.groups.add(Group.objects.get_or_create(name="Gerencia")[0])
        self.client.force_login(user)
        reemplazar_stock(self.papel, 30)
        self.crear_pedido(1, 50)
        self.client.get('/pedidos/eliminarPedido/1')
        self.assertFalse(Pedido.objects.filter(numero=1).exists())
        self.assertAlmostEqual(self.stock_hojas(), 30)


# ---------------------------------------------------------------------------
# Tests: ingreso de material (compra / edición / importación)
# ---------------------------------------------------------------------------

class IngresoMaterialTest(BaseStock):

    def test_ingreso_cubre_por_fecha_de_entrega(self):
        tarde = self.crear_pedido(1, 100, fecha=date(2026, 12, 1))
        pronto = self.crear_pedido(2, 100, fecha=date(2026, 10, 1))
        sin_fecha = self.crear_pedido(3, 100)
        aplicar_ingreso(self.papel, 150)
        self.assertEqual(self.abierto(pronto), 0)
        self.assertAlmostEqual(self.abierto(tarde), 50)
        self.assertAlmostEqual(self.abierto(sin_fecha), 100)
        self.assertAlmostEqual(self.stock_hojas(), 0)

    def test_priorizar_y_postergar_alteran_el_orden(self):
        a = self.crear_pedido(1, 100, fecha=date(2026, 10, 1))  # el más urgente
        b = self.crear_pedido(2, 100, fecha=date(2026, 10, 5))
        c = self.crear_pedido(3, 100, fecha=date(2026, 10, 9))
        # Se decide resolver A y C y postergar B.
        aplicar_ingreso(self.papel, 200, postergados=[2])
        self.assertEqual(self.abierto(a), 0)
        self.assertEqual(self.abierto(c), 0)
        self.assertAlmostEqual(self.abierto(b), 100)

    def test_postergado_se_cubre_si_sobra(self):
        a = self.crear_pedido(1, 100, fecha=date(2026, 10, 1))
        b = self.crear_pedido(2, 100, fecha=date(2026, 10, 5))
        aplicar_ingreso(self.papel, 250, postergados=[1], priorizados=[2])
        self.assertEqual(self.abierto(a), 0)
        self.assertEqual(self.abierto(b), 0)
        self.assertAlmostEqual(self.stock_hojas(), 50)

    def test_registrar_compra_respeta_prioridades(self):
        user = User.objects.create_user(username="u", password="x")
        self.client.force_login(user)
        a = self.crear_pedido(1, 500, fecha=date(2026, 10, 1))
        b = self.crear_pedido(2, 500, fecha=date(2026, 10, 5))
        self.client.post(
            '/productos/insumos/registrarCompra/',
            data=json.dumps({'items': [{'id': self.papel.id, 'unidades': 1}],
                             'priorizados': [2]}),
            content_type='application/json')
        self.assertEqual(self.abierto(b), 0)
        self.assertAlmostEqual(self.abierto(a), 500)

    def test_sobrante_va_a_stock(self):
        a = self.crear_pedido(1, 100)
        aplicar_ingreso(self.papel, 500)
        self.assertEqual(self.abierto(a), 0)
        self.assertAlmostEqual(self.stock_hojas(), 400)
        self.assertEqual(FaltanteInsumo.objects.get(pedido=a).motivo_cierre,
                         FaltanteInsumo.MOTIVO_STOCK)

    def test_registrar_compra_endpoint(self):
        user = User.objects.create_user(username="u", password="x")
        self.client.force_login(user)
        a = self.crear_pedido(1, 600)
        res = self.client.post(
            '/productos/insumos/registrarCompra/',
            data=json.dumps({'items': [{'id': self.papel.id, 'unidades': 2}]}),
            content_type='application/json')
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertIn('1', data['mensaje'])   # pedido destrabado
        self.assertEqual(self.abierto(a), 0)
        self.assertAlmostEqual(self.stock_hojas(), 400)

    def test_importar_stock_compensa_faltantes(self):
        import io
        import openpyxl
        user = User.objects.create_user(username="g", password="x")
        user.groups.add(Group.objects.get_or_create(name="Gerencia")[0])
        self.client.force_login(user)
        a = self.crear_pedido(1, 100)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['nombre', 'stock_real', 'proveedor'])
        ws.append(['Papel obra', 250, 'Distribuidora Sur'])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = 'insumos.xlsx'
        self.client.post('/productos/importarInsumos/', {'excel_file': buf})

        self.assertEqual(self.abierto(a), 0)
        self.assertAlmostEqual(self.stock_hojas(), 150)
        self.papel.refresh_from_db()
        self.assertEqual(self.papel.proveedor.nombre, 'Distribuidora Sur')


# ---------------------------------------------------------------------------
# Tests: vista de faltantes, lista de compra y proveedores
# ---------------------------------------------------------------------------

# Las páginas completas cargan estáticos: sin collectstatic no hay manifest.
@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class VistaFaltantesTest(BaseStock):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="g", password="x")
        self.user.groups.add(Group.objects.get_or_create(name="Gerencia")[0])
        self.client.force_login(self.user)

    def test_agrupa_faltantes_por_insumo(self):
        self.crear_pedido(1, 300, fecha=date(2026, 11, 1))
        self.crear_pedido(2, 400, fecha=date(2026, 10, 1))
        res = self.client.get('/productos/insumos/faltantes/')
        self.assertEqual(res.status_code, 200)
        datos = res.context['faltantes']
        self.assertEqual(len(datos), 1)
        self.assertAlmostEqual(datos[0]['faltante'], 700)
        # Orden de prioridad: primero el de entrega más cercana.
        self.assertEqual([p['numero'] for p in datos[0]['pedidos']], [2, 1])

    def test_alerta_resumida_en_stock(self):
        self.crear_pedido(1, 300)
        res = self.client.get('/productos/insumos/')
        self.assertContains(res, 'Ver faltantes')

    def test_lista_compra_excel(self):
        res = self.client.post('/productos/insumos/faltantes/listaCompra/', {
            'items': json.dumps([{'id': self.papel.id, 'unidades': 2}])})
        self.assertEqual(res.status_code, 200)
        self.assertIn('spreadsheetml', res['Content-Type'])

    def test_crud_proveedor(self):
        self.client.post('/productos/guardarProveedor/', {
            'nombre': 'Papelera Norte', 'telefono': '+54 9 351 123-4567',
            'telefono_whatsapp': 'on', 'email': 'ventas@norte.com', 'web': 'norte.com'})
        prov = Proveedor.objects.get(nombre='Papelera Norte')
        res = self.client.get('/productos/proveedores/')
        self.assertContains(res, 'https://wa.me/5493511234567')
        self.assertEqual(prov.whatsapp_numero, '5493511234567')
        self.assertEqual(prov.web_url, 'https://norte.com')

        # Duplicado ignorando mayúsculas: no se crea.
        self.client.post('/productos/guardarProveedor/', {'nombre': 'papelera norte'})
        self.assertEqual(Proveedor.objects.count(), 1)

        self.papel.proveedor = prov
        self.papel.save()
        self.client.get(f'/productos/borrarProveedor/{prov.id}')
        self.papel.refresh_from_db()
        self.assertIsNone(self.papel.proveedor)

    def test_whatsapp_solo_si_se_marca(self):
        prov = Proveedor.objects.create(nombre='X', telefono='3511234567')
        self.assertEqual(prov.whatsapp_numero, '')
