"""Helpers mínimos de SOAP sobre urllib (sin dependencias externas)."""
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


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
        with urllib.request.urlopen(req, timeout=30) as resp:
            return ET.fromstring(resp.read())
    except urllib.error.HTTPError as e:
        return ET.fromstring(e.read())
