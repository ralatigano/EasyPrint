from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from .models import Pedido, ViajeCadete
from presupuestos.models import Presupuesto
from productos.models import ProductoCotizado, ComponenteProducto, FaltanteInsumo
from clientes.models import Cliente
from django.contrib.auth.models import User
from django.contrib import messages
from .functions import *
from django.http import JsonResponse, Http404, HttpResponse
from datetime import datetime
from django.utils import timezone
import json
from openpyxl import Workbook

# Create your views here.
app_name = 'pedidos'

# Vista con la lista de pedidos


@login_required
def pedidos(request):
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')
    Peds = Pedido.objects.order_by('-numero').all()

    data = {
        'Peds': Peds,
        'usuario': usuario_nombre,
        'img': img,
        'autorizado': autorizado,
    }

    return render(request, 'pedidos/pedidos.html', data)

# Vista que setea algunos valores necesarios para poder ingresar a completar pedido desde la vista de presupuestos.


def preparar_completar_pedido(request, presupuesto_numero):
    request.session['editando_presup'] = True
    request.session['np_global'] = presupuesto_numero
    return redirect('completarPedido')

# Renderiza un formulario para completar detalles de un nuevo pedido. Crea un presupuesto. Registra un cliente si es nuevo.


@login_required
def completar_pedido(request):
    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    vendedor = request.session.get('vendedor')
    img = request.session.get('img')
    n_ped = armar_numero_pedido()
    t = 0
    d = 0
    t_d = 0
    c = ''
    if editando_presup:
        pre = Presupuesto.objects.get(numero=np_global)
        cli = pre.cliente
        Prods = ProductoCotizado.objects.filter(presupuesto=np_global)
    else:
        client_input = request.GET.get('cliente', '').strip()
        cli = client_input
        Prods = ProductoCotizado.objects.filter(
            presupuesto=None).filter(vendedor=vendedor)
    lista = []
    for p in Prods:
        lista.append(f'{p.cantidad} {p.producto}')
        t = t + p.resultado
        d = d + p.desc_plata
        c = cli
    t_d = round(t - d, 2)
    data = {
        'img': img,
        'editando_presup': editando_presup,
        'np': np_global,
        'n_ped': n_ped,
        'cliente': c,
        'prods': lista,
        'total': t,
        'descuento': d,
        'total_neto': t_d,
    }
    return render(request, 'pedidos/completar_pedido.html', data)

# Vista que maneja el POST del modal correspondiente para editar el estado de un pedido.


@login_required
def cambiar_estado(request):
    nuevo_estado = request.POST.get('estado')
    n_pedido = request.POST.get('cambiarPedido_estado')

    if nuevo_estado == 'Elegir un estado':
        return redirect('/pedidos')

    try:
        pedido = Pedido.objects.get(numero=n_pedido)
        # Si el pedido ya fue cancelado y está bloqueado, no se puede modificar
        if pedido.estado == 'Cancelado' and getattr(pedido, 'cancelado_bloqueado', False):
            messages.error(
                request, 'Este pedido fue cancelado y no puede modificarse. Si necesitás reactivarlo, deberás crear uno nuevo.')
            return redirect('/pedidos')

        pedido.estado = nuevo_estado
        pedido.save()

        productos = ProductoCotizado.objects.filter(
            presupuesto=pedido.presupuesto)

        # Resolver faltantes si el pedido está en estado final
        if nuevo_estado in ['Para retirar', 'Entregado']:
            for p in productos:
                if not p.producto.tercerizado:
                    actualizar_stock_insumos(
                        p.producto, p.cantidad, modo='resolver', pedido=pedido)

        # Reponer insumos si el pedido se cancela
        elif nuevo_estado == 'Cancelado':
            for p in productos:
                if not p.producto.tercerizado:
                    actualizar_stock_insumos(
                        p.producto, p.cantidad, modo='reponer', pedido=pedido)
            pedido.cancelado_bloqueado = True  # marca irreversible
            pedido.save()

        messages.success(
            request, 'El estado del pedido se ha cambiado exitosamente.')

    except Exception as e:
        messages.error(request, f'Hubo un error al editar el pedido: {str(e)}')

    return redirect('/pedidos')


# vista que permite cambiar el encargado de un pedido.


