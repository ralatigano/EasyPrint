"""API de pedidos tercerizados para el agente LLM de gerencia.

Pensada para que un agente con acceso al correo registre los encargues cuando
llega la confirmación del proveedor.

**Alcance**: estas vistas son el único lugar del proyecto que acepta un
`TokenAgente`. El token no abre sesión de Django, no pasa por el login y no
sirve para ninguna otra URL del cotizador: su alcance es exactamente el CRUD
de pedidos tercerizados (más la lectura de proveedores, que hace falta para
vincular). Cada escritura queda en el log append-only de auditoría, que la API
no expone para escritura ni borrado.

**Autenticación**: cabecera `Authorization: Bearer <token>` (también se acepta
`X-API-Key: <token>`). El token se genera en /tercerizados/tokens y se muestra
una sola vez.

**Idempotencia**: en el alta conviene mandar `referencia_externa` con el
Message-ID del correo. Si el agente reprocesa el mismo correo, la API devuelve
el registro que ya existía con `duplicado: true` en lugar de duplicarlo.

**Montos**: se aceptan números JSON (`45000.5`) o strings en formato argentino
(`"45.000,50"`). Un string con punto y 1-2 decimales se lee como decimal
(`"45000.50"` = 45000,50); con 3 dígitos después del punto se lee como
separador de miles (`"45.000"` = 45000). Lo más seguro es mandar números.

**Fechas**: `YYYY-MM-DD`.
"""

import json
import re
from datetime import datetime
from decimal import Decimal
from functools import wraps

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from core.utils import parse_ar
from productos.models import Proveedor

from . import services
from .models import PagoTercerizado, PedidoTercerizado, TokenAgente

CERO = Decimal('0.00')

# Un string "45000.50" / "45000" es decimal plano; "45.000" es formato AR.
DECIMAL_PLANO = re.compile(r'^-?\d+(\.\d{1,2})?$')


# ---------------------------------------------------------------- Auth


def _token_de(request):
    cabecera = request.META.get('HTTP_AUTHORIZATION', '')
    if cabecera.lower().startswith('bearer '):
        return cabecera[7:].strip()
    return (request.META.get('HTTP_X_API_KEY') or '').strip()


def _error(mensaje, codigo='invalido', estado=400, **extra):
    cuerpo = {'ok': False, 'error': mensaje, 'codigo': codigo}
    cuerpo.update(extra)
    return JsonResponse(cuerpo, status=estado, json_dumps_params={'ensure_ascii': False})


def _ok(datos=None, estado=200, **extra):
    cuerpo = {'ok': True}
    if datos is not None:
        cuerpo['datos'] = datos
    cuerpo.update(extra)
    return JsonResponse(cuerpo, status=estado, json_dumps_params={'ensure_ascii': False})


def api(accion, metodos):
    """Autentica por token, chequea el permiso del token y arma el actor.

    `accion` es uno de leer/crear/editar/borrar/pagar; el token puede tener
    cada uno habilitado por separado (ver TokenAgente).
    """
    def decorador(vista):
        @csrf_exempt
        @wraps(vista)
        def envoltorio(request, *args, **kwargs):
            if request.method not in metodos:
                return _error(
                    f'Método {request.method} no permitido en este endpoint.',
                    'metodo_no_permitido', 405, metodos_permitidos=metodos)

            en_claro = _token_de(request)
            if not en_claro:
                return _error(
                    'Falta el token. Mandá la cabecera '
                    '"Authorization: Bearer <token>".', 'sin_token', 401)

            token = TokenAgente.objects.filter(
                token_hash=TokenAgente.hashear(en_claro)).first()
            if token is None:
                return _error('Token inválido.', 'token_invalido', 401)
            if not token.activo:
                return _error('El token está desactivado.', 'token_inactivo', 403)
            if not token.permite(accion):
                return _error(
                    f'Este token no tiene permiso para "{accion}".',
                    'sin_permiso', 403)

            TokenAgente.objects.filter(pk=token.pk).update(
                ultimo_uso=timezone.now())
            request.token_agente = token
            request.actor = services.actor_de_token(token, request)
            try:
                return vista(request, *args, **kwargs)
            except services.ErrorTercerizado as e:
                return _error(str(e), 'invalido', 400)
        return envoltorio
    return decorador


