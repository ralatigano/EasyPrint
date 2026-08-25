from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import Presupuesto
from django.contrib.auth.models import User
from django.contrib import messages
from .functions import *
from clientes.functions import parsear_cliente
from presupuestos.models import DetalleSugerido
from productos.models import ProductoCotizado, Categoria, Producto
from clientes.models import Cliente
from django.http import HttpResponse, JsonResponse, Http404
from django.conf import settings
import os
from urllib.parse import unquote
from django.template.loader import render_to_string
from weasyprint import HTML
from datetime import date
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import re

_RANGO_RE = re.compile(r'^(.*?)\s*\[(\d+)[-]([\d]+|INF)\]\s*$')
import json
from core.decorators import solo_gerencia
from core.models import AliasPago, ConfiguracionPresupuesto
from django.db.models import Max
from django.db import models

# Create your views here.
app_name = 'presupuestos'


# Página principal de la app para hacer una nueva cotización.

@login_required
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

    BASE_NP = 3000001090
    ultimo = Presupuesto.objects.filter(numero__gte=BASE_NP).aggregate(
        models.Max('numero'))['numero__max']
    np = (ultimo + 1) if ultimo else BASE_NP + 1

    request.session['np_global'] = np
    Prods = ProductoCotizado.objects.filter(
        presupuesto=None).filter(vendedor=vendedor)
    for p in Prods:
        total += p.precio_bruto
        descuento += p.desc_plata
        totalNeto = total-descuento
    Cat = Categoria.objects.all()
    Sugerencias = DetalleSugerido.objects.order_by("-frecuencia")
    lista_clientes = Cliente.objects.all().order_by('-frecuencia', 'nombre')
    cliente = Cliente.objects.get(nombre="Consumidor final")
    data = {
        'usuario': usuario_nombre,
        'img': img,
        'autorizado': autorizado,
        'np': np,
        'Cat': Cat,
        'Prods': Prods,
        'total': total,
        'descuento': descuento,
        'totalNeto': totalNeto,
        'Sugerencias': Sugerencias,
        'cliente': f"{cliente.id}|{cliente.referencia}",
        'clientes': lista_clientes,
    }

    return render(request, 'presupuestos/inicio.html', data)


@login_required
def generar_grafico(request):

    tipo = request.POST.get("tipo")
    algoritmo = request.POST.get("algoritmo")

    try:
        ancho_hoja = float(request.POST.get("anchoHoja"))
        if request.POST.get("altoHoja") == "Según cálculo":
            alto_hoja = 100000
        else:
            alto_hoja = float(request.POST.get("altoHoja"))
        ancho_elemento = float(request.POST.get("anchoElemento"))
        alto_elemento = float(request.POST.get("altoElemento"))
        separacion = float(request.POST.get("separacionElementos"))
        cantidad_deseada = int(request.POST.get("cantidadElementos"))
    except Exception as e:
        print("❌ Error al parsear datos:", e)
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    resultado = procesar_cotizacion_con_grafico(
        tipo_calculo=tipo,
        ancho_hoja=ancho_hoja,
        alto_hoja=alto_hoja,
        ancho_elemento=ancho_elemento,
        alto_elemento=alto_elemento,
        separacion=separacion,
        cantidad_deseada=cantidad_deseada,
        algoritmo=algoritmo
    )
    if resultado.get("tipo") == "X":
        return JsonResponse(resultado, status=400)
    return JsonResponse(resultado)


