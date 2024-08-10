from .models import Presupuesto
from productos.models import Producto, Categoria
import math
from datetime import datetime
from django.template.loader import get_template
from django.http import HttpResponse
from django.conf import settings
import os
from django.contrib.staticfiles import finders

# Obtiene los datos que vienen del formulario para convertirlos en un diccionario que sirve para crear el producto en la vista AgregarProducto.


def obtener_datos(request):
    np = request.POST['n_presupuesto']
    if request.POST['cliente'] == '':
        cliente = 'Consumidor final'
    else:
        cliente = request.POST['cliente']
    prod_cod = request.POST['producto']
    categoria = request.POST['categoria']
    cat = Categoria.objects.get(nombre=categoria)
    prod = Producto.objects.filter(resultado=0).get(codigo=prod_cod)
    info_adic = request.POST['info_adic']
    cantidad = float(request.POST['cantidad'])
    t_produccion = float(request.POST['t_produccion'])
    if request.POST.get('empaquetado') == 'on':
        empaq = True
    else:
        empaq = False
    precio = float(prod.precio)
    descuento = int(request.POST['descuento'])
    return ({
            'np': np,
            'cliente': cliente,
            'codigo': prod.codigo,
            'producto': prod.nombre,
            'categoria': cat.nombre,
            'info_adic': info_adic,
            'cantidad': cantidad,
            't_produccion': t_produccion,
            'empaquetado': empaq,
            'precio': precio,
            'descuento': descuento,
            })

# Función que calcula el precio de un producto al iniciar una cotización usando la información que viene en el diccionario.


def calc_precio(diccionario):
    costo_produccion = float(Producto.objects.get(codigo=125).precio)
    t_prod = diccionario['t_produccion'] if diccionario['t_produccion'] else 0
    empaquetado_precio = 0
    empaquetado = 'No'
    if diccionario['empaquetado']:
        empaquetado_precio = float(Producto.objects.get(codigo=123).precio)
        empaquetado = 'Si'
    precio = round(diccionario['precio'] * diccionario['cantidad'] +
                   t_prod * costo_produccion + empaquetado_precio, 2)
    desc_plata = float(precio * diccionario['descuento'] / 100)
    resultado = precio - desc_plata
    producto = diccionario['producto']
    info_adic = diccionario['info_adic']
    cantidad = diccionario['cantidad']
    descuento = diccionario['descuento']
    return ({
        'precio': precio,
        'desc_plata': desc_plata,
        'resultado': resultado,
        'producto': producto,
        'info_adic': info_adic,
        'cantidad': cantidad,
        'descuento': descuento,
        'empaquetado': empaquetado,
        't_produccion': t_prod,
    })

# Lógica que genera un nuevo número de pedido en función de la fecha.


def armar_numero_pedido():
    d = datetime.now()
    if d.month < 10:
        m = '0' + str(d.month)
    else:
        m = str(d.month)
    if d.day < 10:
        day = '0' + str(d.day)
    else:
        day = str(d.day)

    if d.hour < 10:
        h = '0' + str(d.hour)
    else:
        h = str(d.hour)
    if d.minute < 10:
        min = '0' + str(d.minute)
    else:
        min = str(d.minute)
    if d.second < 10:
        s = '0' + str(d.second)
    else:
        s = str(d.second)
    return f'{d.year}{m}{day}{h}{min}{s}'
