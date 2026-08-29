import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core import costos, capacidad
from core.models import CostoFijo, ParametrosProduccion, Feriado
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

    def test_trimestral_se_divide_por_3(self):
        c = CostoFijo(monto=Decimal("900"), periodicidad="trimestral")
        self.assertEqual(c.monto_mensual, Decimal("300"))

    def test_cuatrimestral_se_divide_por_4(self):
        c = CostoFijo(monto=Decimal("800"), periodicidad="cuatrimestral")
        self.assertEqual(c.monto_mensual, Decimal("200"))

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


class TiempoEstimadoTests(TestCase):
    """Regresión de la fórmula de tiempo estimado de la Fase 2 (fórmula 2.2):

        tiempo_estimado = (setup + unitario * cantidad_producto) * factor
    """

    def test_formula_basica(self):
        # (0.5 + 0.002 * 1000) * 1 = 2.5
        self.assertEqual(
            costos.tiempo_estimado(Decimal("0.5"), Decimal("0.002"),
                                   Decimal("1000"), Decimal("1")),
            Decimal("2.5"))

    def test_factor_correccion_multiplica_el_total(self):
        # (0.5 + 0.002 * 1000) * 1.2 = 3.0
        self.assertEqual(
            costos.tiempo_estimado(Decimal("0.5"), Decimal("0.002"),
                                   Decimal("1000"), Decimal("1.2")),
            Decimal("3.0"))

    def test_solo_setup(self):
        # Setup sin unitario: cantidad no influye.
        self.assertEqual(
            costos.tiempo_estimado(Decimal("1"), Decimal("0"),
                                   Decimal("500"), Decimal("1")),
            Decimal("1"))

    def test_acepta_tipos_no_decimal(self):
        # La función normaliza a Decimal aunque le pasen int/float/str.
        self.assertEqual(
            costos.tiempo_estimado(0.5, 0.002, 1000, 1),
            Decimal("2.5"))


class DiasHabilesTests(TestCase):
    """Fase 6.3: días hábiles = lun-vie menos feriados de la DB."""

    def test_semana_completa(self):
        # Lun 2024-01-01 a Vie 2024-01-05 = 5 días hábiles.
        self.assertEqual(capacidad.dias_habiles(date(2024, 1, 1), date(2024, 1, 5)), 5)

    def test_excluye_fin_de_semana(self):
        # Lun a Dom = 5 (sáb y dom no cuentan).
        self.assertEqual(capacidad.dias_habiles(date(2024, 1, 1), date(2024, 1, 7)), 5)

    def test_excluye_feriados(self):
        Feriado.objects.create(fecha=date(2024, 1, 1), descripcion="Año nuevo")
        self.assertEqual(capacidad.dias_habiles(date(2024, 1, 1), date(2024, 1, 5)), 4)

    def test_hasta_antes_de_desde(self):
        self.assertEqual(capacidad.dias_habiles(date(2024, 1, 5), date(2024, 1, 1)), 0)


