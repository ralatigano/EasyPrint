from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Cliente
from django.contrib import messages
from datetime import date
from django.http import JsonResponse
from pedidos.models import Pedido
from core.decorators import solo_gerencia

# Create your views here.
app_name = 'clientes'

# Vista que presenta la tabla de clientes.


@login_required
def clientes(request):
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')
    clientes = Cliente.objects.all().order_by('-created')
    data = {
        'usuario': usuario_nombre,
        'autorizado': autorizado,
        'img': img,
        'clientes': clientes,
        'Categorias': Cliente.CONTACTO,
    }

    return render(request, 'clientes/clientes.html', data)

# Vista que recibe el POST del modal de edición de cliente y actualiza la base de datos.


def editar_cliente(request):
    if request.method == 'POST':
        try:
            cliente = Cliente.objects.get(id=request.POST['id'])
            if cliente.nombre != request.POST['nombre']:
                cliente.nombre = request.POST['nombre']
            if cliente.cuit != request.POST['cuit']:
                cliente.cuit = request.POST['cuit']
            if cliente.negocio != request.POST['negocio']:
                cliente.negocio = request.POST['negocio']
            if cliente.metodo_contacto != int(request.POST['met_contacto']):
                cliente.metodo_contacto = int(request.POST['met_contacto'])
            if cliente.telefono != request.POST['telefono']:
                cliente.telefono = request.POST['telefono']
            if cliente.direccion != request.POST['direccion']:
                cliente.direccion = request.POST['direccion']

            cliente.save()
            messages.success(request, 'Cliente actualizado exitosamente')
        except Exception as e:
            messages.error(
                request, 'Error al actualizar el cliente. Error: ' + str(e))

        return redirect('/clientes')


def obtener_cliente(request, cliente_id):
    try:
        cliente = Cliente.objects.get(id=cliente_id)
    except Cliente.DoesNotExist:
        return JsonResponse({'error': 'Cliente no encontrado'}, status=404)

    # Pedidos que impiden el borrado
    pedidos_activos = Pedido.objects.filter(
        cliente=cliente
    ).exclude(
        estado='Terminado y pagado'
    )

    bloqueado = pedidos_activos.exists()

    return JsonResponse({
        'referencia': cliente.referencia,
        'nombre': cliente.nombre,
        'bloqueado': bloqueado,
        'pedidos_activos': list(
            pedidos_activos.values('numero', 'estado')
        ) if bloqueado else [],
    })


@login_required
@solo_gerencia
def borrar_cliente(request, cliente_id):
    try:
        cliente = Cliente.objects.get(id=cliente_id)
        referencia = cliente.referencia  # lo guardamos antes de borrar para el mensaje
        cliente.delete()
        messages.success(
            request, f'El cliente {referencia} se ha eliminado correctamente.')
    except Cliente.DoesNotExist:
        messages.error(request, 'No se encontró el cliente.')
    except Exception as e:
        messages.error(
            request, f'No se ha podido eliminar el cliente. Error: {e}')
    return redirect('/clientes')
