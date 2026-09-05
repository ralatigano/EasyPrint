"""Acumulado facturado contra el tope de la categoría de monotributo.

Alimenta el widget de la vista de comprobantes. FASE 1: el cálculo sale
**exclusivamente de los comprobantes emitidos por la app** (control de emisión
propia); no se consulta a ARCA. Si se emitieran comprobantes por fuera de la app
(portal de ARCA, otro sistema) el número de acá va a quedar corto.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.utils import timezone

from core.utils import format_ar

from ..models import Comprobante, ConfiguracionMonotributo
from . import config

# ── Ventana de recategorización ───────────────────────────────────────────────
# ARCA no evalúa 12 meses móviles ni el año calendario: evalúa la ventana de 12
# meses que corresponde a la PRÓXIMA recategorización (enero y julio). Estos
# meses de corte están como constantes porque ARCA los cambia cada tanto; si eso
# pasa se ajustan acá y el resto del cálculo sigue funcionando igual.

# Desde este mes (agosto) la ventana pasa a ser el año calendario en curso,
# porque la próxima recategorización es la de enero.
MES_DESDE_VENTANA_ANUAL = 8
# En enero la recategorización en curso evalúa el año anterior completo.
MES_RECATEGORIZACION_ENERO = 1
# De febrero a julio rige la ventana semestral: 1/7 del año anterior → 30/6 del
# actual (recategorización de julio).
MES_INICIO_VENTANA_SEMESTRAL = 7

# ── Semáforo del consumo del tope ─────────────────────────────────────────────
UMBRAL_ALERTA = 70    # % consumido a partir del cual la barra pasa a ámbar
UMBRAL_CRITICO = 90   # % consumido a partir del cual la barra pasa a rojo


def ventana_recategorizacion(fecha=None):
    """Ventana de 12 meses que evalúa la próxima recategorización.

    Devuelve ``(desde, hasta)`` como ``date``, ambos inclusive:

    - agosto a diciembre → 1/1 a 31/12 del año en curso.
    - enero              → 1/1 a 31/12 del año anterior.
    - febrero a julio    → 1/7 del año anterior a 30/6 del año en curso.
    """
    if fecha is None:
        fecha = timezone.localdate()

    anio, mes = fecha.year, fecha.month

    if mes >= MES_DESDE_VENTANA_ANUAL:
        return date(anio, 1, 1), date(anio, 12, 31)

    if mes == MES_RECATEGORIZACION_ENERO:
        return date(anio - 1, 1, 1), date(anio - 1, 12, 31)

    # Febrero a julio: semestre corrido. El fin se calcula como "el día anterior
    # al inicio de la ventana siguiente" para no depender de cuántos días tiene
    # el mes de cierre.
    desde = date(anio - 1, MES_INICIO_VENTANA_SEMESTRAL, 1)
    hasta = date(anio, MES_INICIO_VENTANA_SEMESTRAL, 1) - timedelta(days=1)
    return desde, hasta


def acumulado_facturado(desde, hasta, ambiente=None):
    """Suma los comprobantes autorizados emitidos entre ``desde`` y ``hasta``.

    - Solo cuenta comprobantes **autorizados** (los borradores, los rechazados y
      los anulados no computan).
    - Las notas de crédito **restan**; las notas de débito suman.
    - Filtra por ambiente de ARCA (por defecto el activo), para que los
      comprobantes de homologación no se mezclen con los reales.

    La suma se hace en una sola query agregada, no trayendo los comprobantes.
    """
    if ambiente is None:
        ambiente = config.ambiente_actual()

    # Signo por tipo: la nota de crédito es la única que descuenta.
    signo = Case(
        When(tipo_cbte=Comprobante.Tipo.NOTA_CREDITO_C, then=Value(Decimal("-1"))),
        default=Value(Decimal("1")),
        output_field=DecimalField(max_digits=15, decimal_places=2),
    )

    total = (
        Comprobante.objects.filter(
            estado=Comprobante.Estado.AUTORIZADO,
            ambiente=ambiente,
            fecha_emision__gte=desde,
            fecha_emision__lte=hasta,
        )
        .aggregate(total=Sum(F("importe_total") * signo))["total"]
    )
    return total or Decimal("0.00")


def _nivel(porcentaje):
    """Tramo del semáforo según el % consumido del tope."""
    if porcentaje >= UMBRAL_CRITICO:
        return "critico"
    if porcentaje >= UMBRAL_ALERTA:
        return "alerta"
    return "ok"


def resumen(fecha=None):
    """Todo lo que el widget necesita para renderizarse, ya formateado.

    Devuelve siempre un dict (nunca None): si la categoría/tope no están
    cargados, ``configurado`` es False y el widget muestra el estado
    "configurar categoría" en vez de la barra.
    """
    if fecha is None:
        fecha = timezone.localdate()

    cfg = ConfiguracionMonotributo.load()
    desde, hasta = ventana_recategorizacion(fecha)
    # El acumulado corre hasta hoy, o hasta el fin de la ventana si ya cerró.
    hasta_efectivo = min(hasta, fecha)

    facturado = acumulado_facturado(desde, hasta_efectivo)
    tope = cfg.tope_anual

    if cfg.configurado:
        porcentaje = float(facturado / tope * 100)
        restante = tope - facturado
    else:
        porcentaje = 0.0
        restante = Decimal("0.00")

    return {
        "configurado": cfg.configurado,
        "categoria": cfg.categoria,
        "tope": tope,
        "tope_fmt": format_ar(tope),
        "facturado": facturado,
        "facturado_fmt": format_ar(facturado),
        "restante": restante,
        "restante_fmt": format_ar(abs(restante)),
        "excedido": restante < 0,
        "porcentaje": round(porcentaje, 1),
        # Ancho de la barra: recortado a 0-100 y con punto decimal, porque va
        # dentro de un style="width: X%" y la localización es-AR usaría coma.
        "porcentaje_barra": f"{max(0.0, min(porcentaje, 100.0)):.2f}",
        "nivel": _nivel(porcentaje),
        "desde": desde,
        "hasta": hasta,
        "hasta_efectivo": hasta_efectivo,
        "actualizado": timezone.localtime(),
        "ambiente": config.ambiente_actual(),
        "categorias": ConfiguracionMonotributo.CATEGORIAS,
    }
