"""Tests del manual de uso.

Lo que se protege acá es, sobre todo, que el manual **no mienta ni se rompa**:
que cada capítulo del índice exista, que las páginas rendericen con la base
vacía (instalación nueva) y con datos, y que la fórmula del factor que el
manual enseña sea la inversa exacta de la que el cotizador cobra.
"""
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.template.loader import get_template
from django.test import TestCase, override_settings
from django.urls import reverse

from core import roles
from core.models import CostoFijo, ParametrosProduccion
from productos.models import Categoria, ComponenteProducto, Insumo, Producto

from .contenido import CAPITULOS, buscar, para_usuario, publicados, vecinos
from . import contexto

# Igual que en caja/tests.py y tercerizados/tests.py: en tests no hay manifest
# de staticfiles, así que las vistas que renderizan templates necesitan el
# storage simple.
# El capítulo restringido, buscado una sola vez. No va en
# `setUpTestData`: Django hace deepcopy de lo que se cuelga de `cls`
# ahí, y las comparaciones por identidad contra CAPITULOS fallarían.
RESTRINGIDO = next(c for c in CAPITULOS if c.permiso)

STATIC = override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})


class ContenidoTests(TestCase):
    def test_los_capitulos_publicados_tienen_template(self):
        """Un capítulo con link y sin template es un link roto en el índice."""
        for cap in publicados():
            with self.subTest(capitulo=cap.slug):
                get_template(cap.template)

    def test_los_pendientes_no_tienen_template(self):
        """Si alguien escribió uno, hay que sacarle la marca de pendiente."""
        from django.template import TemplateDoesNotExist
        for cap in CAPITULOS:
            if not cap.pendiente:
                continue
            with self.subTest(capitulo=cap.slug):
                with self.assertRaises(TemplateDoesNotExist):
                    get_template(cap.template)

    def test_hay_capitulos_publicados_y_pendientes(self):
        self.assertTrue(publicados())
        self.assertNotEqual(len(publicados()), len(CAPITULOS))

    def test_los_permisos_existen_en_roles(self):
        """Un permiso mal escrito haría explotar `tiene_permiso` con KeyError."""
        for cap in CAPITULOS:
            if cap.permiso is None:
                continue
            with self.subTest(capitulo=cap.slug):
                self.assertIn(cap.permiso, roles.PERMISOS)

    def test_los_numeros_son_consecutivos_desde_uno(self):
        self.assertEqual([c.numero for c in CAPITULOS],
                         list(range(1, len(CAPITULOS) + 1)))

    def test_slugs_unicos(self):
        slugs = [c.slug for c in CAPITULOS]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_vecinos_en_los_extremos(self):
        disponibles = publicados()
        anterior, _ = vecinos(disponibles[0].slug)
        self.assertIsNone(anterior)
        _, siguiente = vecinos(disponibles[-1].slug)
        self.assertIsNone(siguiente)

    def test_vecinos_en_el_medio(self):
        disponibles = publicados()
        if len(disponibles) < 3:
            self.skipTest('hacen falta al menos 3 capítulos publicados')
        anterior, siguiente = vecinos(disponibles[1].slug)
        self.assertEqual(anterior.slug, disponibles[0].slug)
        self.assertEqual(siguiente.slug, disponibles[2].slug)

    def test_los_vecinos_saltean_los_pendientes(self):
        """«Siguiente» tiene que llevar a algo que se pueda leer."""
        pendientes = {c.slug for c in CAPITULOS if c.pendiente}
        for cap in publicados():
            anterior, siguiente = vecinos(cap.slug)
            for vecino in (anterior, siguiente):
                if vecino is not None:
                    self.assertNotIn(vecino.slug, pendientes)

    def test_un_pendiente_no_tiene_vecinos(self):
        pendiente = next(c for c in CAPITULOS if c.pendiente)
        self.assertEqual(vecinos(pendiente.slug), (None, None))

    def test_slug_desconocido_no_tiene_vecinos(self):
        self.assertEqual(vecinos('no-existe'), (None, None))


