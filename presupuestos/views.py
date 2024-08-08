from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from . models import Presupuesto
from django.contrib.auth.models import User
from core.models import Usuario
from django.contrib import messages
from core.functions import *
from .prueba import calcular_cant_etiquetas_por_superficie
from productos.models import Producto, Categoria
from clientes.models import Cliente
from django.http import JsonResponse
from django.conf import settings
import json
import os
from urllib.parse import unquote
from django.contrib.sessions.models import Session
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from datetime import date

# Create your views here.
app_name = 'presupuestos'

# editando_presup = False
# confirma = False
# np_global = 0

# Página principal de la app para hacer una nueva cotización.


def Inicio(request):
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')
    request.session['confirma'] = False
    request.session['editando_presup'] = False
    total = 0
    descuento = 0
    totalNeto = 0
    vendedor = request.session.get('vendedor')
    # np_global = 0
    pres = Presupuesto.objects.all()
    # np = 0
    np = max(p.numero for p in pres) + 1 if pres else 1
    request.session['np_global'] = np
    # ListProds = Producto.objects.all()
    Prods = Producto.objects.filter(
        presupuesto=None).filter(vendedor=vendedor)
    for p in Prods:
        total += p.precio
        descuento += p.desc_plata
        totalNeto = total-descuento
    Cat = Categoria.objects.all()
    data = {
        'usuario': usuario_nombre,
        'img': img,
        'autorizado': autorizado,
        'np': np,
        'Cat': Cat,
        'Prods': Prods,
        'total': total,
        'descuento': descuento,
        'totalNeto': totalNeto
    }

    return render(request, 'presupuestos/inicio.html', data)

# Vista llamada desde el frontend que genera un JsonResponse con los productos de una determinada categoria para poder cargarlos en el elemento select correspondiente.


@login_required
def obtener_productos(request):
    categoria_nombre = request.GET.get('categoria_nombre')
    categoria = get_object_or_404(Categoria, nombre=categoria_nombre)
    productos = Producto.objects.filter(
        categoria=categoria).filter(presupuesto=None).filter(vendedor=None).values('codigo', 'nombre')
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
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')

    data = {
        'Pres': Pres,
        'usuario': usuario_nombre,
        'img': img,
        'autorizado': autorizado,
    }
    return render(request, 'presupuestos/presupuestos.html', data)


@login_required
@csrf_exempt
# Recibe el diccionario desde ObetenerDatos y envía la información al frontend para mostrarla en un modal donde se decide si se agrega el producto al presupuesto o se descarta.
def calculo_rapido(request):

    # Obtener datos del formulario
    diccionario = obtener_datos(request)
    # Almacenar los datos en la sesión
    request.session['datos_producto'] = diccionario
    # Calcular el costo
    costo = calc_precio(diccionario)

    return JsonResponse({
        'producto': costo['producto'],
        'cantidad': costo['cantidad'],
        'cant_area': costo['cant_area'],
        'precio': costo['resultado'],
        'descuento': costo['descuento'],
        'detalle': costo['info_adic'],
        'empaquetado': costo['empaquetado'],
        't_produccion': costo['t_produccion'],
    })

# Vista que permite agregar o descartar un producto desde el modal de cálculo rápido.


