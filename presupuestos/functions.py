import os
from django.conf import settings
from django.template.loader import get_template
from datetime import datetime
from productos.models import Producto, Categoria
from rectpack import newPacker, SkylineMwf, MaxRectsBssf
from rectpack import SORT_RATIO


def configurar_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt

# Obtiene los datos que vienen del formulario para convertirlos en un diccionario que sirve para crear el producto en la vista AgregarProducto.


def obtener_datos(request):
    np = request.POST['n_presupuesto']
    if request.POST['cliente'] == '':
        cliente = 'Consumidor final'
    else:
        cliente = request.POST['cliente']
    prod_cod = request.POST['producto']
    categoria = request.POST['categoria']
    cat = Categoria.objects.get(nombre=categoria)
    prod = Producto.objects.filter(resultado=0).get(codigo=prod_cod)
    info_adic = request.POST['info_adic']
    cantidad = float(request.POST['cantidad'])
    t_produccion = float(request.POST['t_produccion'])
    if request.POST.get('empaquetado') == 'on':
        empaq = True
    else:
        empaq = False
    precio = float(prod.precio)
    descuento = int(request.POST['descuento'])
    return ({
            'np': np,
            'cliente': cliente,
            'codigo': prod.codigo,
            'producto': prod.nombre,
            'categoria': cat.nombre,
            'info_adic': info_adic,
            'cantidad': cantidad,
            't_produccion': t_produccion,
            'empaquetado': empaq,
            'precio': precio,
            'descuento': descuento,
            })

# Función que calcula el precio de un producto al iniciar una cotización usando la información que viene en el diccionario.


def calc_precio(diccionario):
    costo_produccion = float(Producto.objects.get(codigo=125).precio)
    t_prod = diccionario['t_produccion'] if diccionario['t_produccion'] else 0
    empaquetado_precio = 0
    empaquetado = 'No'
    if diccionario['empaquetado']:
        empaquetado_precio = float(Producto.objects.get(codigo=123).precio)
        empaquetado = 'Si'
    precio = round(diccionario['precio'] * diccionario['cantidad'] +
                   t_prod * costo_produccion + empaquetado_precio, 2)
    desc_plata = float(precio * diccionario['descuento'] / 100)
    resultado = precio - desc_plata
    producto = diccionario['producto']
    info_adic = diccionario['info_adic']
    cantidad = diccionario['cantidad']
    descuento = diccionario['descuento']
    return ({
        'precio': precio,
        'desc_plata': desc_plata,
        'resultado': resultado,
        'producto': producto,
        'info_adic': info_adic,
        'cantidad': cantidad,
        'descuento': descuento,
        'empaquetado': empaquetado,
        't_produccion': t_prod,
    })

# Lógica que genera un nuevo número de pedido en función de la fecha.


def armar_numero_pedido():
    d = datetime.now()
    if d.month < 10:
        m = '0' + str(d.month)
    else:
        m = str(d.month)
    if d.day < 10:
        day = '0' + str(d.day)
    else:
        day = str(d.day)

    if d.hour < 10:
        h = '0' + str(d.hour)
    else:
        h = str(d.hour)
    if d.minute < 10:
        min = '0' + str(d.minute)
    else:
        min = str(d.minute)
    if d.second < 10:
        s = '0' + str(d.second)
    else:
        s = str(d.second)
    return f'{d.year}{m}{day}{h}{min}{s}'


