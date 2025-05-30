from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from . models import Presupuesto
from django.contrib.auth.models import User
from core.models import Usuario
from django.contrib import messages
from core.functions import *
from .prueba import calcular_cant_etiquetas_por_superficie
from productos.models import Producto, Categoria
from clientes.models import Cliente
from django.http import HttpResponse, JsonResponse, Http404
from django.conf import settings
import json
import os
from urllib.parse import unquote
from django.contrib.sessions.models import Session
from django.template.loader import render_to_string
from weasyprint import HTML
from datetime import date

# Create your views here.
app_name = 'presupuestos'


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
    pres = Presupuesto.objects.all()
    np = max(p.numero for p in pres) + 1 if pres else 1
    request.session['np_global'] = np
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

# Vista llamada desde el frontend que genera un JsonResponse con los productos de una determinada categoria para poder cargarlos en el elemento select correspondiente
# además de realizar algunos cálculos para brindar información de utilidad durante la cotización.


@login_required
def productos_por_categoria(request):
    if request.method == 'POST':
        categoria = request.POST.get('categoria')
        cantidad_repeticion = int(request.POST.get('cantidad_repeticion'))
        ancho_elemento = float(request.POST.get('ancho'))
        alto_elemento = float(request.POST.get('alto'))
        separacion = float(request.POST.get('separacion', 0))
        algoritmo = request.POST.get('algoritmo', 'MaxRects')
        # Obtener productos de la categoría seleccionada
        productos = Producto.objects.filter(categoria__id=categoria)

        if productos.exists():
            # Tomamos el primer producto para realizar el cálculo del gráfico
            producto = productos.first()
            ancho = producto.ancho
            alto = producto.alto

            # Llama a la función que genera el gráfico y calcula los resultados
            cant_elementos_empaquetados, grafico_url, area_ocupada = calcular_cant_etiquetas_por_superficie(
                ancho_hoja=ancho, alto_hoja=alto, ancho_elemento=ancho_elemento,
                alto_elemento=alto_elemento, separacion=separacion, cantidad_deseada=cantidad_repeticion, algoritmo=algoritmo
            )
            # En función de cuantos elementos entran por pliego calcula la cantidad de pliegos que serán necesarios para cumplir con el pedido
            if cantidad_repeticion != 0:
                cantidad_hojas = math.ceil(
                    cantidad_repeticion / cant_elementos_empaquetados)

            # Formar la respuesta con los productos y los resultados del cálculo
            productos_data = [{'id': p.codigo, 'nombre': p.nombre}
                              for p in productos]
            response_data = {
                'productos': productos_data,
                'grafico_url': grafico_url,
                'area_ocupada': area_ocupada,
                'cant_elementos_empaquetados': cant_elementos_empaquetados,
                'cantidad_hojas': cantidad_hojas,
            }

            return JsonResponse(response_data)
        else:
            return JsonResponse({'error': 'No se encontraron productos en esta categoría'}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)


# Vista que procesa una llamada desde el frontend para borrar todos los gráficos que se generan durante la cotización.


@csrf_exempt
def borrar_imagen_generada(request):
    if request.method == 'POST':
        try:
            # Directorio donde están guardadas las imágenes generadas
            directorio_graficos = os.path.join(
                settings.MEDIA_ROOT, 'presupuestos/graficos')

            # Verificar si el directorio existe
            if os.path.exists(directorio_graficos):
                # Lista todos los archivos en el directorio
                archivos = os.listdir(directorio_graficos)

                # Contador para saber cuántos archivos se han eliminado
                archivos_eliminados = 0

                # Itera y elimina cada archivo
                for archivo in archivos:
                    archivo_path = os.path.join(directorio_graficos, archivo)
                    # Asegurarse de que sea un archivo y no un directorio
                    if os.path.isfile(archivo_path):
                        os.remove(archivo_path)
                        archivos_eliminados += 1

                return JsonResponse({'message': f'{archivos_eliminados} imágenes eliminadas correctamente.'})
            else:
                return JsonResponse({'message': 'El directorio de imágenes no existe.'}, status=404)

        except Exception as e:
            return JsonResponse({'message': f'Error al intentar eliminar las imágenes: {str(e)}'}, status=500)
    else:
        return JsonResponse({'message': 'Método no permitido.'}, status=405)

