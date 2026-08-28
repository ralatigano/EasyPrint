# Plan de implementación — Estructura de costos fijos y tasa horaria

> Documento de especificación para implementar por fases. Leer **entero** antes de
> escribir código. Las fases son secuenciales: no empezar una hasta que la anterior
> esté andando y probada en la UI.

---

## 1. Contexto y problema

Hoy el cotizador calcula el precio así (`presupuestos/views.py::calcular_cotizacion_final`):

```
cantidad_producto = cantidad              # tipo D
                  | resultado_grafico     # A: hojas, B: m², C: metros lineales

subtotal      = cantidad_producto * precio_producto * margen
total_bruto   = subtotal + (tiempo * precio_hora) + precio_empaquetado
resultado     = total_bruto * (1 - descuento/100)
```

Donde `precio_hora` sale de un producto fantasma (`Producto.objects.get(nombre="Mano de obra").precio_proveedor`)
y es **un valor arbitrario**: nadie sabe de dónde salió ni si cubre los costos fijos del negocio.

El objetivo es reemplazar ese número arbitrario por una **tasa derivada de la estructura
de costos fijos reales** del negocio y de la capacidad productiva disponible:

```
tasa_hora = costos_fijos_mensuales / horas_productivas_mensuales
```

Y, sobre esa base, dar tres cosas que hoy no existen:

1. Un **piso de precio defendible** por trabajo (con dos umbrales, ver Fase 4).
2. Un **panel de absorción**: si vendemos menos horas de las que asumimos al calcular
   la tasa, no cubrimos los costos fijos, y eso hoy es invisible porque cada cotización
   individual parece rentable.
3. Un **control de fechas de entrega** contra capacidad real (Fase 6).

### Por qué importa la ocupación

La tasa es un pronóstico disfrazado de dato: calcular `$4.000/h` equivale a afirmar
"vamos a vender 250 horas este mes". El denominador **no** son las horas disponibles
sino las horas productivas: `horas_disponibles × ratio_productivas`. Si se divide por
las disponibles, la tasa queda sistemáticamente baja y los costos fijos no se recuperan.

---

## 2. Decisiones ya tomadas — NO re-litigar

Estas decisiones se discutieron y están cerradas. Implementarlas como están:

| # | Decisión | Motivo |
|---|---|---|
| D1 | **El precio que se cobra sigue saliendo de la fórmula actual.** El método nuevo se calcula, se muestra al lado y se guarda, pero no se cobra. | Cero riesgo de mover precios sin evidencia. En 2-3 meses se decide con datos reales guardados en la DB. |
| D2 | **Los tiers `[N-M]` no se tocan.** | Fueron armados por la dueña como ajuste de "precio mayorista" sobre el material. No tienen relación con tiempo de trabajo, así que no hay solapamiento con el setup. |
| D3 | **El tiempo es el mismo para ambos métodos; lo que cambia es la tasa.** Un solo campo de horas, dos tasas, dos precios. | Si cada método usara su propio tiempo, la comparación no diría nada. |
| D4 | **Se agregan `tiempo_setup` y `tiempo_unitario` a `Producto`**, sembrados por categoría. | Es lo que hace que el tiempo deje de ser `1` por default. Nadie estima bien con el cliente esperando: el tiempo tiene que venir precargado. |
| D5 | **Medición de horas: solo "Nivel 0"** (factor de corrección global + panel). NO implementar registro de tiempos por pedido ni cronómetros. | Los empleados no tienen el hábito de registrar. Un sesgo global se corrige con un multiplicador global. |
| D6 | **No migrar datos históricos de `t_produccion`.** | Están todos en el valor por default (`1`) y truncados por el tipo de campo. No sirven como referencia. La calibración arranca de cero. |
| D7 | **El control de fechas de entrega (Fase 6) va último**, cuando el resto ya esté andando. | Suma superficie a un cambio que ya es grande. |
| D8 | **La tasa se define sobre horas-persona, no horas-máquina.** | Los empleados multitasquean entre máquinas (mientras la estampadora calienta, diseñan otro trabajo). El recurso escaso es la persona. |

---

## 3. Convenciones del proyecto que aplican acá

Leer `CLAUDE.md` antes de empezar. Lo crítico para este trabajo:

