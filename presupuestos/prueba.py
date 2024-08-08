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
    # print(f'Se empaquetaron {cant_elementos_empaquetados} elementos')

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

    # # Crea un HTML con la imagen
    # html = f"""
    # <!DOCTYPE html>
    # <html>
    # <head>
    #     <title>Representación gráfica de la superficie x con las etiquetas ubicadas</title>
    # </head>
    # <body>
    #     <h1>Representación gráfica de la superficie x con las etiquetas ubicadas</h1>
    #     <img src="surface.png" alt="Surface x con etiquetas ubicadas">
    #     <p>Número de etiquetas: {num_packed_labels} en una superficie de  {a} x {b}</p>
    # </body>
    # </html>
    # """

    # # Guarda el HTML en un archivo
    # with open('surface.html', 'w') as file:
    #     file.write(html)

    # # Abre el HTML en el navegador
    # webbrowser.open('surface.html')

    ########################### Esto funciona pero no considera la froma óptima de orientar las etiquetas ###########################
    # # Supongamos que las dimensiones de la superficie x son a*x e b*y
    # a = 31
    # b = 46

    # # Supongamos que las dimensiones de la etiqueta de superficie y son c*x e d*y
    # c = 2
    # d = 4
    # gap = 0.5  # Gap de 0.5 unidades entre las etiquetas

    # # Crea una imagen de la superficie x con las etiquetas ubicadas
    # fig, ax = plt.subplots()
    # ax.set_xlim(0, a)
    # ax.set_ylim(0, b)

    # # Crea un rectángulo para representar la superficie x
    # rect = plt.Rectangle((0, 0), a, b, color='blue', alpha=0.5)
    # ax.add_patch(rect)

    # # Crea rectángulos para representar las etiquetas de superficie y con gap de 0.5 unidades
    # etiquetas_x = []
    # etiquetas_y = []
    # num_etiquetas = 0

    # for i in range(a // c):
    #     x_pos = i * (c + gap)
    #     for j in range(b // d):
    #         y_pos = j * (d + gap)
    #         if x_pos + c <= a and y_pos + d <= b:
    #             rect = plt.Rectangle((x_pos, y_pos), c,
    #                                  d, color='red', alpha=0.5)
    #             ax.add_patch(rect)
    #             etiquetas_x.append(x_pos)
    #             etiquetas_y.append(y_pos)
    #             num_etiquetas += 1

    # # Ajusta la escala de ambos ejes para mantenerla igual
    # ax.set_aspect('equal')
    # # Guarda el gráfico en un archivo HTML
    # plt.savefig('surface.png')

    # # Crea un HTML con la imagen
    # html = f"""
    # <!DOCTYPE html>
    # <html>
    # <head>
    #     <title>Representación gráfica de la superficie x con las etiquetas ubicadas</title>
    # </head>
    # <body>
    #     <h1>Representación gráfica de la superficie x con las etiquetas ubicadas</h1>
    #     <img src="surface.png" alt="Surface x con etiquetas ubicadas">
    #     <p>Número de etiquetas: {num_etiquetas} en una superficie de  {a} x {b}</p>
    # </body>
    # </html>
    # """

    # # Guarda el HTML en un archivo
    # with open('surface.html', 'w') as file:
    #     file.write(html)

    # # Abre el HTML en el navegador
    # webbrowser.open('surface.html')
