"""WSFEv1: facturación electrónica. Lecturas y solicitud de CAE.

NOTA: las lecturas (dummy / ultimo_autorizado / puntos_de_venta) están validadas.
`solicitar_cae` (FECAESolicitar) es la primera implementación y debe validarse
contra HOMOLOGACIÓN antes de confiar en producción — los puntos sensibles son el
orden de los campos del FECAEDetRequest y `CondicionIVAReceptorId` (obligatorio
desde 2024).
"""
import datetime

from . import config
from ._soap import find_all, find_text, post_soap
from .wsaa import obtener_ta

NS = "http://ar.gov.afip.dif.FEV1/"


class WSFEError(Exception):
    pass


def _auth_xml(ta):
    return (
        "<ar:Auth>"
        f"<ar:Token>{ta.token}</ar:Token>"
        f"<ar:Sign>{ta.sign}</ar:Sign>"
        f"<ar:Cuit>{config.cuit()}</ar:Cuit>"
        "</ar:Auth>"
    )


def _raise_on_errors(root):
    errs = find_all(root, "Err")
    if errs:
        raise WSFEError(
            "; ".join(f"{find_text(e, 'Code')}: {find_text(e, 'Msg')}" for e in errs)
        )
    fault = find_text(root, "faultstring")
    if fault:
        raise WSFEError(fault)


def _call(method, extra_xml="", con_auth=True):
    inner = _auth_xml(obtener_ta("wsfe")) if con_auth else ""
    soap = (
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:ar="http://ar.gov.afip.dif.FEV1/">'
        f"<soapenv:Body><ar:{method}>{inner}{extra_xml}</ar:{method}>"
        "</soapenv:Body></soapenv:Envelope>"
    )
    root = post_soap(config.url("wsfev1"), soap, soap_action=NS + method)
    _raise_on_errors(root)
    return root


# --- Lecturas --------------------------------------------------------------
def dummy():
    root = _call("FEDummy", con_auth=False)
    return {k: find_text(root, k) for k in ("AppServer", "DbServer", "AuthServer")}


def ultimo_autorizado(punto_venta, tipo_cbte):
    root = _call(
        "FECompUltimoAutorizado",
        f"<ar:PtoVta>{punto_venta}</ar:PtoVta><ar:CbteTipo>{tipo_cbte}</ar:CbteTipo>",
    )
    return int(find_text(root, "CbteNro"))


def puntos_de_venta():
    root = _call("FEParamGetPtosVenta")
    return [
        {
            "nro": find_text(pv, "Nro"),
            "emision": find_text(pv, "EmisionTipo"),
            "bloqueado": find_text(pv, "Bloqueado"),
        }
        for pv in find_all(root, "PtoVenta")
    ]


# --- Emisión ---------------------------------------------------------------
def solicitar_cae(
    *,
    punto_venta,
    tipo_cbte,
    concepto,
    doc_tipo,
    doc_nro,
    cond_iva_receptor,
    importe_total,
    cbtes_asoc=None,
    fecha=None,
):
    """Solicita un CAE (FECAESolicitar) para UN comprobante.

    Para Factura C (monotributo): ImpNeto = ImpTotal, sin IVA discriminado
    (no se envía el nodo <Iva>). El número lo determinamos como
    último autorizado + 1.
    """
    fecha = fecha or datetime.date.today()
    numero = ultimo_autorizado(punto_venta, tipo_cbte) + 1
    total = f"{importe_total:.2f}"

    # Fechas de servicio: obligatorias sólo si el concepto incluye servicios.
    fechas_servicio = ""
    if concepto in (2, 3):
        f = f"{fecha:%Y%m%d}"
        fechas_servicio = (
            f"<ar:FchServDesde>{f}</ar:FchServDesde>"
            f"<ar:FchServHasta>{f}</ar:FchServHasta>"
            f"<ar:FchVtoPago>{f}</ar:FchVtoPago>"
        )

    # Comprobantes asociados (para notas de crédito/débito).
    asoc_xml = ""
    if cbtes_asoc:
        items = "".join(
            "<ar:CbteAsoc>"
            f"<ar:Tipo>{c['tipo']}</ar:Tipo>"
            f"<ar:PtoVta>{c['punto_venta']}</ar:PtoVta>"
            f"<ar:Nro>{c['numero']}</ar:Nro>"
            "</ar:CbteAsoc>"
            for c in cbtes_asoc
        )
        asoc_xml = f"<ar:CbtesAsoc>{items}</ar:CbtesAsoc>"

    # Orden de los campos según el XSD de FEV1 (el .asmx valida la secuencia).
    det = (
        f"<ar:Concepto>{concepto}</ar:Concepto>"
        f"<ar:DocTipo>{doc_tipo}</ar:DocTipo>"
        f"<ar:DocNro>{doc_nro}</ar:DocNro>"
        f"<ar:CbteDesde>{numero}</ar:CbteDesde>"
        f"<ar:CbteHasta>{numero}</ar:CbteHasta>"
        f"<ar:CbteFch>{fecha:%Y%m%d}</ar:CbteFch>"
        f"<ar:ImpTotal>{total}</ar:ImpTotal>"
        "<ar:ImpTotConc>0.00</ar:ImpTotConc>"
        f"<ar:ImpNeto>{total}</ar:ImpNeto>"
        "<ar:ImpOpEx>0.00</ar:ImpOpEx>"
        "<ar:ImpTrib>0.00</ar:ImpTrib>"
        "<ar:ImpIVA>0.00</ar:ImpIVA>"
        f"{fechas_servicio}"
        "<ar:MonId>PES</ar:MonId>"
        "<ar:MonCotiz>1</ar:MonCotiz>"
        f"<ar:CondicionIVAReceptorId>{cond_iva_receptor}</ar:CondicionIVAReceptorId>"
        f"{asoc_xml}"
    )
    extra = (
        "<ar:FeCAEReq>"
        f"<ar:FeCabReq><ar:CantReg>1</ar:CantReg>"
        f"<ar:PtoVta>{punto_venta}</ar:PtoVta>"
        f"<ar:CbteTipo>{tipo_cbte}</ar:CbteTipo></ar:FeCabReq>"
        f"<ar:FeDetReq><ar:FECAEDetRequest>{det}</ar:FECAEDetRequest></ar:FeDetReq>"
        "</ar:FeCAEReq>"
    )
    root = _call("FECAESolicitar", extra)

    return {
        "numero": numero,
        "resultado": find_text(root, "Resultado"),  # A (aprobado) / R (rechazado)
        "cae": find_text(root, "CAE"),
        "cae_vto": find_text(root, "CAEFchVto"),  # YYYYMMDD
        "observaciones": [
            f"{find_text(o, 'Code')}: {find_text(o, 'Msg')}" for o in find_all(root, "Obs")
        ],
    }
