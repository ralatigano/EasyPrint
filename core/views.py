from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from datetime import datetime
from django.contrib.auth.decorators import login_required
from .functions import *
from django.contrib.auth.models import User, Group
from .models import Usuario
from productos.models import Producto, Categoria
from presupuestos.models import Presupuesto
from pedidos.models import Pedido
from clientes.models import Cliente
from datetime import date
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.contrib.auth import login
from .forms import RegistroUsuarioForm

# Create your views here.

# Vista de inicio de sesión.


def iniciar_sesion(request):
    if request.user.is_authenticated:
        usuario = User.objects.get(username=request.user)
        autorizado = usuario.is_superuser or usuario.groups.filter(
            name='Gerencia').exists()
        usuario_model = Usuario.objects.get(user=usuario)
        request.session['vendedor'] = usuario.id
        request.session['autorizado'] = autorizado
        request.session['usuario_nombre'] = usuario.get_full_name()
        request.session['img'] = usuario_model.image.url if usuario_model.image else None

        return redirect('presupuestos/inicio')
    else:
        if request.method == 'POST':
            username = request.POST['username']
            password = request.POST['password']
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                autorizado = user.is_superuser or user.groups.filter(
                    name='Gerencia').exists()
                usuario_model = Usuario.objects.get(user=user)
                request.session['vendedor'] = usuario_model.id
                request.session['autorizado'] = autorizado
                request.session['usuario_nombre'] = user.get_full_name()
                request.session['img'] = usuario_model.image.url if usuario_model.image else None
                return redirect('presupuestos/inicio')
            else:
                messages.error(request, 'Usuario o contraseña incorrectos.')
        form = AuthenticationForm()
        return render(request, 'core/login.html', {'form': form})

# Vista que permite la creación de nuevos usuarios.


@login_required
def registrar_usuario(request):
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Usuario creado con éxito.')
            form = RegistroUsuarioForm()  # Limpiar el formulario para la próxima entrada
        else:
            messages.error(
                request, 'Error al crear el usuario. Por favor, revisa los datos ingresados.')
    else:
        form = RegistroUsuarioForm()
    data = {
        'form': form,
        'autorizado': autorizado,
        'usuario': usuario_nombre,
        'img': img
    }
    return render(request, 'core/registro.html', data)

# Vista que permite la edición del perfil del usuario por el usuario mismo.


@login_required
def editar_perfil(request):
    if request.method == 'POST':
        username = request.user
        try:
            info_usuario = User.objects.get(username=username)
            if request.POST['nombre'] != info_usuario.first_name:
                info_usuario.first_name = request.POST['nombre']
            if request.POST['apellido'] != info_usuario.last_name:
                info_usuario.last_name = request.POST['apellido']
            if request.POST['fecha_nac'] != info_usuario.usuario.birthday:
                info_usuario.usuario.birthday = request.POST['fecha_nac']
            if request.FILES:
                info_usuario.usuario.image = request.FILES['imagen_nueva']
            info_usuario.usuario.save()
            info_usuario.save()
            request.session['img'] = info_usuario.usuario.image.url
            messages.success(request, 'Información actualizada correctamente.')
        except Exception as e:
            messages.error(
                request, 'Hubo un error al actualizar la información de perfil: ' + str(e) + '.')
        return redirect('perfil')
    else:
        username = request.user
        autorizado = request.session.get('autorizado')
        usuario_nombre = request.session.get('usuario_nombre')
        img = request.session.get('img')
        first_name = User.objects.get(username=username).first_name
        last_name = User.objects.get(username=username).last_name
        birthday = datetime.strftime(User.objects.get(
            username=username).usuario.birthday, '%Y-%m-%d') if User.objects.get(username=username).usuario.birthday else ''
        try:
            img = User.objects.get(username=request.user).usuario.image.url
        except:
            img = ''
        data = {
            'autorizado': autorizado,
            'usuario': usuario_nombre,
            'first_name': first_name,
            'last_name': last_name,
            'birthday': birthday,
            'img': img
        }
        return render(request, 'core/perfil.html', data)

# Vista que permite cambiar la contraseña al usuario una vez que este ingresó a la aplicación.


@login_required
def cambiar_contrasena(request):
    if request.method == 'POST':
        if request.POST['contrasena1'] == request.POST['contrasena2'] and len(request.POST['contrasena1']) >= 8:
            user = User.objects.get(username=request.user)
            user.set_password(request.POST['contrasena1'])
            user.save()
            messages.success(request, 'Contraseña cambiada correctamente.')
            return redirect('perfil')
        else:
            messages.error(
                request, 'Las contraseñas no coinciden o es demasiado corta.')
            return redirect('cambiarContrasena')
    else:
        usuario = User.objects.get(username=request.user).get_full_name()
        try:
            img = User.objects.get(username=request.user).usuario.image.url
            data = {
                'usuario': usuario,
                'img': img
            }
        except:
            data = {'usuario': usuario}
        return render(request, 'core/cambiar_contrasena.html', data)

# Vista que permite restablecer la contraseña en caso de olvido sin haber ingresado a la app.


def restablecer_contrasena(request):
    return render(request, 'core/restablecer_contrasena.html')

# Vista complementaria al reesttablecimiento de la contraseña.


