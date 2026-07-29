"""Orquestador de alto nivel: emite un Comprobante en borrador contra ARCA."""
import datetime

from ..models import Comprobante
from . import wsfev1


def emitir(comprobante):
    """Solicita el CAE para un Comprobante en borrador y lo actualiza.

    Lo deja en estado AUTORIZADO (con CAE y número asignado) o ERROR (con el
    motivo en `respuesta_afip`). Devuelve el comprobante actualizado.

    Nota de concurrencia: el número se calcula como último autorizado + 1. Si dos
    emisiones corrieran en paralelo podrían pedir el mismo número; ARCA rechaza el
    duplicado (la fuente de verdad de la numeración es ARCA, no la DB local).
    """
    cbtes_asoc = None
    if comprobante.es_nota and comprobante.comprobante_asociado_id:
        asoc = comprobante.comprobante_asociado
        cbtes_asoc = [
            {"tipo": asoc.tipo_cbte, "punto_venta": asoc.punto_venta, "numero": asoc.numero}
        ]

    resp = wsfev1.solicitar_cae(
        punto_venta=comprobante.punto_venta,
        tipo_cbte=comprobante.tipo_cbte,
        concepto=comprobante.concepto,
        doc_tipo=comprobante.doc_tipo,
        doc_nro=comprobante.doc_nro,
        cond_iva_receptor=comprobante.cond_iva_receptor,
        importe_total=comprobante.importe_total,
        cbtes_asoc=cbtes_asoc,
    )

    comprobante.respuesta_afip = resp
    if resp["resultado"] == "A":
        comprobante.numero = resp["numero"]
        comprobante.cae = resp["cae"]
        comprobante.cae_vencimiento = datetime.datetime.strptime(
            resp["cae_vto"], "%Y%m%d"
        ).date()
        comprobante.fecha_emision = datetime.date.today()
        comprobante.estado = Comprobante.Estado.AUTORIZADO
    else:
        # Rechazado: el número no fue asignado por ARCA, no lo persistimos.
        comprobante.estado = Comprobante.Estado.ERROR
    comprobante.save()
    return comprobante