# ---------------------------------------------------------------- Parseo


def _cuerpo(request):
    if not request.body:
        return {}
    try:
        datos = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise services.ErrorTercerizado('El cuerpo tiene que ser JSON válido.')
    if not isinstance(datos, dict):
        raise services.ErrorTercerizado('El cuerpo tiene que ser un objeto JSON.')
    return datos


def _monto(valor, campo='monto'):
    """Número JSON o string (decimal plano o formato argentino)."""
    if isinstance(valor, bool) or valor is None:
        raise services.ErrorTercerizado(f'"{campo}" tiene que ser un número.')
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    texto = str(valor).strip()
    if not texto:
        raise services.ErrorTercerizado(f'"{campo}" no puede estar vacío.')
    if DECIMAL_PLANO.match(texto):
        return Decimal(texto)
    convertido = parse_ar(texto)
    if convertido == CERO and not re.search(r'[1-9]', texto):
        raise services.ErrorTercerizado(
            f'No pude interpretar "{campo}" = {valor!r}. Mandá un número '
            f'(45000.5) o formato argentino ("45.000,50").')
    return convertido


def _fecha(valor, campo='fecha'):
    if valor in (None, ''):
        return None
    if isinstance(valor, str):
        try:
            return datetime.strptime(valor.strip(), '%Y-%m-%d').date()
        except ValueError:
            pass
    raise services.ErrorTercerizado(
        f'"{campo}" tiene que venir como YYYY-MM-DD (llegó {valor!r}).')


def _opcion(valor, choices, campo):
    if valor in (None, ''):
        return None
    valores = [v for v, _ in choices]
    if valor not in valores:
        raise services.ErrorTercerizado(
            f'"{campo}" tiene que ser uno de: {", ".join(valores)} '
            f'(llegó {valor!r}).')
    return valor


def _resolver_proveedor(datos, obligatorio=True):
    """Acepta `proveedor` (id o nombre) o `proveedor_nombre`.

    No crea proveedores: si el nombre no existe devuelve error con la lista,
    para que el agente elija uno (el alta de proveedores es de la ABM, no de
    esta API)."""
    bruto = datos.get('proveedor', datos.get('proveedor_nombre'))
    if bruto in (None, ''):
        if obligatorio:
            raise services.ErrorTercerizado(
                'Falta "proveedor" (id o nombre). Consultá '
                'GET /api/tercerizados/proveedores.')
        return None
    if isinstance(bruto, int) or (isinstance(bruto, str) and bruto.isdigit()):
        proveedor = Proveedor.objects.filter(pk=int(bruto)).first()
        if proveedor is None:
            raise services.ErrorTercerizado(
                f'No existe el proveedor con id {bruto}.')
        return proveedor
    proveedor = Proveedor.objects.filter(nombre__iexact=str(bruto).strip()).first()
    if proveedor is None:
        disponibles = list(
            Proveedor.objects.values_list('nombre', flat=True)[:50])
        raise services.ErrorTercerizado(
            f'No existe el proveedor "{bruto}". Proveedores cargados: '
            f'{", ".join(disponibles) or "(ninguno)"}.')
    return proveedor


def _resolver_pedido_interno(datos):
    """`pedido_interno`: número de pedido del cotizador, opcional."""
    bruto = datos.get('pedido_interno')
    if bruto in (None, ''):
        return None
    from pedidos.models import Pedido
    interno = Pedido.objects.filter(numero=bruto).first()
    if interno is None:
        raise services.ErrorTercerizado(
            f'No existe el pedido interno #{bruto}. Omitilo si no aplica.')
    return interno


# ---------------------------------------------------------------- Serializar