def agregar_descartar_producto(request, str):
    # Agregar la URL en caso de edición
    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    vendedor = User.objects.get(id=request.session.get('vendedor'))
    if str == 'add':
        datos_producto = request.session.get('datos_producto')
        costo = calc_precio(datos_producto)
        empaq_booleano = True if costo['empaquetado'] == 'Si' else False
        if editando_presup:
            Producto.objects.create(
                presupuesto=Presupuesto.objects.get(numero=np_global),
                cliente=datos_producto['cliente'],
                nombre=costo['producto'],
                categoria=Categoria.objects.get(
                    nombre=datos_producto['categoria']),
                info_adic=costo['info_adic'],
                cantidad=costo['cantidad'],
                cant_area=costo['cant_area'],
                precio=costo['precio'],
                desc_porcentaje=costo['descuento'],
                desc_plata=costo['desc_plata'],
                resultado=costo['resultado'],
                empaquetado=empaq_booleano,
                t_produccion=costo['t_produccion'],
                vendedor=vendedor,
            )
            url = f'/presupuestos/verPresupuesto/{np_global}'
            # costo['url'] = url
        else:
            Producto.objects.create(
                presupuesto=None,
                cliente=datos_producto['cliente'],
                nombre=costo['producto'],
                categoria=Categoria.objects.get(
                    nombre=datos_producto['categoria']),
                info_adic=costo['info_adic'],
                cantidad=costo['cantidad'],
                cant_area=costo['cant_area'],
                precio=costo['precio'],
                desc_porcentaje=costo['descuento'],
                desc_plata=costo['desc_plata'],
                resultado=costo['resultado'],
                empaquetado=empaq_booleano,
                t_produccion=costo['t_produccion'],
                vendedor=vendedor,
            )
            url = '/presupuestos/inicio'
            # costo['url'] = url
        messages.success(request, 'El producto se ha agregado correctamente.')
        # Limpiar los datos de la sesión
        request.session.pop('datos_producto', None)
    if str == 'del':
        messages.warning(
            request, 'El producto se ha descartado correctamente.')
        if editando_presup:
            url = f'/presupuestos/verPresupuesto/{np_global}'
        else:
            url = '/presupuestos/inicio'
        request.session.pop('datos_producto', None)
    return redirect(url)

# Vista que permite editar un producto de la cotización actual.


@login_required
def edit_producto_cotizado(request):
    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    try:
        cambios_precio = False
        cambios = False
        # print(request.POST)
        prod = Producto.objects.get(codigo=int(request.POST['cod_edit']))
        if prod.cantidad != request.POST['cant_edit']:
            prod.cantidad = float(request.POST['cant_edit'])
            cambios_precio = True
        if prod.cant_area != request.POST['cant_area_edit']:
            prod.cant_area = float(request.POST['cant_area_edit'])
            cambios_precio = True
        if prod.desc_porcentaje != request.POST['desc_edit']:
            prod.desc_porcentaje = int(request.POST['desc_edit'])
            cambios_precio = True
        if request.POST.get('empaq_edit'):
            empaquetado_precio = float(Producto.objects.get(codigo=123).precio)
            prod.empaquetado = True
            cambios_precio = True
        else:
            empaquetado_precio = 0
            prod.empaquetado = False
        if prod.t_produccion != request.POST['t_prod_edit']:
            tiempo = str(request.POST['t_prod_edit']).replace(',', '.')
            prod.t_produccion = float(tiempo)
            costo_produccion = float(Producto.objects.get(
                codigo=125).precio) * float(tiempo)
            cambios_precio = True
        if cambios_precio:
            p_precio = float(Producto.objects.filter(
                nombre=prod.nombre).filter(resultado=0).values_list('precio', flat=True).first())
            # print(f'p_precio: {p_precio}')
            prod.precio = round(p_precio * prod.cantidad * prod.cant_area +
                                costo_produccion + empaquetado_precio, 2)
            prod.desc_plata = float(prod.precio * prod.desc_porcentaje / 100)
            prod.resultado = round(prod.precio - prod.desc_plata, 2)
        if prod.info_adic != request.POST['detalle_edit']:
            prod.info_adic = request.POST['detalle_edit']
            cambios = True
        if cambios or cambios_precio:
            prod.save()
        if editando_presup:
            url = f'/presupuestos/verPresupuesto/{np_global}'
        else:
            url = '/presupuestos/inicio'
        messages.success(
            request, 'Los datos del producto se han actualizado correctamente.')
        return redirect(url)
    except Exception as e:
        messages.error(
            request, f'No se ha podido actualizar los datos del producto. Error({e})')
        print(messages)
        return redirect('/presupuestos/inicio')
# Borra un ítem particular del presupuesto que se esta armando.


def delete_calc_presupuesto(request, r):
    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    try:
        prod = Producto.objects.get(codigo=r)
        prod.delete()
        messages.success(
            request, f'El producto {r} se ha borrado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se ha podido borrar el producto. Error({e})')
    if editando_presup:
        return redirect(f'/presupuestos/verPresupuesto/{np_global}')
    else:
        return redirect('/presupuestos/inicio')
# Borra todos los ítems del presupuesto que se está armando./Borra los elementos de la BD que no tienen un presupuesto asociado.


