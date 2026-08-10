"""Generación del PDF del comprobante y del QR de ARCA.

El QR sigue la especificación de ARCA (RG 4892): una URL
`https://www.afip.gob.ar/fe/qr/?p=<base64(json)>` con los datos del comprobante.
Se embebe como data-URI en el HTML para que weasyprint lo renderice sin acceder
a archivos externos.
"""
import base64
import io
import json
from decimal import Decimal

import qrcode
from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML

from core.utils import format_ar

QR_BASE = "https://www.afip.gob.ar/fe/qr/?p="


def format_cuit(numero):
    """Formatea un CUIT/CUIL de 11 dígitos como XX-XXXXXXXX-X."""
    s = str(numero or "").strip()
    if len(s) == 11 and s.isdigit():
        return f"{s[:2]}-{s[2:10]}-{s[10]}"
    return s

# Códigos de condición frente al IVA del receptor (ARCA) → etiqueta legible.
COND_IVA_LABELS = {
    1: "IVA Responsable Inscripto",
    4: "IVA Sujeto Exento",
    5: "Consumidor Final",
    6: "Responsable Monotributo",
    7: "Sujeto No Categorizado",
    13: "Monotributista Social",
}


def _qr_url(comprobante):
    """Arma la URL del QR de ARCA con los datos del comprobante autorizado."""
    datos = {
        "ver": 1,
        "fecha": comprobante.fecha_emision.strftime("%Y-%m-%d"),
        "cuit": settings.AFIP["CUIT"],
        "ptoVta": comprobante.punto_venta,
        "tipoCmp": comprobante.tipo_cbte,
        "nroCmp": comprobante.numero,
        "importe": float(comprobante.importe_total),
        "moneda": "PES",
        "ctz": 1,
        "tipoDocRec": comprobante.doc_tipo,
        "nroDocRec": comprobante.doc_nro,
        "tipoCodAut": "E",  # E = CAE
        "codAut": int(comprobante.cae),
    }
    payload = base64.b64encode(
        json.dumps(datos, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    return QR_BASE + payload


def _qr_data_uri(comprobante):
    """Genera el PNG del QR y lo devuelve como data-URI base64."""
    img = qrcode.make(_qr_url(comprobante))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


# Logos del emisor (isotipo + logotipo). Se embeben como data-URI para que
# weasyprint no dependa de rutas/servidor de estáticos (funciona igual en la VM).
# OJO case-sensitive en Linux: usar los nombres de archivo exactos.
_IMG_DIR = settings.BASE_DIR / "core" / "static" / "core" / "img" / "light"


def _img_data_uri(nombre):
    """Lee un PNG de la carpeta de imágenes y lo devuelve como data-URI (o '')."""
    ruta = _IMG_DIR / nombre
    try:
        b64 = base64.b64encode(ruta.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/png;base64,{b64}"


def _cantidad_fmt(cantidad):
    """Cantidad como entero si es redonda (200), o con decimales si no."""
    if cantidad == int(cantidad):
        return str(int(cantidad))
    return format_ar(cantidad)


def _construir_items(comprobante):
    """Arma las líneas de la factura.

    Estrategia "detallada con fallback": si el pedido proviene de un presupuesto
    y la suma de las líneas cotizadas coincide con el importe facturado, se
    detallan los ítems reales (cantidad + precio unitario). Si no (monto editado,
    parcial, o pedido sin presupuesto), se usa una única línea con el importe total.
    """
    from productos.models import ProductoCotizado

    pedido = comprobante.pedido
    total = comprobante.importe_total

    if pedido.presupuesto:
        cotizados = list(
            ProductoCotizado.objects.filter(presupuesto=pedido.presupuesto)
        )
        suma = sum((p.resultado for p in cotizados), Decimal("0"))
        # Sólo detallamos si los subtotales cierran con el importe facturado.
        if cotizados and abs(suma - total) <= Decimal("0.01"):
            items = []
            for p in cotizados:
                cant = p.cantidad or 1
                subtotal = p.resultado
                unitario = (subtotal / Decimal(str(cant))) if cant else subtotal
                items.append({
                    "descripcion": p.producto_final or p.descripcion or "—",
                    "cantidad": _cantidad_fmt(cant),
                    "unitario_fmt": format_ar(unitario),
                    "subtotal_fmt": format_ar(subtotal),
                })
            return items

    # Fallback: una sola línea con el importe total.
    concepto = (
        pedido.producto or pedido.descripcion or f"Pedido N° {pedido.numero}"
    ).strip()
    return [{
        "descripcion": concepto,
        "cantidad": "1",
        "unitario_fmt": format_ar(total),
        "subtotal_fmt": format_ar(total),
    }]


def render_pdf(comprobante):
    """Renderiza el comprobante a bytes de PDF. El comprobante debe estar autorizado."""
    pedido = comprobante.pedido

    # Documento del receptor: CUIT/CUIL con guiones; DNI/otros tal cual.
    if comprobante.doc_tipo in (80, 86):
        doc_receptor_fmt = format_cuit(comprobante.doc_nro)
    else:
        doc_receptor_fmt = str(comprobante.doc_nro)

    contexto = {
        "c": comprobante,
        "emisor": settings.AFIP_EMISOR,
        "cuit_emisor": format_cuit(settings.AFIP["CUIT"]),
        "doc_receptor_fmt": doc_receptor_fmt,
        "es_homologacion": comprobante.ambiente == "homologacion",
        "items": _construir_items(comprobante),
        "cond_iva_receptor_label": COND_IVA_LABELS.get(
            comprobante.cond_iva_receptor, "—"
        ),
        "es_consumidor_final": comprobante.doc_tipo == 99 or comprobante.doc_nro == 0,
        "importe_fmt": format_ar(comprobante.importe_total),
        "qr": _qr_data_uri(comprobante),
        "logo_isotipo": _img_data_uri("easy.png"),
        "logo_texto": _img_data_uri("Isologotipo_easy_light1.png"),
        # La "letra" del comprobante (C para monotributo) y el código AFIP
        # (3 dígitos, ej. 011 para Factura C).
        "letra": "C",
        "codigo_cbte": f"{comprobante.tipo_cbte:03d}",
        "pv_fmt": f"{comprobante.punto_venta:05d}",
        "nro_fmt": f"{comprobante.numero:08d}",
    }
    html_string = render_to_string("facturacion/comprobante_pdf.html", contexto)
    return HTML(string=html_string).write_pdf()