@login_required
def cambiar_enc(request):

    n_pedido = request.POST['cambiarPedido_enc']
    try:
        pedido = Pedido.objects.get(numero=n_pedido)
        if pedido.encargado == None:
            enc_viejo = 'Sin asignar'
        else:
            enc_viejo = pedido.encargado.first_name
        if request.POST['encargadoSelect'] == 'None':
            pedido.encargado = None
            enc_nuevo = 'Sin asignar'
        else:
            pedido.encargado = User.objects.get(
                id=request.POST['encargadoSelect'])
            enc_nuevo = pedido.encargado.first_name
        pedido.save()
        messages.success(
            request, f'Se ha cambiado a {enc_viejo} por {enc_nuevo} como responsable del pedido {n_pedido} de manera exitosa.')
    except Exception as e:
        messages.error(
            request, 'Hubo un error al editar el pedido. ' + str(e))

    return redirect('/pedidos')

# vista que permite agregar una descripción al pedido.


@login_required
def agregar_descripcion(request):

    n_pedido = request.POST['cambiarPedido_desc']
    print(n_pedido, request.POST['cambiarPedido_desc'])
    try:
        pedido = Pedido.objects.get(numero=n_pedido)
        if pedido.descripcion != request.POST['descripcion']:
            pedido.descripcion = request.POST['descripcion']
            pedido.save()
            messages.success(
                request, f'La descripción del pedido {n_pedido} se ha cambiado exitosamente.')
    except Exception as e:
        messages.error(
            request, 'Hubo un error al editar el pedido. ' + str(e))
    return redirect('/pedidos')

# vista que permite agregar/modificar la seña de un pedido.


@login_required
def agregar_senia(request):
    if request.POST['senia'] != '':
        n_pedido = request.POST['cambiarPedido_senia']
        try:
            pedido = Pedido.objects.get(numero=n_pedido)
            nuev_senia = float(request.POST['senia'].replace(',', '.'))
            pedido.senia = pedido.senia + nuev_senia
            pedido.saldo = round(pedido.precio - pedido.senia, 2)
            pedido.save()
            messages.success(
                request, f'La seña del pedido {n_pedido} se ha actualizado exitosamente.')
        except Exception as e:
            messages.error(
                request, 'Hubo un error al editar el pedido. ' + str(e))
    return redirect('/pedidos')

# Vista que recibe el POST de la plantilla para completar el pedido desde la nueva cotización.


@login_required
@transaction.atomic
def confirmar_pedido(request):
    if request.method != 'POST':
        return redirect('/')

    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    vendedor = request.session.get('vendedor')
    n_pedido = request.POST['n_pedido']
    pre = request.POST['total_neto']
    se = request.POST['senia']
    url = '/pedidos' if editando_presup else '/presupuestos/guardarPresupuesto'

    # Obtener productos cotizados
    if editando_presup:
        Prods = ProductoCotizado.objects.filter(presupuesto=np_global)
    else:
        Prods = ProductoCotizado.objects.filter(
            presupuesto=None, vendedor=vendedor)
        request.session['confirma'] = True

    # Armar lista de productos para el pedido
    list_p = [f'{p.cantidad} {p.producto}' for p in Prods]

    # Procesar cliente
    consumidor_final = Cliente.objects.get(nombre="Consumidor final")
    client_input = request.POST['cliente'].strip()
    if client_input:
        client_obj = Cliente.objects.filter(
            nombre__iexact=client_input).first()
        if not client_obj:
            client_obj = Cliente.objects.create(nombre=client_input)
    else:
        client_obj = consumidor_final

    try:
        # Crear el pedido
        pedido = Pedido.objects.create(
            numero=n_pedido,
            producto=', '.join(list_p),
            descripcion=request.POST['info_adic'],
            precio=float(pre.replace(',', '.')),
            senia=float(se.replace(',', '.')),
            saldo=round(float(pre.replace(',', '.')) -
                        float(se.replace(',', '.')), 2),
            estado=request.POST['estado'],
            presupuesto=request.POST['n_presupuesto'],
            cliente=client_obj,
        )

        # Segunda pasada: actualizar insumos
        for p in Prods:
            if not p.producto.tercerizado:
                actualizar_stock_insumos(
                    p.producto, p.cantidad, modo='descontar',
                    request=request, pedido=pedido
                )

        messages.success(
            request, f'El pedido {n_pedido} se ha registrado exitosamente.')

    except Exception as e:
        transaction.set_rollback(True)
        messages.error(
            request, f'Hubo un error al registrar el pedido: {str(e)}')

    return redirect(url)