def destroy_calc_presupuesto(request):
    vendedor = request.session.get('vendedor')
    Calcs = Producto.objects.filter(presupuesto=None).filter(vendedor=vendedor)
    contador = 0
    for c in Calcs:
        if c.presupuesto != 0:
            c.delete()
            contador += 1
    messages.success(
        request, f'El presupuesto se ha borrado correctamente. {contador} ítems borrados.')
    return redirect('/presupuestos/inicio')

# Vista que guarda el presupuesto en la base de datos. Si es un presupuesto que se está editando, se crea uno nuevo con los
# nuevos ítems. El presupuesto original queda sin ítems.


def guardar_presupuesto(request):
    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    confirma = request.session.get('confirma', False)
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

        # return redirect('/presupuestos')
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
            messages.success(
                request, f'Se ha creado y guardado el presupuesto {n_presupuesto} correctamente.')
        # Si el cliente no existe en la base de datos lo crea y actualiza la info del presupuesto
        except:
            Cliente.objects.create(
                nombre=c
            )
            messages.success(
                request, f'Se ha agregado el cliente {c} a la base de datos.')
            # Actualizo el presupuesto con el valor total y el nombre del cliente
            pre = Presupuesto.objects.get(numero=n_presupuesto)
            pre.cliente = Cliente.objects.get(nombre=c)
            pre.total = t
            pre.desc_plata = d
            pre.save()
            messages.success(
                request, f'Se ha creado y guardado el presupuesto {n_presupuesto} correctamente.')
        # Si se utiliza el botón de generar pedido desde la vista de Inicio la bandera confirma es True para renderizar el template 'Completar_Pedido'.
        if confirma:
            return redirect('/pedidos')

            # si no se utiliza el botón de generar pedido se redirecciona a la vista de Inicio después de crear el presupuesto con el botón 'Guardar presupuesto'.
    return redirect('/presupuestos')

# Vista que conduce a la vista del inicial del cotizador para agregar o modificar items en un presupuesto particular.


@login_required
def editar_presupuesto(request, np):
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')
    request.session['editando_presup'] = True
    request.session['np_global'] = np
    request.session['confirma'] = False
    total = 0
    descuento = 0
    totalNeto = 0
    Cat = Categoria.objects.all()
    Prods = Producto.objects.filter(presupuesto=np)
    for p in Prods:
        total += p.precio
        descuento += p.desc_plata
        totalNeto = total-descuento
    pres = Presupuesto.objects.get(numero=np)
    cli = pres.cliente

    data = {
        'usuario': usuario_nombre,
        'img': img,
        'autorizado': autorizado,
        'cli': cli,
        'np': np,
        'Cat': Cat,
        'Prods': Prods,
        'total': total,
        'descuento': descuento,
        'totalNeto': totalNeto
    }
    return render(request, 'presupuestos/inicio.html', data)

# Genera un pdf del presupuesto para que pueda enviarse al cliente.


@login_required
def generar_presupuesto_pdf(request, np):
    # Obtener el presupuesto junto con información relevante basado en el np

    total = 0
    descuento = 0
    total_neto = 0
    fecha = date.today()
    Prods = Producto.objects.filter(presupuesto=np)
    for p in Prods:
        total += p.precio
        descuento += p.desc_plata
        total_neto = total-descuento
    pres = Presupuesto.objects.get(numero=np)
    cli = pres.cliente

    # Construir la URL base
    base_url = request.build_absolute_uri('/')
    data = {
        'cliente': cli,
        'np': np,
        'dia': fecha.day,
        'mes': fecha.month,
        'anio': str(fecha.year)[2:4],
        'Prods': Prods,
        'total': total,
        'descuento': descuento,
        'total_neto': total_neto,
        'base_url': base_url,
    }
    # return render(request, 'presupuestos/descargar_presupuesto.html', data)
    # Renderizar la plantilla HTML
    html_string = render_to_string(
        'presupuestos/descargar_presupuesto.html', data)

    # Generar el PDF
    html = HTML(string=html_string)
    pdf = html.write_pdf()

    # Crear la respuesta HTTP con el tipo de contenido 'application/pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Presupuesto_{np}.pdf"'

    return response
