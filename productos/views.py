from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http.response import JsonResponse, FileResponse
from .models import Producto, Categoria, Insumo, ComponenteProducto, FaltanteInsumo
from .functions import *
from django.contrib import messages
import openpyxl
from openpyxl import Workbook
from django.http import HttpResponse, Http404
from django.utils import timezone
from core.utils import format_ar, parse_ar
from core.decorators import solo_gerencia
import re

# Regex compartido: detecta "Nombre [N-M]" o "Nombre [N-INF]"
_RANGO_RE = re.compile(r'^(.*?)\s*\[(\d+)[-]([\d]+|INF)\]\s*$')

app_name = 'productos'

# -------------------------PRODUCTOS----------------------------------
# Muestra la tabla de productos.


@login_required
def productos(request):
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')
    prods = Producto.objects.all()
    if request.user.is_superuser or request.user.groups.filter(name='Gerencia').exists():
        autorizado = True
    data = {
        'usuario': usuario_nombre,
        'img': img,
        'prods': prods,
        'autorizado': autorizado,
    }
    return render(request, 'productos/productos.html', data)


@login_required
def obtener_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    data = {
        "id": producto.id,
        "nombre": producto.nombre,
        "categoria_id": producto.categoria.id,
        "ancho": producto.ancho,
        "alto": producto.alto,
        "tercerizado": producto.tercerizado,
        "precio_proveedor": producto.precio_proveedor,
        "margen": producto.factor,
        "insumos": []
    }

    if not producto.tercerizado:
        componentes = ComponenteProducto.objects.filter(producto=producto)
        for comp in componentes:
            data["insumos"].append({
                "id": comp.insumo.id,
                "cantidad": comp.cantidad
            })

    return JsonResponse(data)


@login_required
def obtener_dimensiones_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    data = {
        "ancho": producto.ancho,
        "alto": producto.alto
    }
    return JsonResponse(data)


@login_required
def obtener_productos_categoria(request, categoria_id):
    """
    Devuelve un producto representante por familia.
    Productos con el mismo nombre base (ignorando el rango [N-M] y la capitalización)
    se agrupan y solo se devuelve el primero encontrado.
    """
    productos = Producto.objects.filter(
        categoria_id=categoria_id, activo=True
    ).values("id", "nombre").order_by("nombre")

    familias = {}   # key: base_lower → {"id": ..., "nombre": ...}
    for prod in productos:
        nombre = prod["nombre"].strip()
        m = _RANGO_RE.match(nombre)
        if m:
            base = m.group(1).strip()
            key = base.lower()
            if key not in familias:
                familias[key] = {"id": prod["id"], "nombre": base}
        else:
            key = nombre.lower()
            if key not in familias:
                familias[key] = {"id": prod["id"], "nombre": nombre}

    return JsonResponse(list(familias.values()), safe=False)


# Vista que recibe la información de los modales de editar y agregar producto para luego actualizar la base de datos.