def _dinero(valor):
    """Siempre con 2 decimales: los agregados de SQLite pueden venir sin
    escala ('70000' en lugar de '70000.00') y el cliente no debería notarlo."""
    return str(Decimal(valor or 0).quantize(Decimal('0.01')))


def _json_pedido(p):
    return {
        'id': p.pk,
        'fecha': p.fecha.isoformat(),
        'proveedor_id': p.proveedor_id,
        'proveedor': p.proveedor.nombre if p.proveedor_id else None,
        'descripcion': p.descripcion,
        'pedido_interno': p.pedido_id,
        'monto': _dinero(p.monto),
        'monto_pagado': _dinero(p.monto_pagado),
        'saldo': _dinero(p.saldo),
        'forma_pago': p.forma_pago,
        'estado': p.estado,
        'estado_pago': p.estado_pago,
        'nota': p.nota,
        'origen': p.origen,
        'referencia_externa': p.referencia_externa,
        'revisado': p.revisado,
        'created': p.created.isoformat() if p.created else None,
    }


def _json_pago(pago):
    return {
        'id': pago.pk,
        'fecha': pago.fecha.isoformat(),
        'proveedor_id': pago.proveedor_id,
        'proveedor': pago.proveedor.nombre if pago.proveedor_id else None,
        'monto': _dinero(pago.monto),
        'medio': pago.medio,
        'comprobante': pago.comprobante,
        'nota': pago.nota,
        'imputado': _dinero(pago.imputado),
        'sin_imputar': _dinero(pago.sin_imputar),
        'imputaciones': [
            {'pedido': i.pedido_id, 'monto': _dinero(i.monto)}
            for i in pago.imputaciones.all()
        ],
    }


# ---------------------------------------------------------------- Endpoints


@api('leer', ['GET'])
def ping(request):
    """Chequeo de credenciales: dice qué puede hacer este token."""
    token = request.token_agente
    return _ok({
        'token': token.nombre,
        'permisos': {
            'leer': token.permite_leer, 'crear': token.permite_crear,
            'editar': token.permite_editar, 'borrar': token.permite_borrar,
            'pagar': token.permite_pagar,
        },
        'alcance': 'Solo pedidos tercerizados (y lectura de proveedores).',
        'servidor': timezone.now().isoformat(),
    })


