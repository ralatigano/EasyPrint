import random
import string
from django.template.loader import get_template
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib.auth.models import User
import matplotlib.pyplot as plt
from rectpack import newPacker, PackingBin, SORT_AREA, GuillotineBssfMaxas
from presupuestos.models import Presupuesto
from productos.models import Producto, Categoria
import math
from datetime import datetime
from django.http import HttpResponse
import os
from django.contrib.staticfiles import finders


# Función que genera una contraseña aleatoria de 10 caracteres para que el usuario pueda ingresar
# cuando se ha olvidado su contraseña y una vez adentro, pueda acceder a cambiarla.


def generar_contrasena():
    caracteres = string.ascii_letters + string.digits + string.punctuation
    contrasena = ''.join(random.choice(caracteres) for _ in range(10))
    return contrasena


def notificar_contrasena(correo, usuario, contrasena):

    # tarea = Tareas.objects.get(id=tarea_id)
    # correo_encargado = User.objects.get(username=tarea.encargado).email
    # url_tarea = f'https://{settings.ALLOWED_HOSTS[0]}/core/explorarTarea/{tarea.nombre}'
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

# Función que permite averiguar cuantas etiquetas/stickers/elementos caben en una hoja o pliego de un determinado tammaño.


def calcular_cant_etiquetas_por_superficie(ancho_hoja, alto_hoja, ancho_elemento, alto_elemento, separacion):

    # Ajustamos las dimensiones del elemento para considerar la separación si es que hubiera
    ancho_elemento_ajustado = ancho_elemento + separacion
    alto_elemento_ajustado = alto_elemento + separacion

    # Creamos una instancia del empaquetador
    packer = newPacker(pack_algo=GuillotineBssfMaxas,
                       sort_algo=SORT_AREA, rotation=True)

    # Creamos un emboltorio (bin) con las dimensiones de la hoja
    packer.add_bin(ancho_hoja, alto_hoja)

    # Agregamos elementos al paquete. Intentamos agregar un número alto de elementos para averiguar cuantos entran.
    # Los elementos que intentamos agregar tienen que ser con las dimensiones ajustadas, de modo que se tenga en cuenta la separación si es que existe.
    num_elementos = 10000
    for _ in range(num_elementos):
        packer.add_rect(ancho_elemento_ajustado, alto_elemento_ajustado)

    # Empaquetamos
    packer.pack()

    # Iniciamos una lista para almacenar las etiquetas empaquetadas
    elementos_empaquetados = []

    for abin in packer:
        for rect in abin:
            rectangulo_ajustado = (
                rect.x, rect.y, rect.width - separacion, rect.height - separacion)
            elementos_empaquetados.append(rectangulo_ajustado)

    # Usamos len para averiguar cuantos elementos entraron.
    cant_elementos_empaquetados = len(elementos_empaquetados)

    # Crea una imagen de la superficie de la hoja con las etiquetas ubicadas
    fig, ax = plt.subplots()
    ax.set_xlim(0, ancho_hoja)
    ax.set_ylim(0, alto_hoja)

    # Crea un rectángulo para representar la superficie de la hoja
    rect = plt.Rectangle((0, 0), ancho_hoja, alto_hoja,
                         color='white', alpha=0.5)
    ax.add_patch(rect)

    # Draw the labels
    for rect in elementos_empaquetados:
        # Apply separation in the plot
        rect_x = rect[0] + separacion/2
        rect_y = rect[1] + separacion/2
        ax.add_patch(plt.Rectangle((rect_x, rect_y),
                                   rect[2], rect[3], fill=True, edgecolor='blue', facecolor='green', alpha=0.5))

    ax.set_xlim(0, ancho_hoja)
    ax.set_ylim(0, alto_hoja)
    ax.set_aspect('equal', adjustable='box')
    plt.gca().invert_yaxis()  # Invert y axis to match the coordinate system

    # Guarda el gráfico en un archivo HTML
    plt.savefig('surface.png')


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
    cant_area = float(request.POST['cant_area'])
    # print(f'cantidad obtener datos: {cantidad}')
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
            'cant_area': cant_area,
            't_produccion': t_produccion,
            'empaquetado': empaq,
            'precio': precio,
            'descuento': descuento,
            'factor': prod.factor,
            # 'desc_plata': desc_plata,
            # 'resultado': resultado
            })


def calc_precio(diccionario):
    costo_produccion = float(Producto.objects.get(codigo=125).precio)
    t_prod = diccionario['t_produccion'] if diccionario['t_produccion'] else 0
    cant_area = diccionario['cant_area'] if diccionario['cant_area'] else 1
    print(f'cant_area: {cant_area}')
    empaquetado_precio = 0
    empaquetado = 'No'
    if diccionario['empaquetado']:
        empaquetado_precio = float(Producto.objects.get(codigo=123).precio)
        empaquetado = 'Si'
    precio = round(diccionario['precio'] * diccionario['cantidad'] * cant_area * diccionario['factor'] +
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
        'cant_area': cant_area,
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