@login_required
@solo_gerencia
def guardar_producto(request):
    try:

        # 1. Recopilar datos
        id_producto = request.POST.get("id_producto")
        nombre = request.POST.get("productoNombre")
        categoria_id = request.POST.get("productoCategoria")
        ancho = float(request.POST.get("productoAncho") or 0)
        alto = float(request.POST.get("productoAlto") or 0)
        tercerizado = request.POST.get("tercerizado") == "on"
        precio = float(request.POST.get(
            "productoPrecio") or 0)
        margen = float(parse_ar(request.POST.get("productoMargen")) or 1)
        categoria = get_object_or_404(Categoria, id=categoria_id)

        # 2. Crear o editar producto
        if id_producto and id_producto != "0":
            producto = get_object_or_404(Producto, id=id_producto)
            accion = "actualizado"
        else:
            producto = Producto()
            accion = "creado"

        producto.nombre = nombre
        producto.categoria = categoria
        producto.ancho = ancho
        producto.alto = alto
        producto.tercerizado = tercerizado
        if tercerizado:
            producto.precio = 0
            producto.precio_proveedor = precio
        else:
            producto.precio = precio
            producto.precio_proveedor = 0
        producto.factor = margen
        producto.save()

        # 3. Procesar insumos si no es tercerizado
        if not tercerizado:
            # Limpiar composiciones anteriores si es edición
            ComponenteProducto.objects.filter(producto=producto).delete()

            # Extraer insumos desde request.POST
            # Ejemplo esperado:
            # insumo_0_id, insumo_0_cantidad
            # insumo_1_id, insumo_1_cantidad
            for key in request.POST:
                if key.startswith("insumo_") and key.endswith("_id"):
                    idx = key.split("_")[1]
                    insumo_id = request.POST.get(f"insumo_{idx}_id")
                    cantidad = float(request.POST.get(
                        f"insumo_{idx}_cantidad") or 0)

                    if insumo_id and cantidad > 0:
                        insumo = get_object_or_404(Insumo, id=insumo_id)
                        ComponenteProducto.objects.create(
                            producto=producto,
                            insumo=insumo,
                            cantidad=cantidad
                        )

            # Calcular precio desde los componentes guardados (no confiar en el frontend)
            precio_calculado = sum(
                float(comp.insumo.precio / comp.insumo.factor_conversion) * comp.cantidad
                for comp in ComponenteProducto.objects.filter(producto=producto)
            )
            producto.precio = round(precio_calculado, 2)
            producto.save()

        # 4. Respuesta OK
        mensaje = f"Producto {accion} correctamente."
        return JsonResponse({"ok": True, "mensaje": mensaje, "redirect_url": "/productos"})

    except Exception as e:
        print(f"Error al guardar producto: {e}")
        return JsonResponse({"ok": False, "mensaje": "No se pudo guardar el producto. Revisá los datos."})

# Vista que permite borrar un producto de la base de datos.


@login_required
@solo_gerencia
def borrar_producto(request, producto_id):
    try:
        prod = Producto.objects.filter(pk=producto_id)
        prod.delete()
        messages.success(request, 'El producto se ha borrado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se ha podido borrar el producto. Error({e})')
    return redirect('/productos', messages)
# Devuelve los insumos activos en formato JSON para ser utilizados en una petición AJAX desde el frontend.


@login_required
def insumos_select(request):
    insumos = Insumo.objects.filter(activo=True).values('id', 'nombre')
    return JsonResponse(list(insumos), safe=False)


@login_required
def categorias_select(request):
    categorias = Categoria.objects.all().values('id', 'nombre')
    return JsonResponse(list(categorias), safe=False)


@login_required
def datos_insumo(request, id):
    try:
        insumo = Insumo.objects.get(pk=id)
        precio = insumo.precio/insumo.factor_conversion
    except Insumo.DoesNotExist:
        raise Http404("Insumo no encontrado")

    return JsonResponse({'nombre': insumo.nombre, 'precio': precio, 'u_de_uso': insumo.unidad_composicion})


# Función que carga productos desde un archivo excel.

