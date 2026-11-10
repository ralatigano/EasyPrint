"""Los números con los que el manual arma sus ejemplos.

Decisión de fondo: **los ejemplos del manual salen de la base real**, no de
números inventados. Un manual que muestra la tasa por hora de esta imprenta y
un producto que existe se entiende y se verifica solo; uno con cifras de
fantasía se lee como teoría y no se aplica.

Todo lo de acá es tolerante a una base vacía: si no hay datos devuelve ``None``
y el template cae a una explicación genérica. Así el manual no se rompe en una
instalación nueva ni en los tests.
"""
import re
from decimal import Decimal

from core import costos

# Familias de productos por cantidad: "Papel obra ... [31-100]". Es la MISMA
# convención que resuelve `_RANGO_RE` en presupuestos/views.py (ahí está el
# comportamiento canónico, al cotizar). Se repite acá para no importar las
# vistas de otra app sólo para armar un ejemplo; hay un test que verifica que
# las dos expresiones coincidan, para que no se separen con el tiempo.
RANGO_RE = re.compile(r'^(.*?)\s*\[(\d+)-(\d+|INF)\]\s*$')


def _producto(nombre):
    """Los pseudo-productos de configuración ("Mano de obra", "Empaquetado")."""
    from productos.models import Producto
    return Producto.objects.filter(nombre=nombre).first()


def parametros():
    """La estructura de costos vigente, tal como la usa el cotizador."""
    from core.models import ParametrosProduccion
    mano_obra = _producto('Mano de obra')
    empaquetado = _producto('Empaquetado')
    prod = ParametrosProduccion.load()
    p = {
        # Los factores con los que se arman las horas del mes: el capítulo del
        # tablero muestra la cuenta entera, no sólo su resultado.
        'operarios': prod.operarios,
        'horas_dia': prod.horas_dia,
        'dias_mes': prod.dias_mes,
        'ratio_productivas': prod.ratio_productivas,
        'costo_fijo': costos.costo_fijo_mensual(),
        'horas_disponibles': costos.horas_disponibles_mes(),
        'horas_productivas': costos.horas_productivas_mes(),
        'tasa_hora': costos.tasa_hora(),
        'margen_objetivo': costos.margen_objetivo(),
        'horas_legacy': costos.horas_legacy(),
        'precio_hora': mano_obra.precio_proveedor if mano_obra else None,
        'precio_empaquetado': empaquetado.precio_proveedor if empaquetado else None,
    }
    p['hay_estructura'] = bool(p['costo_fijo'] and p['horas_productivas'])
    return p


def insumo_ejemplo():
    """Un insumo donde la unidad de compra y la de uso NO coinciden.

    Es el caso que hay que entender (resma → hoja); uno con factor 1 no enseña
    nada. Se elige el de factor de conversión más alto para que el ejemplo sea
    bien visible, y a igualdad de factor el de id más bajo (determinista).
    """
    from productos.models import Insumo
    return (
        Insumo.objects
        .filter(activo=True, factor_conversion__gt=1, precio__gt=0)
        .exclude(unidad_composicion='')
        .order_by('-factor_conversion', 'id')
        .first()
    )


def _tiers(nombre_base, categoria_id):
    """Los escalones de una familia [N-M], ordenados por cantidad."""
    from productos.models import Producto
    tiers = []
    candidatos = Producto.objects.filter(
        nombre__istartswith=nombre_base, categoria_id=categoria_id, activo=True)
    for p in candidatos:
        m = RANGO_RE.match(p.nombre)
        if not m or m.group(1).strip().lower() != nombre_base.lower():
            continue
        desde = int(m.group(2))
        hasta = None if m.group(3) == 'INF' else int(m.group(3))
        tiers.append({'producto': p, 'desde': desde, 'hasta': hasta})
    tiers.sort(key=lambda t: t['desde'])
    return tiers


