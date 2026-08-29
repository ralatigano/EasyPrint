from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from .models import Pedido, ViajeCadete
from presupuestos.models import Presupuesto, DetalleSugerido
from productos.models import ProductoCotizado, ComponenteProducto, FaltanteInsumo
from clientes.models import Cliente
from django.contrib.auth.models import User
from django.contrib import messages
from .functions import *
from clientes.functions import parsear_cliente, normalizar_cuit
from django.http import JsonResponse, Http404, HttpResponse
from datetime import datetime
from django.utils import timezone
import json
from openpyxl import Workbook
from core.utils import format_ar, parse_ar
from core.decorators import solo_gerencia

# Create your views here.
app_name = 'pedidos'

# Vista con la lista de pedidos


def _pedidos_context(request):
    return {
        'Peds': Pedido.objects.order_by('-numero').all(),
        'Clientes': Cliente.objects.all().order_by("nombre"),
        'Sugerencias': DetalleSugerido.objects.order_by('-frecuencia'),
        'Estados': [e[0] for e in Pedido.ESTADOS],
        'usuario': request.session.get('usuario_nombre'),
        'img': request.session.get('img'),
        'autorizado': request.session.get('autorizado'),
    }


@login_required
def pedidos(request):
    return render(request, 'pedidos/pedidos.html', _pedidos_context(request))


@login_required
def pedidos_v2(request):
    return render(request, 'pedidos/pedidos_v2.html', _pedidos_context(request))

# Vista que setea algunos valores necesarios para poder ingresar a completar pedido desde la vista de presupuestos.


@login_required
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
    estados = [e[0] for e in Pedido.ESTADOS]
    t = 0
    d = 0
    t_d = 0
    if editando_presup:
        pre = Presupuesto.objects.get(numero=np_global)
        cliente_obj = Cliente.objects.get(id=pre.cliente.id)
        cli = f"{cliente_obj.id}|{cliente_obj.referencia}"
        Prods = ProductoCotizado.objects.filter(presupuesto=np_global)
    else:
        client_input = request.session.get('cliente_input', '').strip()
        cliente_obj = parsear_cliente(client_input)
        cli = f"{cliente_obj.id}|{cliente_obj.referencia}"
        Prods = ProductoCotizado.objects.filter(
            presupuesto=None).filter(vendedor=vendedor)
    lista = []
    for p in Prods:
        lista.append(f'{p.cantidad} {p.insumo}')
        t = t + p.resultado
        d = d + p.desc_plata
    t_d = round(t - d, 2)
    lista_clientes = Cliente.objects.all().order_by('-frecuencia', 'nombre')
    data = {
        'img': img,
        'editando_presup': editando_presup,
        'np': np_global,
        'n_ped': n_ped,
        'cliente': cli,
        'cliente_cuit': cliente_obj.cuit or '',
        'cliente_telefono': cliente_obj.telefono or '',
        'prods': lista,
        'total': t,
        'descuento': d,
        'total_neto': t_d,
        'clientes': lista_clientes,
        'Estados': estados
    }
    # request.session.pop('cliente_input', None)
    return render(request, 'pedidos/completar_pedido.html', data)

# Vista que maneja el POST del modal correspondiente para editar el estado de un pedido.


@login_required
def cambiar_estado(request):
    nuevo_estado = request.POST.get('estado')
    n_pedido = request.POST.get('cambiarPedido_estado')

    if nuevo_estado == 'Elegir un estado':
        return redirect('/pedidos/v2')

    try:
        pedido = Pedido.objects.get(numero=n_pedido)
        # Si el pedido ya fue cancelado y está bloqueado, no se puede modificar
        if pedido.estado == 'Cancelado' and getattr(pedido, 'cancelado_bloqueado', False):
            messages.error(
                request, 'Este pedido fue cancelado y no puede modificarse. Si necesitás reactivarlo, deberás crear uno nuevo.')
            return redirect('/pedidos/v2')

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

    return redirect('/pedidos/v2')