- **Formato de números argentino.** Punto = miles, coma = decimales. **Todo valor
  monetario que venga de un `request.POST` debe pasar por `parse_ar`**, nunca por
  `float()` / `Decimal()` directo. En el front, `formatearNumeroLocal` /
  `parsearNumeroLocal` de `core/static/core/js/core.js`.
  Esto aplica sí o sí a los montos de `CostoFijo` y a los parámetros de producción.
- **Permisos**: `@solo_gerencia` de `core/decorators.py` para toda la sección de
  configuración de costos.
- **Patrón de configuración existente**: mirar `AliasPago` (ABM de líneas) y
  `ConfiguracionPresupuesto` (singleton con `load()`) en `core/models.py`, más
  `configuracion_pagos` en `core/views.py`, sus rutas en `core/urls.py` y el template
  `core/templates/core/configuracion_pagos.html`. **Copiar ese patrón**, no inventar uno nuevo.
- **Tests**: agregar tests de regresión en `core/tests.py` (o el `tests.py` de la app
  correspondiente) para cada cálculo nuevo. La suite corre con
  `../env/Scripts/python.exe manage.py test`.

---

## FASE 0 — Arreglos previos

Nada de lo que sigue funciona bien sin esto. Es una fase corta y aislada: hacerla,
correr los tests, commitear, y recién ahí seguir.

### 0.1 `t_produccion` está mal tipado

En `productos/models.py`:

```python
# Tiempo estimado de producción en minutos
t_produccion = models.IntegerField(default=0)
```

El comentario **miente**: el formulario (`inicio.html`, `inputTiempo`) manda **horas**,
y `calcular_cotizacion_final` las usa como horas. Además `IntegerField` **trunca**:
1,5 horas se guarda como 1.

Cambiar a:

```python
# Tiempo estimado de producción, en HORAS
t_produccion = models.DecimalField(max_digits=8, decimal_places=2, default=0)
```

Migración simple, sin data migration (ver D6).

### 0.2 El input no acepta fracciones de hora

En `core/templates/presupuestos/inicio.html`:

```html
<input type="number" id="inputTiempo" class="form-control" min="1" value="1">
```

`min="1"` impide cotizar media hora. Cambiar a `min="0"` y `step="0.25"`.
El `value="1"` fijo se elimina en la Fase 2 (pasa a precargarse desde el producto).

### 0.3 `updated` nunca se actualiza

En `pedidos/models.py`, `presupuestos/models.py` y `productos/models.py` (modelo `Categoria`):

```python
updated = models.DateTimeField(auto_now_add=True)   # ← bug: es la fecha de creación con otro nombre
```

Cambiar a `auto_now=True`.

> **Importante**: esto empieza a registrar cuándo cambian de estado los pedidos.
> **No calcular nada con ese dato todavía** — los empleados no marcan los estados con
> rigurosidad, así que hay que dejar que junte historia varios meses antes de confiar
> en él. No construir gráficos sobre esto en esta tanda.

### 0.4 `precio_arb` borra el tiempo

En `presupuestos/views.py::editar_producto_cotizado`, la rama de precio arbitrario hace
`producto.t_produccion = 0`. Un ítem con precio manual desaparece de la contabilidad de
horas aunque haya ocupado el taller igual. **Quitar esa línea**: el precio y el tiempo son
cosas independientes.

### 0.5 Código muerto — borrar

Estas funciones referencian campos que ya no existen en los modelos (`codigo`, `cant_area`,
`resultado` en `Producto`) y no están ruteadas. Si quedan, es cuestión de tiempo que alguien
edite la fórmula equivocada:

- `presupuestos/views.py::edit_producto_cotizado` (línea ~383). **Ojo**: no confundir con
  `editar_producto_cotizado`, que sí está ruteada y sí se usa. Sacarla también del import
  en `presupuestos/urls.py` si estuviera.
- `presupuestos/functions.py::obtener_datos` y `::calc_precio`.
- `core/functions.py::obtener_datos` y `::calc_precio` (duplicadas).

Verificar con grep que no queden referencias antes de borrar.

---

## FASE 1 — Configuración: estructura de costos

Sección nueva en Configuración, **solo Gerencia**, siguiendo el patrón de
`configuracion_pagos`.

### 1.1 Modelos nuevos en `core/models.py`

