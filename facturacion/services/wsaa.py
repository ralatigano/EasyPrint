"""WSAA: autenticación contra ARCA. Obtiene y cachea el Token de Acceso (TA).

Portado del hola-mundo ya validado contra homologación: firma un TRA como CMS
(PKCS#7, SHA256) con el certificado + clave, lo envía a WSAA y guarda el
Token/Sign resultante. El TA se cachea en DB y se reusa ~12 h (ARCA sólo entrega
un TA válido por CUIT+servicio).
"""
import base64
import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import Encoding, load_pem_private_key
from cryptography.hazmat.primitives.serialization.pkcs7 import (
    PKCS7Options,
    PKCS7SignatureBuilder,
)

from ..models import TokenAcceso
from . import config
from ._soap import find_text, post_soap


class WSAAError(Exception):
    pass


def _firmar_tra(service):
    now = datetime.datetime.now(datetime.timezone.utc).astimezone()
    gen = now - datetime.timedelta(minutes=10)  # margen por desfasaje de reloj
    exp = now + datetime.timedelta(minutes=10)
    tra = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<loginTicketRequest version="1.0"><header>'
        f"<uniqueId>{int(now.timestamp())}</uniqueId>"
        f"<generationTime>{gen.isoformat()}</generationTime>"
        f"<expirationTime>{exp.isoformat()}</expirationTime>"
        f"</header><service>{service}</service></loginTicketRequest>"
    ).encode("utf-8")

    cert_path, key_path = config.cert_path(), config.key_path()
    if not cert_path or not key_path:
        raise WSAAError(
            "Faltan AFIP_CERT_PATH / AFIP_KEY_PATH en la configuración (.env)."
        )
    cert = x509.load_pem_x509_certificate(Path(cert_path).read_bytes())
    key = load_pem_private_key(Path(key_path).read_bytes(), password=None)
    cms = (
        PKCS7SignatureBuilder()
        .set_data(tra)
        .add_signer(cert, key, hashes.SHA256())
        .sign(Encoding.DER, [PKCS7Options.Binary])
    )
    return base64.b64encode(cms).decode("ascii")


def _login(service):
    cms_b64 = _firmar_tra(service)
    soap = (
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:wsaa="http://wsaa.view.sua.dvadac.desein.afip.gov">'
        f"<soapenv:Body><wsaa:loginCms><wsaa:in0>{cms_b64}</wsaa:in0>"
        "</wsaa:loginCms></soapenv:Body></soapenv:Envelope>"
    )
    root = post_soap(config.url("wsaa"), soap)
    ret = find_text(root, "loginCmsReturn")
    if ret is None:
        raise WSAAError(find_text(root, "faultstring") or "respuesta inesperada de WSAA")
    lt = ET.fromstring(ret)
    return {
        "token": find_text(lt, "token"),
        "sign": find_text(lt, "sign"),
        "expiracion": datetime.datetime.fromisoformat(find_text(lt, "expirationTime")),
    }


def obtener_ta(service="wsfe"):
    """Devuelve un TokenAcceso vigente, reusando el cacheado o pidiendo uno nuevo."""
    amb = config.ambiente_actual()
    ta = TokenAcceso.objects.filter(ambiente=amb, servicio=service).first()
    if ta and ta.vigente():
        return ta
    data = _login(service)
    ta, _ = TokenAcceso.objects.update_or_create(
        ambiente=amb,
        servicio=service,
        defaults={
            "token": data["token"],
            "sign": data["sign"],
            "expiracion": data["expiracion"],
        },
    )
    return ta
