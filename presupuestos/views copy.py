from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from . models import Presupuesto
from django.contrib.auth.models import User
from django.contrib import messages
from .functions import *
from .prueba import calcular_cant_etiquetas_por_superficie
from productos.models import Producto, Categoria
from clientes.models import Cliente
from pedidos.models import Pedido
from django.http import JsonResponse
from django.conf import settings
import json
import os
from urllib.parse import unquote

# Create your views here.
app_name = 'presupuestos'

editando_presup = False
confirma = False
np_global = 0

# Página principal de la app para hacer una nueva cotización.


def Inicio(request):
    usuario = User.objects.get(username=request.user).get_full_name()
    try:
        # img = User.objects.get(username=request.user).usuario.image.url
        global editando_presup
        editando_presup = False
        global np_global
        total = 0
        descuento = 0
        totalNeto = 0
        np_global = 0
        pres = Presupuesto.objects.all()
        np = 0
        for p in pres:
            if p.numero > np:
                np = p.numero
        np = np + 1
        ListProds = Producto.objects.all()
        Prods = Producto.objects.filter(
            presupuesto=None).filter(resultado__gt=0)
        for p in Prods:
            total += p.resultado
            descuento += p.desc_plata
            totalNeto = total-descuento
        Cat = Categoria.objects.all()
        data = {
            'usuario': usuario,
            # 'img': img,
            'np': np,
            'Cat': Cat,
            'ListProds': ListProds,
            'Prods': Prods,
            'total': total,
            'desc_plata': descuento,
            'totalNeto': totalNeto
        }
    except:
        data = {'usuario': usuario}
    return render(request, 'presupuestos/inicio.html', data)


@login_required
def obtener_productos(request):
    categoria_nombre = request.GET.get('categoria_nombre')
    categoria = get_object_or_404(Categoria, nombre=categoria_nombre)
    productos = Producto.objects.filter(
        categoria=categoria).values('codigo', 'nombre')
    return JsonResponse({'productos': list(productos)})

# Vista que procesa la información ingresada en el modal que sirve para calcular la cantidad de hojas/pliegos que se requieren
# para imprimir una determinada cantidad de etiquetas.


@login_required
def calcular_cantidad_por_hoja(request):
    alto_hoja = int(request.POST.get('alto_hoja'))
    ancho_hoja = int(request.POST.get('ancho_hoja'))
    ancho_elemento = int(request.POST.get('ancho_elemento'))
    alto_elemento = int(request.POST.get('alto_elemento'))
    separacion = float(request.POST.get('separacion'))
    cant_deseada = int(request.POST.get('cant_deseada'))

    cant_resultado, relative_path, area_ocupada = calcular_cant_etiquetas_por_superficie(
        ancho_hoja, alto_hoja, ancho_elemento, alto_elemento, separacion, cant_deseada)

    img_path = os.path.join(settings.MEDIA_URL, relative_path)

    if cant_deseada != 0:
        cantidad_hojas = math.ceil(cant_deseada / cant_resultado)

    return JsonResponse({
        'img_hoja': img_path,
        'cant_resultado': cant_resultado,
        'cant_hojas': cantidad_hojas,
        'area_ocupada': area_ocupada})

# Vista que procesa una llamadas desde el frontend para borrar una imagen generada en el modal de cálculo de cantidad de hojas.