@login_required
@csrf_exempt
def calcular_cotizacion_final(request):
    if request.method == "POST":
        producto_id = int(request.POST.get("producto_id"))
        cantidad = int(request.POST.get("cantidadElementos"))
        empaquetado = request.POST.get("empaquetado") == "true"
        producto_final = request.POST.get("producto_final", "").strip()
        info_adic = request.POST.get("info_adic", "").strip()
        if producto_final.strip():
            obj, created = DetalleSugerido.objects.get_or_create(
                texto=producto_final.strip())
            if not created:
                obj.frecuencia += 1
                obj.save()
        tipo_cotizacion = request.POST.get("tipoCotizacion", "D")
        cantidad_producto = 0
        # Conversión segura
        try:
            tiempo = Decimal(request.POST.get("inputTiempo", "0"))
        except InvalidOperation:
            tiempo = Decimal("0")
        try:
            descuento = Decimal(request.POST.get("descuento", "0"))
        except InvalidOperation:
            descuento = Decimal("0")
        try:
            resultado_grafico = round(Decimal(request.POST.get(
                "resultado_grafico", "0")), 3)
        except InvalidOperation:
            resultado_grafico = Decimal("1")

        # Determinar el factor según tipo
        if tipo_cotizacion == "D":
            cantidad_producto = cantidad
        else:
            cantidad_producto = resultado_grafico if resultado_grafico > 0 else cantidad

        # Consultas a la DB
        producto = Producto.objects.get(id=producto_id)

        # Auto-resolución de tier: si el producto tiene rango [N-M] y hubo un
        # resultado de packing (hojas/metros), buscar el tier correcto en la DB.
        # Esto protege contra el caso en que el frontend manda el ID del
        # representante de familia (ej. [1-5]) pero la cantidad calculada cae
        # en otro rango (ej. [6-30]).
        if tipo_cotizacion != "D" and resultado_grafico > 0:
            match = _RANGO_RE.match(producto.nombre)
            if match:
                base_nombre = match.group(1).strip()
                cantidad_hojas = int(resultado_grafico)
                candidatos = Producto.objects.filter(
                    nombre__istartswith=base_nombre,
                    categoria=producto.categoria,
                    activo=True,
                )
                for cand in candidatos:
                    m = _RANGO_RE.match(cand.nombre)
                    if m:
                        rango_min = int(m.group(2))
                        rango_max_str = m.group(3)
                        rango_max = float('inf') if rango_max_str == 'INF' else int(rango_max_str)
                        if rango_min <= cantidad_hojas <= rango_max:
                            producto = cand
                            break

        if producto.tercerizado:
            precio_producto = producto.precio_proveedor
        else:
            precio_producto = producto.precio
        margen = producto.factor

        precio_hora = Producto.objects.get(
            nombre="Mano de obra").precio_proveedor
        precio_empaquetado = Producto.objects.get(
            nombre="Empaquetado").precio_proveedor if empaquetado else 0

        # Cálculo
        subtotal = cantidad_producto * precio_producto * margen
        costo_produccion = tiempo * precio_hora
        total_bruto = subtotal + costo_produccion + precio_empaquetado
        total_con_descuento = total_bruto * \
            (1 - descuento / 100) if descuento > 0 else total_bruto
        # Guardar en sesión
        request.session["cotizacion_previa"] = {
            "producto_id": producto_id,
            "producto_final": producto_final,
            "info_adic": info_adic,
            "cantidad": cantidad,
            "resultado_grafico": float(resultado_grafico),
            "tiempo_produccion": float(tiempo),
            "empaquetado": empaquetado,
            "descuento": float(descuento),
            "total_bruto": float(total_bruto),
            "precio_total": float(total_con_descuento),
            # "detalle": extra
        }

        return JsonResponse({
            "insumo": producto.nombre,
            "producto_final": producto_final,
            "info_adic": info_adic,
            "cantidad": cantidad,
            "resultado_grafico": resultado_grafico,
            "precio_total": round(total_con_descuento, 2),
            "descuento": f"{descuento}%",
            "empaquetado": f"SI" if empaquetado else "NO",
            "tiempo_produccion": float(tiempo),
            # "detalle": extra
        })


