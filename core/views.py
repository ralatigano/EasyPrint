from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .functions import *
from django.contrib.auth.models import User, Group
from .models import (
    Usuario, AliasPago, ConfiguracionPresupuesto,
    CostoFijo, ParametrosProduccion,
)
from datetime import datetime
from .forms import RegistroUsuarioForm
from core.decorators import solo_gerencia
from core.utils import parse_ar, parse_decimal_flexible
from core import costos
from decimal import Decimal, InvalidOperation
from django.views.decorators.http import require_POST, require_GET

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
@solo_gerencia
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
    usuario.dark_mode = (tema != 'light')
    usuario.save()
    return JsonResponse({'ok': True})

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


@login_required
def usuario_info(request, user_id):
    try:
        usuario = User.objects.get(id=user_id)
        data = {
            'id': usuario.id,
            'nombre_completo': usuario.usuario.nombre_completo,
            'username': usuario.username,
            'first_name': usuario.first_name,
            'last_name': usuario.last_name,
            'email': usuario.email,
            'telefono': usuario.usuario.telefono or '',
            'grupos': list(usuario.groups.values_list('id', flat=True)),
            'grupos_names': list(usuario.groups.values_list('name', flat=True)),
        }
        return JsonResponse(data)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)

# Vista que presenta una tabla de los usuarios con las funcionalidades del CRUD de dicho objeto.