@login_required
@csrf_exempt
def borrar_imagen_generada(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        img_path = data.get('imgPath', '')
        img_path = unquote(img_path)
        img_name = img_path.split('/media/')[-1]

        if img_name:
            try:
                # Construye el path absoluto en el servidor
                img_abs_path = os.path.abspath(
                    os.path.join(settings.MEDIA_ROOT, img_name))

                # Verifica si el archivo existe y lo borra
                if os.path.exists(img_abs_path):
                    os.remove(img_abs_path)
                    return JsonResponse({'message': f'Imagen {img_path} eliminada correctamente.'})
                else:
                    return JsonResponse({'message': f'La imagen {img_path} no existe en el servidor.'}, status=404)
            except Exception as e:
                return JsonResponse({'message': f'Error al intentar eliminar la imagen: {str(e)}'}, status=500)
        else:
            return JsonResponse({'message': 'No se proporcionó la ruta de la imagen a eliminar.'}, status=400)
    else:
        return JsonResponse({'message': 'Método no permitido.'}, status=405)


@login_required
def presupuestos(request):
    Pres = Presupuesto.objects.order_by('-numero').all()
    usuario = User.objects.get(username=request.user).get_full_name()
    try:
        img = User.objects.get(username=request.user).usuario.image.url
        data = {
            'Pres': Pres,
            'usuario': usuario,
            'img': img,
        }
    except:
        data = {
            'Pres': Pres,
            'usuario': usuario
        }
    return render(request, 'presupuestos/presupuestos.html', data)


@login_required
# Recibe el diccionario desde ObetenerDatos y envía la información al frontend para mostrarla en un modal donde se decide si se agrega el producto al presupuesto o se descarta.
def agregar_producto(request):
    global editando_presup
    global np_global
    dict = {}
    costo = {}
    dict = obtener_datos(request)
    # caso_part = Producto.objects.filter(resultado=0).get(
    #     codigo=dict['codigo']).caso_part
    # if caso_part:
    #     costo = dict
    # else:
    costo_produccion = Producto.objects.get(codigo=125).precio
    empaquetado = 0
    costo['empaquetado'] = 'No'
    if dict['empaquetado']:
        empaquetado = Producto.objects.get(codigo=123).precio
        costo['empaquetado'] = 'Si'
    precio = round(dict['precio'] * dict['cantidad'] +
                   dict['t_produccion'] * costo_produccion + empaquetado, 2)
    costo['desc_plata'] = precio * dict['descuento'] / 100
    costo['resultado'] = precio - costo['desc_plata']
    # costo['cliente'] = dict['cliente']
    costo['producto'] = dict['producto']
    # costo['categoria'] = dict['categoria']
    costo['info_adic'] = dict['info_adic']
    costo['cantidad'] = dict['cantidad']
    costo['descuento'] = dict['descuento']
    # print(costo)

    if editando_presup:
        url = f'/verPresupuesto/{np_global}'
        costo['url'] = url

    else:
        url = '/'
        costo['url'] = url
        # Producto.objects.create(
        #     presupuesto=None,
        #     cliente=costo['cliente'],
        #     nombre=costo['producto'],
        #     categoria=Categoria.objects.get(nombre=costo['categoria']),
        #     info_adic=costo['info_adic'],
        #     cantidad=costo['cantidad'],
        #     precio=precio,
        #     desc_porcentaje=costo['descuento'],
        #     desc_plata=costo['desc_plata'],
        #     resultado=costo['resultado']
        # )
        # costo['codigo'] = Producto.objects.last().codigo
        # return render(request, 'presupuestos/nuevo_calculo.html', costo)
    return JsonResponse({
        'producto': costo['producto'],
        # 'codigo': costo['codigo'],
        'cantidad': costo['cantidad'],
        'precio': costo['resultado'],
        'descuento': costo['descuento'],
        'detalle': costo['info_adic'],
        'empaquetado': costo['empaquetado'],
    })
# Esta vista y la de EditarProducto son las que ayudan a editar un producto que está incluido en el presupuesto que se está elaborando.


def edit_calc_presupuesto(request, r):
    prod = Producto.objects.get(codigo=r)
    Prods = Producto.objects.all()
    data = {
        'Prods': Prods,
        'prod': prod
    }
    return render(request, 'core/Editar_Item.html', data)  # (Editar_Item)


def editar_producto(request):
    # obtengo el producto a editar desde el request y lo traigo de la BD.
    codigo = request.POST['codigo']
    prod = Producto.objects.get(codigo=codigo)
    # Recibo los datos que podrían haberse modificado.
    producto = request.POST['edit_producto']
    info_adic = request.POST['info_adic']
    cantidad = int(request.POST['cantidad'])
    descuento = int(request.POST['descuento'])
    # Modifico el objeto del modelo con los nuevos datos:
    if prod.nombre != producto:
        prod.nombre = producto
        n_prod = Producto.objects.filter(
            prod.resultado == 0).get(nombre=producto)
        prod.precio = n_prod.precio
    prod.info_adic = info_adic
    prod.cantidad = cantidad
    prod.desc_porcentaje = descuento
    prod.resultado = (int(cantidad)*float(prod.precio))*(1 - descuento/100)
    prod.desc_plata = cantidad * prod.precio * descuento / 100
    prod.save()
    if editando_presup:
        return redirect(f'/presupuestos/verPresupuesto/{np_global}')
    else:
        return redirect('/presupeustos/inicio')
# Borra un ítem particular del presupuesto que se esta armando.


def delete_calc_presupuesto(request, r):
    prod = Producto.objects.get(codigo=r)
    prod.delete()
    if editando_presup:
        return redirect(f'/presupuestos/verPresupuesto/{np_global}')
    else:
        return redirect('/presupeustos/inicio')
# Borra todos los ítems del presupuesto que se está armando./Borra los elementos de la BD que no tienen un presupuesto asociado.


def destroy_calc_presupuesto(request):
    Calcs = Producto.objects.filter(presupuesto=None).filter(resultado__gt=0)
    for c in Calcs:
        if c.presupuesto != 0:
            c.delete()
    if editando_presup:
        pass
    else:
        return redirect('/')


def guardar_presupuesto(request):
    global editando_presup
    global np_global
    t = 0
    d = 0
    n_presupuesto = 3000000000 + Presupuesto.objects.count()
    if editando_presup:
        # Busco el presupuesto que estoy editando con ayuda de la variable global
        pre_v = Presupuesto.objects.get(numero=np_global)
        # Creo un nuevo presupuesto con el mismo cliente que el del presupuesto que estaba editando
        pre_n = Presupuesto.objects.create(
            numero=n_presupuesto,
            cliente=pre_v.cliente,
        )
        Prods = Producto.objects.filter(presupuesto=np_global)
        for p in Prods:
            p.presupuesto = Presupuesto.objects.get(numero=n_presupuesto)
            t = t + p.resultado
            d = d + p.desc_plata
            c = p.cliente
            p.save()
        # Actualizo el presupuesto con el valor total
        pre_n.total = t
        pre_n.save()

        return redirect('/Presupuestos')
    else:
        c = ''
        # Creo el presupuesto solo con el número de modo de poder asignárselo a los productos que perteneceran al nuevo presupuesto
        Presupuesto.objects.create(
            numero=n_presupuesto,
            cliente=None,
        )
        Prods = Producto.objects.all()
        for p in Prods:
            if p.presupuesto == None and p.resultado != 0:
                p.presupuesto = Presupuesto.objects.get(numero=n_presupuesto)
                t = t + p.resultado
                d = d + p.desc_plata
                c = p.cliente
                p.save()
        # Traigo el cliente desde la base de datos si es que existe y si no lo creo solo con nombre
        try:
            cli = Cliente.objects.get(nombre=c)
            # Actualizo el presupuesto con el valor total y el nombre del cliente
            pre = Presupuesto.objects.get(numero=n_presupuesto)
            pre.cliente = Cliente.objects.get(nombre=cli)
            pre.total = t
            pre.desc_plata = d
            pre.save()
        # Si el cliente no existe en la base de datos lo crea y actualiza la info del presupuesto
        except:
            Cliente.objects.create(
                nombre=c
            )
            # Actualizo el presupuesto con el valor total y el nombre del cliente
            pre = Presupuesto.objects.get(numero=n_presupuesto)
            pre.cliente = Cliente.objects.get(nombre=c)
            pre.total = t
            pre.desc_plata = d
            pre.save()
        # Si se utiliza el botón de generar pedido desde la vista de Inicio la bandera confirma es True para renderizar el template 'Completar_Pedido'.
        if confirma:
            n_ped = armar_numero_pedido()
            Prods = Producto.objects.filter(presupuesto=n_presupuesto)
            lista = []
            for p in Prods:
                lista.append(f'{p.cantidad} {p.nombre}')
            data = {
                'np': n_presupuesto,
                'n_ped': n_ped,
                'cliente': c,
                'prods': lista,
                'total': t
            }
            return render(request, 'core/Completar_Pedido.html', data)
        else:
            # si no se utiliza el botón de generar pedido se redirecciona a la vista de Inicio después de crear el presupuesto con el botón 'Guardar presupuesto'.
            return redirect('/')
# Permite ver los elementos de un presupuesto para editarlos o para agregar mas ítems. Al guardar se generará un nuevo presupuesto.


def editar_presupuesto(request, np):
    global editando_presup
    editando_presup = True
    global np_global
    np_global = np
    Prods = Producto.objects.all()
    pres = Presupuesto.objects.get(numero=np)
    cli = pres.cliente
    Cat = Categoria.objects.all()
    data = {
        'Cat': Cat,
        'Prods': Prods,
        'np': np,
        'cli': cli,
    }
    return render(request, 'core/Editar_Presupuesto.html', data)

# Renderiza un formulario para completar detalles de un nuevo pedido. Crea un presupuesto. Registra un cliente si es nuevo.


def completar_pedido(request):
    global editando_presup
    n_ped = armar_numero_pedido()

    if editando_presup:
        Prods = Producto.objects.filter(presupuesto=np_global)
        lista = []
        for p in Prods:
            lista.append(f'{p.cantidad} {p.nombre}')
        cli = Presupuesto.objects.get(numero=np_global).cliente
        total = Presupuesto.objects.get(numero=np_global).total
        data = {
            'n_ped': n_ped,
            'np': np_global,
            'prods': lista,
            'cli': cli,
            'total': total
        }
        return render(request, 'core/Completar_Pedido.html', data)
    else:
        global confirma
        confirma = True
        return redirect('/GuardarPresupuesto')

# Crea un nuevo pedido con la info que se carga en el formulario del template Completar_Pedido.


def confirmar_pedido(request):
    pre = request.POST['total']
    se = request.POST['senia']
    list_p = []
    Prods = Producto.objects.filter(presupuesto=request.POST['n_presupuesto'])
    for p in Prods:
        list_p.append(f'{p.cantidad} {p.nombre},')
    print('ESTADO: ' + request.POST['estado'])
    Pedido.objects.create(
        numero=request.POST['n_pedido'],
        producto=list_p,
        descripcion=request.POST['info_adic'],
        precio=float(pre.replace(',', '.')),
        senia=float(se.replace(',', '.')),
        saldo=float(pre.replace(',', '.')) - float(se.replace(',', '.')),
        estado=request.POST['estado'],
        presupuesto=request.POST['n_presupuesto'],
        cliente=Presupuesto.objects.get(
            numero=request.POST['n_presupuesto']).cliente,
    )
    return redirect('/Pedidos')
