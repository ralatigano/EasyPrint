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
# Create your views here.
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
    productos = Producto.objects.filter(
        categoria_id=categoria_id).values("id", "nombre")
    return JsonResponse(list(productos), safe=False)


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

                        precio_total = sum(
                            comp["precio"] * comp["cantidad"] for comp in componentes)
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

        insumo.nombre = data.get("nombre")
        insumo.unidad_medida = data.get("unidad_medida")
        insumo.unidad_composicion = data.get("unidad_composicion")
        insumo.factor_conversion = data.get("factor_conversion") or 1
        insumo.precio = parse_ar(data.get("precio_unitario")) or 0
        insumo.activo = data.get("activo") == "on"
        cantidad_repuesta = data.get("stock") or 0
        insumo.stock = cantidad_repuesta

        if id_insumo and id_insumo != "0":
            mensaje_reposicion = procesar_reposicion_insumo_por_edicion(request,
                                                                        insumo, cantidad_repuesta)
            insumo.save()
            return JsonResponse({"ok": True, "mensaje": mensaje, "info_reposicion": mensaje_reposicion})
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
            errores = 0
            log = []

            for idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                total_filas += 1

                if all(cell is None or str(cell).strip() == "" for cell in row):
                    continue

                try:
                    data = dict(zip(headers, row))
                    nombre = str(data.get('nombre')).strip()

                    if not nombre:
                        errores += 1
                        log.append(f"Fila {idx}: Insumo sin nombre.")
                        continue

                    unidad_medida = str(data.get('unidad_medida')).strip()
                    unidad_composicion = str(
                        data.get('unidad_composicion')).strip()
                    factor_conversion = int(data.get('factor_conversion') or 1)
                    stock = float(data.get('stock') or 0)
                    precio = float(data.get('precio') or 0)

                    insumo, creado = Insumo.objects.get_or_create(
                        nombre=nombre)

                    insumo.unidad_medida = unidad_medida
                    insumo.unidad_composicion = unidad_composicion
                    insumo.factor_conversion = factor_conversion
                    insumo.stock = stock
                    insumo.precio = precio
                    insumo.save()

                    if creado:
                        creados += 1
                    else:
                        actualizados += 1

                except Exception as e:
                    errores += 1
                    log.append(f"Fila {idx}: Error inesperado ({e})")

            if log:
                mensaje = (
                    f"Carga completada: {creados} nuevos, {actualizados} actualizados, "
                    f"{errores} errores. Revisá el archivo de log descargado."
                )
                return JsonResponse({
                    "ok": True,
                    "mensaje": mensaje,
                    "tiene_errores": True,
                    "log_contenido": "\n".join(log),
                    "log_nombre": "errores_insumos.txt",
                })
            else:
                return JsonResponse({
                    "ok": True,
                    "mensaje": f"Carga completada: {creados} nuevos, {actualizados} actualizados, sin errores.",
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

    columnas = ["nombre", "unidad_medida", "unidad_composicion",
                "factor_conversion", "stock", "precio"]
    ws.append(columnas)

    for insumo in Insumo.objects.all():
        ws.append([
            insumo.nombre,
            insumo.unidad_medida,
            insumo.unidad_composicion,
            insumo.factor_conversion,
            insumo.stock,
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
def procesar_reposicion_insumo_por_edicion(request, insumo, nuevo_valor):
    """
    Reemplaza el stock del insumo por el nuevo valor ingresado por el usuario.
    Compensa faltantes si corresponde. Devuelve mensaje para el usuario.
    """
    nuevo_valor = float(nuevo_valor)
    nuevo_stock_real = nuevo_valor * float(insumo.factor_conversion)

    faltantes = FaltanteInsumo.objects.filter(
        insumo=insumo, resuelto=False).order_by('registrado_en')
    faltante_total = sum(f.cantidad_faltante for f in faltantes)

    if nuevo_stock_real >= faltante_total:
        # Resolver todos los faltantes
        for f in faltantes:
            f.resuelto = True
            f.save()
        stock_final = nuevo_stock_real - faltante_total
        insumo.stock = stock_final / float(insumo.factor_conversion)
        insumo.ultima_modificacion = timezone.now()
        insumo.modificado_por = request.user
        insumo.save()
        return f"Se ha actualizado el stock de {insumo.nombre} a {nuevo_valor:.2f}. Se resolvieron todos los faltantes. Stock disponible: {stock_final:.2f} {insumo.unidad_composicion}."
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
        return f"Se ha actualizado el stock de {insumo.nombre} a {nuevo_valor:.2f}. Aún faltan {faltante_restante:.2f} {insumo.unidad_composicion} para compensar los pedidos pendientes."