@api('leer', ['GET'])
def esquema(request):
    """Contrato de la API, para que el agente no tenga que adivinarlo."""
    return _ok({
        'autenticacion': 'Authorization: Bearer <token> (o X-API-Key)',
        'formatos': {
            'fecha': 'YYYY-MM-DD',
            'monto': 'número JSON (45000.5) o string AR ("45.000,50")',
        },
        'idempotencia': (
            'Mandá "referencia_externa" con el Message-ID del correo en el '
            'alta. Si ya existe, la respuesta trae duplicado: true y el '
            'registro existente, sin crear uno nuevo.'),
        'endpoints': [
            {'metodo': 'GET', 'ruta': '/api/tercerizados/ping',
             'descripcion': 'Verifica el token y lista sus permisos.'},
            {'metodo': 'GET', 'ruta': '/api/tercerizados/proveedores',
             'descripcion': 'Proveedores cargados (id y nombre).'},
            {'metodo': 'GET', 'ruta': '/api/tercerizados/pedidos',
             'descripcion': 'Lista pedidos tercerizados.',
             'parametros': ['proveedor', 'desde', 'hasta', 'estado',
                            'estado_pago', 'buscar', 'limit', 'referencia_externa']},
            {'metodo': 'POST', 'ruta': '/api/tercerizados/pedidos',
             'descripcion': 'Registra un pedido tercerizado.',
             'cuerpo': {
                 'proveedor': 'id o nombre exacto (obligatorio)',
                 'descripcion': 'qué se encargó (obligatorio)',
                 'monto': 'obligatorio',
                 'fecha': 'opcional, por defecto hoy',
                 'forma_pago': [v for v, _ in PedidoTercerizado.FormaPago.choices],
                 'estado': [v for v, _ in PedidoTercerizado.Estado.choices],
                 'pedido_interno': 'opcional, número de pedido del cotizador',
                 'nota': 'opcional',
                 'referencia_externa': 'opcional pero recomendado (Message-ID)',
             }},
            {'metodo': 'GET', 'ruta': '/api/tercerizados/pedidos/<id>',
             'descripcion': 'Un pedido.'},
            {'metodo': 'PATCH', 'ruta': '/api/tercerizados/pedidos/<id>',
             'descripcion': 'Edita los campos que se manden.',
             'cuerpo': {'campos': list(services.CAMPOS_EDITABLES)}},
            {'metodo': 'DELETE', 'ruta': '/api/tercerizados/pedidos/<id>',
             'descripcion': (
                 'Borra el pedido. Si tiene pagos imputados no se borra: '
                 'marcalo con estado "cancelado" vía PATCH.')},
            {'metodo': 'GET', 'ruta': '/api/tercerizados/deuda',
             'descripcion': 'Deuda viva por proveedor.'},
            {'metodo': 'GET', 'ruta': '/api/tercerizados/pagos',
             'descripcion': 'Lista pagos a proveedores.'},
            {'metodo': 'POST', 'ruta': '/api/tercerizados/pagos',
             'descripcion': 'Registra un pago (requiere permiso "pagar").',
             'cuerpo': {
                 'proveedor': 'id o nombre (obligatorio)',
                 'monto': 'obligatorio',
                 'medio': [v for v, _ in PagoTercerizado.Medio.choices],
                 'imputaciones': '[{"pedido": 12, "monto": 45000}, ...]',
                 'automatico': 'true reparte del pedido más viejo al más nuevo',
                 'fecha': 'opcional', 'comprobante': 'opcional', 'nota': 'opcional',
             }},
            {'metodo': 'DELETE', 'ruta': '/api/tercerizados/pagos/<id>',
             'descripcion': 'Anula un pago y devuelve el saldo a los pedidos.'},
        ],
        'notas': [
            'Esta API no crea proveedores ni toca ninguna otra parte del '
            'cotizador.',
            'Todo lo que escribe el token queda en el log de auditoría, que '
            'no se puede editar ni borrar desde la API.',
            'Los pedidos que carga el agente quedan con revisado: false '
            'hasta que gerencia los valide.',
        ],
    })


@api('leer', ['GET'])
def proveedores(request):
    return _ok([
        {'id': p.pk, 'nombre': p.nombre, 'email': p.email,
         'telefono': p.telefono}
        for p in Proveedor.objects.all()
    ])


@api('leer', ['GET'])
def listar_pedidos(request):
    qs = PedidoTercerizado.objects.select_related('proveedor')

    referencia = request.GET.get('referencia_externa', '').strip()
    if referencia:
        qs = qs.filter(referencia_externa=referencia)

    proveedor = request.GET.get('proveedor', '').strip()
    if proveedor:
        if proveedor.isdigit():
            qs = qs.filter(proveedor_id=int(proveedor))
        else:
            qs = qs.filter(proveedor__nombre__iexact=proveedor)

    desde = _fecha(request.GET.get('desde') or None, 'desde')
    hasta = _fecha(request.GET.get('hasta') or None, 'hasta')
    if desde:
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)

    estado = _opcion(request.GET.get('estado') or None,
                     PedidoTercerizado.Estado.choices, 'estado')
    if estado:
        qs = qs.filter(estado=estado)

    buscar = request.GET.get('buscar', '').strip()
    if buscar:
        qs = qs.filter(descripcion__icontains=buscar)

    try:
        limite = min(int(request.GET.get('limit', 100)), 500)
    except ValueError:
        limite = 100

    pedidos = list(qs[:limite])
    estado_pago = request.GET.get('estado_pago', '').strip()
    if estado_pago == 'con_deuda':
        pedidos = [p for p in pedidos if p.saldo > CERO]
    elif estado_pago:
        pedidos = [p for p in pedidos if p.estado_pago == estado_pago]

    return _ok([_json_pedido(p) for p in pedidos], cantidad=len(pedidos))