# Vista que muestra la tabla de presupuestos.


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
        'cantidad_repeticion': costo['cantidad_repeticion'],
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
                cliente=None,
                nombre=costo['producto'],
                categoria=Categoria.objects.get(
                    nombre=datos_producto['categoria']),
                info_adic=costo['info_adic'],
                cantidad=costo['cantidad_repeticion'],
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
        else:
            Producto.objects.create(
                presupuesto=None,
                cliente=None,
                nombre=costo['producto'],
                categoria=Categoria.objects.get(
                    nombre=datos_producto['categoria']),
                info_adic=costo['info_adic'],
                cantidad=costo['cantidad_repeticion'],
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
        prod = Producto.objects.get(codigo=int(request.POST['cod_edit']))
        cantidad_edit = int(request.POST['cant_edit'])
        cantidad_area_edit = float(
            request.POST['cant_area_edit'].replace(',', '.'))
        desc_edit = int(request.POST['desc_edit'])
        precio_edit = float(request.POST['precio_edit'].replace(',', '.'))
        t_produccion_edit = float(
            request.POST['t_prod_edit'].replace(',', '.'))
        if prod.cantidad != cantidad_edit:
            prod.cantidad = cantidad_edit
            cambios_precio = True
        if prod.cant_area != cantidad_area_edit:
            prod.cant_area = cantidad_area_edit
            cambios_precio = True
        if prod.desc_porcentaje != desc_edit:
            prod.desc_porcentaje = desc_edit
            cambios_precio = True
        if prod.precio != precio_edit:
            cambios_precio = True
        if request.POST.get('empaq_edit'):

            empaquetado_precio = float(Producto.objects.get(codigo=123).precio)
            prod.empaquetado = True
            cambios_precio = True
        else:
            empaquetado_precio = 0
            prod.empaquetado = False
        if prod.t_produccion != t_produccion_edit:
            prod.t_produccion = t_produccion_edit
            costo_produccion = float(Producto.objects.get(
                codigo=125).precio) * t_produccion_edit
            cambios_precio = True
        if cambios_precio:
            if prod.precio != request.POST['precio_edit'].replace(',', '.'):
                prod.precio = float(
                    request.POST['precio_edit'].replace(',', '.'))
                prod.desc_plata = float(
                    prod.precio * prod.desc_porcentaje / 100)
                prod.resultado = round(prod.precio - prod.desc_plata, 2)
            else:
                p_precio = float(Producto.objects.filter(
                    nombre=prod.nombre).filter(resultado=0).values_list('precio', flat=True).first())
                p_factor = float(Producto.objects.filter(
                    nombre=prod.nombre).filter(resultado=0).values_list('factor', flat=True).first())
                prod.precio = round(p_precio * prod.cant_area * p_factor +
                                    costo_produccion + empaquetado_precio, 2)
                prod.desc_plata = float(
                    prod.precio * prod.desc_porcentaje / 100)
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

    # Obtengo la instancia del cliente "Consumidor final"
    consumidor_final = Cliente.objects.get(nombre="Consumidor final")

    if editando_presup:
        # Busco el presupuesto que estoy editando con ayuda de la variable global
        pre_v = Presupuesto.objects.get(numero=np_global)
        # Creo un nuevo presupuesto con el mismo cliente que el anterior, o con "Consumidor final"
        pre_n = Presupuesto.objects.create(
            numero=n_presupuesto,
            cliente=pre_v.cliente if pre_v.cliente else consumidor_final
        )
        Prods = Producto.objects.filter(presupuesto=np_global)
        for p in Prods:
            p.presupuesto = pre_n
            t += p.resultado
            d += p.desc_plata
            p.save()
        pre_n.total = t
        pre_n.desc_plata = d
        pre_n.save()

    else:
        # Procesamos el campo "cliente" enviado en el POST (se espera que sea un nombre)
        client_input = request.GET.get('cliente', '').strip()
        if client_input:
            # Se busca en la DB por nombre (sin distinguir mayúsculas/minúsculas)
            client_obj = Cliente.objects.filter(
                nombre__iexact=client_input).first()
            if not client_obj:
                # Si no se encuentra, se crea una nueva instancia de Cliente
                client_obj = Cliente.objects.create(nombre=client_input)
        else:
            # Si el campo está vacío, se asigna el cliente "Consumidor final"
            client_obj = consumidor_final

        pre = Presupuesto.objects.create(
            numero=n_presupuesto,
            cliente=client_obj
        )
        Prods = Producto.objects.filter(presupuesto=None, resultado__gt=0)
        for p in Prods:
            p.presupuesto = pre
            t += p.resultado
            d += p.desc_plata
            p.save()

        pre.total = t
        pre.desc_plata = d
        pre.save()

        messages.success(
            request, f'Se ha creado y guardado el presupuesto {n_presupuesto} correctamente con el cliente "Consumidor final".')

    if confirma:
        return redirect('/pedidos')

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
        'cliente': cli,
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


@require_POST
def cambiar_cliente(request):
    presupuesto_numero = request.POST.get('numero')
    nuevo_cliente_input = request.POST.get('cliente', '').strip()

    # Obtenemos el presupuesto; en caso de no existir retorna 404
    presupuesto = get_object_or_404(Presupuesto, numero=presupuesto_numero)

    # Obtenemos la instancia predeterminada
    consumidor_final = Cliente.objects.get(nombre="Consumidor final")

    if nuevo_cliente_input:
        # Buscamos por nombre sin distinguir mayúsculas/minúsculas
        client_obj = Cliente.objects.filter(
            nombre__iexact=nuevo_cliente_input).first()
        if not client_obj:
            # Si no existe, se crea uno nuevo
            client_obj = Cliente.objects.create(nombre=nuevo_cliente_input)
    else:
        client_obj = consumidor_final

    presupuesto.cliente = client_obj
    presupuesto.save()

    return JsonResponse({'success': True, 'nuevo_cliente': client_obj.nombre})


def obtener_cliente(request):
    presupuesto_numero = request.GET.get('numero')
    try:
        presupuesto = Presupuesto.objects.get(numero=presupuesto_numero)
        cliente_name = presupuesto.cliente.nombre if presupuesto.cliente else ""
        return JsonResponse({'cliente': cliente_name})
    except Presupuesto.DoesNotExist:
        raise Http404("Presupuesto no encontrado")
