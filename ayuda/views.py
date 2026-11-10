"""El manual de uso: índice, capítulos y descarga en PDF.

La wiki y el PDF salen de los **mismos templates**: el PDF concatena los
capítulos en una sola página y la renderiza con weasyprint (ya instalado, lo
usa la impresión de presupuestos). Una sola fuente, dos salidas, y el PDF no
puede quedar desactualizado respecto de la pantalla.

El manual lo ve cualquier usuario autenticado, sin permiso especial: Ventas es
justamente quien más lo necesita. La excepción es el capítulo del dashboard,
que pide el permiso del tablero (ver ``contenido.py``); para quien no lo tiene,
ese capítulo no existe en ninguna de las tres salidas.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone

from .contenido import buscar, para_usuario, publicados, vecinos
from .contexto import contexto_manual, glosario_del_manual


def _base(request):
    """El contexto que comparten todas las pantallas del manual."""
    return {
        'capitulos': para_usuario(request.user),
        'usuario': request.session.get('usuario_nombre'),
        'img': request.session.get('img'),
        'autorizado': request.session.get('autorizado'),
    }


@login_required
def indice(request):
    datos = _base(request)
    datos.update(contexto_manual())
    return render(request, 'ayuda/indice.html', datos)


@login_required
def capitulo(request, slug):
    cap = buscar(slug, request.user)
    if cap is None:
        # Una clave vieja, mal tipeada o de un capítulo que este usuario no
        # puede ver vuelve al índice en vez de dar 404 pelado: el manual es
        # navegación, no una API.
        return render(request, 'ayuda/indice.html',
                      {**_base(request), **contexto_manual(),
                       'no_encontrado': slug}, status=404)
    anterior, siguiente = vecinos(slug, request.user)
    datos = _base(request)
    datos.update(contexto_manual())
    datos.update({'capitulo': cap, 'anterior': anterior, 'siguiente': siguiente})
    return render(request, 'ayuda/capitulo.html', datos)


@login_required
def manual_pdf(request):
    """Los capítulos que este usuario puede leer, en un PDF con los números de hoy."""
    capitulos = publicados(request.user)
    datos = {
        'capitulos': capitulos,
        'generado': timezone.localdate(),
        # En papel no hay tooltips: los conceptos van como glosario al final.
        'glosario': glosario_del_manual(capitulos),
        **contexto_manual(),
    }
    html = render_to_string('ayuda/manual_pdf.html', datos)
    # Sin base_url: el template del PDF no referencia estáticos ni imágenes, a
    # propósito, para que renderice igual en la VM que en desarrollo.
    from weasyprint import HTML
    pdf = HTML(string=html).write_pdf()
    respuesta = HttpResponse(pdf, content_type='application/pdf')
    respuesta['Content-Disposition'] = (
        f'attachment; filename="Manual_EasyPrint_{datos["generado"]}.pdf"')
    return respuesta
