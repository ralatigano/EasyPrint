# productos/middleware.py
from productos.models import FaltanteInsumo


class FaltantesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith('/pedidos') or path.startswith('/productos/insumos') or path.startswith('/presupuestos/inicio'):
            faltantes = FaltanteInsumo.objects.filter(
                resuelto=False).select_related('insumo', 'pedido')
            request.faltantes_activos = faltantes
        else:
            request.faltantes_activos = []

        response = self.get_response(request)
        return response
