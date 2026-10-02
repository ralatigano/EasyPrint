import math
import os
import textwrap
from django.conf import settings
from django.template.loader import get_template
from datetime import datetime
from productos.models import Producto, Categoria
from rectpack import newPacker, SkylineMwf, MaxRectsBssf
from rectpack import SORT_RATIO
from core.utils import format_ar


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


ALGORITMOS_PACKING = {
    "Skyline": SkylineMwf,
    "MaxRects": MaxRectsBssf,
}

# Alto "infinito" con el que se representa un rollo (alto = "Según cálculo").
ALTO_ROLLO = 100000

# Lado del diseño que se corta al partirlo en franjas: el más largo (default)
# o el más corto. El otro lado se mantiene entero.
DIRECCIONES_CORTE = ("largo", "corto")


def _empaquetar(ancho_hoja, alto_hoja, piezas, separacion, algoritmo):
    """Acomoda `piezas` [(ancho, alto, id)] en una hoja/rollo (con rotación).

    Devuelve [(x, y, ancho, alto, id)] de lo que entró, con las medidas reales
    de la pieza (sin la separación, que solo se usa para empaquetar)."""
    packer = newPacker(
        pack_algo=ALGORITMOS_PACKING.get(algoritmo, SkylineMwf),
        sort_algo=SORT_RATIO,
        rotation=True
    )
    packer.add_bin(ancho_hoja, alto_hoja)
    for ancho, alto, rid in piezas:
        packer.add_rect(ancho + separacion, alto + separacion, rid)
    packer.pack()
    return [
        (rect.x, rect.y, rect.width - separacion, rect.height - separacion, rect.rid)
        for abin in packer for rect in abin
    ]


def _altura_ocupada(colocados, separacion):
    return max((r[1] + r[3] + separacion / 2) for r in colocados) if colocados else 0


def _consumo(tipo_calculo, ancho_hoja, altura):
    """Material que se cobra en rollos: m² (B) o metros lineales (C), con el
    10% de margen de largo que usa el cotizador."""
    if tipo_calculo == "B":
        return (ancho_hoja * altura * 1.1) / 10000
    return (altura * 1.1) / 100


def calcular_franjas(ancho_elemento, alto_elemento, ancho_util, solapamiento, direccion="largo"):
    """Parte un diseño en franjas iguales que entren en el ancho del material.

    Se corta un solo lado (el más largo con direccion='largo', el más corto con
    'corto'); el otro queda entero. Las franjas vecinas comparten `solapamiento`
    cm, así que la suma de las franjas es lado + (n-1)·solapamiento. Se usa la
    menor cantidad de franjas (mínimo 2) cuyo largo no supere `ancho_util`.

    Devuelve {'n', 'lado_entero', 'largo_franja', 'lado_cortado'} o lanza
    ValueError si el solapamiento no deja lugar.
    """
    lado_cortado = max(ancho_elemento, alto_elemento) if direccion == "largo" \
        else min(ancho_elemento, alto_elemento)
    lado_entero = min(ancho_elemento, alto_elemento) if direccion == "largo" \
        else max(ancho_elemento, alto_elemento)
    if solapamiento < 0:
        raise ValueError("El solapamiento no puede ser negativo.")
    if ancho_util <= solapamiento:
        raise ValueError("El solapamiento es mayor que el ancho del material.")
    # n franjas de largo (L + (n-1)s)/n <= W  <=>  n >= (L - s) / (W - s)
    n = max(2, math.ceil((lado_cortado - solapamiento) / (ancho_util - solapamiento) - 1e-9))
    largo_franja = (lado_cortado + (n - 1) * solapamiento) / n
    return {
        "n": n,
        "lado_entero": lado_entero,
        "largo_franja": largo_franja,
        "lado_cortado": lado_cortado,
    }


# Arriba de esta cantidad de copias no se busca la combinación enteros/partidos
# (se parten todas): evita un cálculo largo en pedidos de muchas unidades.
MAX_COPIAS_MIXTO = 300