@login_required
def importar_productos_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        wb = openpyxl.load_workbook(excel_file)
        ws = wb.active

        encabezados = [str(cell.value).strip() for cell in ws[1]]
        errores = []
        creados = 0
        actualizados = 0

        for idx, fila in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                fila_data = dict(zip(encabezados, fila))

                nombre = str(fila_data.get("Nombre", "")).strip()
                ancho = float(fila_data.get("Ancho") or 0)
                alto = float(fila_data.get("Alto") or 0)
                precio_excel = float(fila_data.get("Precio") or 0)
                factor = float(fila_data.get("Factor") or 1.0)
                categoria_nombre = str(fila_data.get("Categoría", "")).strip()

                valor_raw = str(fila_data.get(
                    "Tercerizado", "")).strip().lower()
                if valor_raw in ["si", "sí", "s", "true", "1", "x"]:
                    tercerizado = True
                elif valor_raw in ["no", "n", "false", "0"]:
                    tercerizado = False
                else:
                    errores.append(
                        f"Fila {idx}: Valor inválido para 'Tercerizado' → '{valor_raw}'")
                    continue

                categoria = Categoria.objects.filter(
                    nombre__iexact=categoria_nombre).first()
                if not categoria and categoria_nombre:
                    categoria = Categoria.objects.create(
                        nombre=categoria_nombre)

                producto, creado = Producto.objects.update_or_create(
                    nombre=nombre,
                    defaults={
                        "ancho": ancho,
                        "alto": alto,
                        "tercerizado": tercerizado,
                        "factor": factor,
                        "categoria": categoria,
                        "activo": True,
                    }
                )

                if creado:
                    creados += 1
                else:
                    actualizados += 1
                if not tercerizado:
                    componentes = []
                    for key, value in fila_data.items():
                        if key.lower() in ["nombre", "alto", "ancho", "precio", "tercerizado", "categoría", "factor"]:
                            continue  # No intentar parsear estas columnas

                        if not value:
                            continue

                        if isinstance(value, str) and ";" in value:
                            try:
                                nombre_insumo, cantidad_str = value.split(";")
                                nombre_insumo = nombre_insumo.strip()
                                cantidad = float(cantidad_str.strip())
                            except Exception as e:
                                errores.append(
                                    f"Fila {idx}: Error al descomponer insumo en '{value}' → {e}")
                                continue
                        else:
                            errores.append(
                                f"Fila {idx}: Valor inesperado en columna '{key}' → '{value}', se esperaba formato 'nombre;cantidad'")
                            continue

                        insumo = Insumo.objects.filter(
                            nombre__iexact=nombre_insumo).first()
                        if not insumo:
                            errores.append(
                                f"Fila {idx}: Insumo no encontrado → '{nombre_insumo}'")
                            continue

                        ComponenteProducto.objects.update_or_create(
                            producto=producto,
                            insumo=insumo,
                            defaults={
                                "cantidad": cantidad,
                                "unidad": insumo.unidad_composicion,
                                "alternativo": False
                            }
                        )

                        componentes.append({
                            "precio": float(insumo.precio/insumo.factor_conversion),
                            "cantidad": cantidad
                        })

                    # Calcular precio desde los componentes guardados en DB
                    precio_total = sum(
                        float(comp.insumo.precio / comp.insumo.factor_conversion) * comp.cantidad
                        for comp in ComponenteProducto.objects.filter(producto=producto).select_related('insumo')
                    )
                    producto.precio = round(precio_total, 2)
                else:
                    producto.precio_proveedor = precio_excel
                producto.save()

            except Exception as e:
                errores.append(f"Fila {idx}: Error inesperado → {str(e)}")

        if errores:
            log_contenido = "\n".join(errores)
            mensaje = (
                f"Carga completada: {creados} nuevos, {actualizados} actualizados, "
                f"{len(errores)} errores. Revisá el archivo de log descargado."
            )
            return JsonResponse({
                "ok": True,
                "mensaje": mensaje,
                "tiene_errores": True,
                "log_contenido": log_contenido,
                "log_nombre": "errores_productos.txt",
            })
        else:
            return JsonResponse({
                "ok": True,
                "mensaje": f"Carga completada: {creados} nuevos, {actualizados} actualizados, sin errores.",
                "tiene_errores": False,
            })

    return JsonResponse({"ok": False, "mensaje": "No se recibió ningún archivo."})