```python
class CostoFijo(models.Model):
    """Una línea de la estructura de costos fijos del negocio.
    Se administra desde Configuración → Estructura de costos (solo Gerencia)."""

    PERIODICIDADES = [
        ('mensual', 'Mensual'),
        ('anual', 'Anual'),
        ('unico', 'Único / amortizable'),
    ]

    concepto = models.CharField(max_length=120)
    grupo = models.CharField(
        max_length=60, blank=True,
        help_text="Agrupador para lectura, ej: 'Ocupación', 'Sueldos', 'Impuestos', 'Servicios'.")
    monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    periodicidad = models.CharField(max_length=10, choices=PERIODICIDADES, default='mensual')
    meses_amortizacion = models.PositiveIntegerField(
        default=12,
        help_text="Solo aplica si la periodicidad es 'Único'. En cuántos meses se reparte.")
    activo = models.BooleanField(default=True)
    vigencia_desde = models.DateField(default=timezone.localdate)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    @property
    def monto_mensual(self):
        """Normaliza cualquier periodicidad a un monto mensual."""
        if self.periodicidad == 'anual':
            return self.monto / 12
        if self.periodicidad == 'unico':
            return self.monto / max(self.meses_amortizacion, 1)
        return self.monto
```

```python
class ParametrosProduccion(models.Model):
    """Singleton con la capacidad productiva declarada. Ver load()."""

    operarios = models.PositiveIntegerField(
        default=1, help_text="Personas que producen (no incluye administración).")
    horas_dia = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    dias_mes = models.PositiveIntegerField(default=22)

    ratio_productivas = models.DecimalField(
        max_digits=4, decimal_places=3, default=Decimal("0.700"),
        help_text="Proporción de las horas disponibles que se dedican efectivamente a "
                  "producir (el resto es atención, compras, limpieza, tiempo muerto). "
                  "Entre 0 y 1. Ajustar cada trimestre con datos reales.")

    factor_correccion_tiempos = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("1.00"),
        help_text="Multiplicador global sobre los tiempos estimados de cada producto. "
                  "Arranca en 1,00. Si el total de horas vendidas del mes es "
                  "sistemáticamente menor a las horas realmente trabajadas, subirlo.")

    vigencia_desde = models.DateField(default=timezone.localdate)
    updated = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

### 1.2 Servicio de cálculo — `core/costos.py` (archivo nuevo)

Centralizar acá el cálculo para que no quede desparramado en las vistas:

```python
def costo_fijo_mensual() -> Decimal:
    """Suma de todas las líneas activas, normalizadas a mensual."""

def horas_disponibles_mes() -> Decimal:
    """operarios * horas_dia * dias_mes"""

def horas_productivas_mes() -> Decimal:
    """horas_disponibles_mes() * ratio_productivas"""

def tasa_hora() -> Decimal:
    """costo_fijo_mensual() / horas_productivas_mes().
    Devuelve Decimal('0') si horas_productivas_mes() es 0 (no explotar)."""
```

Redondear la tasa a 2 decimales solo para mostrar; en los cálculos usar el `Decimal` completo.

### 1.3 Vistas, rutas y template

- `core/views.py`: `configuracion_costos` (GET + POST), `guardar_costo_fijo`,
  `borrar_costo_fijo`, `guardar_parametros_produccion`. Todas con `@login_required`
  y `@solo_gerencia`.
- `core/urls.py`: rutas bajo `configuracion/costos...`, en línea con
  `configuracion/pagos`.
- `core/templates/core/configuracion_costos.html`, modelado sobre
  `configuracion_pagos.html`.
- Agregar la entrada al menú de Configuración en `core/templates/core/partials/navbar.html`.

### 1.4 Requisitos de UX de esta pantalla

Van a cargar **~20 líneas de costos**. La pantalla tiene que ser cómoda o no la usan:

- ABM de líneas con alta inline (no un modal por línea).
- Agrupación visual por el campo `grupo`, con subtotal por grupo.
- **La tasa se recalcula en vivo** a medida que cargan/editan, en un panel fijo arriba
  o al costado, mostrando: costo fijo mensual, horas disponibles, horas productivas y
  **tasa por hora resultante**, bien grande. Ese feedback inmediato es lo que convierte
  la pantalla de trámite en herramienta.
- El `ratio_productivas` debe ser editable ahí mismo y ver el efecto sobre la tasa al toque.
- Montos con `formatearNumeroLocal` al mostrar y `parse_ar` al guardar.

---

## FASE 2 — Tiempos por producto

### 2.1 Campos nuevos en `Producto` (`productos/models.py`)

```python
tiempo_setup = models.DecimalField(
    max_digits=6, decimal_places=2, default=0,
    help_text="Horas de preparación por trabajo, independientes de la cantidad "
              "(armar el archivo, calibrar, arranque, primera prueba).")

