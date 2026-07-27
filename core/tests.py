from decimal import Decimal

from django.test import TestCase

from core.utils import format_ar, parse_ar


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
