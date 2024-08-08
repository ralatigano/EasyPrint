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
    # print('PRODUCTO: ' + request.POST['producto'])
    categoria = request.POST['categoria']
    cat = Categoria.objects.get(nombre=categoria)
    prod = Producto.objects.filter(resultado=0).get(codigo=prod_cod)
    # codigo = prod.codigo
    info_adic = request.POST['info_adic']
    cantidad = float(request.POST['cantidad'])
    t_produccion = float(request.POST['t_produccion'])
    if request.POST.get('empaquetado') == 'on':
        empaq = True
    else:
        empaq = False
    # ancho = int(request.POST['ancho'])
    # alto = int(request.POST['alto'])
    precio = float(prod.precio)
    descuento = int(request.POST['descuento'])
    # resultado = round((float(precio) * int(cantidad))
    # * (1 - descuento/100), 2)
    # desc_plata = round(cantidad * prod.precio * descuento / 100, 2)
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
            # 'desc_plata': desc_plata,
            # 'resultado': resultado
            })


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

# def cal_precio_papel(dict):
#     if dict['ancho'] == 0 and dict['alto'] == 0:
#         calculo = {'cant_x_hoja': 1, 'orientacion': 'unica', 'sobrante': 0}
#     else:
#         ancho = dict['ancho']
#         alto = dict['alto']
#         desc = dict['descuento']
#         q = dict['cantidad']
#         prod = Producto.objects.filter(
#             resultado=0).get(nombre=dict['producto'])
#         w = prod.ancho
#         l = prod.alto
#         # Caso hoja horizontal - tarjeta horizontal
#         cantx = math.trunc(w/ancho)
#         canty = math.trunc(l/alto)
#         canthoriz = cantx*canty
#         # Caso hoja horizontal - tarjeta vertical
#         cantx = math.trunc(w/alto)
#         canty = math.trunc(l/ancho)
#         cantvert = cantx*canty
#         if canthoriz > cantvert:
#             orientacion = 'horizontal'
#             cant_x_hoja = canthoriz
#         else:
#             orientacion = 'vertical'
#             cant_x_hoja = cantvert
#         if cant_x_hoja != 0:
#             cant_de_hojas = math.ceil(q/cant_x_hoja)
#             sobrante = (cant_de_hojas * cant_x_hoja) - q
#         dict['precio'] = round(cant_de_hojas * prod.precio, 0)
#         dict['resultado'] = round(
#             cant_de_hojas * prod.precio * (1 - desc/100), 0)
#         dict['desc_plata'] = round(cant_de_hojas * prod.precio * desc / 100, 0)
#         calculo = {'cant_de_hojas': cant_de_hojas, 'cant_x_hoja': cant_x_hoja,
#                    'orientacion': orientacion, 'sobrante': sobrante}
#     dict.update(calculo)
#     return dict


# def cal_precio_vinilo(dict):

#     pliegos = 1
#     ancho = dict['ancho']
#     alto = dict['alto']
#     desc = dict['descuento']
#     q = dict['cantidad']
#     prod = Producto.objects.filter(resultado=0).get(nombre=dict['producto'])
#     w = prod.ancho

#     # Ambas dimensiones superan el ancho del pliego, por lo tanto es necesario usar mas de uno.
#     if ancho > w and alto > w:
#         pliegos = min(math.ceil(ancho/w), math.ceil(alto/w))
#         if ancho > alto:
#             # por la ubicación que tendría el diseño en los pliegos, el alto se redefine según la cantidad de pliegos.
#             dict['alto'] = pliegos * w
#             superficie = round(ancho * pliegos * w, 2)/10000
#         else:
#             # por la ubicación que tendría el diseño en los pliegos, el ancho se redefine según la cantidad de pliegos.
#             dict['ancho'] = pliegos * w
#             superficie = round(alto * pliegos * w, 2)/10000
#     # El ancho es mayor que el ancho del pliego (pero el alto no), ubico el diseño de modo que el alto del diseño se corresponde con el ancho del pliego
#     # y el ancho del diseño se extiende en la longitud del pliego.
#     elif ancho > w:
#         dict['alto'] = ancho
#         dict['ancho'] = w
#         superficie = round(ancho * w, 2)/10000
#     # El alto es mayor que el ancho del pliego (pero el ancho no), ubico el diseño de modo que el ancho del diseño se corresponde con el ancho del pliego
#     # y el alto del diseño se extiende en la longitud del pliego.
#     elif alto > w:
#         dict['ancho'] = w
#         superficie = round(alto * w, 2)/10000
#     else:
#         superficie1 = round(ancho * w, 2)/10000
#         superficie2 = round(alto * w, 2)/10000
#         superficie = max(superficie1, superficie2)
#     dict['precio'] = round(superficie * prod.precio, 0)
#     dict['resultado'] = round(q * superficie * prod.precio * (1 - desc/100), 0)
#     dict['desc_plata'] = round(q * superficie * prod.precio * desc / 100, 0)
#     calculo = {'superficie': superficie, 'pliegos': pliegos}
#     dict.update(calculo)
#     return dict


# def cal_precio_lona_impresa(dict):
#     ancho = dict['ancho']
#     alto = dict['alto']
#     desc = dict['descuento']
#     q = dict['cantidad']
#     prod = Producto.objects.filter(resultado=0).get(nombre=dict['producto'])
#     superficie = round(ancho * alto, 2)/10000
#     dict['precio'] = round(superficie * prod.precio, 0)
#     dict['resultado'] = round(q * superficie * prod.precio * (1 - desc/100), 0)
#     dict['desc_plata'] = round(q * superficie * prod.precio * desc / 100, 0)
#     calculo = {'superficie': superficie}
#     dict.update(calculo)
#     return dict


# def cal_precio_stickers(dict):
#     ancho = dict['ancho']
#     alto = dict['alto']
#     desc = dict['descuento']
#     q = dict['cantidad']
#     prod = Producto.objects.filter(resultado=0).get(nombre=dict['producto'])
#     w = prod.ancho
#     cant_x_ancho = min(math.floor(w/ancho), math.floor(w/alto))
#     cant_filas = math.ceil(q/cant_x_ancho)
#     dict['ancho'] = w
#     dict['alto'] = cant_filas * min(alto, ancho)
#     superficie = round(w * cant_filas * min(alto, ancho), 2)/10000
#     dict['precio'] = superficie * prod.precio
#     dict['resultado'] = round(superficie * prod.precio * (1 - desc/100), 0)
#     dict['desc_plata'] = round(superficie * prod.precio * desc / 1000, 0)
#     calculo = {'superficie': superficie}
#     dict.update(calculo)
#     return dict


# def cal_precio_pulseras(dict):

#     desc = dict['descuento']
#     q = dict['cantidad']
#     prod = Producto.objects.filter(resultado=0).get(nombre=dict['producto'])
#     w = prod.ancho
#     cant_de_hojas = math.ceil(q / 10)
#     sobrante = (cant_de_hojas * 10) - q
#     dict['ancho'] = w
#     dict['alto'] = 2
#     dict['precio'] = cant_de_hojas * prod.precio
#     dict['resultado'] = round(cant_de_hojas * prod.precio * (1 - desc/100), 0)
#     dict['desc_plata'] = round(cant_de_hojas * prod.precio * desc / 1000, 0)
#     calculo = {'cant_de_hojas': cant_de_hojas, 'sobrante': sobrante}
#     dict.update(calculo)
#     return dict
