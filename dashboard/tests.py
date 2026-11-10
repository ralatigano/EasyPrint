from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from core import roles
from core.models import CostoFijo, ParametrosProduccion
from dashboard import periodos
from dashboard.metrics import (dinero_por_entrar, panel_horas,
                               ranking_contribucion_hora)
from pedidos.models import Pedido
from presupuestos.models import Presupuesto
from productos.models import Producto, ProductoCotizado


class PanelHorasTests(TestCase):
    """Fase 5: métricas del panel de horas del mes en curso.

    Escenario:
      tasa_hora = 100000 / (1*10*20*0.5=100) = 1000
      Presupuesto 1 VENDIDO (tiene pedido): item t=2 h, resultado 5000, piso 2000
        -> contribucion 3000, contrib/hora 1500
      Presupuesto 2 cotizado, NO vendido: item t=3 h
    """

    def setUp(self):
        CostoFijo.objects.create(concepto="Alquiler", monto=Decimal("100000"),
                                 periodicidad="mensual", activo=True)
        p = ParametrosProduccion.load()
        p.operarios = 1
        p.horas_dia = Decimal("10")
        p.dias_mes = 20
        p.ratio_productivas = Decimal("0.5")
        p.save()

        self.prod = Producto.objects.create(nombre="P", precio=Decimal("100"))
        self.prod2 = Producto.objects.create(nombre="Q", precio=Decimal("100"))

        pre1 = Presupuesto.objects.create(numero=1)
        ProductoCotizado.objects.create(
            insumo=self.prod, presupuesto=pre1, cantidad=10,
            t_produccion=Decimal("2"), resultado=Decimal("5000"),
            piso_absoluto=Decimal("2000"), piso_absorcion=Decimal("4000"))
        Pedido.objects.create(numero=100, presupuesto=1, precio=5000,
                              descripcion="x")

        pre2 = Presupuesto.objects.create(numero=2)
        ProductoCotizado.objects.create(
            insumo=self.prod2, presupuesto=pre2, cantidad=5,
            t_produccion=Decimal("3"), resultado=Decimal("9000"),
            piso_absoluto=Decimal("3000"), piso_absorcion=Decimal("6000"))

    def test_horas_y_contribucion(self):
        m = panel_horas(timezone.localdate())
        self.assertEqual(m["horas_vendidas"], Decimal("2"))
        self.assertEqual(m["horas_cotizadas"], Decimal("5"))  # 2 vendidas + 3 no
        self.assertEqual(m["contribucion_mes"], Decimal("3000"))
        self.assertEqual(m["tasa_hora"], Decimal("1000"))

    def test_punto_equilibrio_y_absorcion(self):
        m = panel_horas(timezone.localdate())
        # contrib/hora = 3000/2 = 1500 ; equilibrio = 100000/1500 = 66,67
        self.assertAlmostEqual(m["contrib_prom_por_hora"], Decimal("1500"))
        self.assertAlmostEqual(float(m["punto_equilibrio_hs"]), 66.6667, places=3)
        # absorción = 2*1000 = 2000 ; sub-absorción = 2000 - 100000
        self.assertEqual(m["absorcion_recuperada"], Decimal("2000"))
        self.assertEqual(m["sub_absorcion"], Decimal("-98000"))

    def test_conversion(self):
        m = panel_horas(timezone.localdate())
        # 2 h vendidas / 5 h cotizadas = 40%
        self.assertEqual(m["conversion"], Decimal("40"))

    def test_ranking_por_contribucion_hora(self):
        """El ranking sigue el filtro de período, así que va aparte del panel."""
        hoy = timezone.localdate()
        ranking = ranking_contribucion_hora(hoy - timedelta(days=30), hoy)
        # Solo el producto vendido (P): Q no tiene pedido.
        self.assertEqual(len(ranking), 1)
        self.assertEqual(ranking[0]["insumo__nombre"], "P")
        self.assertEqual(ranking[0]["contrib_por_hora"], Decimal("1500"))

    def test_el_ranking_respeta_la_ventana(self):
        hoy = timezone.localdate()
        viejo = hoy - timedelta(days=90)
        self.assertEqual(ranking_contribucion_hora(viejo, viejo), [])

    def test_resultado_del_mes(self):
        """Lo que se muestra en el card: contribución − costo fijo."""
        m = panel_horas(timezone.localdate())
        self.assertEqual(m["resultado_mes"], Decimal("-97000"))
        self.assertEqual(m["falta_cubrir"], Decimal("97000"))

    def test_el_equilibrio_entra_en_la_capacidad(self):
        # contrib/hora 1500 > tasa 1000 ⇒ equilibrio 66,67 h ≤ 100 h
        m = panel_horas(timezone.localdate())
        self.assertTrue(m["equilibrio_entra"])
        self.assertIsNone(m["falta_precio_pct"])
        self.assertAlmostEqual(float(m["horas_restantes"]), 64.6667, places=3)

    def test_excluye_items_sin_estructura(self):
        # Un ítem vendido cotizado antes de la Fase 3 (piso_absorcion=0) NO debe
        # contar: su "contribución" sería el precio entero y distorsionaría todo.
        pre3 = Presupuesto.objects.create(numero=3)
        ProductoCotizado.objects.create(
            insumo=self.prod, presupuesto=pre3, cantidad=1,
            t_produccion=Decimal("0"), resultado=Decimal("99999"),
            piso_absoluto=Decimal("0"), piso_absorcion=Decimal("0"))
        Pedido.objects.create(numero=101, presupuesto=3, precio=99999,
                              descripcion="viejo")
        m = panel_horas(timezone.localdate())
        # Sigue igual que sin ese ítem: contribución 3000, no 3000+99999.
        self.assertEqual(m["contribucion_mes"], Decimal("3000"))
        self.assertEqual(m["horas_vendidas"], Decimal("2"))

    def test_sin_ventas_no_explota(self):
        Pedido.objects.all().delete()
        hoy = timezone.localdate()
        m = panel_horas(hoy)
        self.assertEqual(m["horas_vendidas"], Decimal("0"))
        self.assertIsNone(m["punto_equilibrio_hs"])
        self.assertEqual(m["conversion"], Decimal("0"))
        self.assertFalse(m["equilibrio_entra"])
        self.assertIsNone(m["horas_restantes"])
        self.assertEqual(
            ranking_contribucion_hora(hoy - timedelta(days=30), hoy), [])


