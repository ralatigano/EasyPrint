from django.test import TestCase



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