def get_productos_info(request):
    presupuesto_id = request.GET.get('presupuesto_id')

    if not presupuesto_id:
        return JsonResponse({'error': 'Presupuesto ID no proporcionado'}, status=400)

    productos = ProductoCotizado.objects.filter(presupuesto_id=presupuesto_id)

    productos_info = []
    for p in productos:
        productos_info.append({
            'producto': p.producto.nombre,  # 👈 nombre del producto
            'info_adic': p.info_adic or '',  # evitar nulls
            'empaquetado': p.empaquetado,
            'cantidad': p.cantidad,
        })

    return JsonResponse({'productos': productos_info})


@login_required
def eliminar_pedido(request, pedido_id):
    try:
        pedido = Pedido.objects.get(numero=pedido_id)
        productos = ProductoCotizado.objects.filter(
            presupuesto=pedido.presupuesto)

        for p in productos:
            if not p.producto.tercerizado:
                actualizar_stock_insumos(
                    p.producto, p.cantidad, modo='reponer')

        pedido.delete()
        messages.success(
            request, f'El pedido {pedido_id} se ha borrado y los insumos se han restaurado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se ha podido borrar el pedido. Error({e})')
    return redirect('/pedidos')


def actualizar_stock_insumos(producto, cantidad, modo='descontar', request=None, pedido=None):
    advertencias = []
    componentes = ComponenteProducto.objects.filter(
        producto=producto, alternativo=False)

    for comp in componentes:
        insumo = comp.insumo
        cantidad_necesaria = comp.cantidad * cantidad  # en unidad de composición
        stock_real = insumo.stock_real()

        if modo == 'descontar':
            if stock_real >= cantidad_necesaria:
                nuevo_stock = stock_real - cantidad_necesaria
            else:
                faltante = cantidad_necesaria - stock_real
                nuevo_stock = 0
                advertencias.append(
                    f'Necesitarás comprar {faltante:.2f} {insumo.unidad_composicion} de {insumo.nombre} para completar este pedido.'
                )

                # Registro del faltante
                FaltanteInsumo.objects.create(
                    insumo=insumo,
                    cantidad_faltante=faltante,
                    pedido=pedido
                )

            insumo.stock = nuevo_stock / insumo.factor_conversion
            insumo.save()

        elif modo == 'reponer':

            cantidad_disponible = cantidad_necesaria  # en unidad de composición

            faltantes = FaltanteInsumo.objects.filter(
                insumo=insumo, resuelto=False).order_by('registrado_en')

            for f in faltantes:
                if cantidad_disponible <= 0:
                    break

                if cantidad_disponible >= f.cantidad_faltante:
                    cantidad_disponible -= f.cantidad_faltante
                    f.resuelto = True
                    f.save()
                else:
                    f.cantidad_faltante -= cantidad_disponible
                    cantidad_disponible = 0
                    f.save()

            # Solo si sobra después de cubrir faltantes, se actualiza el stock
            if cantidad_disponible > 0:
                insumo.stock += cantidad_disponible / insumo.factor_conversion
                insumo.save()
            elif modo == 'resolver':
                faltantes = FaltanteInsumo.objects.filter(
                    insumo=insumo, pedido=pedido, resuelto=False)
                for f in faltantes:
                    f.resuelto = True
                    f.save()
    # Feedback al usuario
    if request and advertencias:
        for adv in advertencias:
            messages.error(request, adv)


@login_required
def viajes_cadete(request):
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')
    viajes_pendientes = ViajeCadete.objects.filter(
        pagado=False).order_by('-fecha')
    viajes_pagados = ViajeCadete.objects.filter(pagado=True).order_by('-fecha')

    total = sum(v.precio for v in viajes_pendientes)

    data = {
        'viajes_pendientes': viajes_pendientes,
        'viajes_pagados': viajes_pagados,
        'total': total,
        'usuario': usuario_nombre,
        'img': img,
        'autorizado': autorizado,
    }

    return render(request, 'pedidos/viajes_cadete.html', data)