def familia_ejemplo():
    """La familia [N-M] con más escalones, para mostrar cómo baja el factor.

    Sólo devuelve el factor de cada escalón y lo que queda cobrándose por
    unidad de cálculo (``precio del material × factor``). **No compara contra
    el precio sugerido**: son dos criterios distintos, ninguno de los dos
    mecánico, y ponerlos en columnas contiguas sugiere que uno corrige al otro.
    Ver PLAN_v3.10.md, §6.1.
    """
    from productos.models import Producto
    familias = {}
    for p in Producto.objects.filter(activo=True, tercerizado=False):
        m = RANGO_RE.match(p.nombre)
        if m:
            familias.setdefault(
                (m.group(1).strip(), p.categoria_id), []).append(p)
    if not familias:
        return None
    # La familia con más escalones; a igualdad, la primera alfabéticamente,
    # para que el manual muestre siempre lo mismo entre recargas.
    nombre_base, categoria_id = sorted(
        familias, key=lambda k: (-len(familias[k]), k[0].lower()))[0]
    tiers = _tiers(nombre_base, categoria_id)
    if len(tiers) < 2:
        return None

    filas = []
    for t in tiers:
        p = t['producto']
        filas.append({
            'producto': p,
            'desde': t['desde'],
            'hasta': t['hasta'],
            'factor': p.factor,
            # Lo que termina cobrándose por unidad de cálculo en ese escalón.
            # Es la cuenta del método actual sin la hora de mano de obra, que
            # es fija por trabajo y no cambia entre escalones.
            'precio_unidad': p.precio * p.factor,
        })
    return {'nombre': nombre_base, 'filas': filas,
            'unidad': _unidad_de(tiers[0]['producto'])}


def _unidad_de(producto):
    """Qué cuenta el rango de la familia. Los rangos del cotizador se resuelven
    contra el resultado del gráfico, que en papeles son hojas."""
    comp = producto.componenteproducto_set.select_related('insumo').first()
    if comp and comp.insumo.unidad_composicion:
        return comp.insumo.unidad_composicion
    return 'unidad'



def tiempos_cargados():
    """Resumen de los tiempos de producción que hay cargados hoy.

    Sirve al capítulo de productos para hablar de los tiempos *reales* de esta
    base y no en abstracto: cuántos productos comparten exactamente el mismo
    par (setup, unitario) delata que son estimaciones sembradas de arranque y
    no medidas, que es justo lo que el capítulo tiene que explicar.
    """
    from collections import Counter
    from productos.models import Producto
    cuenta = Counter()
    con_tiempos = 0
    for p in Producto.objects.filter(activo=True):
        if p.tiempo_setup or p.tiempo_unitario:
            con_tiempos += 1
            cuenta[(p.tiempo_setup, p.tiempo_unitario)] += 1
    if not con_tiempos:
        return None
    combinaciones = [
        {'setup': s, 'unitario': u, 'productos': n}
        for (s, u), n in cuenta.most_common(5)
    ]
    return {
        'con_tiempos': con_tiempos,
        'total': Producto.objects.filter(activo=True).count(),
        'combinaciones': combinaciones,
        'distintas': len(cuenta),
    }


def costo_unidad_uso(insumo):
    """Lo que cuesta UNA unidad de uso: precio ÷ factor de conversión.

    Es la misma cuenta que hace el recálculo de precios de productos
    (``_recalcular_precios_productos_con_insumo`` en productos/views.py). Se
    calcula acá y no en el template porque ``widthratio`` redondea a entero y
    en insumos baratos (una hoja, un cm²) el redondeo se come el número.
    """
    if not insumo or not insumo.factor_conversion:
        return None
    return insumo.precio / Decimal(insumo.factor_conversion)


def contexto_manual():
    """Todo junto, para el capítulo, el índice y el PDF."""
    insumo = insumo_ejemplo()
    return {
        'par': parametros(),
        'insumo': insumo,
        'insumo_costo_uso': costo_unidad_uso(insumo),
        'familia': familia_ejemplo(),
        'tiempos': tiempos_cargados(),
        'cotizaciones': cotizaciones_ejemplo(),
    }


# Claves de ayuda usadas en un template: {% ayuda 'clave' %} / {% ayuda "clave" %}
_AYUDA_RE = re.compile(r"""\{%\s*ayuda\s+['"]([\w.]+)['"]""")

