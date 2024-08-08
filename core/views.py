from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from datetime import datetime
from django.contrib.auth.decorators import login_required
from .functions import *
from django.contrib.auth.models import User
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

# Vista que permite la edición del perfil del usuario.


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
            username=username).usuario.birthday, '%Y-%m-%d')
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

# Vista que permite cambiar la contraseña una vez que este ingresó a la aplicación.


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

# Vista que permite restablecer la contraseña en caso de olvido.


def restablecer_contrasena(request):
    return render(request, 'core/restablecer_contrasena.html')


def correo_contrasena(request):
    usuario = request.POST['usuario']
    # print(usuario)
    email = request.POST['email']
    # print(email)
    try:
        user = User.objects.get(username=usuario)
        if user.email == email:
            contrasena_temp = generar_contrasena()
            user.set_password(contrasena_temp)
            user.save()
            # print('llega hasta aquí')
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


@login_required
def cerrar_sesion(request):
    logout(request)
    return redirect('login')


@login_required
def obtener_usuarios(request):
    usuarios = User.objects.all().exclude(first_name='Ramiro',
                                          last_name='Latigano').values('id', 'first_name', 'last_name')
    usuarios_list = [
        {'id': user['id'], 'nombre_completo': f"{user['first_name']} {user['last_name']}"} for user in usuarios]
    return JsonResponse({'usuarios': usuarios_list})


def prueba(request):
    return render(request, 'core/prueba.html')