def procesar_cotizacion_con_grafico(
    tipo_calculo,
    ancho_hoja,
    alto_hoja,
    ancho_elemento,
    alto_elemento,
    separacion,
    cantidad_deseada,
    algoritmo
):
    # Ajustar dimensiones con separación
    ancho_elemento_ajustado = ancho_elemento + separacion
    alto_elemento_ajustado = alto_elemento + separacion

    # Selección de algoritmo
    algoritmos = {
        "Skyline": SkylineMwf,
        "MaxRects": MaxRectsBssf,
    }
    packer = newPacker(
        pack_algo=algoritmos.get(algoritmo, SkylineMwf),
        sort_algo=SORT_RATIO,
        rotation=True
    )

    # Crear bin
    packer.add_bin(ancho_hoja, alto_hoja)

    # Agregar elementos
    num_elementos = cantidad_deseada if cantidad_deseada > 1 else 10000
    for _ in range(num_elementos):
        packer.add_rect(ancho_elemento_ajustado, alto_elemento_ajustado)

    packer.pack()

    elementos_empaquetados = []
    for abin in packer:
        for rect in abin:
            rectangulo_ajustado = (
                rect.x,
                rect.y,
                rect.width - separacion,
                rect.height - separacion
            )
            elementos_empaquetados.append(rectangulo_ajustado)

    cant_empaquetados = len(elementos_empaquetados)
    elementos_a_dibujar = elementos_empaquetados[:
                                                 cantidad_deseada] if cantidad_deseada > 1 else elementos_empaquetados[:1]

    # Calcular altura máxima ocupada
    altura_max_ocupada = max(
        (r[1] + r[3] + separacion / 2) for r in elementos_a_dibujar
    ) if elementos_a_dibujar else 0

    if alto_hoja == 100000:
        alto_hoja = altura_max_ocupada * 1.2

    area_ocupada = (ancho_hoja * altura_max_ocupada * 1.1) / 10000
    largo_ocupado = (altura_max_ocupada * 1.1) / 100

    # Crear gráfico
    plt = configurar_matplotlib()
    fig, ax = plt.subplots()
    ax.set_xlim(0, ancho_hoja)
    ax.set_ylim(0, alto_hoja)
    ax.set_aspect('equal', adjustable='box')
    plt.gca().invert_yaxis()

    # Título con datos
    titulo = f"{cantidad_deseada} elementos de {ancho_elemento}x{alto_elemento} cm con {separacion} cm de separación"
    ax.set_title(titulo)

    # Fondo hoja
    hoja = plt.Rectangle((0, 0), ancho_hoja, alto_hoja,
                         color='white', alpha=0.5)
    ax.add_patch(hoja)

    # Etiquetas
    for r in elementos_a_dibujar:
        rect_x = r[0] + separacion / 2
        rect_y = r[1] + separacion / 2
        ax.add_patch(plt.Rectangle(
            (rect_x, rect_y),
            r[2], r[3],
            fill=True,
            edgecolor='blue',
            facecolor='green',
            alpha=0.5
        ))

    # Guardar gráfico
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_filename = f'surface_{timestamp_str}.png'
    relative_path = f'presupuestos/graficos/{img_filename}'
    save_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    grafico_url = settings.MEDIA_URL + relative_path
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path)
    plt.close()

    # Mensaje según tipo
    if tipo_calculo == "A":
        hojas_necesarias = (cantidad_deseada +
                            cant_empaquetados - 1) // cant_empaquetados
        sobrante = (cant_empaquetados * hojas_necesarias) - cantidad_deseada
        mensaje = f"Entran {cant_empaquetados} elementos por hoja. Se requieren {hojas_necesarias} hojas para completar {cantidad_deseada} elementos. Sobrarán {sobrante}."
        tipo = "D"
        return {
            "grafico_url": grafico_url,
            "cantidad_empaquetada": cant_empaquetados,
            "valor_grafico": hojas_necesarias,
            "mensaje": mensaje,
            "tipo": tipo
        }
    elif tipo_calculo == "B":
        mensaje = f"Hacen falta {area_ocupada:.2f} m² para imprimir {cantidad_deseada} elementos."
        tipo = "D"
        return {
            "grafico_url": grafico_url,
            "area_ocupada": area_ocupada,
            "valor_grafico": area_ocupada,
            "mensaje": mensaje,
            "tipo": tipo
        }
    elif tipo_calculo == "C":
        mensaje = f"Hacen falta {largo_ocupado:.2f} metros lineales para imprimir {cantidad_deseada} elementos."
        tipo = "D"
        return {
            "grafico_url": grafico_url,
            "largo_ocupado": largo_ocupado,
            "valor_grafico": largo_ocupado,
            "mensaje": mensaje,
            "tipo": tipo
        }
    else:
        mensaje = "Tipo de cálculo no reconocido."
        return {
            "mensaje": "Tipo de cálculo no reconocido.",
            "tipo": "X"
        }