# Vista que permite general un excel con los productos de la base de datos.
@login_required
def exportar_productos_excel(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Productos"

    # Encabezados fijos
    headers = ["Nombre", "Ancho", "Alto",
               "Tercerizado", "Precio", "Factor", "Categoría"]
    max_insumos = 0
    filas = []

    # Recorremos productos
    for producto in Producto.objects.filter(activo=True).order_by("nombre"):
        fila = [
            producto.nombre,
            producto.ancho,
            producto.alto,
            "Sí" if producto.tercerizado else "No",
            producto.precio_proveedor if producto.tercerizado else producto.precio,
            producto.factor,
            producto.categoria.nombre if producto.categoria else "",
        ]

        # Para productos no tercerizados, agregamos insumos
        insumos = []
        if not producto.tercerizado:
            componentes = ComponenteProducto.objects.filter(
                producto=producto).order_by("id")
            for comp in componentes:
                valor = f"{comp.insumo.nombre};{comp.cantidad}"
                insumos.append(valor)
        max_insumos = max(max_insumos, len(insumos))
        fila.extend(insumos)
        filas.append(fila)

    # Extendemos headers con columnas de insumos: Insumo_0;cantidad, etc.
    for i in range(max_insumos):
        headers.append(f"Insumo_{i};cantidad")

    # Escribimos encabezados
    ws.append(headers)

    # Escribimos datos
    for fila in filas:
        # Completamos con celdas vacías si faltan insumos
        while len(fila) < len(headers):
            fila.append("")
        ws.append(fila)

    # Preparamos respuesta HTTP con Excel adjunto
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = "attachment; filename=productos_exportados.xlsx"
    wb.save(response)
    return response


# Vista que permite borrar todos los productos.

@login_required
@solo_gerencia
def recalcular_precios_productos(request):
    """Recalcula el precio de todos los productos no-tercerizados a partir de sus insumos."""
    actualizados = 0
    errores = []
    productos_nt = Producto.objects.filter(tercerizado=False)
    for producto in productos_nt:
        try:
            componentes = ComponenteProducto.objects.filter(producto=producto).select_related('insumo')
            if componentes.exists():
                precio_calculado = sum(
                    float(comp.insumo.precio / comp.insumo.factor_conversion) * comp.cantidad
                    for comp in componentes
                )
                producto.precio = round(precio_calculado, 2)
                producto.save()
                actualizados += 1
        except Exception as e:
            errores.append(f"{producto.nombre}: {e}")
    return JsonResponse({
        "ok": True,
        "actualizados": actualizados,
        "errores": errores,
        "mensaje": f"Se recalcularon los precios de {actualizados} productos." + (f" {len(errores)} errores." if errores else ""),
    })


@login_required
@solo_gerencia
def borrar_todos_productos(request):
    try:
        Producto.objects.all().delete()
        messages.success(
            request, 'Todos los productos se han borrado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se han podido borrar todos los productos. Error({e})')
    return redirect('/productos', messages)

# -------------------------CATEGORIAS----------------------------------


@login_required
@solo_gerencia
def categorias(request):
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')
    categorias = Categoria.objects.all()

    data = {
        'usuario': usuario_nombre,
        'autorizado': autorizado,
        'img': img,
        'categorias': categorias,
    }

    return render(request, 'productos/categorias.html', data)


@login_required
def obtener_categoria(request, categoria_id):
    try:
        categoria = Categoria.objects.get(id=categoria_id)
        return JsonResponse({'id': categoria.id, 'nombre': categoria.nombre})
    except Categoria.DoesNotExist:
        return JsonResponse({'error': 'Categoría no encontrada'}, status=404)


@login_required
@solo_gerencia
def guardar_categoria(request):
    if request.method == 'POST':
        categoria_id = request.POST.get('id')
        nombre = request.POST.get('nombre')

        if categoria_id:  # Si hay un ID, estamos en modo edición
            try:
                categoria = Categoria.objects.get(id=categoria_id)
                categoria.nombre = nombre
                categoria.save()
                messages.success(
                    request, f'Categoría "{nombre}" actualizada con éxito.')
            except Categoria.DoesNotExist:
                messages.error(request, 'La categoría no existe.')
        else:  # No hay ID, creamos una nueva categoría
            try:
                Categoria.objects.create(nombre=nombre)
                messages.success(
                    request, f'Nueva categoría "{nombre}" creada con éxito.')
            except Exception as e:
                messages.error(
                    request, f'Error al crear la categoría: {str(e)}')

        return redirect('categorias')  # Redirigir a la vista de categorías

    return redirect('categorias')  # Si no es POST, redirigir


@login_required
@solo_gerencia
def borrar_categoria(request, categoria_id):
    try:
        cat = Categoria.objects.get(id=categoria_id)
        cat.delete()
        messages.success(request, 'La categoria se ha borrado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se ha podido borrar la categoria. Error({e})')
    return redirect('/productos/categorias', messages)


@login_required
def listar_categorias(request):
    categorias = list(Categoria.objects.values_list('nombre', flat=True))
    return JsonResponse({'categorias': categorias})

# -------------------------INSUMOS----------------------------------


@login_required
def insumos(request):
    autorizado = request.session.get('autorizado')
    usuario_nombre = request.session.get('usuario_nombre')
    img = request.session.get('img')
    insumos = Insumo.objects.all()
    if request.user.is_superuser or request.user.groups.filter(name='Gerencia').exists():
        autorizado = True
        # es_gerencia = request.user.is_superuser or request.user.groups.filter(
        #    name='Gerencia').exists()
    data = {
        'usuario': usuario_nombre,
        'img': img,
        'insumos': insumos,
        'autorizado': autorizado,
        # 'es_gerencia': es_gerencia
    }
    return render(request, 'productos/insumos.html', data)


@login_required
def resolver_tier_producto(request):
    """Dado un producto_id y una cantidad de hojas, encuentra el tier correcto de su familia."""
    import re
    producto_id = request.POST.get('producto_id')
    try:
        cantidad = int(float(request.POST.get('cantidad', 0)))
    except (ValueError, TypeError):
        cantidad = 0

    producto = get_object_or_404(Producto, id=producto_id)

    match = _RANGO_RE.match(producto.nombre)

    if not match:
        return JsonResponse({'producto_id': producto.id, 'nombre': producto.nombre, 'tier_encontrado': False})

    base_nombre = match.group(1).strip()

    candidatos = Producto.objects.filter(
        nombre__startswith=base_nombre,
        categoria=producto.categoria,
        activo=True
    )

    for prod in candidatos:
        m = _RANGO_RE.match(prod.nombre)
        if m:
            rango_min = int(m.group(2))
            rango_max_str = m.group(3)
            rango_max = float('inf') if rango_max_str == 'INF' else int(rango_max_str)
            if rango_min <= cantidad <= rango_max:
                return JsonResponse({
                    'producto_id': prod.id,
                    'nombre': prod.nombre,
                    'tier_encontrado': True,
                    'rango_display': f"{rango_min}-{rango_max_str}",
                })

    return JsonResponse({'producto_id': producto.id, 'nombre': producto.nombre, 'tier_encontrado': False})


def _recalcular_precios_productos_con_insumo(insumo):
    """Recalcula el precio de todos los productos no-tercerizados que usan este insumo."""
    componentes = ComponenteProducto.objects.filter(insumo=insumo).select_related('producto')
    productos_afectados = set(comp.producto for comp in componentes if not comp.producto.tercerizado)
    for producto in productos_afectados:
        precio_calculado = sum(
            float(comp.insumo.precio / comp.insumo.factor_conversion) * comp.cantidad
            for comp in ComponenteProducto.objects.filter(producto=producto).select_related('insumo')
        )
        producto.precio = round(precio_calculado, 2)
        producto.save()


@login_required
def guardar_insumo(request):
    if request.method == "POST":
        data = request.POST
        id_insumo = data.get("id_insumo")

        if id_insumo and id_insumo != "0":
            insumo = get_object_or_404(Insumo, id=id_insumo)
            mensaje = "Insumo actualizado exitosamente."
        else:
            insumo = Insumo()
            mensaje = "Nuevo insumo creado exitosamente."

        nombre = (data.get("nombre") or "").strip()
        if not nombre:
            return JsonResponse({"ok": False, "mensaje": "El insumo debe tener un nombre."})

        # Protección contra duplicados: no permitir otro insumo con el mismo nombre
        # ignorando mayúsculas/espacios (excluyéndose a sí mismo en edición).
        duplicado = Insumo.objects.filter(nombre__iexact=nombre)
        if insumo.pk:
            duplicado = duplicado.exclude(pk=insumo.pk)
        if duplicado.exists():
            return JsonResponse({
                "ok": False,
                "mensaje": f"Ya existe un insumo llamado '{duplicado.first().nombre}'. "
                           f"Usá ese o elegí un nombre distinto.",
            })

        insumo.nombre = nombre
        insumo.unidad_medida = data.get("unidad_medida")
        insumo.unidad_composicion = data.get("unidad_composicion")
        insumo.factor_conversion = data.get("factor_conversion") or 1
        insumo.precio = parse_ar(data.get("precio_unitario")) or 0
        insumo.activo = data.get("activo") == "on"

        # El usuario ingresa el "stock real": las unidades de uso que efectivamente
        # cuenta (ej: hojas). El stock interno (en unidad de compra) se deriva
        # dividiendo por el factor de conversión.
        stock_real_ingresado = float(data.get("stock_real") or 0)
        factor = float(insumo.factor_conversion or 1) or 1

        if id_insumo and id_insumo != "0":
            mensaje_reposicion = procesar_reposicion_insumo_por_edicion(request,
                                                                        insumo, stock_real_ingresado)
            insumo.save()
            _recalcular_precios_productos_con_insumo(insumo)
            return JsonResponse({"ok": True, "mensaje": mensaje, "info_reposicion": mensaje_reposicion})

        insumo.stock = stock_real_ingresado / factor
        insumo.save()
        return JsonResponse({"ok": True, "mensaje": mensaje})


@login_required
def info_insumo(request, insumo_id):
    print("insumo_id", insumo_id)
    try:
        insumo = get_object_or_404(Insumo, id=insumo_id)
        print("insumo", insumo)
        data = {
            "id": insumo.id,
            "nombre": insumo.nombre,
            "unidad_medida": insumo.unidad_medida,
            "unidad_composicion": insumo.unidad_composicion,
            "factor_conversion": float(insumo.factor_conversion),
            "stock": float(insumo.stock or 0),
            # El stock real (unidades de uso, ej: hojas) se cuenta por unidades
            # enteras. Redondeamos para no arrastrar decimales espurios que
            # provienen de convertir el stock interno (unidad de compra).
            "stock_real": round(insumo.stock_real() or 0),
            "precio_unitario": float(insumo.precio or 0),
            "ultima_modificacion": insumo.ultima_modificacion.isoformat() if insumo.ultima_modificacion else None,
            "modificado_por": insumo.modificado_por.get_full_name() if insumo.modificado_por else None,
            "activo": insumo.activo,
        }

        return JsonResponse(data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@solo_gerencia
def borrar_insumo(request, insumo_id):
    try:
        prod = Insumo.objects.filter(pk=insumo_id)
        nombre = prod[0].nombre
        prod.delete()
        messages.success(
            request, f'El insumo {nombre} se ha borrado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se ha podido borrar el insumo. Error({e})')
    return redirect('insumos')


@login_required
def importar_insumos_excel(request):
    try:
        if request.method == 'POST' and request.FILES.get('excel_file'):
            excel_file = request.FILES['excel_file']
            wb = openpyxl.load_workbook(excel_file)
            sheet = wb.active

            headers = [str(cell.value).strip().lower()
                       if cell.value else "" for cell in sheet[1]]
            total_filas = 0
            creados = 0
            actualizados = 0
            advertencias = 0
            errores = 0
            log = []

            for idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                total_filas += 1

                if all(cell is None or str(cell).strip() == "" for cell in row):
                    continue

                try:
                    data = dict(zip(headers, row))

                    def val(key):
                        """Valor de la celda ya recortado, o None si está vacía/ausente."""
                        v = data.get(key)
                        if v is None:
                            return None
                        s = str(v).strip()
                        return s if s != "" else None

                    nombre = val('nombre')

                    if not nombre:
                        errores += 1
                        log.append(f"Fila {idx}: Insumo sin nombre.")
                        continue

                    # CLAVE: reusar el insumo existente (match case-insensitive) para
                    # NO romper el vínculo con los productos. get_or_create por nombre
                    # exacto creaba duplicados ante diferencias de mayúsculas/acentos,
                    # dejando al producto apuntando al insumo viejo. Si hay duplicados
                    # previos, se toma el más antiguo (el más probablemente vinculado).
                    insumo = Insumo.objects.filter(
                        nombre__iexact=nombre).order_by('id').first()
                    creado = insumo is None
                    if creado:
                        insumo = Insumo(nombre=nombre)
                    elif insumo.nombre != nombre:
                        # Falso positivo posible: el match fue por coincidencia
                        # ignorando mayúsculas/espacios, no por nombre idéntico.
                        # Se avisa para que el usuario verifique que es el mismo
                        # insumo y no uno nuevo que quedó absorbido por error.
                        advertencias += 1
                        log.append(
                            f"Fila {idx}: ADVERTENCIA — '{nombre}' se aplicó sobre el "
                            f"insumo existente '{insumo.nombre}' (id {insumo.id}) por "
                            f"coincidencia ignorando mayúsculas/espacios. Si NO es el "
                            f"mismo insumo, corregí el nombre en la planilla y reimportá.")

                    # Valores previos para detectar si cambia el costo del insumo
                    # (precio o factor), lo que obliga a recalcular productos.
                    precio_anterior = float(insumo.precio or 0)
                    factor_anterior = float(insumo.factor_conversion or 1)

                    # Solo se sobrescriben los campos presentes en la planilla, para que
                    # una actualización masiva de stock no borre unidad/factor/precio.
                    if val('unidad_medida') is not None:
                        insumo.unidad_medida = val('unidad_medida')
                    if val('unidad_composicion') is not None:
                        insumo.unidad_composicion = val('unidad_composicion')
                    if val('factor_conversion') is not None:
                        insumo.factor_conversion = int(
                            float(val('factor_conversion'))) or 1
                    if val('precio') is not None:
                        insumo.precio = float(val('precio'))

                    # Stock: se prioriza 'stock_real' (unidades de uso que se cuentan,
                    # ej: hojas) y la app deriva el stock en unidad de compra. Se
                    # mantiene compatibilidad con planillas viejas que traían 'stock'
                    # (ya expresado en unidad de compra).
                    factor = float(insumo.factor_conversion or 1) or 1
                    if val('stock_real') is not None:
                        insumo.stock = float(val('stock_real')) / factor
                    elif val('stock') is not None:
                        insumo.stock = float(val('stock'))

                    insumo.save()

                    # Si cambió el costo unitario (precio o factor), recalcular el
                    # precio de los productos no tercerizados que usan este insumo.
                    if not creado and (
                        float(insumo.precio or 0) != precio_anterior
                        or float(insumo.factor_conversion or 1) != factor_anterior
                    ):
                        _recalcular_precios_productos_con_insumo(insumo)

                    if creado:
                        creados += 1
                    else:
                        actualizados += 1

                except Exception as e:
                    errores += 1
                    log.append(f"Fila {idx}: Error inesperado ({e})")

            resumen = (
                f"Carga completada: {creados} nuevos, {actualizados} actualizados, "
                f"{advertencias} advertencias, {errores} errores."
            )
            if log:
                return JsonResponse({
                    "ok": True,
                    "mensaje": resumen + " Revisá el archivo descargado.",
                    "tiene_errores": True,
                    "log_contenido": "\n".join(log),
                    "log_nombre": "log_insumos.txt",
                })
            else:
                return JsonResponse({
                    "ok": True,
                    "mensaje": resumen + " Sin observaciones.",
                    "tiene_errores": False,
                })

        return JsonResponse({"ok": False, "mensaje": "No se recibió un archivo válido."})
    except Exception as e:
        return JsonResponse({"ok": False, "mensaje": f"Error inesperado: {str(e)}"})


@login_required
def exportar_insumos_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Insumos"

    # 'stock_real' = unidades de uso que se cuentan (ej: hojas). Al reimportar,
    # la app deriva el stock en unidad de compra dividiendo por el factor.
    columnas = ["nombre", "unidad_medida", "unidad_composicion",
                "factor_conversion", "stock_real", "precio"]
    ws.append(columnas)

    for insumo in Insumo.objects.all():
        ws.append([
            insumo.nombre,
            insumo.unidad_medida,
            insumo.unidad_composicion,
            insumo.factor_conversion,
            insumo.stock_real(),
            insumo.precio,
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="insumos_exportados.xlsx"'
    wb.save(response)

    return response


@login_required
@solo_gerencia
def borrar_todos_insumos(request):
    try:
        Insumo.objects.all().delete()
        messages.success(
            request, 'Todos los productos se han borrado correctamente.')
    except Exception as e:
        messages.error(
            request, f'No se han podido borrar todos los productos. Error({e})')
    return redirect('insumos')


@login_required
def procesar_reposicion_insumo_por_edicion(request, insumo, nuevo_stock_real):
    """
    Reemplaza el stock del insumo por el nuevo valor ingresado por el usuario.
    El valor recibido es el "stock real" (unidades de uso, ej: hojas).
    Compensa faltantes si corresponde. Devuelve mensaje para el usuario.
    """
    nuevo_stock_real = float(nuevo_stock_real)
    factor = float(insumo.factor_conversion) or 1

    faltantes = FaltanteInsumo.objects.filter(
        insumo=insumo, resuelto=False).order_by('registrado_en')
    faltante_total = sum(f.cantidad_faltante for f in faltantes)

    if nuevo_stock_real >= faltante_total:
        # Resolver todos los faltantes
        for f in faltantes:
            f.resuelto = True
            f.save()
        stock_final = nuevo_stock_real - faltante_total
        insumo.stock = stock_final / factor
        insumo.ultima_modificacion = timezone.now()
        insumo.modificado_por = request.user
        insumo.save()
        return f"Se ha actualizado el stock de {insumo.nombre} a {nuevo_stock_real:.2f} {insumo.unidad_composicion}. Se resolvieron todos los faltantes. Stock disponible: {stock_final:.2f} {insumo.unidad_composicion}."
    else:
        # Menguar los faltantes
        restante = nuevo_stock_real
        for f in faltantes:
            if restante <= 0:
                break
            if restante >= f.cantidad_faltante:
                restante -= f.cantidad_faltante
                f.resuelto = True
                f.save()
            else:
                f.cantidad_faltante -= restante
                restante = 0
                f.save()
        insumo.stock = 0
        insumo.ultima_modificacion = timezone.now()
        insumo.modificado_por = request.user
        insumo.save()
        faltante_restante = sum(f.cantidad_faltante for f in FaltanteInsumo.objects.filter(
            insumo=insumo, resuelto=False))
        return f"Se ha actualizado el stock de {insumo.nombre} a {nuevo_stock_real:.2f} {insumo.unidad_composicion}. Aún faltan {faltante_restante:.2f} {insumo.unidad_composicion} para compensar los pedidos pendientes."