class ConversionCohorteTests(TestCase):
    """La conversión tiene que mirar UNA camada de presupuestos.

    Antes dividía "lo vendido este mes" (viniera de cuando viniera) por "lo
    cotizado este mes", y el cociente podía pasar del 100 % (llegó a mostrar
    217 %). Acá se arma justo ese escenario: un presupuesto del mes pasado que
    se cerró este mes.
    """

    def setUp(self):
        CostoFijo.objects.create(concepto="Alquiler", monto=Decimal("100000"),
                                 periodicidad="mensual", activo=True)
        p = ParametrosProduccion.load()
        p.operarios, p.horas_dia, p.dias_mes = 1, Decimal("10"), 20
        p.ratio_productivas = Decimal("0.5")
        p.save()
        self.prod = Producto.objects.create(nombre="P", precio=Decimal("100"))

        # Último día del mes pasado.
        anterior = timezone.now().replace(day=1) - timedelta(days=1)

        # Presupuesto viejo (mes pasado), 10 h, vendido ESTE mes.
        viejo = Presupuesto.objects.create(numero=1)
        Presupuesto.objects.filter(pk=viejo.pk).update(created=anterior)
        ProductoCotizado.objects.create(
            insumo=self.prod, presupuesto=viejo, cantidad=1,
            t_produccion=Decimal("10"), resultado=Decimal("50000"),
            piso_absoluto=Decimal("20000"), piso_absorcion=Decimal("30000"))
        Pedido.objects.create(numero=100, presupuesto=1, precio=50000,
                              descripcion="cerrado este mes")

        # Presupuesto de este mes, 1 h, SIN vender.
        nuevo = Presupuesto.objects.create(numero=2)
        ProductoCotizado.objects.create(
            insumo=self.prod, presupuesto=nuevo, cantidad=1,
            t_produccion=Decimal("1"), resultado=Decimal("5000"),
            piso_absoluto=Decimal("2000"), piso_absorcion=Decimal("3000"))

    def test_la_conversion_no_pasa_de_cien(self):
        m = panel_horas(timezone.localdate())
        # Con la fórmula vieja: 10 h vendidas / 1 h cotizada = 1000 %.
        self.assertEqual(m["horas_vendidas"], Decimal("10"))
        self.assertEqual(m["horas_cotizadas"], Decimal("1"))
        self.assertEqual(m["horas_cotizadas_vendidas"], Decimal("0"))
        self.assertEqual(m["conversion"], Decimal("0"))

    def test_cuenta_el_presupuesto_del_mes_que_si_se_vendio(self):
        Pedido.objects.create(numero=101, presupuesto=2, precio=5000,
                              descripcion="del mes y vendido")
        m = panel_horas(timezone.localdate())
        self.assertEqual(m["horas_cotizadas_vendidas"], Decimal("1"))
        self.assertEqual(m["conversion"], Decimal("100"))


