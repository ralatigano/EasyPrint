import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from clientes.functions import normalizar_cuit
from core.utils import parse_ar
from pedidos.models import Pedido

from .models import Comprobante
from .services import config, emision, padron, pdf
from .services.wsaa import WSAAError
from .services.wsfev1 import WSFEError

# Condición frente al IVA por defecto para consumidor final (código ARCA).
COND_IVA_CONSUMIDOR_FINAL = 5


def _actualizar_cliente_desde_factura(cliente, data, doc_tipo, doc_nro):
    """Actualiza el perfil del cliente con los datos editados en el modal de
    facturación. No pisa datos con vacíos ni toca el cliente "Consumidor final".
    """
    if not cliente or cliente.nombre == "Consumidor final":
        return
    campos = []
    razon_social = (data.get("razon_social") or "").strip()
    if razon_social and razon_social != cliente.razon_social:
        cliente.razon_social = razon_social
        campos.append("razon_social")
    nombre = (data.get("nombre") or "").strip()
    if nombre and nombre != cliente.nombre:
        cliente.nombre = nombre
        campos.append("nombre")
    negocio = (data.get("negocio") or "").strip()
    if negocio and negocio != (cliente.negocio or ""):
        cliente.negocio = negocio
        campos.append("negocio")
    # Sólo se guarda el documento como CUIT del cliente si es de tipo CUIT (80).
    if doc_tipo == Comprobante.DocTipo.CUIT:
        cuit = normalizar_cuit(doc_nro)
        if cuit is not None and cuit != cliente.cuit:
            cliente.cuit = cuit
            campos.append("cuit")
    if campos:
        cliente.save(update_fields=campos)


@login_required
def contexto_facturacion(request, pedido_numero):
    """Datos para armar el modal de facturación de un pedido (GET, JSON)."""
    pedido = get_object_or_404(Pedido, numero=pedido_numero)
    cliente = pedido.cliente

    comprobantes = [
        {
            "id": c.id,
            "tipo": c.tipo_cbte,
            "tipo_label": c.get_tipo_cbte_display(),
            "numero": c.numero_formateado,
            "estado": c.estado,
            "estado_label": c.get_estado_display(),
            "importe": str(c.importe_total),
            # Sólo una factura autorizada puede asociarse a una NC/ND.
            "asociable": c.estado == Comprobante.Estado.AUTORIZADO
            and c.tipo_cbte == Comprobante.Tipo.FACTURA_C,
        }
        for c in pedido.comprobantes.all()
    ]

    return JsonResponse(
        {
            "pedido": pedido_numero,
            "total": str(pedido.precio or 0),
            "cliente": {
                "id": cliente.id if cliente else None,
                "nombre": cliente.nombre if cliente else "",
                "negocio": cliente.negocio if cliente and cliente.negocio else "",
                "razon_social": cliente.razon_social if cliente else "",
                "referencia": cliente.referencia if cliente else "",
                "cuit": cliente.cuit if cliente and cliente.cuit else "",
                "condicion_iva": cliente.condicion_iva if cliente else None,
            },
            "comprobantes": comprobantes,
            "ambiente": config.ambiente_actual(),
            "punto_venta": config.punto_venta(),
        }
    )


@login_required
def consultar_padron(request, cuit):
    """Consulta la razón social de un CUIT en el padrón de ARCA (GET, JSON).

    Devuelve {ok, razon_social, condicion_iva} o {ok:False, error}. Es best-effort:
    ante cualquier fallo devuelve ok=False con el motivo, sin romper.
    """
    return JsonResponse(padron.consultar(cuit))


