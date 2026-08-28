from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import CostoFijo, ParametrosProduccion
from productos.models import Producto, ProductoCotizado


class DobleCalculoCotizacionTests(TestCase):
    """Fase 3: el método actual (que se cobra) y el método nuevo (sugerido,
    informativo) se calculan juntos y los snapshots se guardan al agregar.

    El método nuevo usa margen_objetivo (config), NO producto.factor (que es
    markup sobre el material). Por eso factor=3 y margen_objetivo=2 son distintos:
    así el test prueba que el sugerido usa el 2, no el 3.

    Escenario controlado:
      producto: precio 1000, factor 3 (markup material, solo método actual)
      Mano de obra (hora legacy): 500 · Empaquetado: 300
      tasa_hora = 100000 / (1*10*20*0.5) = 100000/100 = 1000
      margen_objetivo = 2
      inputs: cantidad 5 (tipo D), tiempo 2 h, sin empaquetado, sin descuento

    Método actual:  5*1000*3 + 2*500              = 16000  (bruto)
    Método nuevo:   costo_var = 5*1000 = 5000      (piso absoluto)
                    costo_tot = 5000 + 2*1000 = 7000  (piso absorción)
                    sugerido  = 7000 * 2 (margen_objetivo) = 14000
    """

    def setUp(self):
        self.user = User.objects.create_superuser("v", "v@v.com", "pw12345")
        self.client.force_login(self.user)

        self.producto = Producto.objects.create(
            nombre="Tarjeta", precio=Decimal("1000"), factor=Decimal("3"),
            tercerizado=False)
        Producto.objects.create(
            nombre="Mano de obra", precio_proveedor=Decimal("500"))
        Producto.objects.create(
            nombre="Empaquetado", precio_proveedor=Decimal("300"))

        CostoFijo.objects.create(concepto="Alquiler", monto=Decimal("100000"),
                                 periodicidad="mensual", activo=True)
        p = ParametrosProduccion.load()
        p.operarios = 1
        p.horas_dia = Decimal("10")
        p.dias_mes = 20
        p.ratio_productivas = Decimal("0.5")
        p.margen_objetivo = Decimal("2")
        p.save()

    def _cotizar(self, **overrides):
        data = {
            "producto_id": self.producto.id,
            "cantidadElementos": 5,
            "inputTiempo": "2",
            "empaquetado": "false",
            "tipoCotizacion": "D",
            "descuento": "0",
        }
        data.update(overrides)
        return self.client.post("/presupuestos/calcularCotizacionFinal", data)

    def test_json_devuelve_ambos_metodos(self):
        resp = self._cotizar()
        self.assertEqual(resp.status_code, 200)
        j = resp.json()
        self.assertEqual(Decimal(j["precio_actual_bruto"]), Decimal("16000"))
        self.assertEqual(Decimal(j["precio_sugerido"]), Decimal("14000"))
        self.assertEqual(Decimal(j["piso_absoluto"]), Decimal("5000"))
        self.assertEqual(Decimal(j["piso_absorcion"]), Decimal("7000"))
        self.assertEqual(Decimal(j["tasa_hora"]), Decimal("1000"))

    def test_empaquetado_entra_en_ambos_pisos(self):
        # Con empaquetado (300): piso_absoluto 5300, piso_absorcion 7300,
        # sugerido 7300*2=14600; método actual bruto 15000+1000+300=16300.
        resp = self._cotizar(empaquetado="true")
        j = resp.json()
        self.assertEqual(Decimal(j["piso_absoluto"]), Decimal("5300"))
        self.assertEqual(Decimal(j["piso_absorcion"]), Decimal("7300"))
        self.assertEqual(Decimal(j["precio_sugerido"]), Decimal("14600"))
        self.assertEqual(Decimal(j["precio_actual_bruto"]), Decimal("16300"))

    def test_agregar_persiste_los_snapshots(self):
        # Cotizar (guarda en sesión) y luego agregar (persiste).
        self._cotizar()
        session = self.client.session
        session["vendedor"] = self.user.id
        session.save()

        self.client.get("/presupuestos/agregarProducto")

        pc = ProductoCotizado.objects.latest("id")
        self.assertEqual(pc.piso_absoluto, Decimal("5000"))
        self.assertEqual(pc.piso_absorcion, Decimal("7000"))
        self.assertEqual(pc.precio_sugerido, Decimal("14000"))
        self.assertEqual(pc.costo_insumos_snap, Decimal("5000"))
        # margen_snap guarda el margen_objetivo usado (2), no el factor (3).
        self.assertEqual(pc.margen_snap, Decimal("2"))
        self.assertEqual(pc.tasa_hora_snap, Decimal("1000"))
        self.assertEqual(pc.precio_hora_legacy_snap, Decimal("500"))
        self.assertFalse(pc.precio_manual)
        # resultado (cobrado) = 16000 (bruto, sin descuento)
        self.assertEqual(pc.resultado, Decimal("16000"))
        # contribución = resultado - piso_absoluto = 16000 - 5000 = 11000
        self.assertEqual(pc.contribucion, Decimal("11000"))
        # contribución por hora = 11000 / 2 = 5500
        self.assertEqual(pc.contribucion_por_hora, Decimal("5500"))

    def test_sin_estructura_no_explota(self):
        # Sin costos ni horas productivas, tasa_hora = 0:
        # sugerido = costo_variable * margen_objetivo = 5000 * 2 = 10000.
        CostoFijo.objects.all().delete()
        p = ParametrosProduccion.load()
        p.ratio_productivas = Decimal("0")
        p.save()
        j = self._cotizar().json()
        self.assertEqual(Decimal(j["tasa_hora"]), Decimal("0"))
        self.assertEqual(Decimal(j["piso_absorcion"]), Decimal("5000"))
        self.assertEqual(Decimal(j["precio_sugerido"]), Decimal("10000"))

    def test_usa_margen_objetivo_no_factor(self):
        # Regresión del hallazgo Fase 3: el sugerido NO debe usar producto.factor.
        # factor=3, margen_objetivo=2 -> con 5 elementos y tiempo 2:
        # sugerido = 7000*2 = 14000, nunca 7000*3 = 21000.
        j = self._cotizar().json()
        self.assertEqual(Decimal(j["precio_sugerido"]), Decimal("14000"))
        self.assertNotEqual(Decimal(j["precio_sugerido"]), Decimal("21000"))