class EquilibrioFueraDeCapacidadTests(TestCase):
    """La alarma del tablero: el equilibrio por encima de la capacidad."""

    def setUp(self):
        CostoFijo.objects.create(concepto="Alquiler", monto=Decimal("100000"),
                                 periodicidad="mensual", activo=True)
        p = ParametrosProduccion.load()
        p.operarios, p.horas_dia, p.dias_mes = 1, Decimal("10"), 20
        p.ratio_productivas = Decimal("0.5")   # 100 h, tasa 1000
        p.save()
        prod = Producto.objects.create(nombre="Barato", precio=Decimal("100"))
        pre = Presupuesto.objects.create(numero=1)
        # 10 h, deja 500 de contribución ⇒ 50 por hora, muy abajo de la tasa.
        ProductoCotizado.objects.create(
            insumo=prod, presupuesto=pre, cantidad=1,
            t_produccion=Decimal("10"), resultado=Decimal("5000"),
            piso_absoluto=Decimal("4500"), piso_absorcion=Decimal("14500"))
        Pedido.objects.create(numero=100, presupuesto=1, precio=5000,
                              descripcion="regalado")

    def test_avisa_que_no_cierra_y_cuanto_precio_falta(self):
        m = panel_horas(timezone.localdate())
        # equilibrio = 100000 / 50 = 2000 h, contra 100 h de capacidad
        self.assertAlmostEqual(float(m["punto_equilibrio_hs"]), 2000.0)
        self.assertFalse(m["equilibrio_entra"])
        # Para que entre, la contribución tiene que llegar a la absorción
        # recuperada (10 h × 1000 = 10.000): faltan 9.500 sobre 5.000 cobrados.
        self.assertEqual(m["falta_precio_pct"], Decimal("190"))