def guardar_viaje_cadete(request):
    if request.method != "POST":
        messages.error(request, "Acceso inválido al formulario.")
        return redirect("/pedidos/viajesCadete")

    viaje_id = request.POST.get("viajeId")
    fecha = request.POST.get("fecha")
    origen = request.POST.get("origen")
    destino = request.POST.get("destino")
    precio = request.POST.get("precio")
    pagado = request.POST.get("pagado") == "on"
    fecha_pago = request.POST.get("fecha_pago")

    # Validación mínima
    if not fecha or not origen or not destino or not precio:
        messages.error(
            request, "Todos los campos obligatorios deben estar completos.")
        return redirect("/pedidos/viajesCadete")

    try:
        precio = float(precio)
    except ValueError:
        messages.error(request, "El precio debe ser un número válido.")
        return redirect("/pedidos/viajesCadete")

    try:
        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "La fecha no tiene un formato válido.")
        return redirect("/pedidos/viajesCadete")

    fecha_pago_obj = None
    if pagado and fecha_pago:
        try:
            fecha_pago_obj = datetime.strptime(fecha_pago, "%Y-%m-%d").date()
        except ValueError:
            messages.warning(
                request, "La fecha de pago no es válida. Se omitirá.")

    if viaje_id and viaje_id != "0":
        viaje = get_object_or_404(ViajeCadete, id=viaje_id)
        viaje.fecha = fecha_obj
        viaje.origen = origen
        viaje.destino = destino
        viaje.precio = precio
        viaje.pagado = pagado
        viaje.fecha_pago = fecha_pago_obj
        viaje.save()
        messages.success(
            request, f"Viaje #{viaje.id} actualizado correctamente.")
    else:
        viaje = ViajeCadete.objects.create(
            fecha=fecha_obj,
            origen=origen,
            destino=destino,
            precio=precio,
            pagado=pagado,
            fecha_pago=fecha_pago_obj
        )
        messages.success(request, f"Viaje #{viaje.id} creado exitosamente.")

    return redirect("/pedidos/viajesCadete")


def borrar_viaje_cadete(request, viaje_id):
    try:
        viaje = ViajeCadete.objects.get(id=viaje_id)
        origen_destino = f"{viaje.origen} -> {viaje.destino}"
        viaje.delete()
        messages.success(
            request, f'El viaje {origen_destino} se ha borrado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se ha podido borrar el viaje. Error({e})')
    return redirect('/pedidos/viajesCadete')


def info_viaje_cadete(request, viaje_id):
    try:
        viaje = ViajeCadete.objects.get(id=viaje_id)
        data = {
            'id': viaje.id,
            'fecha': viaje.fecha.strftime('%Y-%m-%d'),
            'origen': viaje.origen,
            'destino': viaje.destino,
            'precio': float(viaje.precio),
            'pagado': viaje.pagado,
            'fecha_pago': viaje.fecha_pago.strftime('%Y-%m-%d') if viaje.fecha_pago else None
        }
        return JsonResponse(data)
    except ViajeCadete.DoesNotExist:
        raise Http404("Viaje no encontrado")


@csrf_exempt
def actualizar_estado_viajes(request):
    if request.method != "POST":
        messages.error(request, "Método no permitido.")
        return JsonResponse({"redirect_url": reverse("nombre_de_la_vista_principal")})

    try:
        data = json.loads(request.body)
        ids = data.get("ids", [])
        pagado = data.get("pagado", False)

        actualizados = 0
        for viaje_id in ids:
            viaje = ViajeCadete.objects.filter(id=viaje_id).first()
            if viaje:
                viaje.pagado = pagado
                viaje.fecha_pago = timezone.now() if pagado else None
                viaje.save()
                actualizados += 1

        if actualizados:
            estado_txt = "pagados" if pagado else "NO pagados"
            messages.success(
                request, f"{actualizados} viaje(s) marcados como {estado_txt}.")
        else:
            messages.error(request, "No se pudo actualizar ningún viaje.")

        return JsonResponse({"redirect_url": reverse("viajesCadete")})
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return JsonResponse({"redirect_url": reverse("viajesCadete")})


def exportar_viajes_cadete(request):
    # Filtrar solo los viajes no pagados
    viajes = ViajeCadete.objects.filter(fecha_pago__isnull=True)

    # Crear workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Viajes NO pagados"

    # Encabezados
    ws.append(["Fecha", "Origen", "Destino", "Precio", "Estado"])

    total = 0

    for v in viajes:
        precio = float(v.precio)
        total += precio
        ws.append([
            v.fecha.strftime("%d/%m/%Y"),
            v.origen,
            v.destino,
            precio,
            "Pendiente"
        ])

    # Fila totalizadora
    ws.append(["", "", "TOTAL", total, ""])

    # Estilo opcional: negrita en la fila total
    from openpyxl.styles import Font
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=viajes_no_pagados.xlsx'
    wb.save(response)
    return response