def correo_contrasena(request):
    usuario = request.POST['usuario']
    email = request.POST['email']
    try:
        user = User.objects.get(username=usuario)
        if user.email == email:
            contrasena_temp = generar_contrasena()
            user.set_password(contrasena_temp)
            user.save()
            notificar_contrasena(email, usuario, contrasena_temp)
            messages.success(
                request, 'Se ha generado una contraseña temporal y se ha enviado al correo electrónico suministrado.')
        else:
            messages.error(
                request, 'El usuario no coincide con el correo suministrado.')
    except Exception as e:
        messages.error(
            request, 'El nombre de usuario es incorrecto. ' + str(e) + '.')
    return redirect('login')

  # Vista que almacena la preferencia del usuario en relación al tema claro u oscuro de modo que
  # este se ajuste en cualquier dispositivo donde se loguee el usuario.


@login_required
def dark_mode(request, tema):

    usuario = Usuario.objects.get(user=request.user)
    if tema == 'light':
        usuario.dark_mode = False
    else:
        usuario.dark_mode = True
    usuario.save()

    request.session['url_anterior'] = request.META.get('HTTP_REFERER')
    # Redirigir al usuario a la misma página después del procesamiento
    return redirect(request.session['url_anterior'])

# Vista que pasa la preferencia de tema del usuario que se loguea.


@login_required
def get_dark_mode(request):
    usuario = Usuario.objects.get(user=request.user)
    dark_mode = 'dark' if usuario.dark_mode else 'light'
    return JsonResponse({'dark_mode': dark_mode})

# Vista que maneja el cerrado de sesión.


@login_required
def cerrar_sesion(request):
    logout(request)
    return redirect('login')

# Vista que obtiene los datos de los usuarios para pasarlos al frontend para el modal de edición.


@login_required
def obtener_usuarios(request):
    usuarios = User.objects.all().exclude(first_name='Ramiro',
                                          last_name='Latigano').values('id', 'first_name', 'last_name')
    usuarios_list = [
        {'id': user['id'], 'nombre_completo': f"{user['first_name']} {user['last_name']}"} for user in usuarios]
    return JsonResponse({'usuarios': usuarios_list})


# Vista que presenta una tabla de los usuarios con las funcionalidades del CRUD de dicho objeto.
@login_required
def usuarios(request):
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')
    Usus = User.objects.all().exclude(first_name='Ramiro', last_name='Latigano')
    usuarios_con_datos = []
    for usuario in Usus:
        grupos_ids = ','.join([str(grupo.id)
                              for grupo in usuario.groups.all()])
        usuario.recipient_data = f"{usuario.id}|{usuario.username}|{usuario.first_name}|{usuario.last_name}|{usuario.email}|{usuario.usuario.telefono}|{grupos_ids}"
        usuarios_con_datos.append(usuario)
    if autorizado:
        data = {
            'usuario': usuario_nombre,
            'img': img,
            'Usus': usuarios_con_datos,
            'autorizado': autorizado,
        }
        return render(request, 'core/usuarios.html', data)
    else:
        messages.error(
            request, 'No tiene permisos para acceder a esta sección.')
        return redirect('presupuestos/inicio')

# Vista consultada desde el frontend para obtener información para editar un usuario.


@login_required
def info_grupos(request):
    if request.method == 'GET':
        grupos = Group.objects.all()
        data = {'Group': [{'id': grupo.id, 'nombre': grupo.name}
                          for grupo in grupos]}
        return JsonResponse(data)
    else:
        return JsonResponse({'error': 'Método no permitido'}, status=405)

# Vista que recibe el POST del modal de edición de usuario y actualiza la base de datos.


@login_required
def editar_usuario(request):
    if request.method == 'POST':
        user_id = request.POST.get('id')
        username = request.POST.get('username')
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        email = request.POST.get('email')
        telefono = request.POST.get('telefono')
        # Obtener los grupos seleccionados como lista
        grupos = request.POST.getlist('grupo')

        # Cargar la instancia del usuario
        user = get_object_or_404(User, id=user_id)
        usuario = get_object_or_404(Usuario, user=user)

        # Inicializar la bandera de cambios
        cambios = False

        # Comparar y actualizar los valores si hay cambios
        if user.username != username:
            user.username = username
            cambios = True
        if user.first_name != nombre:
            user.first_name = nombre
            cambios = True
        if user.last_name != apellido:
            user.last_name = apellido
            cambios = True
        if user.email != email:
            user.email = email
            cambios = True
        if usuario.telefono != telefono:
            usuario.telefono = telefono
            cambios = True

        # Actualizar los grupos
        if set(grupos) != set(user.groups.values_list('id', flat=True)):
            user.groups.clear()  # Limpiar grupos actuales
            for grupo_id in grupos:
                grupo = Group.objects.get(id=grupo_id)
                user.groups.add(grupo)
            cambios = True

        # Guardar los cambios si hay alguno
        if cambios:
            user.save()
            usuario.save()
            messages.success(request, 'Usuario actualizado correctamente.')
        else:
            messages.info(request, 'No hubo cambios para guardar.')
    return redirect('usuarios')  # Redirige a la vista deseada

# Vista que permite eliminar un usuario de la base de datos.


@login_required
def borrar_usuario(request, usuario_id):
    try:
        usu = User.objects.filter(id=usuario_id)
        usu.delete()
        messages.success(request, 'El usuario se ha aniquilado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se ha podido borrar el usuario. Error({e})')
    return redirect('/usuarios')
