from .models import Producto

# Función que compara los ids de un producto para establecer si existe o no en la base de datos.


def comparar(c):
    prods = Producto.objects.all()
    for p in prods:
        if p.codigo == int(c):
            return True