tiempo_unitario = models.DecimalField(
    max_digits=8, decimal_places=4, default=0,
    help_text="Horas por unidad producida. La unidad es la misma que la del precio "
              "del producto: por hoja (tipo A), por m² (tipo B), por metro lineal "
              "(tipo C) o por unidad (tipo D).")
```

> **Atención a la unidad de `tiempo_unitario`.** Se aplica sobre `cantidad_producto`,
> que es la magnitud a la que ya convergen los cuatro tipos de cálculo — la misma que
> multiplica al precio del insumo. No sobre `cantidad` (elementos).

### 2.2 Fórmula del tiempo

```
tiempo_estimado = (tiempo_setup + tiempo_unitario * cantidad_producto) * factor_correccion_tiempos
```

### 2.3 Limitación conocida (documentarla, no resolverla ahora)

Los acabados que escalan con la cantidad de **elementos** y no con la de hojas/m²
(cortar 500 stickers de 3 pliegos vs. cortar 50) quedan mal modelados: se los absorbe
aproximando dentro de `tiempo_unitario`.

Si en la práctica resulta insuficiente, la salida es agregar un tercer campo
`tiempo_por_elemento` aplicado sobre `cantidad`, **solo para los tipos A/B/C** (en el
tipo D `cantidad_producto == cantidad` y se contaría dos veces). No hacerlo ahora.

### 2.4 UI de carga

- Los dos campos van en el modal de alta/edición de producto (`productos.html` +
  `Products.js`), en una sección "Tiempos de producción".
- Incluirlos en el import/export Excel de productos (`importar_productos_excel` /
  `exportar_productos_excel`) — es la vía práctica para sembrar el catálogo entero.
- **Siembra por categoría**: un comando de management
  (`productos/management/commands/sembrar_tiempos.py`) que reciba categoría, setup y
  unitario y los aplique en lote a los productos de esa categoría. La dueña estima una
  vez por categoría y después refina los casos que se desvían.

### 2.5 Precarga en el cotizador

En `cotizacion.js`, cuando se selecciona el producto y hay una cantidad calculada,
pedir los tiempos al backend y **precargar `inputTiempo`** con el resultado de la
fórmula de 2.2. El campo sigue siendo editable — el valor precargado es una sugerencia,
no una imposición.

Extender el endpoint `productos/obtener_producto` (o crear uno nuevo) para devolver
`tiempo_setup` y `tiempo_unitario`.

> **Advertir a la dueña antes de sembrar los tiempos**: el tiempo ya es un input de la
> fórmula actual, así que cargar tiempos reales **mueve los precios de hoy**, incluso
> sin cambiar ninguna fórmula. Si el promedio pasa de 1 h a 2,5 h, el precio sube
> 1,5 × `precio_hora`.
>
> Truco para una transición neutral: el mismo día que se cargan los tiempos, dividir el
> valor de "Mano de obra" por el factor promedio de aumento del tiempo. Los precios
> quedan donde estaban, pero la estructura pasa a ser honesta, y a partir de ahí se
> ajusta a propósito y no por accidente.

---

## FASE 3 — Doble cálculo y snapshot

El corazón del cambio. Todo pasa por `presupuestos/views.py::calcular_cotizacion_final`.

### 3.1 Las dos fórmulas

```python
# ---- Método actual (ES EL QUE SE COBRA) ----
subtotal_actual = cantidad_producto * precio_producto * margen
precio_actual   = subtotal_actual + (tiempo_estimado * precio_hora_legacy) + precio_empaquetado

# ---- Método nuevo (sugerido; NO se cobra en esta etapa) ----
costo_variable  = (cantidad_producto * precio_producto) + costo_empaquetado
costo_total     = costo_variable + (tiempo_estimado * tasa_hora)
precio_sugerido = costo_total * margen