@login_required
@csrf_exempt
def actualizar_detalle(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            detalle = data.get("detalle", "").strip()

            if "cotizacion_previa" in request.session:
                request.session["cotizacion_previa"]["detalle"] = detalle
                request.session.modified = True

            return JsonResponse({"status": "ok", "detalle": detalle})

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    return JsonResponse({"status": "error", "message": "Método no permitido"}, status=405)


# Vista que procesa una llamada desde el frontend para borrar todos los gráficos que se generan durante la cotización.

@login_required
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


@login_required
def agregar_producto(request):
    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    vendedor = User.objects.get(id=request.session.get('vendedor'))
    datos = request.session.get("cotizacion_previa")
    url = ''

    if not datos:
        messages.error(
            request, "No se encontraron datos para agregar el producto.")
        return redirect("/presupuestos")

    try:
        # --- Datos base ---
        insumo = Producto.objects.get(id=datos["producto_id"])
        producto_final = datos.get("producto_final", "").strip()
        descripcion = datos.get("detalle", "").strip()  # detalle extendido
        info_adic = datos.get("info_adic", "").strip()

        cantidad = datos["cantidad"]
        total_bruto = Decimal(str(datos["total_bruto"]))
        desc_porcentaje = Decimal(str(datos["descuento"]))
        desc_plata = Decimal(total_bruto * desc_porcentaje /
                             100 if desc_porcentaje > 0 else 0)

        resultado = Decimal(str(datos["precio_total"]))
        t_produccion = datos["tiempo_produccion"]
        empaquetado = datos["empaquetado"]

        # --- Crear instancia ---
        kwargs = {
            "insumo": insumo,
            "producto_final": producto_final,
            "descripcion": descripcion,
            "info_adic": info_adic,
            "cantidad": cantidad,
            "resultado": resultado,
            "desc_plata": desc_plata,
            "desc_porcentaje": desc_porcentaje,
            "t_produccion": t_produccion,
            "empaquetado": empaquetado,
            "vendedor": vendedor,
        }

        if editando_presup:
            kwargs["presupuesto"] = Presupuesto.objects.get(numero=np_global)
            ProductoCotizado.objects.create(**kwargs)
            messages.success(request, "Producto agregado al presupuesto.")
            url = f'/presupuestos/verPresupuesto/{np_global}'
        else:
            ProductoCotizado.objects.create(**kwargs)
            messages.success(request, "Producto agregado al presupuesto.")
            url = '/presupuestos/inicio'

        # Limpiar sesión
        del request.session["cotizacion_previa"]

    except Exception as e:
        messages.error(request, f"Error al agregar producto: {str(e)}")
        return redirect("/presupuestos")

    return redirect(url)


@login_required
def descartar_producto(request):
    request.session.pop("cotizacion_previa", None)
    return JsonResponse({"status": "ok"})


# Vista que muestra la tabla de presupuestos.


@login_required
def presupuestos(request):
    Pres = Presupuesto.objects.all()
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')
    clientes = Cliente.objects.all().order_by('-frecuencia', 'nombre')
    data = {
        'Pres': Pres,
        'usuario': usuario_nombre,
        'img': img,
        'autorizado': autorizado,
        'Clientes': clientes,
    }
    return render(request, 'presupuestos/presupuestos.html', data)


# Vista que permite editar un producto de la cotización actual.


@login_required
def edit_producto_cotizado(request):
    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    try:
        cambios_precio = False
        cambios = False
        prod = ProductoCotizado.objects.get(
            codigo=int(request.POST['cod_edit']))
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


@login_required
def delete_calc_presupuesto(request, r):
    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    try:
        prod = ProductoCotizado.objects.get(id=r)
        prod.delete()
        messages.success(
            request, f'El producto {prod.producto_final} se ha borrado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se ha podido borrar el producto. Error({e})')
    if editando_presup:
        return redirect(f'/presupuestos/verPresupuesto/{np_global}')
    else:
        return redirect('/presupuestos/inicio')
# Borra todos los ítems del presupuesto que se está armando./Borra los elementos de la BD que no tienen un presupuesto asociado.


@login_required
def destroy_calc_presupuesto(request):
    vendedor = request.session.get('vendedor')
    Calcs = ProductoCotizado.objects.filter(
        presupuesto=None).filter(vendedor=vendedor)
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


@login_required
def guardar_presupuesto(request):
    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    confirma = request.session.get('confirma', False)
    t = 0
    d = 0
    BASE_NP = 3000001090
    ultimo = Presupuesto.objects.filter(numero__gte=BASE_NP).aggregate(
        models.Max('numero'))['numero__max']
    n_presupuesto = (ultimo + 1) if ultimo else BASE_NP + 1

    # Obtengo la instancia del cliente "Consumidor final"
    consumidor_final = Cliente.objects.get(nombre="Consumidor final")

    if editando_presup:
        # Busco el presupuesto que estoy editando con ayuda de la variable global
        pre_v = Presupuesto.objects.get(numero=np_global)
        cliente = pre_v.cliente if pre_v.cliente else consumidor_final
        # Creo un nuevo presupuesto con el mismo cliente que el anterior, o con "Consumidor final"
        try:
            pre_n = Presupuesto.objects.create(
                numero=n_presupuesto,
                cliente=cliente
            )
            Prods = ProductoCotizado.objects.filter(presupuesto=np_global)
            for p in Prods:
                p.presupuesto = pre_n
                t += p.resultado
                d += p.desc_plata
                p.save()
            pre_n.total = t
            pre_n.desc_plata = d
            pre_n.save()
            messages.success(
                request, f'Se ha creado y guardado el presupuesto {n_presupuesto} correctamente con el cliente {cliente}].')
        except Exception as e:
            messages.error(
                request, f'No se ha podido editar el presupuesto. Error({e})')
            return redirect('/presupuestos/inicio')
    else:
        client_input = request.session.get('cliente_input', '').strip()
        client_obj = parsear_cliente(client_input)

        try:
            pre = Presupuesto.objects.create(
                numero=n_presupuesto,
                cliente=client_obj
            )
            Prods = ProductoCotizado.objects.filter(
                presupuesto=None, resultado__gt=0)
            for p in Prods:
                p.presupuesto = pre
                t += p.resultado
                d += p.desc_plata
                p.save()

            pre.total = t
            pre.desc_plata = d
            pre.save()
            request.session.pop('cliente_input', None)
            messages.success(
                request, f'Se ha creado y guardado el presupuesto {n_presupuesto} correctamente.')
        except Exception as e:
            messages.error(
                request, f'No se ha podido guardar el presupuesto. Error({e})')
            return redirect('/presupuestos/inicio')
    if confirma:
        return redirect('/pedidos/v2')

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
    Prods = ProductoCotizado.objects.filter(presupuesto=np)
    for p in Prods:
        total += p.precio_bruto
        descuento += p.desc_plata
        totalNeto = total-descuento
    pres = Presupuesto.objects.get(numero=np)
    cli = pres.cliente
    cliente_str = f"{cli.id}|{cli.referencia}" if cli else ""

    data = {
        'usuario': usuario_nombre,
        'img': img,
        'autorizado': autorizado,
        'cliente': cliente_str,
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
    Prods = ProductoCotizado.objects.filter(presupuesto=np)
    for p in Prods:
        total += p.precio_bruto
        descuento += p.desc_plata
        total_neto = total-descuento
    pres = Presupuesto.objects.get(numero=np)
    cli = pres.cliente

    # Fecha de CREACIÓN del presupuesto (no la fecha actual): un presupuesto tiene
    # vigencia y sus precios pueden cambiar con el tiempo, así que al reenviarlo
    # debe conservar la fecha en que fue cotizado. `created` se guarda en UTC
    # (USE_TZ=True), por eso se convierte a hora local para que coincida con la
    # fecha de creación que muestra el listado.
    fecha = timezone.localtime(pres.created)

    # Seña del 50% para dar de alta el pedido (y saldo restante a la entrega).
    senia = round(total_neto / 2, 2)
    saldo = round(total_neto - senia, 2)

    # Alias de pago activo y texto del disclaimer (configurables desde Configuración).
    alias_pago = AliasPago.objects.filter(activo=True).first()
    disclaimer = ConfiguracionPresupuesto.load().disclaimer

    # Construir la URL base
    img_base = settings.IMG_BASE_PATH
    css_path = settings.CSS_PATH
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
        'senia': senia,
        'saldo': saldo,
        'porcentaje_senia': 50,
        'alias_pago': alias_pago,
        'disclaimer': disclaimer,
        'img_base': img_base,
        'css_path': css_path
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

    presupuesto = get_object_or_404(Presupuesto, numero=presupuesto_numero)

    # Nuevo sistema basado en ID
    client_obj = parsear_cliente(nuevo_cliente_input)

    presupuesto.cliente = client_obj
    presupuesto.save()

    return JsonResponse({
        'success': True,
        'nuevo_cliente': client_obj.referencia
    })


@login_required
def obtener_cliente(request):
    presupuesto_numero = request.GET.get('numero')

    try:
        presupuesto = Presupuesto.objects.get(numero=presupuesto_numero)
        cliente = presupuesto.cliente

        if cliente:
            return JsonResponse({
                'id': cliente.id,
                'referencia': cliente.referencia
            })
        else:
            return JsonResponse({
                'id': None,
                'referencia': ""
            })

    except Presupuesto.DoesNotExist:
        raise Http404("Presupuesto no encontrado")


@login_required
def info_prod_cotizado(request, producto_id):
    try:
        producto = ProductoCotizado.objects.get(id=producto_id)
        precio_hora = Producto.objects.get(
            nombre="Mano de obra").precio_proveedor
        precio_empaquetado = Producto.objects.get(
            nombre="Empaquetado").precio_proveedor
        data = {
            'producto_nombre': producto.insumo.nombre,
            'info_adicional': producto.info_adic,
            'precio': producto.precio_bruto,
            'resultado': producto.resultado,
            'descuento': producto.desc_porcentaje,
            'tiempo_estimado': producto.t_produccion,
            'empaquetado': producto.empaquetado,
            'precio_hora': precio_hora,
            'precio_empaquetado': precio_empaquetado,
        }
        return JsonResponse(data)
    except ProductoCotizado.DoesNotExist:
        raise Http404("Producto no encontrado")


@login_required
def editar_producto_cotizado(request):
    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    if request.method == 'POST':
        try:
            producto_id = request.POST.get('id_producto')
            producto = get_object_or_404(ProductoCotizado, id=producto_id)

            # Inputs del formulario
            info_adicional = request.POST.get('info_adicional', '').strip()
            precio = request.POST.get('precio')
            descuento = request.POST.get('descuento')
            tiempo = request.POST.get('tiempo')
            subtotal = request.POST.get('subtotal')
            resultado = request.POST.get('resultado')
            empaquetado = request.POST.get('empaquetado') == 'on'
            precio_arb = request.POST.get('precio_arb_checkbox') == 'on'
            # Conversión segura
            precio = float(precio) if precio else 0
            subtotal = float(subtotal) if subtotal else 0
            resultado = float(resultado) if resultado else 0
            descuento = float(descuento) if descuento else 0
            tiempo = float(tiempo) if tiempo else 0

            # Lógica de edición
            producto.info_adic = info_adicional
            producto.empaquetado = empaquetado

            if precio_arb:
                producto.resultado = precio
                producto.desc_plata = 0
                producto.desc_porcentaje = 0
                producto.t_produccion = 0
                messages.success(
                    request, f'Producto editado con precio arbitrario: ${precio:.2f}')
            else:
                producto.desc_porcentaje = descuento
                producto.t_produccion = tiempo
                producto.desc_plata = round(subtotal * descuento / 100, 2)
                producto.resultado = resultado
                messages.success(
                    request, f'Producto editado correctamente. Precio final: ${resultado:.2f}')

            producto.save()

        except Exception as e:
            messages.error(request, f'Error al editar el producto: {str(e)}')
    if editando_presup:
        return redirect(f'/presupuestos/verPresupuesto/{np_global}')
    else:
        return redirect('/presupuestos/inicio')


@login_required
def productos_por_presupuesto(request, presupuesto_numero):
    productos = ProductoCotizado.objects.filter(presupuesto=presupuesto_numero)
    data = [
        {"nombre": p.producto_final, "cantidad": p.cantidad}
        for p in productos
    ]
    return JsonResponse({"data": data})


@login_required
def set_cliente_session(request):
    cliente = request.POST.get('cliente', '').strip()
    if cliente.lower() in ["", "none", "null"]:
        cliente = ""
    request.session['cliente_input'] = cliente
    return JsonResponse({'ok': True})