@api('leer', ['GET'])
def ver_pedido(request, pedido_id):
    pedido = (PedidoTercerizado.objects
              .select_related('proveedor').filter(pk=pedido_id).first())
    if pedido is None:
        return _error(f'No existe el pedido tercerizado #{pedido_id}.',
                      'no_encontrado', 404)
    return _ok(_json_pedido(pedido))


@api('crear', ['POST'])
def crear_pedido(request):
    datos = _cuerpo(request)
    pedido, creado = services.crear_pedido(
        proveedor=_resolver_proveedor(datos),
        descripcion=datos.get('descripcion', ''),
        monto=_monto(datos.get('monto'), 'monto'),
        fecha=_fecha(datos.get('fecha')),
        pedido=_resolver_pedido_interno(datos),
        forma_pago=_opcion(datos.get('forma_pago'),
                           PedidoTercerizado.FormaPago.choices, 'forma_pago'),
        estado=_opcion(datos.get('estado'),
                       PedidoTercerizado.Estado.choices, 'estado'),
        nota=datos.get('nota', '') or '',
        referencia_externa=datos.get('referencia_externa', '') or '',
        origen=PedidoTercerizado.Origen.AGENTE,
        actor=request.actor,
    )
    if not creado:
        return _ok(_json_pedido(pedido), duplicado=True,
                   mensaje='Ya existía un pedido con esa referencia_externa.')
    return _ok(_json_pedido(pedido), estado=201, duplicado=False)


@api('editar', ['PATCH', 'PUT', 'POST'])
def editar_pedido(request, pedido_id):
    pedido = PedidoTercerizado.objects.filter(pk=pedido_id).first()
    if pedido is None:
        return _error(f'No existe el pedido tercerizado #{pedido_id}.',
                      'no_encontrado', 404)
    datos = _cuerpo(request)

    cambios = {}
    if 'fecha' in datos:
        cambios['fecha'] = _fecha(datos['fecha'])
    if 'proveedor' in datos or 'proveedor_nombre' in datos:
        cambios['proveedor'] = _resolver_proveedor(datos)
    if 'descripcion' in datos:
        cambios['descripcion'] = datos['descripcion']
    if 'pedido_interno' in datos:
        cambios['pedido'] = _resolver_pedido_interno(datos)
    if 'monto' in datos:
        cambios['monto'] = _monto(datos['monto'], 'monto')
    if 'forma_pago' in datos:
        cambios['forma_pago'] = _opcion(
            datos['forma_pago'], PedidoTercerizado.FormaPago.choices, 'forma_pago')
    if 'estado' in datos:
        cambios['estado'] = _opcion(
            datos['estado'], PedidoTercerizado.Estado.choices, 'estado')
    if 'nota' in datos:
        cambios['nota'] = datos['nota'] or ''

    desconocidos = set(datos) - {
        'fecha', 'proveedor', 'proveedor_nombre', 'descripcion',
        'pedido_interno', 'monto', 'forma_pago', 'estado', 'nota',
        'referencia_externa'}
    if desconocidos:
        return _error(
            'Campos no editables por API: ' + ', '.join(sorted(desconocidos)),
            'campo_no_editable', 400,
            campos_editables=sorted({
                'fecha', 'proveedor', 'descripcion', 'pedido_interno',
                'monto', 'forma_pago', 'estado', 'nota'}))
    if not cambios:
        return _error('No mandaste ningún campo para cambiar.', 'sin_cambios')

    services.editar_pedido(pedido, actor=request.actor, **cambios)
    pedido.refresh_from_db()
    return _ok(_json_pedido(pedido))


@api('borrar', ['DELETE'])
def borrar_pedido(request, pedido_id):
    pedido = PedidoTercerizado.objects.filter(pk=pedido_id).first()
    if pedido is None:
        return _error(f'No existe el pedido tercerizado #{pedido_id}.',
                      'no_encontrado', 404)
    services.borrar_pedido(pedido, actor=request.actor)
    return _ok({'id': pedido_id, 'borrado': True})