class RangoRegexTests(TestCase):
    """La expresión de familias del manual tiene que coincidir con la que el
    cotizador usa de verdad; si se separan, el manual explica otra cosa."""

    CASOS = [
        'Papel obra oficio 75g simple faz byn [1-5]',
        'Papel obra oficio 75g simple faz byn [501-INF]',
        'Lona impresa',
        'Vinilo [10-20] brillante',
        'Algo [3-7]',
    ]

    def test_coincide_con_la_del_cotizador(self):
        from presupuestos.views import _RANGO_RE
        for nombre in self.CASOS:
            with self.subTest(nombre=nombre):
                propio = contexto.RANGO_RE.match(nombre)
                canonico = _RANGO_RE.match(nombre)
                self.assertEqual(bool(propio), bool(canonico))
                if propio:
                    self.assertEqual(propio.groups(), canonico.groups())



class ContextoBaseVaciaTests(TestCase):
    """Una instalación nueva no tiene insumos ni productos: el manual tiene que
    abrirse igual, con la explicación genérica."""

    def test_no_explota_sin_datos(self):
        datos = contexto.contexto_manual()
        self.assertIsNone(datos['insumo'])
        self.assertIsNone(datos['familia'])
        self.assertIsNone(datos['tiempos'])
        self.assertFalse(datos['par']['hay_estructura'])


class ContextoConDatosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ParametrosProduccion.objects.all().delete()
        p = ParametrosProduccion.load()
        p.operarios = 2
        p.horas_dia = Decimal('6')
        p.dias_mes = 22
        p.ratio_productivas = Decimal('0.75')
        p.margen_objetivo = Decimal('1.30')
        p.horas_legacy = Decimal('1.00')
        p.save()
        CostoFijo.objects.create(
            concepto='Alquiler', monto=Decimal('1000000'), activo=True)

        Producto.objects.create(
            nombre='Mano de obra', precio_proveedor=Decimal('2000'))
        Producto.objects.create(
            nombre='Empaquetado', precio_proveedor=Decimal('500'))

        cls.cat = Categoria.objects.create(nombre='Papeles')
        cls.insumo = Insumo.objects.create(
            nombre='Resma oficio 75g', unidad_medida='resma',
            unidad_composicion='hoja', factor_conversion=500,
            precio=Decimal('18000'), stock=10)
        for desde, hasta, factor in [(1, 5, '20'), (6, 30, '10'),
                                     (31, 100, '8')]:
            prod = Producto.objects.create(
                nombre=f'Papel oficio byn [{desde}-{hasta}]',
                categoria=cls.cat, precio=Decimal('36'),
                factor=Decimal(factor), tiempo_setup=Decimal('0.17'),
                tiempo_unitario=Decimal('0.0170'))
            ComponenteProducto.objects.create(
                producto=prod, insumo=cls.insumo, cantidad=1)

    def test_insumo_ejemplo_elige_uno_con_dos_unidades(self):
        insumo = contexto.insumo_ejemplo()
        self.assertEqual(insumo, self.insumo)
        self.assertGreater(insumo.factor_conversion, 1)

    def test_familia_ejemplo_arma_los_escalones_ordenados(self):
        familia = contexto.familia_ejemplo()
        self.assertIsNotNone(familia)
        self.assertEqual([f['desde'] for f in familia['filas']], [1, 6, 31])
        self.assertEqual(familia['unidad'], 'hoja')

    def test_familia_ejemplo_da_el_precio_por_unidad(self):
        familia = contexto.familia_ejemplo()
        # $36 por hoja × factor 20
        self.assertEqual(familia['filas'][0]['precio_unidad'], Decimal('720'))

    def test_el_precio_por_unidad_baja_escalon_a_escalon(self):
        """Es la razón de ser de las familias: más cantidad, menos por unidad."""
        precios = [f['precio_unidad'] for f in contexto.familia_ejemplo()['filas']]
        self.assertEqual(precios, sorted(precios, reverse=True))

    def test_familia_ejemplo_no_compara_contra_el_sugerido(self):
        """Se sacó a propósito: son dos criterios distintos, ninguno mecánico."""
        fila = contexto.familia_ejemplo()['filas'][0]
        for clave in ('cobrado', 'sugerido', 'factor_ideal'):
            self.assertNotIn(clave, fila)

    def test_tiempos_cargados_detecta_las_combinaciones_repetidas(self):
        tiempos = contexto.tiempos_cargados()
        self.assertEqual(tiempos['con_tiempos'], 3)
        self.assertEqual(tiempos['distintas'], 1)


