from .models import Producto


def comparar(c):
    prods = Producto.objects.all()
    for p in prods:
        if p.codigo == int(c):
            return True
