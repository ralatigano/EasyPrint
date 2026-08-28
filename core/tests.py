from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core import costos
from core.models import CostoFijo, ParametrosProduccion
from core.utils import format_ar, parse_ar, parse_decimal_flexible


class ParseArTests(TestCase):
    """Regresión del bug: el precio del insumo se guardaba en 0 al editar
    desde el modal, porque el campo llegaba con formato "$ 1.234,56" y
    parse_ar no toleraba el símbolo de moneda ni los espacios."""

    def test_formato_moneda_con_simbolo(self):
        # El modal manda el precio con prefijo "$ " (ver Insumos.js).
        self.assertEqual(parse_ar("$ 350,50"), Decimal("350.50"))
        self.assertEqual(parse_ar("$ 1.234,56"), Decimal("1234.56"))
        self.assertEqual(parse_ar("  $  2.000,00  "), Decimal("2000.00"))

    def test_formato_ar_sin_simbolo(self):
        self.assertEqual(parse_ar("350,50"), Decimal("350.50"))
        self.assertEqual(parse_ar("1.234,56"), Decimal("1234.56"))

    def test_negativos(self):
        self.assertEqual(parse_ar("-1.500,25"), Decimal("-1500.25"))

    def test_valores_numericos(self):
        # Si ya es numérico no se reinterpretan separadores.
        self.assertEqual(parse_ar(1234.56), Decimal("1234.56"))
        self.assertEqual(parse_ar(350), Decimal("350"))

    def test_vacios_e_invalidos(self):
        self.assertEqual(parse_ar(""), Decimal("0.00"))
        self.assertEqual(parse_ar(None), Decimal("0.00"))
        self.assertEqual(parse_ar("abc"), Decimal("0.00"))

    def test_roundtrip_format_parse(self):
        # format_ar y parse_ar deben ser inversos entre sí.
        self.assertEqual(parse_ar(format_ar(1234.56)), Decimal("1234.56"))


class CostoFijoMontoMensualTests(TestCase):
    """La property monto_mensual normaliza cualquier periodicidad a mensual."""

    def test_mensual_es_directo(self):
        c = CostoFijo(monto=Decimal("1000"), periodicidad="mensual")
        self.assertEqual(c.monto_mensual, Decimal("1000"))

    def test_anual_se_divide_por_12(self):
        c = CostoFijo(monto=Decimal("1200"), periodicidad="anual")
        self.assertEqual(c.monto_mensual, Decimal("100"))

    def test_unico_se_amortiza(self):
        c = CostoFijo(monto=Decimal("1000"), periodicidad="unico",
                      meses_amortizacion=10)
        self.assertEqual(c.monto_mensual, Decimal("100"))

    def test_unico_amortizacion_cero_no_explota(self):
        # max(meses, 1) evita división por cero.
        c = CostoFijo(monto=Decimal("500"), periodicidad="unico",
                      meses_amortizacion=0)
        self.assertEqual(c.monto_mensual, Decimal("500"))


class TasaHoraTests(TestCase):
    """Regresión de la fórmula de la tasa horaria (ver PLAN_ESTRUCTURA_COSTOS.md)."""

    def setUp(self):
        # Solo suma las líneas activas, normalizadas a mensual.
        CostoFijo.objects.create(concepto="Alquiler", monto=Decimal("200000"),
                                 periodicidad="mensual", activo=True)
        CostoFijo.objects.create(concepto="Seguro anual", monto=Decimal("120000"),
                                 periodicidad="anual", activo=True)  # -> 10.000/mes
        CostoFijo.objects.create(concepto="Compra inactiva", monto=Decimal("999999"),
                                 periodicidad="mensual", activo=False)  # no cuenta

        p = ParametrosProduccion.load()
        p.operarios = 2
        p.horas_dia = Decimal("8")
        p.dias_mes = 22
        p.ratio_productivas = Decimal("0.700")
        p.save()

    def test_costo_fijo_mensual_solo_activos(self):
        self.assertEqual(costos.costo_fijo_mensual(), Decimal("210000"))

    def test_horas_disponibles(self):
        # 2 * 8 * 22
        self.assertEqual(costos.horas_disponibles_mes(), Decimal("352"))

    def test_horas_productivas(self):
        # 352 * 0.7
        self.assertEqual(costos.horas_productivas_mes(), Decimal("246.4"))

    def test_tasa_hora(self):
        # 210000 / 246.4
        self.assertAlmostEqual(costos.tasa_hora(), Decimal("852.2727272727"),
                               places=4)

    def test_tasa_hora_sin_horas_no_explota(self):
        # ratio 0 -> horas productivas 0 -> tasa 0, no ZeroDivisionError.
        p = ParametrosProduccion.load()
        p.ratio_productivas = Decimal("0")
        p.save()
        self.assertEqual(costos.tasa_hora(), Decimal("0"))