class CapacidadTests(TestCase):
    """Fase 6.1: capacidad, carga comprometida y margen libre."""

    def setUp(self):
        p = ParametrosProduccion.load()
        p.operarios = 2
        p.horas_dia = Decimal("8")
        p.ratio_productivas = Decimal("0.5")
        p.save()

    def test_capacidad_hasta(self):
        # 5 días hábiles * 8 h * 2 operarios * 0.5 = 40 h.
        cap = capacidad.capacidad_hasta(date(2024, 1, 5), hoy=date(2024, 1, 1))
        self.assertEqual(cap, Decimal("40.0"))

    def test_evaluar_entrega_alcanza_y_no_alcanza(self):
        from pedidos.models import Pedido
        from presupuestos.models import Presupuesto
        from productos.models import Producto, ProductoCotizado

        prod = Producto.objects.create(nombre="P", precio=Decimal("100"))
        pre = Presupuesto.objects.create(numero=1)
        ProductoCotizado.objects.create(
            insumo=prod, presupuesto=pre, cantidad=1, t_produccion=Decimal("30"),
            resultado=Decimal("1000"))
        Pedido.objects.create(numero=1, presupuesto=1, precio=1000,
                              descripcion="x", estado="En proceso",
                              fecha_entrega=date(2024, 1, 5))

        # Capacidad 40 h, ya comprometidas 30 h -> libre 10 h.
        r = capacidad.evaluar_entrega(date(2024, 1, 5), 8, hoy=date(2024, 1, 1))
        self.assertEqual(r["capacidad"], Decimal("40.0"))
        self.assertEqual(r["carga_comprometida"], Decimal("30"))
        self.assertEqual(r["margen_libre"], Decimal("10.0"))
        self.assertTrue(r["alcanza"])       # 8 <= 10

        r2 = capacidad.evaluar_entrega(date(2024, 1, 5), 15, hoy=date(2024, 1, 1))
        self.assertFalse(r2["alcanza"])     # 15 > 10
        self.assertEqual(r2["faltante"], Decimal("5.0"))


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class FeriadosViewTests(TestCase):
    """Fase 6: pantalla de feriados (alta manual, borrado, agrupado, import).

    Se usa storage estático plano: los tests que renderizan la página no dependen
    del manifest de collectstatic.
    """

    def setUp(self):
        self.user = User.objects.create_superuser("gerf", "gf@g.com", "pw12345")
        self.client.force_login(self.user)

    def test_alta_manual(self):
        self.client.post("/configuracion/feriados",
                         {"fecha": "2026-12-25", "descripcion": "Navidad"})
        self.assertTrue(Feriado.objects.filter(fecha=date(2026, 12, 25)).exists())

    def test_alta_duplicada_no_crea_otro(self):
        Feriado.objects.create(fecha=date(2026, 1, 1), descripcion="Año nuevo")
        self.client.post("/configuracion/feriados",
                         {"fecha": "2026-01-01", "descripcion": "otro"})
        self.assertEqual(Feriado.objects.filter(fecha=date(2026, 1, 1)).count(), 1)

    def test_borrar(self):
        f = Feriado.objects.create(fecha=date(2026, 1, 1))
        self.client.post(f"/configuracion/feriados/borrar/{f.id}")
        self.assertFalse(Feriado.objects.filter(id=f.id).exists())

    def test_pagina_agrupa_por_mes(self):
        Feriado.objects.create(fecha=date(2026, 1, 1))
        Feriado.objects.create(fecha=date(2026, 5, 1))
        resp = self.client.get("/configuracion/feriados?anio=2026")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["meses"]), 2)  # enero y mayo

    def test_importar_desde_api_mockeada(self):
        payload = json.dumps([
            {"date": "2026-01-01", "localName": "Año Nuevo", "name": "New Year"},
            {"date": "2026-05-01", "localName": "Día del Trabajador", "name": "Labour"},
        ]).encode("utf-8")
        cm = MagicMock()
        cm.read.return_value = payload
        cm.__enter__.return_value = cm
        cm.__exit__.return_value = False
        with patch("urllib.request.urlopen", return_value=cm):
            self.client.post("/configuracion/feriados/importar", {"anio": "2026"})
        self.assertEqual(Feriado.objects.filter(fecha__year=2026).count(), 2)
        self.assertEqual(
            Feriado.objects.get(fecha=date(2026, 1, 1)).descripcion, "Año Nuevo")

    def test_importar_error_de_red_no_rompe(self):
        with patch("urllib.request.urlopen", side_effect=Exception("network")):
            resp = self.client.post("/configuracion/feriados/importar",
                                    {"anio": "2026"}, follow=True)
        self.assertEqual(resp.status_code, 200)  # redirige, no 500
        self.assertEqual(Feriado.objects.count(), 0)


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
            "margen_objetivo": "1.3", "horas_legacy": "1",
        })
        self.assertEqual(resp.status_code, 302)
        p = ParametrosProduccion.load()
        self.assertEqual(p.ratio_productivas, Decimal("0.750"))
        self.assertEqual(p.horas_dia, Decimal("7.50"))

    def test_valores_ar_con_coma(self):
        resp = self.client.post(self.url, {
            "operarios": "1", "horas_dia": "8,5", "dias_mes": "20",
            "ratio_productivas": "0,7", "factor_correccion_tiempos": "1,25",
            "margen_objetivo": "1,3", "horas_legacy": "1",
        })
        self.assertEqual(resp.status_code, 302)
        p = ParametrosProduccion.load()
        self.assertEqual(p.ratio_productivas, Decimal("0.700"))
        self.assertEqual(p.horas_dia, Decimal("8.50"))

    def test_margen_objetivo_se_guarda(self):
        self.client.post(self.url, {
            "operarios": "1", "horas_dia": "8", "dias_mes": "22",
            "ratio_productivas": "0,75", "factor_correccion_tiempos": "1",
            "margen_objetivo": "1,3", "horas_legacy": "1",
        })
        self.assertEqual(ParametrosProduccion.load().margen_objetivo,
                         Decimal("1.30"))

    def test_horas_legacy_se_guarda(self):
        self.client.post(self.url, {
            "operarios": "1", "horas_dia": "8", "dias_mes": "22",
            "ratio_productivas": "0,75", "factor_correccion_tiempos": "1",
            "margen_objetivo": "1,3", "horas_legacy": "2,5",
        })
        self.assertEqual(ParametrosProduccion.load().horas_legacy,
                         Decimal("2.50"))

    def test_horas_legacy_invalida_no_guarda(self):
        # Negativa debe rechazarse; queda el default 1,00.
        resp = self.client.post(self.url, {
            "operarios": "1", "horas_dia": "8", "dias_mes": "22",
            "ratio_productivas": "0,75", "factor_correccion_tiempos": "1",
            "margen_objetivo": "1,3", "horas_legacy": "-1",
        })
        self.assertEqual(resp.status_code, 302)  # no 500
        self.assertEqual(ParametrosProduccion.load().horas_legacy,
                         Decimal("1.00"))

    def test_margen_objetivo_invalido_no_guarda(self):
        # margen_objetivo 0 (o negativo) debe rechazarse; queda el default 1,30.
        resp = self.client.post(self.url, {
            "operarios": "1", "horas_dia": "8", "dias_mes": "22",
            "ratio_productivas": "0,75", "factor_correccion_tiempos": "1",
            "margen_objetivo": "0",
        })
        self.assertEqual(resp.status_code, 302)  # no 500
        self.assertEqual(ParametrosProduccion.load().margen_objetivo,
                         Decimal("1.30"))