# ---- Los dos pisos ----
piso_absoluto  = costo_variable   # por debajo se pierde plata en el trabajo, siempre
piso_absorcion = costo_total      # por debajo no se paga la parte de estructura
```

Donde:
- `precio_hora_legacy` = `Producto.objects.get(nombre="Mano de obra").precio_proveedor`
  (lo de hoy, sin cambios).
- `tasa_hora` = `core.costos.tasa_hora()`.
- `margen` = `producto.factor` — **el mismo en ambos métodos**, para que sean comparables.
- `tiempo_estimado` = **el mismo en ambos métodos** (D3).

**Diferencia conceptual clave**: en el método actual el margen multiplica **solo los
insumos** y el tiempo se suma al costo, o sea que la hora se vende exactamente al costo.
En el método nuevo el margen multiplica el **costo total**, con lo que cada hora aporta
como mínimo `tasa_hora × (margen - 1)` sin importar qué producto sea. Eso es lo que
convierte el riesgo de mezcla de productos en un piso garantizado.

**Supuesto sobre el empaquetado**: se asume que el precio del empaquetado es su costo
(margen 1). Es una simplificación; dejarla comentada en el código.

### 3.2 Campos nuevos en `ProductoCotizado` (`productos/models.py`)

Sin esto no se puede reconstruir nada después, ni comparar métodos, ni evitar que
actualizar los costos reescriba la historia. Todos son **snapshots del momento de la
cotización** y no deben recalcularse nunca:

```python
costo_insumos_snap     = DecimalField(max_digits=12, decimal_places=2, default=0)
costo_empaquetado_snap = DecimalField(max_digits=10, decimal_places=2, default=0)
margen_snap            = DecimalField(max_digits=6,  decimal_places=2, default=1)
tasa_hora_snap         = DecimalField(max_digits=12, decimal_places=2, default=0)
precio_hora_legacy_snap= DecimalField(max_digits=12, decimal_places=2, default=0)

precio_sugerido        = DecimalField(max_digits=12, decimal_places=2, default=0)
piso_absoluto          = DecimalField(max_digits=12, decimal_places=2, default=0)
piso_absorcion         = DecimalField(max_digits=12, decimal_places=2, default=0)

precio_manual          = BooleanField(default=False)
```

Y una property útil para el panel:

```python
@property
def contribucion(self):
    """Precio efectivamente cobrado menos costo variable."""
    return self.resultado - self.piso_absoluto

@property
def contribucion_por_hora(self):
    return self.contribucion / self.t_produccion if self.t_produccion else None
