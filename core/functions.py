import random
import string
from django.template.loader import get_template
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from productos.models import Producto, Categoria


# Función que genera una contraseña aleatoria de 10 caracteres para que el usuario pueda ingresar
# cuando se ha olvidado su contraseña y una vez adentro, pueda acceder a cambiarla.


def generar_contrasena():
    caracteres = string.ascii_letters + string.digits + string.punctuation
    contrasena = ''.join(random.choice(caracteres) for _ in range(10))
    return contrasena

# Vista que envía el correo con la contraseña para que el usuario pueda ingresar al sistema.


def notificar_contrasena(correo, usuario, contrasena):

    template = get_template('core/correo_contrasena.html')
    data = {
        'usuario': usuario,
        'contrasena': contrasena,
    }
    content = template.render(data)

    email = EmailMultiAlternatives(
        'Nueva contraseña.',
        'Se ha solicitado restablecer la contraseña de esta cuenta.',
        'gerencia@connelec.com.ar',
        [correo],
    )

    email.attach_alternative(content, 'text/html')
    email.send()


# Obtiene los datos que vienen del formulario para convertirlos en un diccionario que sirve para crear el producto en la vista AgregarProducto.


def obtener_datos(request):
    np = request.POST['presupuesto']
    # if request.POST['cliente'] == '':
    #     cliente = 'Consumidor final'
    # else:
    # cliente = request.POST['cliente']
    prod_cod = request.POST['producto']
    categoria = request.POST['categoria']
    cat = Categoria.objects.get(id=categoria)
    prod = Producto.objects.filter(resultado=0).get(codigo=prod_cod)
    info_adic = request.POST['info_adic']
    cantidad_repeticion = float(request.POST['cantidad_repeticion'])
    cantidad_area = float(request.POST['cantidad_area'])
    t_produccion = float(request.POST['t_produccion'])
    if request.POST.get('empaquetado') == 'on':
        empaq = True
    else:
        empaq = False
    precio = float(prod.precio)
    descuento = int(request.POST['descuento']
                    ) if request.POST['descuento'] else 0
    return ({
            'np': np,
            # 'cliente': cliente,
            'codigo': prod.codigo,
            'producto': prod.nombre,
            'categoria': cat.nombre,
            'info_adic': info_adic,
            'cantidad_repeticion': cantidad_repeticion,
            'cantidad_area': cantidad_area,
            't_produccion': t_produccion,
            'empaquetado': empaq,
            'precio': precio,
            'descuento': descuento,
            'factor': prod.factor,
            })

# Función que toma datos del formulario inicial para calcular el precio de un producto al iniciar una cotización.


def calc_precio(diccionario):
    costo_produccion = float(Producto.objects.get(codigo=125).precio)
    t_prod = diccionario['t_produccion'] if diccionario['t_produccion'] else 0
    cant_area = diccionario['cantidad_area'] if diccionario['cantidad_area'] else 1
    empaquetado_precio = 0
    empaquetado = 'No'
    if diccionario['empaquetado']:
        empaquetado_precio = float(Producto.objects.get(codigo=123).precio)
        empaquetado = 'Si'
    precio = round(diccionario['precio'] * cant_area * diccionario['factor'] +
                   t_prod * costo_produccion + empaquetado_precio, 2)
    desc_plata = float(precio * diccionario['descuento'] / 100)
    resultado = precio - desc_plata
    producto = diccionario['producto']
    info_adic = diccionario['info_adic']
    cantidad_repeticion = diccionario['cantidad_repeticion']
    descuento = diccionario['descuento']
    return ({
        'precio': precio,
        'desc_plata': desc_plata,
        'resultado': resultado,
        'producto': producto,
        'info_adic': info_adic,
        'cantidad_repeticion': cantidad_repeticion,
        'cant_area': cant_area,
        'descuento': descuento,
        'empaquetado': empaquetado,
        't_produccion': t_prod,
    })
