"""Padrón ARCA (ws_sr_padron_a13): consulta de razón social por CUIT.

Devuelve la razón social (persona jurídica) o apellido+nombre (persona física)
a partir de un CUIT, para autocompletar el receptor al facturar.

Detalles del servicio (tomados del WSDL oficial de homologación):
  - Servicio WSAA:  ws_sr_padron_a13
  - Endpoint homo:  https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA13
  - Endpoint prod:  https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA13
  - targetNamespace: http://a13.soap.ws.server.puc.sr/
  - Método:  getPersona(token, sign, cuitRepresentada, idPersona)  ·  SOAPAction vacío
  - Respuesta (persona): razonSocial | apellido + nombre | tipoPersona

⚠️ Requiere que el CUIT emisor tenga **adherido** el web service
`ws_sr_padron_a13` (homologación vía WSASS; producción vía Administrador de
Relaciones de Clave Fiscal). Mientras no esté adherido —o si el WS falla—,
`consultar()` devuelve `None` de forma defensiva y la emisión sigue funcionando
sin autocompletar.
"""
from . import config
from ._soap import find_text, post_soap
from .wsaa import WSAAError, obtener_ta

SERVICIO = "ws_sr_padron_a13"
NS = "http://a13.soap.ws.server.puc.sr/"


class PadronError(Exception):
    pass


def _url(ambiente=None):
    """URL del WS de padrón A13 según el ambiente activo."""
    amb = ambiente or config.ambiente_actual()
    # Configurable por settings.AFIP_URLS[amb]["padron_a13"]; si no está, se usa
    # el endpoint público estándar de ARCA.
    from django.conf import settings

    urls = settings.AFIP_URLS.get(amb, {})
    if "padron_a13" in urls:
        return urls["padron_a13"]
    if amb == "produccion":
        return "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA13"
    return "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA13"


def _razon_social_desde_persona(root):
    """Extrae la razón social del XML de respuesta (jurídica o física)."""
    razon = find_text(root, "razonSocial")
    if razon:
        return razon.strip()
    apellido = (find_text(root, "apellido") or "").strip()
    nombre = (find_text(root, "nombre") or "").strip()
    combinado = f"{apellido} {nombre}".strip()
    return combinado or None


def consultar(cuit):
    """Consulta el padrón A13. Devuelve un dict con el resultado.

    - Éxito:  {'ok': True, 'razon_social': str, 'condicion_iva': None}
    - Fallo:  {'ok': False, 'error': str}  (CUIT inexistente, no adherido, red…)

    Nunca propaga excepciones, para que el llamador (endpoint/UI) siempre reciba
    un resultado y la emisión —que no depende de esto— nunca se rompa.
    """
    cuit = "".join(ch for ch in str(cuit) if ch.isdigit())
    if len(cuit) != 11:
        return {"ok": False, "error": "El CUIT debe tener 11 dígitos."}

    try:
        ta = obtener_ta(SERVICIO)
    except WSAAError:
        return {
            "ok": False,
            "error": "No se pudo autenticar el servicio de padrón. Verificá que el "
            "CUIT tenga adherido 'ws_sr_padron_a13' en ARCA.",
        }
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "No se pudo autenticar contra ARCA."}

    soap = (
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
        f' xmlns:a13="{NS}">'
        "<soapenv:Body><a13:getPersona>"
        f"<token>{ta.token}</token>"
        f"<sign>{ta.sign}</sign>"
        f"<cuitRepresentada>{config.cuit()}</cuitRepresentada>"
        f"<idPersona>{cuit}</idPersona>"
        "</a13:getPersona></soapenv:Body></soapenv:Envelope>"
    )
    try:
        root = post_soap(_url(), soap, soap_action="")
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "No se pudo comunicar con el padrón de ARCA."}

    fault = find_text(root, "faultstring")
    if fault:
        # Fault de negocio de ARCA (p. ej. "La Clave (CUIT/CUIL) ... es inexistente").
        return {"ok": False, "error": fault.strip()}

    razon_social = _razon_social_desde_persona(root)
    if not razon_social:
        return {"ok": False, "error": "ARCA no devolvió razón social para ese CUIT."}
    # A13 no trae la condición de IVA de forma directa; se deja en None.
    return {"ok": True, "razon_social": razon_social, "condicion_iva": None}
