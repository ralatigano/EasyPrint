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

    def test_agregar_con_precio_sugerido(self):
        # "Agregar con precio sugerido" cobra el sugerido (14000) sin descuento,
        # y NO marca precio_manual (es un precio del sistema).
        self._cotizar(descuento="10")
        session = self.client.session
        session["vendedor"] = self.user.id
        session.save()
        self.client.get("/presupuestos/agregarProducto?usar=sugerido")
        pc = ProductoCotizado.objects.latest("id")
        self.assertEqual(pc.resultado, Decimal("14000"))
        self.assertEqual(pc.desc_porcentaje, Decimal("0"))
        self.assertFalse(pc.precio_manual)

    def test_agregar_normal_usa_el_cobrado(self):
        # Sin ?usar=sugerido se agrega con el precio del método viejo (cobrado).
        self._cotizar()
        session = self.client.session
        session["vendedor"] = self.user.id
        session.save()
        self.client.get("/presupuestos/agregarProducto")
        pc = ProductoCotizado.objects.latest("id")
        self.assertEqual(pc.resultado, Decimal("15500"))

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


class SemaforoFase4Tests(TestCase):
    """Fase 4: info_prod_cotizado expone los snapshots para el semáforo, y editar
    marca precio_manual cuando el precio se fija a mano (precio arbitrario)."""

    def setUp(self):
        self.user = User.objects.create_superuser("v2", "v2@v.com", "pw12345")
        self.client.force_login(self.user)
        # info_prod_cotizado busca estos productos fantasma.
        Producto.objects.create(nombre="Mano de obra", precio_proveedor=Decimal("500"))
        Producto.objects.create(nombre="Empaquetado", precio_proveedor=Decimal("300"))
        prod = Producto.objects.create(
            nombre="X", precio=Decimal("100"), factor=Decimal("2"))
        self.pc = ProductoCotizado.objects.create(
            insumo=prod, cantidad=10, resultado=Decimal("5000"),
            t_produccion=Decimal("1"), precio_sugerido=Decimal("6000"),
            piso_absoluto=Decimal("2000"), piso_absorcion=Decimal("4000"))

    def test_info_incluye_snapshots(self):
        r = self.client.get(f"/presupuestos/infoProductoCotizado/{self.pc.id}/")
        j = r.json()
        self.assertEqual(Decimal(str(j["precio_sugerido"])), Decimal("6000"))
        self.assertEqual(Decimal(str(j["piso_absoluto"])), Decimal("2000"))
        self.assertEqual(Decimal(str(j["piso_absorcion"])), Decimal("4000"))
        self.assertEqual(j["cantidad"], 10)
        self.assertFalse(j["precio_manual"])

    def test_precio_arbitrario_marca_manual(self):
        self.client.post("/presupuestos/editarProductoCotizado/", {
            "id_producto": self.pc.id, "precio": "5500",
            "precio_arb_checkbox": "on", "info_adicional": "",
            "descuento": "0", "tiempo": "1", "subtotal": "5000", "resultado": "5000",
        })
        self.pc.refresh_from_db()
        self.assertTrue(self.pc.precio_manual)
        self.assertEqual(self.pc.resultado, Decimal("5500"))

    def test_precio_arbitrario_formato_ar(self):
        # El precio arbitrario llega en formato AR (con "$"): parse_ar lo tolera.
        self.client.post("/presupuestos/editarProductoCotizado/", {
            "id_producto": self.pc.id, "precio": "$ 3.499,00",
            "precio_arb_checkbox": "on", "info_adicional": "",
            "descuento": "0", "tiempo": "1", "subtotal": "5000", "resultado": "5000",
        })
        self.pc.refresh_from_db()
        self.assertEqual(self.pc.resultado, Decimal("3499.00"))
        self.assertTrue(self.pc.precio_manual)

    def test_precio_calculado_no_marca_manual(self):
        self.pc.precio_manual = True
        self.pc.save()
        self.client.post("/presupuestos/editarProductoCotizado/", {
            "id_producto": self.pc.id, "precio": "5000", "info_adicional": "",
            "descuento": "10", "tiempo": "1", "subtotal": "5000", "resultado": "4500",
        })
        self.pc.refresh_from_db()
        self.assertFalse(self.pc.precio_manual)
        self.assertEqual(self.pc.resultado, Decimal("4500"))