@login_required
def cambiar_estado_bulk(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    try:
        data = json.loads(request.body)
        ids = data.get("ids", [])
        nuevo_estado = data.get("estado", "")

        if not ids or not nuevo_estado:
            return JsonResponse({"error": "Datos incompletos"}, status=400)

        actualizados = 0
        saltados = 0

        for numero in ids:
            try:
                pedido = Pedido.objects.get(numero=numero)
                if pedido.estado == 'Cancelado' and getattr(pedido, 'cancelado_bloqueado', False):
                    saltados += 1
                    continue
                pedido.estado = nuevo_estado
                pedido.save()
                productos = ProductoCotizado.objects.filter(presupuesto=pedido.presupuesto)
                if nuevo_estado in ['Para retirar', 'Entregado']:
                    for p in productos:
                        if not p.producto.tercerizado:
                            actualizar_stock_insumos(p.producto, p.cantidad, modo='resolver', pedido=pedido)
                elif nuevo_estado == 'Cancelado':
                    for p in productos:
                        if not p.producto.tercerizado:
                            actualizar_stock_insumos(p.producto, p.cantidad, modo='reponer', pedido=pedido)
                    pedido.cancelado_bloqueado = True
                    pedido.save()
                actualizados += 1
            except Pedido.DoesNotExist:
                saltados += 1

        if actualizados:
            msg = f"{actualizados} pedido(s) actualizados al estado '{nuevo_estado}'."
            if saltados:
                msg += f" {saltados} no se pudieron modificar (cancelados o no encontrados)."
            messages.success(request, msg)
        else:
            messages.error(request, "No se pudo actualizar ningún pedido.")

        return JsonResponse({"redirect_url": reverse("pedidos_v2")})
    except Exception as e:
        messages.error(request, f"Error al actualizar pedidos: {str(e)}")
        return JsonResponse({"redirect_url": reverse("pedidos_v2")})


@login_required
def cambiar_enc_bulk(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    try:
        data = json.loads(request.body)
        ids = data.get("ids", [])
        encargado_id = data.get("encargado_id")

        if not ids:
            return JsonResponse({"error": "Datos incompletos"}, status=400)

        encargado = None
        enc_nombre = "Sin asignar"
        if encargado_id and encargado_id != "None":
            encargado = User.objects.get(id=encargado_id)
            enc_nombre = encargado.first_name

        actualizados = 0
        for numero in ids:
            try:
                pedido = Pedido.objects.get(numero=numero)
                pedido.encargado = encargado
                pedido.save()
                actualizados += 1
            except Pedido.DoesNotExist:
                pass

        if actualizados:
            messages.success(request, f"{actualizados} pedido(s) asignados a {enc_nombre}.")
        else:
            messages.error(request, "No se pudo actualizar ningún pedido.")

        return JsonResponse({"redirect_url": reverse("pedidos_v2")})
    except Exception as e:
        messages.error(request, f"Error al actualizar pedidos: {str(e)}")
        return JsonResponse({"redirect_url": reverse("pedidos_v2")})


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

    return redirect('/pedidos/v2')

# vista que permite agregar una descripción al pedido.


@login_required
def agregar_descripcion(request):

    n_pedido = request.POST['cambiarPedido_desc']
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
    return redirect('/pedidos/v2')

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
    return redirect('/pedidos/v2')

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
    precio = parse_ar(request.POST['total_neto'])
    senia = parse_ar(request.POST['senia'])
    saldo = round(precio - senia, 2)
    fecha_entrega = datetime.strptime(
        request.POST['fecha_entrega'], "%Y-%m-%d").date()
    url = '/pedidos/v2' if editando_presup else '/presupuestos/guardarPresupuesto'

    # Obtener productos cotizados
    if editando_presup:
        Prods = ProductoCotizado.objects.filter(presupuesto=np_global)
    else:
        Prods = ProductoCotizado.objects.filter(
            presupuesto=None, vendedor=vendedor)
        request.session['confirma'] = True

    # Armar lista de productos para el pedido
    list_p = [f'{p.cantidad} {p.producto_final}' for p in Prods]

    # Procesar cliente
    client_input = request.POST.get('cliente', '').strip()
    client_obj = parsear_cliente(client_input)

    # Actualizar el perfil del cliente con los datos del form (sólo si vinieron
    # cargados: un campo vacío no debe pisar un dato existente). No se toca el
    # cliente genérico "Consumidor final", que es un registro compartido.
    if client_obj.nombre != 'Consumidor final':
        cuit_form = normalizar_cuit(request.POST.get('cliente_cuit'))
        telefono_form = request.POST.get('cliente_telefono', '').strip()
        campos_cliente = []
        if cuit_form is not None and cuit_form != client_obj.cuit:
            client_obj.cuit = cuit_form
            campos_cliente.append('cuit')
        if telefono_form and telefono_form != client_obj.telefono:
            client_obj.telefono = telefono_form
            campos_cliente.append('telefono')
        if campos_cliente:
            client_obj.save(update_fields=campos_cliente)

    try:
        # Crear el pedido
        pedido = Pedido.objects.create(
            numero=n_pedido,
            producto=', '.join(list_p),
            descripcion=request.POST['info_adic'],
            precio=precio,
            senia=senia,
            saldo=saldo,
            estado=request.POST['estado'],
            presupuesto=request.POST['n_presupuesto'],
            cliente=client_obj,
            fecha_entrega=fecha_entrega,
        )

        # Segunda pasada: actualizar insumos
        for p in Prods:
            if not p.insumo.tercerizado:
                actualizar_stock_insumos(
                    p.insumo, p.cantidad, modo='descontar',
                    request=request, pedido=pedido
                )

        messages.success(
            request, f'El pedido {n_pedido} se ha registrado exitosamente.')

    except Exception as e:
        transaction.set_rollback(True)
        messages.error(
            request, f'Hubo un error al registrar el pedido: {str(e)}')

    return redirect(url)


@login_required
def evaluar_entrega_fecha(request):
    """Evalúa la capacidad para una fecha de entrega (Fase 6). AJAX, no bloquea.

    Las horas del pedido nuevo salen de los ítems de la cotización en curso, igual
    que confirmar_pedido: si se edita un presupuesto, sus ítems; si no, los ítems
    sueltos del vendedor en sesión.
    """
    from django.db.models import Sum
    from core import capacidad as cap

    fecha_str = request.GET.get('fecha')
    if not fecha_str:
        return JsonResponse({'ok': False, 'mensaje': 'Falta la fecha.'})
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'ok': False, 'mensaje': 'Fecha inválida.'})

    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    vendedor = request.session.get('vendedor')
    if editando_presup:
        prods = ProductoCotizado.objects.filter(presupuesto=np_global)
    else:
        prods = ProductoCotizado.objects.filter(presupuesto=None, vendedor=vendedor)
    horas_nuevas = prods.aggregate(s=Sum('t_produccion'))['s'] or 0

    r = cap.evaluar_entrega(fecha, horas_nuevas)
    return JsonResponse({
        'ok': True,
        'alcanza': r['alcanza'],
        'capacidad': float(r['capacidad']),
        'carga_comprometida': float(r['carga_comprometida']),
        'margen_libre': float(r['margen_libre']),
        'horas_nuevas': float(r['horas_nuevas']),
        'faltante': float(r['faltante']),
    })


