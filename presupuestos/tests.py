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

    DESACOPLE (Fase 2): el método viejo usa horas_legacy (default 1), NO el tiempo
    del input. El tiempo del input (2 h) alimenta solo el método nuevo.

    Método actual:  5*1000*3 + horas_legacy(1)*500 = 15500  (bruto)
    Método nuevo:   costo_var = 5*1000 = 5000      (piso absoluto)
                    costo_tot = 5000 + 2*1000 = 7000  (piso absorción)  [tiempo=2]
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
        self.assertEqual(Decimal(j["precio_actual_bruto"]), Decimal("15500"))
        self.assertEqual(Decimal(j["precio_sugerido"]), Decimal("14000"))
        self.assertEqual(Decimal(j["piso_absoluto"]), Decimal("5000"))
        self.assertEqual(Decimal(j["piso_absorcion"]), Decimal("7000"))
        self.assertEqual(Decimal(j["tasa_hora"]), Decimal("1000"))

    def test_desacople_tiempo_no_mueve_el_cobrado(self):
        # El tiempo del input mueve SOLO el sugerido; el cobrado usa horas_legacy.
        j1 = self._cotizar(inputTiempo="2").json()
        j2 = self._cotizar(inputTiempo="8").json()
        # Cobrado idéntico con 2 h y con 8 h (usa horas_legacy=1).
        self.assertEqual(j1["precio_actual_bruto"], j2["precio_actual_bruto"])
        self.assertEqual(Decimal(j1["precio_actual_bruto"]), Decimal("15500"))
        # Sugerido sí cambia: 8 h -> (5000 + 8*1000)*2 = 26000.
        self.assertEqual(Decimal(j2["precio_sugerido"]), Decimal("26000"))

    def test_horas_legacy_configurable_mueve_el_cobrado(self):
        # Subir horas_legacy a 3 sí mueve el cobrado: 15000 + 3*500 = 16500.
        p = ParametrosProduccion.load()
        p.horas_legacy = Decimal("3")
        p.save()
        j = self._cotizar().json()
        self.assertEqual(Decimal(j["precio_actual_bruto"]), Decimal("16500"))

    def test_empaquetado_entra_en_ambos_pisos(self):
        # Con empaquetado (300): piso_absoluto 5300, piso_absorcion 7300,
        # sugerido 7300*2=14600; método actual bruto 15000 + 1*500 + 300 = 15800.
        resp = self._cotizar(empaquetado="true")
        j = resp.json()
        self.assertEqual(Decimal(j["piso_absoluto"]), Decimal("5300"))
        self.assertEqual(Decimal(j["piso_absorcion"]), Decimal("7300"))
        self.assertEqual(Decimal(j["precio_sugerido"]), Decimal("14600"))
        self.assertEqual(Decimal(j["precio_actual_bruto"]), Decimal("15800"))

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
        # resultado (cobrado) = 15500 (bruto, sin descuento): usa horas_legacy=1.
        self.assertEqual(pc.resultado, Decimal("15500"))
        # contribución = resultado - piso_absoluto = 15500 - 5000 = 10500
        self.assertEqual(pc.contribucion, Decimal("10500"))
        # contribución por hora = 10500 / 2 = 5250 (t_produccion estructural = 2)
        self.assertEqual(pc.contribucion_por_hora, Decimal("5250"))

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