```

Persistirlos en `agregar_producto`, leyéndolos de `request.session["cotizacion_previa"]`
(hay que agregarlos también al dict que guarda `calcular_cotizacion_final`).

### 3.3 UI del modal de resultado

`calcular_cotizacion_final` ya devuelve un JSON que alimenta un modal
(`mostrarModalResultado` en `cotizacion.js`). Agregar un bloque comparativo:

```
Precio (método actual)     $ XX.XXX        ← el que se cobra
Precio sugerido            $ YY.YYY        ← método nuevo, informativo
Diferencia                 +Z%
---
Costo variable (piso)      $ A.AAA
Costo con estructura       $ B.BBB
Tiempo estimado            N,NN h
```

Dejar claro visualmente cuál es el que se cobra, para que no se confunda.

---

## FASE 4 — Semáforo de precio

Al editar el precio de un producto cotizado
(`modal_editar_producto.html` + `editar_producto_cotizado.js`), colorear según el precio
final ingresado:

| Zona | Condición | Significado |
|---|---|---|
| 🟢 Verde | `precio >= precio_sugerido` | Cubre costos, estructura y margen objetivo. |
| 🟡 Amarillo | `piso_absorcion <= precio < precio_sugerido` | No se pierde plata en el trabajo, pero no se paga la parte de estructura. Razonable en un mes flojo; malo en uno cargado. |
| 🔴 Rojo | `precio < piso_absoluto` | Se pierde plata sí o sí, en cualquier mes. |

Reglas:

- **Nunca bloquear.** Siempre permitir guardar. Es una advertencia, no una validación.
- Mostrar en texto cuánto falta para el siguiente umbral.
- Si se guarda un precio distinto del calculado, setear `precio_manual = True`.
  Eso permite después reportar cuánto margen se resignó en el mes, que hoy no se sabe.
- Recordar: la Fase 0.4 ya sacó el borrado de `t_produccion` en precio arbitrario. El
  tiempo se conserva siempre.

### 4.1 Margen de descuento y aporte por unidad

Complemento del semáforo (misma pantalla, misma data de la Fase 3: no hay cálculo
nuevo de backend, es todo resta sobre los snapshots ya guardados). Mientras el vendedor
edita el precio/descuento de un ítem, mostrar cuánto puede bajar y cuánto sigue
aportando:

```
descuento aplicado   → precio resultante
aporte por unidad    = (precio - piso_absoluto) / cantidad     ← "cada unidad aporta $Y"
margen hasta absorción = precio - piso_absorcion  (en $ y en %)
margen hasta no perder = precio - piso_absoluto    (en $ y en %)
```

Reglas de diseño (importan tanto como el cálculo):

- **Es capacidad a pedido, no una sugerencia proactiva de descontar.** La info de
  headroom aparece **atada al descuento que el vendedor ya está ingresando** (o detrás
  de un "¿hasta cuánto puedo bajar?"), nunca como un empujón del sistema a descontar.
  El objetivo de toda la tasa es un precio defendible; si el sistema ofrece bajar hasta
  el piso, el piso se vuelve el precio. Mismo poder informativo, sin el sesgo a erosionar
  margen.
- **"Por unidad" es la unidad que compra el cliente** (`cantidad`, los elementos: 500
  stickers), no `cantidad_producto` (hojas/m²). Así "cada sticker aporta $Y" le habla al
  vendedor y al cliente.
- Es especialmente útil en cotizaciones grandes (donde hay más margen para negociar),
  pero la info sirve para cualquier tamaño; no hace falta gatearla por cantidad.

---

## FASE 5 — Panel de horas en el dashboard

Nueva sección en `dashboard/views.py` + `core/templates/dashboard/dashboard.html`.

### 5.1 Métricas del mes en curso

```
horas_objetivo        = core.costos.horas_productivas_mes()
horas_vendidas        = Σ t_produccion de ProductoCotizado de presupuestos convertidos en pedido en el mes
horas_cotizadas       = Σ t_produccion de ProductoCotizado de presupuestos creados en el mes
absorcion_recuperada  = horas_vendidas * tasa_hora
sub_absorcion         = absorcion_recuperada - costo_fijo_mensual
contribucion_mes      = Σ (resultado - piso_absoluto) de los ítems vendidos
contrib_prom_por_hora = contribucion_mes / horas_vendidas
punto_equilibrio_hs   = costo_fijo_mensual / contrib_prom_por_hora
conversion            = horas_vendidas / horas_cotizadas
```

> **Ojo con el join.** `Pedido.presupuesto` es un `IntegerField` que guarda el `numero`
> del presupuesto — **no** es una FK. `ProductoCotizado.presupuesto` sí es FK a
> `Presupuesto`. El cruce va por `presupuesto__numero__in=[...]`.

### 5.2 Qué mostrar

El número más grande y visible tiene que ser el **punto de equilibrio en horas**:

> "Necesitan vender **172 horas** de producción este mes para no perder plata. Van **94**."

Es una sola cifra, la entiende cualquiera, y convierte una discusión contable en una
meta operativa. Alrededor:

- Barra de progreso: horas vendidas vs. objetivo vs. punto de equilibrio.
- Absorción del mes en pesos (con el signo bien claro si es negativa).
- Conversión cotizadas → vendidas, como porcentaje. Es el indicador a vigilar si algún
  día se suben los precios: si la conversión se derrumba, el mercado está diciendo que
  la tasa no es cobrable.
- Ranking de productos por **contribución por hora** (no por margen porcentual). Un
  producto con 82% de margen que se hace en 15 minutos puede rendir mucho más por hora
  que uno con 90% que lleva 3 horas. Ese ranking es el criterio real para decidir qué
  empujar comercialmente.

### 5.3 Cómo se interpreta la sub-absorción (documentar en la UI con un tooltip)

La absorción es un mecanismo de fijación de precios, **no un flujo de fondos**: el
alquiler y los sueldos se pagan igual. Si un mes se absorbe menos, el faltante sale del
resultado del mes, no de una reserva.

Un mes con sub-absorción no es una alarma (hay estacionalidad). **Varios meses seguidos
son un diagnóstico**: o la tasa es muy baja, o los costos fijos son muy altos para el
volumen, o la capacidad declarada no se está vendiendo.

---

## FASE 6 — Control de fechas de entrega

**Última fase.** No empezarla hasta que las anteriores estén andando y probadas.

Al convertir un presupuesto en pedido y fijar `fecha_entrega`, verificar si hay tiempo
físico para producirlo dado todo lo ya comprometido.

### 6.1 Cálculo

```
capacidad_hasta(F) = dias_habiles(hoy, F) * horas_dia * operarios * ratio_productivas
carga_comprometida(F) = Σ t_produccion de ítems de pedidos NO terminados
                        con fecha_entrega <= F
