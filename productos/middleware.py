# productos/middleware.py
from productos.models import FaltanteInsumo


class FaltantesMiddleware:
    """
    En las pantallas de pedidos, stock e inicio deja en el request un resumen
    de los faltantes abiertos (cuántos insumos y cuántos pedidos) para la
    alerta de base.html, que enlaza a la vista de faltantes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.faltantes_resumen = None
        path = request.path
        en_vista_faltantes = path.startswith('/productos/insumos/faltantes')
        if not en_vista_faltantes and (
                path.startswith('/pedidos') or path.startswith('/productos/insumos')
                or path.startswith('/presupuestos/inicio')):
            abiertos = FaltanteInsumo.objects.filter(resuelto=False)
            insumos = abiertos.values('insumo').distinct().count()
            if insumos:
                request.faltantes_resumen = {
                    'insumos': insumos,
                    'pedidos': abiertos.exclude(pedido=None).values('pedido').distinct().count(),
                }

        return self.get_response(request)
