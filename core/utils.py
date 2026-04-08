from decimal import Decimal, InvalidOperation


def format_ar(valor, decimales=2):
    """Formatea un número al estilo argentino: 1.234,56"""
    formatted = f"{valor:,.{decimales}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def parse_ar(valor):
    if not valor:
        return Decimal("0.00")
    limpio = str(valor).replace(".", "").replace(",", ".")
    try:
        return Decimal(limpio)
    except InvalidOperation:
        return Decimal("0.00")
