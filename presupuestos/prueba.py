import webbrowser
import matplotlib.pyplot as plt
from rectpack import newPacker, PackingBin, SORT_AREA, GuillotineBssfMaxas
import os
from django.conf import settings
from django.utils.timezone import now


def calcular_cant_etiquetas_por_superficie(ancho_hoja, alto_hoja, ancho_elemento, alto_elemento, separacion, cantidad_deseada):

    # Ajustamos las dimensiones del elemento para considerar la separación si es que hubiera
    ancho_elemento_ajustado = ancho_elemento + separacion
    alto_elemento_ajustado = alto_elemento + separacion

    # Creamos una instancia del empaquetador
    packer = newPacker(pack_algo=GuillotineBssfMaxas,
                       sort_algo=SORT_AREA, rotation=True)

    # Creamos un emboltorio (bin) con las dimensiones de la hoja
    packer.add_bin(ancho_hoja, alto_hoja)

    # Agregamos elementos al paquete. Intentamos agregar un número alto de elementos para averiguar cuantos entran.
    # Los elementos que intentamos agregar tienen que ser con las dimensiones ajustadas, de modo que se tenga en cuenta la separación si es que existe.
    num_elementos = cantidad_deseada if cantidad_deseada != 1 else 10000
    for _ in range(num_elementos):
        packer.add_rect(ancho_elemento_ajustado, alto_elemento_ajustado)

    # Empaquetamos
    packer.pack()

    # Iniciamos una lista para almacenar las etiquetas empaquetadas
    elementos_empaquetados = []

    for abin in packer:
        for rect in abin:
            rectangulo_ajustado = (
                rect.x, rect.y, rect.width - separacion, rect.height - separacion)
            elementos_empaquetados.append(rectangulo_ajustado)

    # Usamos len para averiguar cuantos elementos entraron.
    cant_elementos_empaquetados = len(elementos_empaquetados)

    # Calcular la altura máxima ocupada por las etiquetas empacadas
    altura_max_ocupada = 0
    for rect in elementos_empaquetados:
        altura_max_ocupada = max(
            altura_max_ocupada, rect[1] + rect[3] + separacion / 2)

    # Calcular el área ocupada
    area_ocupada = (ancho_hoja * altura_max_ocupada) / 10000

    # Crea una imagen de la superficie de la hoja con las etiquetas ubicadas
    fig, ax = plt.subplots()
    ax.set_xlim(0, ancho_hoja)
    ax.set_ylim(0, alto_hoja)

    # Crea un rectángulo para representar la superficie de la hoja
    rect = plt.Rectangle((0, 0), ancho_hoja, alto_hoja,
                         color='white', alpha=0.5)
    ax.add_patch(rect)

    # Draw the labels
    for rect in elementos_empaquetados:
        # Apply separation in the plot
        rect_x = rect[0] + separacion/2
        rect_y = rect[1] + separacion/2
        ax.add_patch(plt.Rectangle((rect_x, rect_y),
                                   rect[2], rect[3], fill=True, edgecolor='blue', facecolor='green', alpha=0.5))

    ax.set_xlim(0, ancho_hoja)
    ax.set_ylim(0, alto_hoja)
    ax.set_aspect('equal', adjustable='box')
    plt.gca().invert_yaxis()  # Invert y axis to match the coordinate system

    # Define el path relativo al directorio media
    timestamp_str = now().strftime("%Y%m%d_%H%M%S")
    img_filename = f'surface_{timestamp_str}.png'
    relative_path = 'presupuestos/gráficos/' + img_filename
    save_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path)

    return cant_elementos_empaquetados, relative_path, area_ocupada
