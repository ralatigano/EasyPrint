import re
from decimal import Decimal, InvalidOperation


def format_ar(valor, decimales=2):
    """Formatea un número al estilo argentino: 1.234,56"""
    formatted = f"{valor:,.{decimales}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def parse_ar(valor):
    """Convierte un string en formato argentino (1.234,56) a Decimal.

    Es tolerante con lo que llega desde la UI: acepta símbolos de moneda,
    espacios y otros caracteres no numéricos (ej: "$ 1.234,56"). Antes,
    cualquiera de esos caracteres hacía fallar la conversión y devolvía 0,
    lo que borraba el precio al guardar un insumo desde el modal.
    """
    if valor is None or valor == "":
        return Decimal("0.00")

    # Si ya es numérico, no reinterpretar separadores: convertir directo.
    if isinstance(valor, (int, float, Decimal)):
        try:
            return Decimal(str(valor))
        except InvalidOperation:
            return Decimal("0.00")

    # Descartar todo lo que no sea dígito, coma, punto o signo menos
    # (símbolos de moneda, espacios, letras, etc.).
    limpio = re.sub(r"[^\d,.\-]", "", str(valor))
    if not limpio:
        return Decimal("0.00")

    # Formato AR: el punto es separador de miles y la coma es decimal.
    limpio = limpio.replace(".", "").replace(",", ".")
    try:
        return Decimal(limpio)
    except InvalidOperation:
        return Decimal("0.00")


def parse_decimal_flexible(valor):
    """Convierte a Decimal un número *chico* (ratio, factor, horas) aceptando
    tanto la coma como el punto decimal, y devuelve ``None`` ante entrada inválida.

    A diferencia de :func:`parse_ar` (pensada para dinero, donde el punto es
    separador de miles), acá un punto solo se interpreta como separador decimal.
    Esto evita que un valor como "0.75" tecleado a la inglesa termine valiendo 75.
    Reglas:

    - Si aparecen coma y punto juntos ("1.234,56") se asume formato AR
      (punto = miles, coma = decimal).
    - Si solo hay coma ("0,75") la coma es el decimal.
    - Si solo hay punto ("0.75") el punto es el decimal.

    Devuelve ``None`` (no 0) cuando no puede parsear, para que el llamador
    distinga "vacío/erróneo" de un 0 legítimo y avise en vez de guardar basura.
    """
    if valor is None:
        return None
    if isinstance(valor, (int, float, Decimal)):
        try:
            return Decimal(str(valor))
        except InvalidOperation:
            return None

    limpio = re.sub(r"[^\d,.\-]", "", str(valor))
    if not limpio:
        return None

    if "," in limpio and "." in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    # Si solo hay punto (o ninguno), ya está en formato parseable por Decimal.

    try:
        return Decimal(limpio)
    except InvalidOperation:
        return None