@STATIC
class VistasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Gerencia: ve el manual completo. El filtrado por rol se prueba aparte
        # (PermisosCapituloTests).
        cls.user = User.objects.create_user('tester', password='x' * 12)
        cls.user.groups.add(Group.objects.get_or_create(name=roles.GERENCIA)[0])

    def setUp(self):
        self.client.force_login(self.user)

    def test_indice_responde(self):
        r = self.client.get(reverse('ayuda_indice'))
        self.assertEqual(r.status_code, 200)
        for cap in CAPITULOS:
            self.assertContains(r, cap.titulo)

    def test_cada_capitulo_renderiza(self):
        for cap in publicados():
            with self.subTest(capitulo=cap.slug):
                r = self.client.get(reverse('ayuda_capitulo', args=[cap.slug]))
                self.assertEqual(r.status_code, 200)

    def test_un_capitulo_pendiente_no_tiene_pagina(self):
        pendiente = next(c for c in CAPITULOS if c.pendiente)
        r = self.client.get(reverse('ayuda_capitulo', args=[pendiente.slug]))
        self.assertEqual(r.status_code, 404)

    def test_el_indice_lista_los_pendientes_sin_link(self):
        r = self.client.get(reverse('ayuda_indice'))
        pendiente = next(c for c in CAPITULOS if c.pendiente)
        self.assertContains(r, pendiente.titulo)
        self.assertNotContains(
            r, reverse('ayuda_capitulo', args=[pendiente.slug]))

    def test_capitulo_inexistente_vuelve_al_indice(self):
        r = self.client.get(reverse('ayuda_capitulo', args=['inventado']))
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, 'inventado', status_code=404)

    def test_pdf_se_genera(self):
        r = self.client.get(reverse('ayuda_pdf'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_pide_login(self):
        self.client.logout()
        r = self.client.get(reverse('ayuda_indice'))
        self.assertEqual(r.status_code, 302)


@STATIC
class PermisosCapituloTests(TestCase):
    """El capítulo del dashboard pide el permiso del tablero.

    Para quien no lo tiene se comporta como si no existiera: no aparece en el
    índice, no se puede abrir y no entra al PDF. Muestra el costo fijo, la tasa
    por hora y lo que se cobró en cotizaciones reales, así que no puede quedar
    al alcance de Ventas sólo porque el manual sea público.
    """

    @classmethod
    def setUpTestData(cls):
        # Los grupos ya existen (los crea una migración de datos).
        gerencia, _ = Group.objects.get_or_create(name=roles.GERENCIA)
        ventas, _ = Group.objects.get_or_create(name=roles.VENTAS)
        cls.gerente = User.objects.create_user('gerente', password='x' * 12)
        cls.gerente.groups.add(gerencia)
        cls.vendedor = User.objects.create_user('vendedor', password='x' * 12)
        cls.vendedor.groups.add(ventas)

    def test_el_capitulo_restringido_es_el_del_dashboard(self):
        self.assertEqual(RESTRINGIDO.slug, 'dashboard')
        self.assertEqual(RESTRINGIDO.permiso, 'dashboard')

    def test_ventas_no_lo_tiene_en_su_lista_y_gerencia_si(self):
        self.assertNotIn(RESTRINGIDO, para_usuario(self.vendedor))
        self.assertIn(RESTRINGIDO, para_usuario(self.gerente))

    def test_buscar_lo_esconde_de_ventas(self):
        self.assertIsNone(buscar('dashboard', self.vendedor))
        self.assertIsNotNone(buscar('dashboard', self.gerente))

    def test_el_indice_de_ventas_no_lo_lista(self):
        self.client.force_login(self.vendedor)
        r = self.client.get(reverse('ayuda_indice'))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, RESTRINGIDO.titulo)
        self.assertNotContains(
            r, reverse('ayuda_capitulo', args=[RESTRINGIDO.slug]))

    def test_ventas_no_puede_abrirlo(self):
        self.client.force_login(self.vendedor)
        r = self.client.get(
            reverse('ayuda_capitulo', args=[RESTRINGIDO.slug]))
        self.assertEqual(r.status_code, 404)

    def test_gerencia_si_puede_abrirlo(self):
        self.client.force_login(self.gerente)
        r = self.client.get(
            reverse('ayuda_capitulo', args=[RESTRINGIDO.slug]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, RESTRINGIDO.titulo)

    def test_el_pdf_de_ventas_no_lo_incluye(self):
        self.assertNotIn(RESTRINGIDO, publicados(self.vendedor))
        self.assertIn(RESTRINGIDO, publicados(self.gerente))
        self.client.force_login(self.vendedor)
        r = self.client.get(reverse('ayuda_pdf'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_los_vecinos_lo_saltean_para_ventas(self):
        """«Siguiente» no puede llevar a una página que da 404."""
        # El anterior redactado, no el número anterior: los capítulos 5 a 7
        # están pendientes.
        anterior = [c for c in publicados()
                    if c.numero < RESTRINGIDO.numero][-1]
        _, siguiente_gerencia = vecinos(anterior.slug, self.gerente)
        _, siguiente_ventas = vecinos(anterior.slug, self.vendedor)
        self.assertEqual(siguiente_gerencia, RESTRINGIDO)
        self.assertNotEqual(siguiente_ventas, RESTRINGIDO)

    def test_el_numero_de_capitulo_no_cambia_segun_el_rol(self):
        """Si la numeración se corriera, «el capítulo 8» sería otro para cada rol."""
        de_ventas = {c.slug: c.numero for c in para_usuario(self.vendedor)}
        de_gerencia = {c.slug: c.numero for c in para_usuario(self.gerente)}
        for slug, numero in de_ventas.items():
            with self.subTest(capitulo=slug):
                self.assertEqual(numero, de_gerencia[slug])

    def test_el_superusuario_ve_todo(self):
        admin = User.objects.create_superuser('jefe', password='x' * 12)
        self.assertEqual(para_usuario(admin), CAPITULOS)


@STATIC
class NavbarTests(TestCase):
    def test_el_manual_esta_en_la_navegacion(self):
        user = User.objects.create_user('nav', password='x' * 12)
        self.client.force_login(user)
        r = self.client.get(reverse('ayuda_indice'))
        self.assertContains(r, 'nav_item_ayuda')


class CostoUnidadUsoTests(TestCase):
    def test_divide_por_el_factor_de_conversion(self):
        insumo = Insumo(nombre='X', factor_conversion=500,
                        precio=Decimal('5551.00'))
        self.assertEqual(contexto.costo_unidad_uso(insumo),
                         Decimal('5551.00') / 500)

    def test_sin_insumo_devuelve_none(self):
        self.assertIsNone(contexto.costo_unidad_uso(None))

    def test_factor_cero_no_explota(self):
        self.assertIsNone(contexto.costo_unidad_uso(
            Insumo(nombre='X', factor_conversion=0, precio=Decimal('10'))))


class GlosarioDelManualTests(TestCase):
    """El PDF no tiene tooltips: los conceptos usados van como glosario final."""

    def test_junta_las_claves_usadas_sin_repetir(self):
        entradas = contexto.glosario_del_manual(publicados())
        claves = [e['clave'] for e in entradas]
        self.assertEqual(len(claves), len(set(claves)))
        self.assertIn('precio_sugerido', claves)

    def test_el_texto_sale_del_glosario_canonico(self):
        from core.glosario import GLOSARIO
        for e in contexto.glosario_del_manual(publicados()):
            self.assertEqual(e['texto'], GLOSARIO[e['clave']])

    def test_no_explota_con_un_capitulo_pendiente(self):
        """Listar lo que falta no puede romper el PDF."""
        self.assertEqual(
            contexto.glosario_del_manual(CAPITULOS),
            contexto.glosario_del_manual(publicados()))

    def test_todas_tienen_titulo_legible(self):
        for e in contexto.glosario_del_manual(publicados()):
            self.assertTrue(e['titulo'])
            self.assertNotIn('_', e['titulo'])


@STATIC
class PdfTests(TestCase):
    """El PDF no puede mostrar los botones "(i)": sin la hoja de estilos del
    sitio, weasyprint los dibuja como un recuadro gris vacío."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('pdf', password='x' * 12)

    def _html(self):
        from django.template.loader import render_to_string
        from django.utils import timezone
        from .contexto import contexto_manual, glosario_del_manual
        caps = publicados()
        return render_to_string('ayuda/manual_pdf.html', {
            'capitulos': caps, 'generado': timezone.localdate(),
            'glosario': glosario_del_manual(caps), **contexto_manual()})

    def test_oculta_los_botones_de_ayuda(self):
        html = self._html()
        self.assertIn('.ayuda-info', html)
        bloque = html[html.index('.ayuda-info'):]
        self.assertTrue(bloque.lstrip('.ayuda-info').lstrip().startswith(
            '{ display: none; }'), 'la regla que oculta el botón (i) cambió')

    def test_incluye_el_glosario_al_final(self):
        html = self._html()
        self.assertIn('Glosario', html)
        self.assertIn('Piso de absorción', html)
        self.assertGreater(html.index('Glosario'), html.index('Contenido'))


class CotizacionesEjemploTests(TestCase):
    """Los ejemplos del capítulo del tablero salen de cotizaciones reales."""

    def test_sin_cotizaciones_devuelve_none(self):
        self.assertIsNone(contexto.cotizaciones_ejemplo())


@STATIC
class CotizacionesEjemploConDatosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from presupuestos.models import Presupuesto
        from productos.models import ProductoCotizado
        cat = Categoria.objects.create(nombre='Papeles')
        prod = Producto.objects.create(
            nombre='Papel de prueba', categoria=cat, precio=Decimal('10'))
        pres = Presupuesto.objects.create(numero=1)
        # Rápido y rendidor: deja mucho por hora.
        cls.rapido = ProductoCotizado.objects.create(
            insumo=prod, presupuesto=pres, producto_final='Rápido',
            t_produccion=Decimal('0.50'), piso_absoluto=Decimal('100'),
            piso_absorcion=Decimal('600'), resultado=Decimal('2100'),
            tasa_hora_snap=Decimal('1000'))
        # Cobrado por debajo de su piso de absorción.
        cls.flojo = ProductoCotizado.objects.create(
            insumo=prod, presupuesto=pres, producto_final='Flojo',
            t_produccion=Decimal('2.00'), piso_absoluto=Decimal('100'),
            piso_absorcion=Decimal('2100'), resultado=Decimal('500'),
            tasa_hora_snap=Decimal('1000'))

    def test_identifica_el_mejor_y_el_peor_por_hora(self):
        d = contexto.cotizaciones_ejemplo()
        self.assertEqual(d['mejor']['nombre'], 'Rápido')
        self.assertEqual(d['peor']['nombre'], 'Flojo')

    def test_la_estructura_es_el_piso_de_absorcion_menos_el_material(self):
        d = contexto.cotizaciones_ejemplo()
        self.assertEqual(d['mejor']['estructura'], Decimal('500'))

    def test_detecta_el_cobrado_por_debajo_del_piso(self):
        d = contexto.cotizaciones_ejemplo()
        self.assertIsNotNone(d['bajo_piso'])
        self.assertEqual(d['bajo_piso']['nombre'], 'Flojo')
        self.assertFalse(d['bajo_piso']['paga_su_parte'])

    def test_marca_el_que_si_paga_su_parte(self):
        d = contexto.cotizaciones_ejemplo()
        self.assertTrue(d['mejor']['paga_su_parte'])

    def test_ignora_las_cotizaciones_sin_estructura(self):
        """Las viejas no tienen snapshots: su 'contribución' sería el precio
        entero, justo el malentendido que el capítulo quiere evitar."""
        from presupuestos.models import Presupuesto
        from productos.models import ProductoCotizado
        ProductoCotizado.objects.create(
            insumo=Producto.objects.first(),
            presupuesto=Presupuesto.objects.first(), producto_final='Vieja',
            t_produccion=Decimal('1'), piso_absorcion=Decimal('0'),
            resultado=Decimal('9999'))
        d = contexto.cotizaciones_ejemplo()
        self.assertEqual(d['total'], 2)