class ParseDecimalFlexibleTests(TestCase):
    """Regresión del bug: "0.75" tecleado a la inglesa en el ratio pasaba por
    parse_ar y valía 75, rompiendo el DecimalField (InvalidOperation / 500)."""

    def test_punto_es_decimal(self):
        self.assertEqual(parse_decimal_flexible("0.75"), Decimal("0.75"))
        self.assertEqual(parse_decimal_flexible("7.5"), Decimal("7.5"))

    def test_coma_es_decimal(self):
        self.assertEqual(parse_decimal_flexible("0,75"), Decimal("0.75"))

    def test_formato_ar_con_miles(self):
        self.assertEqual(parse_decimal_flexible("1.234,56"), Decimal("1234.56"))

    def test_numericos_directos(self):
        self.assertEqual(parse_decimal_flexible(0.7), Decimal("0.7"))
        self.assertEqual(parse_decimal_flexible(8), Decimal("8"))

    def test_invalidos_devuelven_none(self):
        # None, no 0: el llamador distingue "erróneo" de un 0 legítimo.
        self.assertIsNone(parse_decimal_flexible(""))
        self.assertIsNone(parse_decimal_flexible(None))
        self.assertIsNone(parse_decimal_flexible("abc"))


class GuardarParametrosProduccionViewTests(TestCase):
    """La vista valida rangos y nunca devuelve 500 por entrada inválida."""

    def setUp(self):
        self.user = User.objects.create_superuser("ger", "g@g.com", "pw12345")
        self.client.force_login(self.user)
        self.url = "/configuracion/costos/parametros"

    def test_ratio_fuera_de_rango_no_guarda(self):
        # ratio 6 debe rechazarse; el singleton queda en su default.
        resp = self.client.post(self.url, {
            "operarios": "2", "horas_dia": "8", "dias_mes": "22",
            "ratio_productivas": "6", "factor_correccion_tiempos": "1",
        })
        self.assertEqual(resp.status_code, 302)  # redirect, no 500
        self.assertEqual(ParametrosProduccion.load().ratio_productivas,
                         Decimal("0.700"))

    def test_ratio_con_punto_no_rompe_y_guarda(self):
        # "0.75" (a la inglesa) debe guardarse como 0.75, sin InvalidOperation.
        resp = self.client.post(self.url, {
            "operarios": "2", "horas_dia": "7.5", "dias_mes": "22",
            "ratio_productivas": "0.75", "factor_correccion_tiempos": "1.1",
        })
        self.assertEqual(resp.status_code, 302)
        p = ParametrosProduccion.load()
        self.assertEqual(p.ratio_productivas, Decimal("0.750"))
        self.assertEqual(p.horas_dia, Decimal("7.50"))

    def test_valores_ar_con_coma(self):
        resp = self.client.post(self.url, {
            "operarios": "1", "horas_dia": "8,5", "dias_mes": "20",
            "ratio_productivas": "0,7", "factor_correccion_tiempos": "1,25",
        })
        self.assertEqual(resp.status_code, 302)
        p = ParametrosProduccion.load()
        self.assertEqual(p.ratio_productivas, Decimal("0.700"))
        self.assertEqual(p.factor_correccion_tiempos, Decimal("1.25"))