class PartirDisenoTests(TestCase):
    """Partir el diseño en franjas (tipos B/C): un lado queda entero y cada
    franja va con su largo a lo ancho del rollo."""

    def setUp(self):
        import tempfile
        from django.test import override_settings
        self._media = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        self._media.enable()
        self.addCleanup(self._media.disable)

    def test_calcular_franjas(self):
        from presupuestos.functions import calcular_franjas
        f = calcular_franjas(120, 400, 200, 5)
        self.assertEqual((f["n"], f["lado_entero"]), (3, 120))
        self.assertAlmostEqual(f["largo_franja"], 410 / 3)
        # Sin solapamiento, 2 franjas de exactamente el ancho.
        self.assertEqual(calcular_franjas(120, 400, 200, 0)["largo_franja"], 200)
        # Corta el lado corto si se pide; siempre al menos 2 franjas.
        f = calcular_franjas(120, 190, 200, 5, direccion="corto")
        self.assertEqual((f["n"], f["lado_entero"], f["largo_franja"]), (2, 190, 62.5))
        with self.assertRaises(ValueError):
            calcular_franjas(120, 400, 200, 200)

    def _partir(self, ancho, alto, cantidad=1, direccion="largo", tipo="B"):
        from presupuestos.functions import procesar_cotizacion_con_grafico
        return procesar_cotizacion_con_grafico(
            tipo, 200, 100000, ancho, alto, 0, cantidad, "Skyline",
            partir=True, solapamiento=5, direccion=direccion)

    def test_aprovecha_el_ancho_y_compara_con_sin_partir(self):
        r = self._partir(120, 400)
        self.assertAlmostEqual(r["valor_grafico"], 7.92)          # 3 × 120 cm de largo
        self.assertAlmostEqual(r["particion"]["valor_sin_partir"], 8.8)
        self.assertIn("Sin partir: 8,80 m²", r["mensaje"])

    def test_franjas_lado_a_lado_si_entran(self):
        # Dos franjas de 97,5 cm entran en 200 cm: una sola fila de 120 cm.
        self.assertAlmostEqual(self._partir(120, 190)["valor_grafico"], 2.64)

    def test_metros_lineales(self):
        r = self._partir(120, 400, tipo="C")
        self.assertAlmostEqual(r["valor_grafico"], 3.96)

    def test_diseno_que_no_entra_sin_partir(self):
        from presupuestos.functions import procesar_cotizacion_con_grafico
        r = procesar_cotizacion_con_grafico("B", 200, 100000, 250, 300, 0, 1, "Skyline")
        self.assertEqual(r["tipo"], "X")
        self.assertIn("Partir diseño", r["mensaje"])
        r = self._partir(250, 300)
        self.assertAlmostEqual(r["valor_grafico"], 11.0)
        self.assertIsNone(r["particion"]["valor_sin_partir"])

    def test_alternativa_solo_si_cambia_y_mejora(self):
        # 120×400: cortar el lado de 120 no mejora lo que se gasta sin partir.
        self.assertIsNone(self._partir(120, 400)["particion"]["alternativa"])
        # Con 4 copias, franjas de 62,5 cm (3 por fila) sí mejoran: se ofrece.
        alt = self._partir(120, 400, cantidad=4)["particion"]["alternativa"]
        self.assertEqual(alt["direccion"], "corto")
        self.assertAlmostEqual(alt["valor"], 26.4)
        # Desde 'corto' siempre se puede volver a 'largo'.
        alt = self._partir(120, 400, direccion="corto")["particion"]["alternativa"]
        self.assertEqual(alt["direccion"], "largo")

    def _partir_en(self, ancho_rollo, ancho, alto, cantidad, direccion):
        from presupuestos.functions import procesar_cotizacion_con_grafico
        return procesar_cotizacion_con_grafico(
            "B", ancho_rollo, 100000, ancho, alto, 0, cantidad, "Skyline",
            partir=True, solapamiento=5, direccion=direccion)

    def test_solo_se_parten_los_disenos_necesarios(self):
        # 3 lonas de 120×400 en 2 m cortando el lado corto: 2 van enteras y
        # solo una se parte (sus 2 franjas completan las dos filas).
        r = self._partir_en(200, 120, 400, 3, "corto")
        self.assertEqual(r["particion"]["partidas"], 1)
        self.assertAlmostEqual(r["valor_grafico"], 17.6)   # 2 filas de 400 cm
        self.assertIn("Se parte 1 de los 3 diseños", r["mensaje"])

    def test_no_partir_evita_que_el_solapamiento_reste_lugar(self):
        # En 185 cm entran 2 franjas de 62,5 por fila, no 3: partir todo da 3
        # filas; entero (120) + franja (62,5) entra en 2 filas.
        r = self._partir_en(185, 120, 400, 3, "corto")
        self.assertAlmostEqual(r["valor_grafico"], 1.85 * 8 * 1.1)

    def test_no_hace_falta_partir(self):
        r = self._partir_en(200, 120, 400, 1, "corto")
        self.assertEqual(r["particion"]["partidas"], 0)
        self.assertIn("No hace falta partir", r["mensaje"])