@login_required
@solo_gerencia
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
    grupos = Group.objects.all()
    if autorizado:
        data = {
            'usuario': usuario_nombre,
            'grupos': grupos,
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
@solo_gerencia
def crear_editar_usuario(request):
    user_id = request.POST.get('user_id')
    es_nuevo = (not user_id or user_id == '0')

    try:
        if es_nuevo:
            username = (request.POST.get('username') or '').strip()
            if not username:
                messages.error(request, 'El nombre de usuario es obligatorio.')
                return redirect('usuarios')
            if User.objects.filter(username=username).exists():
                messages.error(request, 'El nombre de usuario ya existe.')
                return redirect('usuarios')

            password = request.POST.get('password') or ''
            password2 = request.POST.get('password2') or ''
            if not password or not password2:
                messages.error(
                    request, 'Debés ingresar y confirmar la contraseña.')
                return redirect('usuarios')
            if password != password2:
                messages.error(request, 'Las contraseñas no coinciden.')
                return redirect('usuarios')

            user = User.objects.create_user(
                username=username,
                email=request.POST.get('email') or '',
                first_name=request.POST.get('first_name') or '',
                last_name=request.POST.get('last_name') or '',
                password=password,
            )
            usuario = get_object_or_404(Usuario, user=user)
            mensaje_ok = 'Usuario creado correctamente.'

        else:
            user = get_object_or_404(User, id=user_id)
            usuario = get_object_or_404(Usuario, user=user)

            username = (request.POST.get('username') or '').strip()
            if not username:
                messages.error(request, 'El nombre de usuario es obligatorio.')
                return redirect('usuarios')
            if User.objects.filter(username=username).exclude(id=user.id).exists():
                messages.error(request, 'El nombre de usuario ya existe.')
                return redirect('usuarios')

            user.username = username
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            user.save()

            # Cambio de contraseña opcional
            cambiar_password = request.POST.get('cambiar_password') == '1'
            if cambiar_password:
                password = request.POST.get('password') or ''
                password2 = request.POST.get('password2') or ''
                if not password or not password2:
                    messages.error(
                        request, 'Debés ingresar y confirmar la nueva contraseña.')
                    return redirect('usuarios')
                if password != password2:
                    messages.error(request, 'Las contraseñas no coinciden.')
                    return redirect('usuarios')
                try:
                    validate_password(password, user)
                    user.set_password(password)
                    user.save()
                except ValidationError as e:
                    messages.error(request, ' '.join(e.messages))
                    return redirect('usuarios')

            mensaje_ok = 'Usuario actualizado correctamente.'

        # Datos del perfil
        usuario.telefono = request.POST.get('telefono', '')
        usuario.save()

        # Grupos
        grupo_id = request.POST.get('grupo')
        if grupo_id:
            grupo = Group.objects.filter(id=grupo_id).first()
            if grupo:
                user.groups.set([grupo])
        else:
            user.groups.clear()

        messages.success(request, mensaje_ok)

    except Exception as e:
        messages.error(request, f'Ocurrió un error al guardar el usuario: {e}')

    return redirect('usuarios')

# Vista que permite eliminar un usuario de la base de datos.


@login_required
@solo_gerencia
def borrar_usuario(request, usuario_id):
    try:
        usu = User.objects.filter(id=usuario_id)
        usu.delete()
        messages.success(request, 'El usuario se ha aniquilado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se ha podido borrar el usuario. Error({e})')
    return redirect('/usuarios')


@require_GET
@login_required
def validar_username(request):
    username = (request.GET.get('u') or '').strip()
    # para excluir al usuario actual en edición
    user_id = request.GET.get('user_id')

    if not username:
        return JsonResponse({'exists': False})

    qs = User.objects.filter(username=username)
    if user_id:
        qs = qs.exclude(id=user_id)

    return JsonResponse({'exists': qs.exists()})


# ── Configuración de medios de pago (alias) — solo Gerencia ──────────────────
@login_required
@solo_gerencia
def configuracion_pagos(request):
    """Página de administración de alias de pago. POST agrega un alias nuevo."""
    if request.method == 'POST':
        alias = request.POST.get('alias', '').strip()
        titular = request.POST.get('titular', '').strip()
        if not alias:
            messages.error(request, 'El alias no puede estar vacío.')
        else:
            nuevo = AliasPago.objects.create(alias=alias, titular=titular)
            # Si es el primero, queda activo por defecto.
            if AliasPago.objects.count() == 1:
                nuevo.activo = True
                nuevo.save(update_fields=['activo'])
            messages.success(request, f'Alias "{alias}" agregado.')
        return redirect('configuracion_pagos')

    data = {
        'usuario': request.session.get('usuario_nombre'),
        'img': request.session.get('img'),
        'autorizado': request.session.get('autorizado'),
        'alias_pago': AliasPago.objects.all(),
        'config_presupuesto': ConfiguracionPresupuesto.load(),
    }
    return render(request, 'core/configuracion_pagos.html', data)


@login_required
@solo_gerencia
@require_POST
def guardar_disclaimer(request):
    """Guarda el texto del disclaimer/nota que se imprime en el PDF."""
    config = ConfiguracionPresupuesto.load()
    config.disclaimer = request.POST.get('disclaimer', '').strip()
    config.save(update_fields=['disclaimer', 'updated'])
    messages.success(request, 'Texto del presupuesto actualizado.')
    return redirect('configuracion_pagos')


@login_required
@solo_gerencia
@require_POST
def activar_alias_pago(request, alias_id):
    """Marca un alias como activo (el que se imprime) y desactiva los demás."""
    alias = get_object_or_404(AliasPago, id=alias_id)
    AliasPago.objects.exclude(id=alias.id).update(activo=False)
    alias.activo = True
    alias.save(update_fields=['activo'])
    messages.success(request, f'Alias "{alias.alias}" marcado como activo.')
    return redirect('configuracion_pagos')


@login_required
@solo_gerencia
@require_POST
def borrar_alias_pago(request, alias_id):
    """Elimina un alias. Si era el activo, activa otro si queda alguno."""
    alias = get_object_or_404(AliasPago, id=alias_id)
    era_activo = alias.activo
    alias.delete()
    if era_activo:
        otro = AliasPago.objects.first()
        if otro:
            otro.activo = True
            otro.save(update_fields=['activo'])
    messages.success(request, 'Alias eliminado.')
    return redirect('configuracion_pagos')


# ── Configuración de estructura de costos — solo Gerencia ────────────────────
def _safe_int(valor, default=0):
    """int() tolerante: nunca lanza; devuelve `default` ante entrada inválida."""
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return default


def _grupos_costos():
    """Agrupa las líneas de costo por `grupo` con subtotal (mensual) por grupo,
    para el render del listado. El orden ya viene por (grupo, concepto)."""
    grupos = {}
    for c in CostoFijo.objects.all():
        clave = c.grupo or 'Sin grupo'
        grupos.setdefault(clave, {'nombre': clave, 'items': [], 'subtotal': Decimal('0')})
        grupos[clave]['items'].append(c)
        if c.activo:
            grupos[clave]['subtotal'] += c.monto_mensual
    return list(grupos.values())


def _panel_costos():
    """Valores autoritativos calculados en el server para el panel de la tasa."""
    return {
        'costo_fijo_mensual': costos.costo_fijo_mensual(),
        'horas_disponibles': costos.horas_disponibles_mes(),
        'horas_productivas': costos.horas_productivas_mes(),
        'tasa_hora': costos.tasa_hora(),
    }


@login_required
@solo_gerencia
def configuracion_costos(request):
    """Página de administración de la estructura de costos fijos y la capacidad
    productiva. POST agrega una línea de costo nueva (alta inline)."""
    if request.method == 'POST':
        concepto = request.POST.get('concepto', '').strip()
        periodicidad = request.POST.get('periodicidad', 'mensual')
        periodicidades_validas = [p[0] for p in CostoFijo.PERIODICIDADES]
        if not concepto:
            messages.error(request, 'El concepto no puede estar vacío.')
        elif periodicidad not in periodicidades_validas:
            messages.error(request, 'Periodicidad inválida.')
        else:
            CostoFijo.objects.create(
                concepto=concepto,
                grupo=request.POST.get('grupo', '').strip(),
                monto=parse_ar(request.POST.get('monto')),
                periodicidad=periodicidad,
                meses_amortizacion=max(_safe_int(
                    request.POST.get('meses_amortizacion'), 12), 1),
            )
            messages.success(request, f'Costo "{concepto}" agregado.')
        return redirect('configuracion_costos')

    data = {
        'usuario': request.session.get('usuario_nombre'),
        'img': request.session.get('img'),
        'autorizado': request.session.get('autorizado'),
        'grupos_costos': _grupos_costos(),
        'parametros': ParametrosProduccion.load(),
        'periodicidades': CostoFijo.PERIODICIDADES,
        'panel': _panel_costos(),
    }
    return render(request, 'core/configuracion_costos.html', data)


@login_required
@solo_gerencia
@require_POST
def guardar_costo_fijo(request, costo_id):
    """Edición inline de una línea de costo existente."""
    c = get_object_or_404(CostoFijo, id=costo_id)
    concepto = request.POST.get('concepto', c.concepto).strip()
    periodicidad = request.POST.get('periodicidad', c.periodicidad)
    periodicidades_validas = [p[0] for p in CostoFijo.PERIODICIDADES]
    if not concepto:
        messages.error(request, 'El concepto no puede estar vacío.')
        return redirect('configuracion_costos')
    if periodicidad not in periodicidades_validas:
        messages.error(request, 'Periodicidad inválida.')
        return redirect('configuracion_costos')

    c.concepto = concepto
    c.grupo = request.POST.get('grupo', c.grupo).strip()
    c.monto = parse_ar(request.POST.get('monto'))
    c.periodicidad = periodicidad
    c.meses_amortizacion = max(_safe_int(
        request.POST.get('meses_amortizacion'), 12), 1)
    c.activo = request.POST.get('activo') == 'on'
    c.save()
    messages.success(request, f'Costo "{c.concepto}" actualizado.')
    return redirect('configuracion_costos')


@login_required
@solo_gerencia
@require_POST
def borrar_costo_fijo(request, costo_id):
    """Elimina una línea de costo."""
    c = get_object_or_404(CostoFijo, id=costo_id)
    concepto = c.concepto
    c.delete()
    messages.success(request, f'Costo "{concepto}" eliminado.')
    return redirect('configuracion_costos')


@login_required
@solo_gerencia
@require_POST
def guardar_parametros_produccion(request):
    """Guarda el singleton de capacidad productiva (operarios, jornada, ratio,
    factor de corrección).

    Valida rangos y nunca deja pasar un valor que rompa el cálculo o el modelo:
    ante un dato fuera de rango avisa y no guarda nada (evita corromper la tasa
    en silencio y evita el 500 por overflow del DecimalField)."""
    operarios = _safe_int(request.POST.get('operarios'), default=None)
    dias_mes = _safe_int(request.POST.get('dias_mes'), default=None)
    horas_dia = parse_decimal_flexible(request.POST.get('horas_dia'))
    ratio = parse_decimal_flexible(request.POST.get('ratio_productivas'))
    factor = parse_decimal_flexible(request.POST.get('factor_correccion_tiempos'))

    errores = []
    if operarios is None or operarios < 0:
        errores.append('La cantidad de operarios debe ser un entero ≥ 0.')
    if dias_mes is None or not (0 <= dias_mes <= 31):
        errores.append('Los días por mes deben estar entre 0 y 31.')
    if horas_dia is None or not (Decimal('0') <= horas_dia <= Decimal('24')):
        errores.append('Las horas por día deben estar entre 0 y 24.')
    if ratio is None or not (Decimal('0') <= ratio <= Decimal('1')):
        errores.append(
            'El ratio de horas productivas debe estar entre 0 y 1 (ej: 0,70).')
    if factor is None or not (Decimal('0') < factor <= Decimal('100')):
        errores.append('El factor de corrección debe ser mayor a 0 (ej: 1,00).')

    if errores:
        for e in errores:
            messages.error(request, e)
        return redirect('configuracion_costos')

    p = ParametrosProduccion.load()
    p.operarios = operarios
    p.horas_dia = horas_dia
    p.dias_mes = dias_mes
    p.ratio_productivas = ratio
    p.factor_correccion_tiempos = factor
    try:
        p.save()
    except InvalidOperation:
        messages.error(request, 'Alguno de los valores es demasiado grande.')
        return redirect('configuracion_costos')
    messages.success(request, 'Parámetros de producción actualizados.')
    return redirect('configuracion_costos')