margen_libre(F) = capacidad_hasta(F) - carga_comprometida(F)
```

Si las horas del pedido nuevo superan `margen_libre(F)` → advertencia.

### 6.2 Qué NO hacer

- **No es un planificador.** Decidir qué trabajo va en qué máquina y en qué orden es un
  problema genuinamente difícil y no hace falta. El alcance es la curva de carga
  comprometida por fecha, nada más.
- **No bloquear** la carga del pedido. Si dos pedidos vencen el mismo día y entra uno
  solo, el sistema avisa; la prioridad la decide la persona.
- **No** hacer el chequeo local ("¿entran 6 horas antes del viernes?"): eso siempre da
  que sí y no sirve. Tiene que ser **acumulativo** sobre el backlog.

### 6.3 Días hábiles

Arrancar con lunes a viernes. Agregar una lista de feriados/excepciones cargable a mano
en la misma pantalla de Configuración de la Fase 1. No usar librerías de feriados.

### 6.4 Por qué esta fase importa más de lo que parece

Es lo que hace que estimar tiempos rinda **el mismo día**. Cargar tiempos "para que el
costeo sea más preciso" es una tarea sin recompensa visible; cargarlos para que el
sistema diga si se puede prometer el viernes es una herramienta de uso diario. El costeo
pasa a ser un subproducto de algo que ya sirve.

Además trae dos efectos secundarios valiosos:

- **Calibra los tiempos gratis.** Si el sistema dice "lleno hasta el jueves" y el taller
  está parado el martes, los tiempos están sobrecargados. Si dice "hay lugar de sobra" y
  están trabajando el sábado, están cortos.
- **Le da sentido a marcar los estados.** Si no se marca "Terminado", el backlog queda
  inflado y el sistema avisa que no hay lugar cuando sí lo hay. Esa molestia se arregla
  con un click, que es justamente el hábito que se quiere instalar.

---

## 7. Checklist de verificación por fase

Antes de dar una fase por terminada:

- [ ] Migraciones creadas y aplicadas sin errores.
- [ ] `manage.py test` en verde.
- [ ] Test de regresión nuevo para cada fórmula introducida
      (`tasa_hora`, `tiempo_estimado`, `precio_sugerido`, `piso_absoluto`,
      `piso_absorcion`, y las métricas del panel).
- [ ] Probado a mano en la UI con un producto de cada tipo de cálculo (A, B, C y D):
      los cuatro tipos convergen en `cantidad_producto`, pero conviene verificar que
      ninguno rompa.
- [ ] Los montos entran y salen en formato AR correctamente (probar con `1.234,56`).
- [ ] Un usuario sin grupo Gerencia **no** puede entrar a Configuración → Estructura de costos.
- [ ] **El precio que se cobra no cambió** respecto de antes del cambio, salvo por el
      efecto esperado de los tiempos precargados (Fase 2). Verificar con una cotización
      de control antes y después.

---

## 8. Glosario

| Término | Significado |
|---|---|
| **Tasa horaria / tasa de estructura** | `costos_fijos_mensuales / horas_productivas_mensuales`. Cuánto tiene que aportar cada hora vendida para pagar la estructura. |
| **Hora vendida** | El tiempo de producción embebido en un trabajo que el cliente aceptó. No es tiempo de reloj: es capacidad comprometida y facturada. |
| **Absorción** | La porción de costos fijos recuperada vía las horas vendidas. |
| **Sub-absorción** | Cuando lo recuperado es menor a los costos fijos reales del período. |
| **Contribución** | Precio cobrado menos costo variable. Lo que queda para pagar la estructura y generar ganancia. |
| **Contribución por hora** | Contribución dividida por las horas del trabajo. **Es el criterio de ranking correcto**, no el margen porcentual, porque el recurso escaso es el tiempo. |
| **Piso absoluto** | Costo variable. Por debajo se pierde plata siempre. |
| **Piso con absorción** | Costo variable + estructura. Por debajo no se pierde en el trabajo pero no se paga la parte de estructura. |
| **Ratio productivas/disponibles** | Qué proporción de las horas pagadas se dedica efectivamente a producir. |
| **Factor de corrección de tiempos** | Multiplicador global sobre los tiempos estimados, para corregir el sesgo sistemático de la estimación sin medir trabajo por trabajo. |
