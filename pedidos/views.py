from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Pedido
from presupuestos.models import Presupuesto
from productos.models import Producto
from clientes.models import Cliente
from django.contrib.auth.models import User
from django.contrib import messages
from core.functions import *
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

# Renderiza un formulario para completar detalles de un nuevo pedido. Crea un presupuesto. Registra un cliente si es nuevo.


@login_required
def completar_pedido(request):
    editando_presup = request.session.get('editando_presup', False)
    np_global = request.session.get('np_global', 0)
    vendedor = request.session.get('vendedor')
    n_ped = armar_numero_pedido()
    t = 0
    d = 0
    t_d = 0
    c = ''
    if editando_presup:
        Prods = Producto.objects.filter(presupuesto=np_global)
    else:
        Prods = Producto.objects.filter(
            presupuesto=None).filter(vendedor=vendedor)
    lista = []
    for p in Prods:
        lista.append(f'{p.cantidad} {p.nombre}')
        t = t + p.resultado
        d = d + p.desc_plata
        c = p.cliente
    t_d = round(t - d, 2)
    data = {
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

    # if editando_presup:
    #     Prods = Producto.objects.filter(presupuesto=np_global)
    #     lista = []
    #     for p in Prods:
    #         lista.append(f'{p.cantidad} {p.nombre}')
    #     cli = Presupuesto.objects.get(numero=np_global).cliente
    #     total = Presupuesto.objects.get(numero=np_global).total
    #     data = {
    #         'n_ped': n_ped,
    #         'np': np_global,
    #         'prods': lista,
    #         'cli': cli,
    #         'total': total
    #     }
    #     return render(request, 'pedidos/completar_pedido.html', data)
    # else:
    #     request.session['confirma'] = True
    #     return redirect('/presupuestos/guardarPresupuesto')

# vista que permite cambiar el estado de un pedido.


@login_required
def cambiar_estado(request):
    if request.POST['estado'] != 'Elegir un estado':
        n_pedido = request.POST['cambiarPedido_estado']
        try:
            pedido = Pedido.objects.get(numero=n_pedido)
            pedido.estado = request.POST['estado']
            pedido.save()
            messages.success(
                request, 'El estado del pedido se ha cambiado exitosamente.')
        except Exception as e:
            messages.error(
                request, 'Hubo un error al editar el pedido. ' + str(e))
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


@login_required
def confirmar_pedido(request):
    if request.method == 'POST':
        url = ''
        editando_presup = request.session.get('editando_presup', False)
        np_global = request.session.get('np_global', 0)
        pre = request.POST['total_neto']
        se = request.POST['senia']
        vendedor = request.session.get('vendedor')
        list_p = []
        if editando_presup:
            Prods = Producto.objects.filter(presupuesto=np_global)
            url = '/pedidos'
        else:
            Prods = Producto.objects.filter(
                presupuesto=None).filter(vendedor=vendedor)
            request.session['confirma'] = True
            url = '/presupuestos/guardarPresupuesto'
        for p in Prods:
            list_p.append(f'{p.cantidad} {p.nombre}')
        try:
            cliente = Cliente.objects.get(nombre=request.POST['cliente'])
        except:
            cliente = Cliente.objects.create(
                nombre=request.POST['cliente'],
            )
        try:
            Pedido.objects.create(
                numero=request.POST['n_pedido'],
                producto=list_p,
                descripcion=request.POST['info_adic'],
                precio=float(pre.replace(',', '.')),
                senia=float(se.replace(',', '.')),
                saldo=round(float(pre.replace(',', '.')) -
                            float(se.replace(',', '.')), 2),
                estado=request.POST['estado'],
                presupuesto=request.POST['n_presupuesto'],
                cliente=cliente,
            )
            messages.success(
                request, f'El pedido {request.POST["n_pedido"]} se ha registrado exitosamente.')
        except Exception as e:
            messages.error(
                request, 'Hubo un error al registrar el pedido. ' + str(e))

        return redirect(url)

    # return redirect('/pedidos')
