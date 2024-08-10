from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Cliente
from django.contrib import messages
from datetime import date

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
    }

    return render(request, 'clientes/clientes.html', data)

# Vista que recibe el POST del modal de edición de cliente y actualiza la base de datos.


def editar_cliente(request):
    if request.method == 'POST':
        try:
            cliente = Cliente.objects.get(id=request.POST['id'])
            if cliente.nombre != request.POST['nombre']:
                cliente.nombre = request.POST['nombre']
            if cliente.negocio != request.POST['negocio']:
                cliente.negocio = request.POST['negocio']
            if cliente.telefono != request.POST['telefono']:
                cliente.telefono = request.POST['telefono']
            if cliente.direccion != request.POST['direccion']:
                cliente.direccion = request.POST['direccion']

            cliente.updated = date.today()
            cliente.save()
            messages.success(request, 'Cliente actualizado exitosamente')
        except Exception as e:
            messages.error(
                request, 'Error al actualizar el cliente. Error: ' + str(e))

        return redirect('/clientes')