def _filas_mixtas(ancho_hoja, copias, ancho_entero, ancho_franja, n, separacion):
    """Decide cuántas copias van enteras y cuántas partidas, fila por fila.

    Todas las piezas miden lo mismo a lo largo del rollo (el lado entero), así
    que el problema es llenar filas de ancho `ancho_hoja` con copias enteras
    (ancho `ancho_entero`, si entra) o con sus `n` franjas (`ancho_franja`
    cada una, pueden quedar en filas distintas). Busca la menor cantidad de
    filas y, con esa, la menor cantidad de copias partidas: un diseño que entra
    entero no se parte ni suma solapamiento.

    Devuelve (enteras_por_fila, partidas): enteras_por_fila[i] = copias enteras
    en la fila i (el resto de la fila se llena con franjas).
    """
    paso_entero = ancho_entero + separacion
    paso_franja = ancho_franja + separacion
    ancho = ancho_hoja + 1e-9
    max_enteras = int(ancho // paso_entero) if copias <= MAX_COPIAS_MIXTO else 0
    # franjas_en_fila[a] = franjas que entran en una fila con `a` copias enteras
    franjas_en_fila = [int((ancho - a * paso_entero) // paso_franja)
                       for a in range(max_enteras + 1)]
    max_filas = math.ceil(copias * n / franjas_en_fila[0])

    # capacidad[w] = máximo de franjas que entran con exactamente w copias enteras
    # en las filas consideradas; padres[f][w] = (w anterior, enteras en la fila f).
    capacidad = [0] + [-1] * copias
    padres = []
    for _ in range(max_filas):
        nueva = [-1] * (copias + 1)
        padre = [None] * (copias + 1)
        for w, cap in enumerate(capacidad):
            if cap < 0:
                continue
            for a in range(min(max_enteras, copias - w) + 1):
                if cap + franjas_en_fila[a] > nueva[w + a]:
                    nueva[w + a] = cap + franjas_en_fila[a]
                    padre[w + a] = (w, a)
        capacidad = nueva
        padres.append(padre)
        for partidas in range(copias + 1):
            if capacidad[copias - partidas] >= partidas * n:
                enteras_por_fila = []
                w = copias - partidas
                for padre in reversed(padres):
                    w, a = padre[w]
                    enteras_por_fila.append(a)
                return list(reversed(enteras_por_fila)), partidas
    return None


def _acomodar_franjas(ancho_hoja, alto_hoja, franjas, copias, separacion):
    """Ubica copias enteras y franjas según _filas_mixtas. Mismo formato que
    _empaquetar, con id = (n° de diseño, n° de franja, total de franjas): una
    copia entera es (d, 0, 1). Devuelve (colocados, partidas) o None."""
    n, alto = franjas["n"], franjas["lado_entero"]
    ancho_entero, ancho_franja = franjas["lado_cortado"], franjas["largo_franja"]
    plan = _filas_mixtas(ancho_hoja, copias, ancho_entero, ancho_franja, n, separacion)
    if plan is None:
        return None
    enteras_por_fila, partidas = plan
    paso_y = alto + separacion
    if len(enteras_por_fila) * paso_y > alto_hoja + 1e-9:
        return None

    enteras = copias - partidas
    # Las franjas se reparten en orden: una copia puede empezar al final de una
    # fila y terminar en la siguiente.
    pendientes = [(d, i, n) for d in range(enteras + 1, copias + 1) for i in range(n)]
    proxima_entera = 1
    colocados = []
    for fila, a in enumerate(enteras_por_fila):
        x, y = 0, fila * paso_y
        for _ in range(a):
            colocados.append((x, y, ancho_entero, alto, (proxima_entera, 0, 1)))
            proxima_entera += 1
            x += ancho_entero + separacion
        while pendientes and x + ancho_franja + separacion <= ancho_hoja + 1e-9:
            colocados.append((x, y, ancho_franja, alto, pendientes.pop(0)))
            x += ancho_franja + separacion
    return colocados, partidas


def _empaquetar_franjas(tipo_calculo, ancho_hoja, alto_hoja, ancho_elemento, alto_elemento,
                        separacion, solapamiento, direccion, copias, algoritmo):
    """Parte las copias que hace falta y devuelve
    (franjas, colocados, consumo, copias_partidas) o None si no entran."""
    franjas = calcular_franjas(ancho_elemento, alto_elemento,
                               ancho_hoja - separacion, solapamiento, direccion)
    resultado = _acomodar_franjas(ancho_hoja, alto_hoja, franjas, copias, separacion)
    if resultado is None:
        return None
    colocados, partidas = resultado
    altura = _altura_ocupada(colocados, separacion)
    return franjas, colocados, _consumo(tipo_calculo, ancho_hoja, altura), partidas


def _consumo_sin_partir(tipo_calculo, ancho_hoja, alto_hoja, ancho_elemento, alto_elemento,
                        separacion, copias, algoritmo):
    piezas = [(ancho_elemento, alto_elemento, i) for i in range(copias)]
    colocados = _empaquetar(ancho_hoja, alto_hoja, piezas, separacion, algoritmo)
    if len(colocados) < copias:
        return None
    return _consumo(tipo_calculo, ancho_hoja, _altura_ocupada(colocados, separacion))


def _guardar_grafico(ancho_hoja, alto_hoja, titulo, colocados, separacion, franjas=None, solapamiento=0):
    """Dibuja la hoja/rollo con las piezas y devuelve la URL de la imagen.

    Con `franjas`, rotula cada pieza con su diseño (D1, D2…) y n° de franja
    (1/n…), y raya las zonas de solapamiento."""
    plt = configurar_matplotlib()
    fig, ax = plt.subplots()
    ax.set_xlim(0, ancho_hoja)
    ax.set_ylim(0, alto_hoja)
    ax.set_aspect('equal', adjustable='box')
    plt.gca().invert_yaxis()
    # Los títulos con franjas son largos: se parten en líneas para que no se corten.
    ax.set_title(textwrap.fill(titulo, 70) if franjas else titulo,
                 fontsize=9 if franjas else None)

    # Fondo hoja
    ax.add_patch(plt.Rectangle((0, 0), ancho_hoja, alto_hoja, color='white', alpha=0.5))

    for x, y, ancho, alto, rid in colocados:
        x += separacion / 2
        y += separacion / 2
        ax.add_patch(plt.Rectangle(
            (x, y), ancho, alto, fill=True, edgecolor='blue', facecolor='green', alpha=0.5))
        if not franjas:
            continue
        diseno, indice, n = rid
        etiqueta = f"D{diseno}" if n == 1 else f"D{diseno}\n{indice + 1}/{n}"
        ax.text(x + ancho / 2, y + alto / 2, etiqueta,
                ha='center', va='center', fontsize=7, color='black')
        if n == 1 or solapamiento <= 0:
            continue
        # Las franjas van sin rotar (largo de franja en x): el solapamiento con
        # la franja anterior/siguiente queda a la izquierda/derecha.
        bandas = []
        if indice > 0:
            bandas.append(0)
        if indice < n - 1:
            bandas.append(ancho - solapamiento)
        for desde in bandas:
            ax.add_patch(plt.Rectangle((x + desde, y), solapamiento, alto, fill=False,
                                       hatch='///', edgecolor='darkred', linewidth=0.5))

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_filename = f'surface_{timestamp_str}.png'
    relative_path = f'presupuestos/graficos/{img_filename}'
    save_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path)
    plt.close()
    return settings.MEDIA_URL + relative_path


def _texto_consumo(tipo_calculo, valor):
    return f"{format_ar(valor)} m²" if tipo_calculo == "B" else f"{format_ar(valor)} metros lineales"


def procesar_cotizacion_partida(tipo_calculo, ancho_hoja, alto_hoja, ancho_elemento, alto_elemento,
                                separacion, cantidad_deseada, algoritmo, solapamiento, direccion):
    """Tipos B/C con el diseño partido en franjas (ver calcular_franjas).

    Además del resultado, informa el consumo sin partir (para comparar) y si
    cortar por la otra dimensión da un resultado distinto que valga ofrecer."""
    copias = max(cantidad_deseada, 1)
    direccion = direccion if direccion in DIRECCIONES_CORTE else "largo"
    try:
        resultado = _empaquetar_franjas(
            tipo_calculo, ancho_hoja, alto_hoja, ancho_elemento, alto_elemento,
            separacion, solapamiento, direccion, copias, algoritmo)
    except ValueError as e:
        return {"mensaje": str(e), "tipo": "X"}
    if resultado is None:
        return {"mensaje": "Las franjas no entran en el material.", "tipo": "X"}
    franjas, colocados, consumo, partidas = resultado

    sin_partir = _consumo_sin_partir(
        tipo_calculo, ancho_hoja, alto_hoja, ancho_elemento, alto_elemento,
        separacion, copias, algoritmo)

    # ¿Tiene sentido ofrecer cortar por la otra dimensión? Desde 'corto' siempre
    # se puede volver a 'largo'; desde 'largo' solo si la alternativa cambia el
    # resultado y mejora lo que se gasta sin partir (o sin partir no entra).
    otra = "corto" if direccion == "largo" else "largo"
    alternativa = None
    if ancho_elemento != alto_elemento:
        try:
            res_otra = _empaquetar_franjas(
                tipo_calculo, ancho_hoja, alto_hoja, ancho_elemento, alto_elemento,
                separacion, solapamiento, otra, copias, algoritmo)
        except ValueError:
            res_otra = None
        if res_otra:
            consumo_otra = res_otra[2]
            if otra == "largo" or (
                abs(consumo_otra - consumo) > 1e-6
                and (sin_partir is None or consumo_otra < sin_partir - 1e-6)
            ):
                alternativa = {"direccion": otra, "valor": consumo_otra}

    n, entero, largo = franjas["n"], franjas["lado_entero"], franjas["largo_franja"]
    cortado = franjas["lado_cortado"]
    franjas_txt = (f"{n} franjas de {format_ar(entero)} × {format_ar(largo)} cm "
                   f"(solapamiento {format_ar(solapamiento)} cm)")
    if partidas == 0:
        titulo = (f"{copias} × diseño de {format_ar(ancho_elemento)} x {format_ar(alto_elemento)} cm, "
                  f"enteros con el lado de {format_ar(cortado)} cm a lo ancho")
        detalle = ("No hace falta partir: " +
                   (f"el diseño entra entero" if copias == 1 else f"los {copias} diseños entran enteros") +
                   f" con el lado de {format_ar(cortado)} cm a lo ancho del material.")
    elif partidas == copias:
        titulo = (f"{copias} × diseño de {format_ar(ancho_elemento)} x {format_ar(alto_elemento)} cm "
                  f"en {franjas_txt}")
        detalle = ((f"Diseño partido en " if copias == 1 else f"Cada diseño se parte en ") +
                   f"{franjas_txt}; queda entero el lado de {format_ar(entero)} cm.")
    else:
        titulo = (f"{copias} × diseño de {format_ar(ancho_elemento)} x {format_ar(alto_elemento)} cm: "
                  f"{partidas} en {franjas_txt}, {copias - partidas} enteros")
        detalle = (f"Se parte{'n' if partidas != 1 else ''} {partidas} de los {copias} diseños en "
                   f"{franjas_txt}; los otros {copias - partidas} van enteros.")
    altura = _altura_ocupada(colocados, separacion)
    alto_dibujo = altura * 1.2 if alto_hoja == ALTO_ROLLO else alto_hoja
    grafico_url = _guardar_grafico(ancho_hoja, alto_dibujo, titulo, colocados, separacion,
                                   franjas=franjas, solapamiento=solapamiento)

    mensaje = (f"{detalle} Hacen falta {_texto_consumo(tipo_calculo, consumo)} "
               f"para imprimir {copias} elemento{'s' if copias != 1 else ''}. ")
    if sin_partir is None:
        mensaje += "Sin partir, el diseño no entra en el ancho del material."
    else:
        mensaje += f"Sin partir: {_texto_consumo(tipo_calculo, sin_partir)}."

    clave = "area_ocupada" if tipo_calculo == "B" else "largo_ocupado"
    return {
        "grafico_url": grafico_url,
        clave: consumo,
        "valor_grafico": consumo,
        "mensaje": mensaje,
        "tipo": "D",
        "particion": {
            "direccion": direccion,
            "n": n,
            "copias": copias,
            "partidas": partidas,
            "lado_entero": entero,
            "largo_franja": largo,
            "solapamiento": solapamiento,
            "valor_sin_partir": sin_partir,
            "alternativa": alternativa,
        },
    }


def procesar_cotizacion_con_grafico(
    tipo_calculo,
    ancho_hoja,
    alto_hoja,
    ancho_elemento,
    alto_elemento,
    separacion,
    cantidad_deseada,
    algoritmo,
    partir=False,
    solapamiento=5,
    direccion="largo",
):
    es_rollo = alto_hoja == ALTO_ROLLO
    if partir and tipo_calculo in ("B", "C"):
        return procesar_cotizacion_partida(
            tipo_calculo, ancho_hoja, alto_hoja, ancho_elemento, alto_elemento,
            separacion, cantidad_deseada, algoritmo, solapamiento, direccion)

    # Con cantidad 1 se llena la hoja para saber cuántos entran (tipo A).
    num_elementos = cantidad_deseada if cantidad_deseada > 1 else 10000
    colocados = _empaquetar(
        ancho_hoja, alto_hoja,
        [(ancho_elemento, alto_elemento, i) for i in range(num_elementos)],
        separacion, algoritmo)

    cant_empaquetados = len(colocados)
    if cant_empaquetados == 0:
        sugerencia = (" Probá con «Partir diseño»." if tipo_calculo in ("B", "C") else "")
        return {
            "mensaje": f"El diseño de {format_ar(ancho_elemento)} × {format_ar(alto_elemento)} cm "
                       f"no entra en el ancho del material ({format_ar(ancho_hoja)} cm).{sugerencia}",
            "tipo": "X",
        }
    elementos_a_dibujar = colocados[:cantidad_deseada] if cantidad_deseada > 1 else colocados[:1]

    # Calcular altura máxima ocupada
    altura_max_ocupada = _altura_ocupada(elementos_a_dibujar, separacion)

    alto_dibujo = altura_max_ocupada * 1.2 if es_rollo else alto_hoja
    titulo = f"{cantidad_deseada} elementos de {format_ar(ancho_elemento)} x {format_ar(alto_elemento)} cm con {format_ar(separacion)} cm de separación"
    grafico_url = _guardar_grafico(ancho_hoja, alto_dibujo, titulo, elementos_a_dibujar, separacion)

    # Mensaje según tipo
    if tipo_calculo == "A":
        hojas_necesarias = (cantidad_deseada +
                            cant_empaquetados - 1) // cant_empaquetados
        sobrante = (cant_empaquetados * hojas_necesarias) - cantidad_deseada
        mensaje = f"Entran {cant_empaquetados} elementos por hoja. Se requieren {hojas_necesarias} hojas para completar {cantidad_deseada} elementos. Sobrarán {sobrante}."
        return {
            "grafico_url": grafico_url,
            "cantidad_empaquetada": cant_empaquetados,
            "valor_grafico": hojas_necesarias,
            "mensaje": mensaje,
            "tipo": "D"
        }
    elif tipo_calculo == "B":
        area_ocupada = _consumo("B", ancho_hoja, altura_max_ocupada)
        mensaje = f"Hacen falta {format_ar(area_ocupada)} m² para imprimir {cantidad_deseada} elementos."
        return {
            "grafico_url": grafico_url,
            "area_ocupada": area_ocupada,
            "valor_grafico": area_ocupada,
            "mensaje": mensaje,
            "tipo": "D"
        }
    elif tipo_calculo == "C":
        largo_ocupado = _consumo("C", ancho_hoja, altura_max_ocupada)
        mensaje = f"Hacen falta {format_ar(largo_ocupado)} metros lineales para imprimir {cantidad_deseada} elementos."
        return {
            "grafico_url": grafico_url,
            "largo_ocupado": largo_ocupado,
            "valor_grafico": largo_ocupado,
            "mensaje": mensaje,
            "tipo": "D"
        }
    else:
        return {
            "mensaje": "Tipo de cálculo no reconocido.",
            "tipo": "X"
        }