@login_required
def get_productos_info(request):
    presupuesto_id = request.GET.get('presupuesto_id')
    pedido_numero = request.GET.get('pedido_numero')
    if not presupuesto_id:
        return JsonResponse({'error': 'Presupuesto ID no proporcionado'}, status=400)

    # Obtener productos cotizados
    productos = ProductoCotizado.objects.filter(presupuesto_id=presupuesto_id)

    productos_info = []
    for p in productos:
        productos_info.append({
            'insumo': p.insumo.nombre,
            'producto_final': p.producto_final or '',
            'descripcion': p.descripcion or '',
            'info_adic': p.info_adic or '',
            'empaquetado': p.empaquetado,
            'cantidad': p.cantidad,
        })

    # Si NO se envió pedido_numero → devolver solo productos (modal de detalles)
    if not pedido_numero:
        return JsonResponse({'productos': productos_info})

    # Si SÍ se envió pedido_numero → devolver también datos del pedido
    try:
        pedido = Pedido.objects.get(numero=pedido_numero)
        pedido_info = {
            'numero': pedido.numero,
            'cliente': pedido.cliente.referencia,
            'fecha_pedido': pedido.created.strftime('%d/%m/%Y'),
            'fecha_entrega': pedido.fecha_entrega.strftime('%d/%m/%Y') if pedido.fecha_entrega else '',
            'precio': pedido.precio,
            'senia': pedido.senia or 0,
            'saldo': pedido.saldo_real,
            'estado': pedido.estado,
        }
    except Pedido.DoesNotExist:
        pedido_info = {}

    return JsonResponse({
        'productos': productos_info,
        'pedido': pedido_info
    })