# Título legible de cada concepto para el glosario impreso. Sólo el RÓTULO: el
# texto sigue saliendo de core.glosario, que es la fuente única. Vive acá y no
# ahí porque es una necesidad del PDF (las claves son slugs sin acentos y en
# pantalla nunca se muestran). Lo que no esté acá cae al slug con espacios.
_TITULOS = {
    'tasa_hora': 'Tasa por hora',
    'ratio_productivas': 'Ratio de horas productivas',
    'precio_actual': 'Precio actual',
    'precio_sugerido': 'Precio sugerido',
    'piso_absoluto': 'Piso absoluto',
    'piso_absorcion': 'Piso de absorción',
    'diferencia_metodos': 'Diferencia entre los dos métodos',
    'tiempo_produccion': 'Tiempo de producción',
    'contribucion_por_hora': 'Contribución por hora',
    'punto_equilibrio': 'Punto de equilibrio',
}


def glosario_del_manual(capitulos):
    """Los conceptos que el manual usa, con su definición, en orden de aparición.

    El PDF no tiene tooltips: los botones "(i)" no se pueden tocar en papel. En
    vez de perder esa información, se junta acá y el PDF la imprime como
    glosario al final. Los textos siguen saliendo de ``core.glosario``, que es
    la fuente única; esto sólo decide cuáles entran y en qué orden.
    """
    from django.template import TemplateDoesNotExist
    from django.template.loader import get_template

    from core.glosario import GLOSARIO

    vistas, salida = set(), []
    for cap in capitulos:
        # Un capítulo pendiente no tiene template: se saltea en vez de explotar,
        # para que listar lo que falta nunca pueda romper el PDF.
        try:
            origen = get_template(cap.template).origin.name
        except TemplateDoesNotExist:
            continue
        try:
            with open(origen, encoding='utf-8') as f:
                fuente = f.read()
        except OSError:
            continue
        for clave in _AYUDA_RE.findall(fuente):
            if clave in vistas or clave not in GLOSARIO:
                continue
            vistas.add(clave)
            salida.append({
                'clave': clave,
                'titulo': _TITULOS.get(
                    clave, clave.replace('_', ' ').capitalize()),
                'texto': GLOSARIO[clave],
            })
    return salida


def _fila_cotizacion(pc):
    """Una cotización real descompuesta como la explica el capítulo del tablero."""
    estructura = pc.piso_absorcion - pc.piso_absoluto   # = tiempo × tasa del día
    return {
        'nombre': pc.producto_final or pc.insumo.nombre,
        'producto': pc.insumo.nombre,
        'horas': pc.t_produccion,
        'material': pc.piso_absoluto,
        'estructura': estructura,
        'piso_absorcion': pc.piso_absorcion,
        'cobrado': pc.resultado,
        'contribucion': pc.contribucion,
        'contribucion_por_hora': pc.contribucion_por_hora,
        'tasa_del_dia': pc.tasa_hora_snap,
        'paga_su_parte': pc.resultado >= pc.piso_absorcion,
    }


def cotizaciones_ejemplo():
    """Cotizaciones reales para los ejemplos del capítulo del tablero.

    Sólo las que tienen la estructura de costos (``piso_absorcion > 0``): las
    anteriores no guardaron los snapshots y su "contribución" sería el precio
    entero, que es justo el malentendido que el capítulo quiere evitar.

    Devuelve el caso para el paso a paso, el mejor y el peor por contribución
    por hora, y —si existe— uno cobrado por debajo de su piso de absorción, que
    es el ejemplo que más enseña.
    """
    from productos.models import ProductoCotizado
    items = [
        pc for pc in ProductoCotizado.objects
        .filter(piso_absorcion__gt=0, t_produccion__gt=0)
        .select_related('insumo')
        if pc.contribucion_por_hora is not None
    ]
    if not items:
        return None

    por_hora = sorted(items, key=lambda pc: pc.contribucion_por_hora)
    bajo_piso = [pc for pc in items if pc.resultado < pc.piso_absorcion]
    return {
        # El más reciente: el paso a paso conviene hacerlo sobre algo que la
        # persona pueda ir a mirar en el presupuesto.
        'caso': _fila_cotizacion(max(items, key=lambda pc: pc.id)),
        'mejor': _fila_cotizacion(por_hora[-1]),
        'peor': _fila_cotizacion(por_hora[0]),
        'bajo_piso': _fila_cotizacion(bajo_piso[0]) if bajo_piso else None,
        'total': len(items),
    }
