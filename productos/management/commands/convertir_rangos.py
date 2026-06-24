import re
from django.core.management.base import BaseCommand
from productos.models import Producto

# ---------------------------------------------------------------------------
# Patrones viejos a detectar (orden importa: mas especificos primero)
# ---------------------------------------------------------------------------

_PATRONES = [
    # "(301 o 500)"  ->  [301-500]
    (re.compile(r'^(.*?)\s*\(\s*(\d+)\s+o\s+(\d+)\s*\)\s*$', re.IGNORECASE),
     lambda m: (m.group(1).strip(), m.group(2), m.group(3))),

    # "(501-inf)" o "(501-INF)"  ->  [501-INF]
    (re.compile(r'^(.*?)\s*\(\s*(\d+)\s*-\s*inf\s*\)\s*$', re.IGNORECASE),
     lambda m: (m.group(1).strip(), m.group(2), 'INF')),

    # "(301+)"  ->  [301-INF]
    (re.compile(r'^(.*?)\s*\(\s*(\d+)\s*\+\s*\)\s*$'),
     lambda m: (m.group(1).strip(), m.group(2), 'INF')),

    # "(1-5)" o "(301 - 500)"  ->  [1-5]
    (re.compile(r'^(.*?)\s*\(\s*(\d+)\s*-\s*(\d+)\s*\)\s*$'),
     lambda m: (m.group(1).strip(), m.group(2), m.group(3))),

    # "nombre - 301+"  ->  nombre [301-INF]
    (re.compile(r'^(.*?)\s+-\s+(\d+)\+\s*$'),
     lambda m: (m.group(1).strip(), m.group(2), 'INF')),

    # "nombre - 1-5" o "nombre - 31-100"  ->  nombre [1-5]
    (re.compile(r'^(.*?)\s+-\s+(\d+)-(\d+)\s*$'),
     lambda m: (m.group(1).strip(), m.group(2), m.group(3))),

    # "nombre - 501-inf"  ->  nombre [501-INF]
    (re.compile(r'^(.*?)\s+-\s+(\d+)-inf\s*$', re.IGNORECASE),
     lambda m: (m.group(1).strip(), m.group(2), 'INF')),
]

_NUEVO_FORMATO = re.compile(r'^(.*?)\s*\[(\d+)[-](\d+|INF)\]\s*$')


def detectar_y_convertir(nombre):
    """
    Detecta un rango en el nombre usando los patrones conocidos
    y devuelve el nombre normalizado al formato [N-M].
    Devuelve None si el nombre ya esta en el nuevo formato o no tiene rango.
    """
    if _NUEVO_FORMATO.match(nombre):
        return None  # ya esta en el formato correcto

    for patron, extractor in _PATRONES:
        m = patron.match(nombre)
        if m:
            base, rango_min, rango_max = extractor(m)
            return f"{base} [{rango_min}-{rango_max}]"

    return None  # no se reconocio ningun rango


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        'Convierte nombres de productos con rangos en formatos viejos '
        'al nuevo formato estandar [N-M]. '
        'Usar --dry-run para previsualizar sin aplicar cambios.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra los cambios sin aplicarlos a la base de datos.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        productos = Producto.objects.all().order_by('nombre')
        cambios = []
        sin_rango = []

        for prod in productos:
            nuevo_nombre = detectar_y_convertir(prod.nombre)
            if nuevo_nombre:
                cambios.append((prod, nuevo_nombre))
            elif not _NUEVO_FORMATO.match(prod.nombre):
                sin_rango.append(prod.nombre)

        # --- Resumen ---
        self.stdout.write(f'\nTotal de productos : {productos.count()}')
        self.stdout.write(f'Con rango a convertir: {len(cambios)}')
        self.stdout.write(f'Sin rango detectado  : {len(sin_rango)}')

        if not cambios:
            self.stdout.write(self.style.SUCCESS('\nNo hay nada que convertir.'))
            return

        # --- Preview de cambios ---
        self.stdout.write('\n' + '=' * 72)
        self.stdout.write('CAMBIOS PROPUESTOS')
        self.stdout.write('=' * 72)

        for prod, nuevo in cambios:
            self.stdout.write(f'\n  ANTES  : {prod.nombre}')
            self.stdout.write(f'  DESPUES: {nuevo}')

        # --- Nombres sin rango detectado (informativo) ---
        if sin_rango:
            self.stdout.write('\n' + '-' * 72)
            self.stdout.write(f'Productos sin rango detectado ({len(sin_rango)}) - no se tocan:')
            for nombre in sin_rango[:20]:
                self.stdout.write(f'  - {nombre}')
            if len(sin_rango) > 20:
                self.stdout.write(f'  ... y {len(sin_rango) - 20} mas.')

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] {len(cambios)} cambios pendientes. '
                    'Correr sin --dry-run para aplicarlos.'
                )
            )
            return

        # --- Confirmacion antes de aplicar ---
        self.stdout.write('')
        confirmacion = input(f'Aplicar {len(cambios)} cambios? [s/N]: ').strip().lower()
        if confirmacion != 's':
            self.stdout.write(self.style.WARNING('Operacion cancelada.'))
            return

        for prod, nuevo in cambios:
            prod.nombre = nuevo
            prod.save(update_fields=['nombre'])

        self.stdout.write(
            self.style.SUCCESS(f'\n{len(cambios)} productos actualizados correctamente.')
        )