@login_required
@solo_gerencia
def eliminar_pedido(request, pedido_id):
    try:
        pedido = Pedido.objects.get(numero=pedido_id)
        productos = ProductoCotizado.objects.filter(
            presupuesto=pedido.presupuesto)

        for p in productos:
            if not p.insumo.tercerizado:
                actualizar_stock_insumos(
                    p.insumo, p.cantidad, modo='reponer')

        pedido.delete()
        messages.success(
            request, f'El pedido {pedido_id} se ha borrado y los insumos se han restaurado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se ha podido borrar el pedido. Error({e})')
    return redirect('/pedidos/v2')


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


@login_required
def guardar_viaje_cadete(request):
    if request.method != "POST":
        messages.error(request, "Acceso inválido al formulario.")
        return redirect("/pedidos/viajesCadete")

    viaje_id = request.POST.get("viajeId")
    print(f'Viaje ID: {viaje_id}')
    fecha = request.POST.get("fecha")
    origen = request.POST.get("origen")
    destino = request.POST.get("destino")
    precio = parse_ar(request.POST.get("precio"))
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


@login_required
@solo_gerencia
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


@login_required
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


@login_required
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


@login_required
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


@login_required
def cambiar_cliente_pedido(request):
    pedido_numero = request.POST.get('pedidoNumero')
    presupuesto_numero = request.POST.get('presupuestoNumero')
    cliente_input = request.POST.get('nuevoCliente', '').strip()

    if not pedido_numero or not presupuesto_numero:
        messages.error(request, "Datos incompletos para cambiar el cliente.")
        return redirect('/pedidos/v2')

    # Nuevo sistema basado en ID
    cliente = parsear_cliente(cliente_input)

    # Actualizar pedido
    try:
        pedido = Pedido.objects.get(numero=pedido_numero)
        pedido.cliente = cliente
        pedido.save()
    except Pedido.DoesNotExist:
        messages.error(request, "No se encontró el pedido.")
        return redirect('/pedidos/v2')

    # Actualizar presupuesto asociado
    try:
        presupuesto = Presupuesto.objects.get(numero=presupuesto_numero)
        presupuesto.cliente = cliente
        presupuesto.save()
    except Presupuesto.DoesNotExist:
        messages.warning(
            request,
            "El pedido fue actualizado, pero no se encontró el presupuesto asociado."
        )

    messages.success(request, "Cliente actualizado correctamente.")
    return redirect('/pedidos/v2')