@login_required
@require_POST
def emitir_comprobante(request):
    """Crea un Comprobante en borrador y solicita el CAE a ARCA (POST, JSON)."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Solicitud inválida."}, status=400)

    pedido = get_object_or_404(Pedido, numero=data.get("pedido_numero"))
    tipo = int(data.get("tipo_cbte", Comprobante.Tipo.FACTURA_C))

    # Receptor: consumidor final o cliente identificado.
    if data.get("receptor") == "identificado":
        try:
            doc_tipo = int(data["doc_tipo"])
            doc_nro = int(data["doc_nro"])
            cond_iva = int(data["cond_iva_receptor"])
        except (KeyError, ValueError, TypeError):
            return JsonResponse(
                {"ok": False, "error": "Faltan datos del receptor identificado."},
                status=400,
            )
        # Persistir en el perfil del cliente los datos editados en el modal
        # (razón social, nombre, negocio y CUIT), sin pisar el registro genérico
        # "Consumidor final" ni sobrescribir con vacíos.
        _actualizar_cliente_desde_factura(pedido.cliente, data, doc_tipo, doc_nro)
        # Nombre del receptor: razón social si la hay, si no la referencia.
        receptor_nombre = (
            (data.get("razon_social") or "").strip()
            or (pedido.cliente.nombre_facturacion if pedido.cliente else "")
        )
    else:
        doc_tipo = Comprobante.DocTipo.CONSUMIDOR_FINAL
        doc_nro = 0
        cond_iva = COND_IVA_CONSUMIDOR_FINAL
        receptor_nombre = "Consumidor Final"

    importe = parse_ar(data.get("importe"))
    if importe <= 0:
        return JsonResponse(
            {"ok": False, "error": "El importe debe ser mayor a cero."}, status=400
        )

    # Comprobante asociado (obligatorio para notas de crédito/débito).
    asociado = None
    if tipo in (Comprobante.Tipo.NOTA_DEBITO_C, Comprobante.Tipo.NOTA_CREDITO_C):
        asociado = get_object_or_404(
            Comprobante, id=data.get("comprobante_asociado_id"), pedido=pedido
        )

    comprobante = Comprobante(
        pedido=pedido,
        comprobante_asociado=asociado,
        ambiente=config.ambiente_actual(),
        tipo_cbte=tipo,
        punto_venta=config.punto_venta(),
        concepto=Comprobante.Concepto.PRODUCTOS,
        importe_total=importe,
        doc_tipo=doc_tipo,
        doc_nro=doc_nro,
        cond_iva_receptor=cond_iva,
        receptor_nombre=receptor_nombre,
    )

    try:
        emision.emitir(comprobante)
    except (WSAAError, WSFEError) as e:
        return JsonResponse(
            {"ok": False, "error": f"ARCA rechazó la operación: {e}"}, status=502
        )
    except Exception as e:  # noqa: BLE001 - fallo de red/inesperado
        return JsonResponse(
            {"ok": False, "error": f"No se pudo comunicar con ARCA: {e}"}, status=502
        )

    if comprobante.estado == Comprobante.Estado.AUTORIZADO:
        return JsonResponse(
            {
                "ok": True,
                "comprobante_id": comprobante.id,
                "numero": comprobante.numero_formateado,
                "cae": comprobante.cae,
                "cae_vto": comprobante.cae_vencimiento.strftime("%d/%m/%Y"),
            }
        )

    return JsonResponse(
        {
            "ok": False,
            "error": "ARCA no autorizó el comprobante.",
            "observaciones": (comprobante.respuesta_afip or {}).get("observaciones", []),
        },
        status=422,
    )


@login_required
def lista_comprobantes(request):
    """Página global de comprobantes emitidos, con descarga de PDF."""
    from core.utils import format_ar

    comprobantes = list(
        Comprobante.objects.select_related("pedido", "pedido__cliente").all()
    )
    for c in comprobantes:
        c.importe_fmt = format_ar(c.importe_total)
    data = {
        "usuario": request.session.get("usuario_nombre"),
        "autorizado": request.session.get("autorizado"),
        "img": request.session.get("img"),
        "comprobantes": comprobantes,
        "ambiente": config.ambiente_actual(),
        "Estado": Comprobante.Estado,
    }
    return render(request, "facturacion/comprobantes.html", data)


@login_required
def comprobante_pdf(request, comprobante_id):
    """Descarga el PDF de un comprobante autorizado (con CAE y QR de ARCA)."""
    comprobante = get_object_or_404(Comprobante, id=comprobante_id)
    if comprobante.estado != Comprobante.Estado.AUTORIZADO or not comprobante.cae:
        return JsonResponse(
            {"ok": False, "error": "El comprobante no está autorizado."}, status=400
        )

    contenido = pdf.render_pdf(comprobante)
    filename = f"comprobante_{comprobante.numero_formateado}.pdf"
    response = HttpResponse(contenido, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