@api('leer', ['GET'])
def deuda(request):
    proveedor = None
    if request.GET.get('proveedor'):
        proveedor = _resolver_proveedor(
            {'proveedor': request.GET['proveedor']})
    filas = services.resumen_deuda(proveedor)
    return _ok([{
        'proveedor_id': f['proveedor_id'],
        'proveedor': f['proveedor'],
        'encargado': _dinero(f['encargado']),
        'pagado': _dinero(f['pagado']),
        'deuda': _dinero(f['deuda']),
        'a_cuenta': _dinero(f['a_cuenta']),
        'deuda_neta': _dinero(f['deuda_neta']),
        'pedidos_con_saldo': f['pendientes'],
        'mas_antiguo': f['desde'].isoformat() if f['desde'] else None,
    } for f in filas])


@api('leer', ['GET'])
def listar_pagos(request):
    qs = (PagoTercerizado.objects
          .select_related('proveedor').prefetch_related('imputaciones'))
    if request.GET.get('proveedor'):
        proveedor = _resolver_proveedor({'proveedor': request.GET['proveedor']})
        qs = qs.filter(proveedor=proveedor)
    desde = _fecha(request.GET.get('desde') or None, 'desde')
    hasta = _fecha(request.GET.get('hasta') or None, 'hasta')
    if desde:
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)
    try:
        limite = min(int(request.GET.get('limit', 100)), 500)
    except ValueError:
        limite = 100
    pagos = list(qs[:limite])
    return _ok([_json_pago(p) for p in pagos], cantidad=len(pagos))


@api('pagar', ['POST'])
def crear_pago(request):
    datos = _cuerpo(request)
    imputaciones = []
    for item in datos.get('imputaciones') or []:
        if not isinstance(item, dict):
            raise services.ErrorTercerizado(
                'Cada imputación tiene que ser {"pedido": id, "monto": n}.')
        imputaciones.append(
            (item.get('pedido'), _monto(item.get('monto'), 'imputación')))

    pago = services.registrar_pago(
        proveedor=_resolver_proveedor(datos),
        monto=_monto(datos.get('monto'), 'monto'),
        medio=_opcion(datos.get('medio'), PagoTercerizado.Medio.choices, 'medio'),
        fecha=_fecha(datos.get('fecha')),
        imputaciones=imputaciones,
        automatico=bool(datos.get('automatico')),
        nota=datos.get('nota', '') or '',
        comprobante=datos.get('comprobante', '') or '',
        actor=request.actor,
    )
    return _ok(_json_pago(pago), estado=201)


@api('pagar', ['DELETE'])
def borrar_pago(request, pago_id):
    pago = PagoTercerizado.objects.filter(pk=pago_id).first()
    if pago is None:
        return _error(f'No existe el pago #{pago_id}.', 'no_encontrado', 404)
    services.anular_pago(pago, actor=request.actor)
    return _ok({'id': pago_id, 'anulado': True})


# ------------------------------------------------- Ruteo por método HTTP
# Una sola ruta por recurso (REST), porque cada método necesita un permiso
# distinto del token y eso se resuelve en la vista concreta.


@csrf_exempt
def pedidos_coleccion(request):
    if request.method == 'POST':
        return crear_pedido(request)
    return listar_pedidos(request)


@csrf_exempt
def pedidos_detalle(request, pedido_id):
    if request.method in ('PATCH', 'PUT', 'POST'):
        return editar_pedido(request, pedido_id)
    if request.method == 'DELETE':
        return borrar_pedido(request, pedido_id)
    return ver_pedido(request, pedido_id)


@csrf_exempt
def pagos_coleccion(request):
    if request.method == 'POST':
        return crear_pago(request)
    return listar_pagos(request)


@csrf_exempt
def pagos_detalle(request, pago_id):
    return borrar_pago(request, pago_id)
