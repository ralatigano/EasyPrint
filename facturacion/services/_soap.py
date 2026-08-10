"""Helpers mínimos de SOAP sobre urllib (sin dependencias externas)."""
import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


def _arca_ssl_context():
    """Contexto SSL tolerante para los web services de ARCA.

    Los servidores de ARCA (AFIP) negocian con parámetros Diffie-Hellman chicos
    que OpenSSL 3 (ej. Ubuntu 24.04) rechaza por defecto con
    `DH_KEY_TOO_SMALL`. Bajamos el nivel de seguridad a SECLEVEL=1 SÓLO para
    estas conexiones (post_soap se usa exclusivamente contra ARCA), manteniendo
    la validación de certificado del servidor.
    """
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    except ssl.SSLError:
        pass
    return ctx


_SSL_CONTEXT = _arca_ssl_context()


def localname(tag):
    """Nombre de la etiqueta sin el namespace (`{ns}Tag` -> `Tag`)."""
    return tag.rsplit("}", 1)[-1]


def find_text(root, name):
    """Texto del primer elemento cuyo local-name es `name` (o None)."""
    for el in root.iter():
        if localname(el.tag) == name:
            return el.text
    return None


def find_all(root, name):
    """Todos los elementos cuyo local-name es `name`."""
    return [el for el in root.iter() if localname(el.tag) == name]


def post_soap(url, body, soap_action=""):
    """POST de un envelope SOAP. Devuelve el XML parseado (ElementTree).

    Los SOAP faults de ARCA llegan como HTTP 500 con el detalle en el body,
    así que también se parsean y se devuelven para que el caller los inspeccione.
    """
    data = body.encode("utf-8") if isinstance(body, str) else body
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": soap_action,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CONTEXT) as resp:
            return ET.fromstring(resp.read())
    except urllib.error.HTTPError as e:
        return ET.fromstring(e.read())