class DineroPorEntrarTests(TestCase):
    """Dos mitades que piden acciones distintas, por eso van separadas."""

    def setUp(self):
        Pedido.objects.create(numero=1, precio=1000, saldo=1000,
                              descripcion="a", estado="No iniciado")
        Pedido.objects.create(numero=2, precio=2000, saldo=500,
                              descripcion="b", estado="En proceso")
        Pedido.objects.create(numero=3, precio=3000, saldo=3000,
                              descripcion="c",
                              estado="Terminado (falta pago)")
        Pedido.objects.create(numero=4, precio=4000, saldo=0,
                              descripcion="d", estado="Terminado y pagado")
        Pedido.objects.create(numero=5, precio=5000, saldo=5000,
                              descripcion="e", estado="En proceso",
                              bloqueado_cancelado=True)

    def test_separa_en_curso_de_entregado_sin_pagar(self):
        d = dinero_por_entrar()
        self.assertEqual(d["en_curso"], Decimal("1500"))
        self.assertEqual(d["en_curso_count"], 2)
        self.assertEqual(d["entregado"], Decimal("3000"))
        self.assertEqual(d["entregado_count"], 1)

    def test_el_total_suma_las_dos_mitades(self):
        d = dinero_por_entrar()
        self.assertEqual(d["total"], Decimal("4500"))

    def test_ignora_los_cancelados_y_los_pagados(self):
        """Un pedido cancelado no es plata por entrar aunque tenga saldo."""
        d = dinero_por_entrar()
        self.assertNotIn(Decimal("5000"), (d["en_curso"], d["entregado"]))
        self.assertEqual(d["total"], Decimal("4500"))


class PeriodosTests(TestCase):
    """Un solo lugar resuelve el período: la pantalla y el Excel no se separan."""

    def setUp(self):
        self.rf = RequestFactory()
        self.hoy = date(2026, 11, 9)

    def resolver(self, query=""):
        return periodos.resolver(self.rf.get("/dashboard/" + query), self.hoy)

    def test_por_defecto_treinta_dias(self):
        p = self.resolver()
        self.assertEqual(p.clave, "mes")
        self.assertEqual(p.desde, date(2026, 10, 10))
        self.assertEqual(p.hasta, self.hoy)

    def test_semana_y_trimestre(self):
        self.assertEqual(self.resolver("?periodo=semana").desde,
                         date(2026, 11, 2))
        self.assertEqual(self.resolver("?periodo=trimestre").desde,
                         date(2026, 8, 11))

    def test_una_clave_desconocida_cae_en_el_default(self):
        self.assertEqual(self.resolver("?periodo=inventado").clave, "mes")

    def test_rango_personalizado(self):
        p = self.resolver("?periodo=personalizado&desde=2026-01-05&hasta=2026-02-10")
        self.assertTrue(p.es_personalizado)
        self.assertEqual(p.desde, date(2026, 1, 5))
        self.assertEqual(p.hasta, date(2026, 2, 10))
        self.assertIn("05", p.etiqueta)

    def test_rango_al_reves_se_da_vuelta(self):
        """Más útil que un error: el usuario quiso ese rango."""
        p = self.resolver("?periodo=personalizado&desde=2026-02-10&hasta=2026-01-05")
        self.assertEqual(p.desde, date(2026, 1, 5))
        self.assertEqual(p.hasta, date(2026, 2, 10))

    def test_un_rango_ilegible_no_rompe_el_dashboard(self):
        for query in ("?periodo=personalizado",
                      "?periodo=personalizado&desde=ayer&hasta=hoy",
                      "?periodo=personalizado&desde=2026-01-05"):
            with self.subTest(query=query):
                p = self.resolver(query)
                self.assertEqual(p.clave, "mes")

    def test_el_filtro_cierra_el_rango_por_los_dos_lados(self):
        """Con un rango que termina en el pasado, el tope importa."""
        p = self.resolver("?periodo=personalizado&desde=2026-01-05&hasta=2026-02-10")
        self.assertEqual(p.filtro(),
                         {"created__date__range": (p.desde, p.hasta)})

    def test_la_querystring_arrastra_el_rango_al_excel(self):
        p = self.resolver("?periodo=personalizado&desde=2026-01-05&hasta=2026-02-10")
        self.assertEqual(
            p.querystring,
            "periodo=personalizado&desde=2026-01-05&hasta=2026-02-10")
        self.assertEqual(p.sufijo_archivo, "2026-01-05_a_2026-02-10")
        self.assertEqual(self.resolver("?periodo=semana").querystring,
                         "periodo=semana")


