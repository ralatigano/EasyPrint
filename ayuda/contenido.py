"""Índice del manual: la lista de capítulos y su orden.

Cada capítulo **redactado** es un template en
``core/templates/ayuda/capitulos/<slug>.html``. Esta lista es la **fuente
única** del orden, los títulos y la navegación (índice, anterior/siguiente y el
PDF completo), así que agregar un capítulo es agregar una entrada acá y su
template, nada más.

Un capítulo puede estar ``pendiente``: aparece en el índice con su título y su
resumen, pero sin link y sin template. Sirve para que se vea qué falta y en qué
orden va, sin prometer una página que no existe. Los pendientes no entran al
PDF y la navegación anterior/siguiente los saltea.

Un capítulo puede además pedir un ``permiso`` de ``core.roles.PERMISOS``. El
del dashboard lo pide porque explica el tablero con los números reales de la
imprenta —costo fijo, tasa por hora, lo que se cobró en cada trabajo— y el
tablero mismo es sólo de Gerencia: no tiene sentido que el manual cuente lo que
la pantalla no deja ver. Un capítulo restringido se comporta, para quien no
tiene el permiso, como si no existiera: no sale en el índice, ni en la barra
lateral, ni en el PDF, y su URL cae en el índice con 404.

Hay tests que recorren la lista: fallan si a un capítulo redactado le falta el
template, si uno pendiente tiene uno (sería señal de que alguien lo escribió y
se olvidó de marcarlo), y si un ``permiso`` no existe en ``PERMISOS``.
"""

LISTO = 'listo'
PENDIENTE = 'pendiente'


class Capitulo:
    def __init__(self, slug, titulo, resumen, icono, estado=LISTO,
                 permiso=None):
        self.slug = slug
        self.titulo = titulo
        self.resumen = resumen
        self.icono = icono
        self.estado = estado
        self.permiso = permiso

    @property
    def pendiente(self):
        return self.estado == PENDIENTE

    @property
    def template(self):
        return f'ayuda/capitulos/{self.slug}.html'

    def visible_para(self, user):
        if self.permiso is None:
            return True
        from core.roles import tiene_permiso
        return tiene_permiso(user, self.permiso)


CAPITULOS = [
    Capitulo(
        slug='introduccion',
        titulo='Cómo funciona el cotizador',
        resumen='El recorrido completo, de un insumo a un pedido cobrado, y en '
                'qué orden se carga cada cosa.',
        icono='fa-solid fa-diagram-project',
    ),
    Capitulo(
        slug='insumos',
        titulo='Insumos: lo que se compra',
        resumen='Unidad de compra y unidad de uso, el factor de conversión, el '
                'precio y el stock. Es donde más se confunde la gente.',
        icono='fa-solid fa-boxes-stacked',
    ),
    Capitulo(
        slug='productos',
        titulo='Productos: lo que se cotiza',
        resumen='Los cuatro tipos de cálculo, la receta de insumos, qué es el '
                'factor y cómo se miden los tiempos.',
        icono='fa-solid fa-tags',
    ),
    Capitulo(
        slug='cotizar',
        titulo='Cotizar un trabajo',
        resumen='De dónde sale cada número del presupuesto y cómo se lee la '
                'comparación entre los dos precios.',
        icono='fa-solid fa-calculator',
    ),
    Capitulo(
        slug='pedidos',
        titulo='Pedidos, stock y faltantes',
        resumen='Qué dispara cada cambio de estado, cuándo se descuenta el '
                'material y cómo se cubren los faltantes.',
        icono='fa-solid fa-clipboard-list',
        estado=PENDIENTE,
    ),
    Capitulo(
        slug='caja',
        titulo='Caja y facturación',
        resumen='Señas, pagos y devoluciones; cuándo y cómo se emite la '
                'factura electrónica.',
        icono='fa-solid fa-cash-register',
        estado=PENDIENTE,
    ),
    Capitulo(
        slug='tercerizados',
        titulo='Pedidos tercerizados',
        resumen='Lo que se le encarga a un proveedor externo y la deuda de '
                'cuenta corriente.',
        icono='fa-solid fa-truck-ramp-box',
        estado=PENDIENTE,
    ),
    Capitulo(
        slug='dashboard',
        titulo='Entender el dashboard',
        resumen='De dónde salen el piso de absorción, el punto de equilibrio y '
                'la contribución por hora, con ejemplos. Por qué el tablero '
                'habla de horas y no de plata.',
        icono='fa-solid fa-chart-line',
        # Mismo permiso que el tablero: muestra la estructura de costos y los
        # precios cobrados de cotizaciones reales.
        permiso='dashboard',
    ),
    Capitulo(
        slug='recetario',
        titulo='Recetario',
        resumen='«Quiero agregar un producto nuevo», «me subió el papel», «un '
                'trabajo salió más caro de lo cotizado».',
        icono='fa-solid fa-book',
        estado=PENDIENTE,
    ),
]

CAPITULOS_POR_SLUG = {c.slug: c for c in CAPITULOS if not c.pendiente}

# El número de capítulo se fija acá, por posición en la lista completa, y NO se
# saca del `forloop.counter` del template: si no, un capítulo oculto por
# permisos correría la numeración y "el capítulo 8" sería distinto según quién
# mire. El número es el mismo para todos; lo que cambia es qué se ve.
for _i, _c in enumerate(CAPITULOS, start=1):
    _c.numero = _i


def para_usuario(user):
    """La lista completa que ve ese usuario, pendientes incluidos.

    Es lo que se dibuja en el índice y en la barra lateral.
    """
    return [c for c in CAPITULOS if c.visible_para(user)]


def publicados(user=None):
    """Los capítulos que tienen página: índice del PDF y navegación.

    Sin ``user`` devuelve todos los redactados (se usa en los tests y en las
    comprobaciones del contenido); con ``user``, sólo los que puede ver.
    """
    return [c for c in CAPITULOS
            if not c.pendiente and (user is None or c.visible_para(user))]


def buscar(slug, user):
    """El capítulo de ese slug si el usuario puede verlo, o ``None``.

    Un capítulo restringido devuelve ``None`` igual que un slug inexistente: la
    vista no distingue los dos casos a propósito, para no avisar de que existe
    un capítulo que no se puede abrir.
    """
    cap = CAPITULOS_POR_SLUG.get(slug)
    if cap is None or not cap.visible_para(user):
        return None
    return cap


def vecinos(slug, user=None):
    """(anterior, siguiente) de un capítulo, salteando los pendientes.

    Se saltean a propósito: el botón «Siguiente» tiene que llevar a algo que se
    pueda leer, no a un capítulo que todavía no existe. Lo mismo vale para un
    capítulo que ese usuario no puede ver.
    """
    disponibles = publicados(user)
    slugs = [c.slug for c in disponibles]
    if slug not in slugs:
        return None, None
    i = slugs.index(slug)
    return (disponibles[i - 1] if i > 0 else None,
            disponibles[i + 1] if i < len(disponibles) - 1 else None)
