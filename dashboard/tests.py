from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.models import CostoFijo, ParametrosProduccion
from dashboard.metrics import panel_horas
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
        m = panel_horas(timezone.localdate())
        ranking = m["ranking_contrib_hora"]
        # Solo el producto vendido (P): Q no tiene pedido.
        self.assertEqual(len(ranking), 1)
        self.assertEqual(ranking[0]["insumo__nombre"], "P")
        self.assertEqual(ranking[0]["contrib_por_hora"], Decimal("1500"))

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
        m = panel_horas(timezone.localdate())
        self.assertEqual(m["horas_vendidas"], Decimal("0"))
        self.assertIsNone(m["punto_equilibrio_hs"])
        self.assertEqual(m["conversion"], Decimal("0"))
        self.assertEqual(m["ranking_contrib_hora"], [])