# En tests no hay manifest de staticfiles; las vistas que renderizan templates
# necesitan el storage simple (mismo patrón que caja/, tercerizados/ y ayuda/).
STATIC = override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})


def _estructura(ratio="0.5"):
    CostoFijo.objects.create(concepto="Alquiler", monto=Decimal("100000"),
                             periodicidad="mensual", activo=True)
    p = ParametrosProduccion.load()
    p.operarios, p.horas_dia, p.dias_mes = 1, Decimal("10"), 20
    p.ratio_productivas = Decimal(ratio)
    p.save()


def _vendido(numero, horas, cobrado, material):
    """Un ítem cotizado con estructura, convertido en pedido hoy."""
    prod = Producto.objects.create(nombre=f"P{numero}", precio=Decimal("100"))
    pre = Presupuesto.objects.create(numero=numero)
    ProductoCotizado.objects.create(
        insumo=prod, presupuesto=pre, cantidad=1,
        t_produccion=Decimal(horas), resultado=Decimal(cobrado),
        piso_absoluto=Decimal(material),
        piso_absorcion=Decimal(material) + Decimal("1"))
    Pedido.objects.create(numero=numero, presupuesto=numero,
                          precio=Decimal(cobrado), descripcion="x")


@STATIC
class DashboardVistaTests(TestCase):
    """Lo que la pantalla tiene que DECIR en cada situación.

    El reclamo original era que el número grande se leía como un objetivo y
    que nada avisaba lo importante: que con esos precios el mes no cierra ni
    vendiendo toda la capacidad.
    """

    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=roles.GERENCIA)
        self.user = User.objects.create_user("gerente", password="x" * 12)
        self.user.groups.add(grupo)
        self.client.force_login(self.user)

    def test_avisa_cuando_el_equilibrio_no_entra_en_la_capacidad(self):
        _estructura()                      # 100 h, tasa 1000
        _vendido(1, "10", "5000", "4500")  # 50 por hora: equilibrio 2000 h
        html = self.client.get("/dashboard/").content.decode("utf-8")
        self.assertIn("no cierra", html)
        self.assertIn("No se arregla trabajando más", html)
        self.assertIn("más de precio", html)

    def test_cuando_entra_dice_cuantas_horas_faltan(self):
        _estructura()                       # 100 h, tasa 1000
        _vendido(1, "10", "25000", "5000")  # 2000 por hora: equilibrio 50 h
        html = self.client.get("/dashboard/").content.decode("utf-8")
        self.assertIn("te faltan vender", html)
        self.assertNotIn("no cierra", html)

    def test_los_dos_bloques_estan_rotulados(self):
        _estructura()
        html = self.client.get("/dashboard/").content.decode("utf-8")
        self.assertIn("Salud del mes", html)
        self.assertIn("no sigue el filtro de período", html)
        self.assertIn("Actividad comercial", html)
        self.assertIn("Dinero por entrar", html)

    def test_el_rango_personalizado_se_muestra_y_se_arrastra_al_excel(self):
        _estructura()
        html = self.client.get(
            "/dashboard/",
            {"periodo": "personalizado", "desde": "2026-01-05",
             "hasta": "2026-02-10"}).content.decode("utf-8")
        self.assertIn("del 05/01/2026 al 10/02/2026", html)
        self.assertIn(
            "periodo=personalizado&amp;desde=2026-01-05&amp;hasta=2026-02-10",
            html)

    def test_el_excel_usa_el_mismo_periodo_que_la_pantalla(self):
        _estructura()
        r = self.client.get("/dashboard/exportar/pedidos/",
                            {"periodo": "personalizado",
                             "desde": "2026-01-05", "hasta": "2026-02-10"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("2026-01-05_a_2026-02-10", r["Content-Disposition"])

    def test_no_queda_una_imagen_apuntando_a_none(self):
        """Un usuario sin foto de perfil tiraba un 404 en cada página."""
        _estructura()
        html = self.client.get("/dashboard/").content.decode("utf-8")
        self.assertNotIn('src="None"', html)
