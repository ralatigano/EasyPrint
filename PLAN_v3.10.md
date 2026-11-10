# Plan v3.10 — Manual de uso y mejoras de lectura

Estado: **lotes A (v3.10.0), B (v3.11.0) y C (v3.12.0) terminados y
desplegados**; quedan D y E. Punto de partida: `main` en `e09f8c6` (v3.9.0,
desplegada en la VM).

Los lotes salen de a uno, a medida que se terminan, en lugar de esperar a un
release grande: **A = v3.10.0** (manual), **B = v3.11.0** (dashboard),
**C = v3.12.0** (pedidos). Lo que queda (D, E) va a releases posteriores.

Este plan agrupa un conjunto de trabajos heterogéneos que salieron de una misma
observación: el cotizador acumuló features y la forma de usarlo dejó de ser
evidente, incluso para quien lo pidió. Hay dos frentes: **explicar** (manual) y
**arreglar lo que quedó confuso o mal medido** (dashboard, pedidos, costos).

---

## 1. Cómo se ordena esto en el repo

No se usa `parche_XX`. El repo ya tiene una convención que funciona y conviene
no mezclar dos:

- Ramas `feature/<tema>`, cortas, **saliendo de `main`** (las ramas viejas
  quedaron obsoletas con el merge de v3.9.0).
- Un `PLAN_*.md` en la raíz como documento rector del conjunto (igual que
  `PLAN_ESTRUCTURA_COSTOS.md`). Este archivo es ese documento.
- Cada lote termina en `main` con su entrada en `Changelog.txt`. El lote A
  salió como **v3.10.0** y el B como **v3.11.0**; lo que resta va a releases
  posteriores.

Lotes y ramas:

| Lote | Rama | Contenido | Tamaño |
|------|------|-----------|--------|
| **A** | `feature/manual` | Manual de uso como wiki en la app (`/ayuda/`) + export PDF | **hecho**, v3.10.0 |
| **B** | `feature/dashboard-claro` | Corte en dos bloques, panel de horas reescrito, conversión arreglada, card "Dinero por entrar", filtro de fechas | **hecho**, v3.11.0 |
| **C** | `feature/pedidos-filtros` | Indicador de facturado + filtro de fechas en pedidos | **hecho**, v3.12.0 |
| **D** | `feature/buscador-costos` | Buscador en estructura de costos | mínimo (puede ir con B) |
| **E** | `feature/producto-estandar` | Guardar un ProductoCotizado como producto estándar reutilizable | grande |

**Orden**: A, B y C hechos. Quedan D (mínimo) y E (grande). El capítulo del dashboard se escribió **antes** de B, así que
describe el tablero actual: cuando B cambie la pantalla hay que repasar el paso
5 del capítulo y sacar el recuadro sobre absorción vs. equilibrio (ver §2.4).

B, C y D no se pisan entre sí (tocan `dashboard/`, `pedidos/` y `core/views.py`),
así que pueden ir en paralelo.

---

## 2. Diagnóstico del dashboard (lote B)

Sobre la captura del mes en curso: costo fijo **$7.249.215**, horas productivas
**297 h**, tasa por hora ≈ **$24.424**, horas vendidas **61,3 h**, absorción
recuperada **$1.497.195**.

### 2.1. El corte estructural: dos bloques, no uno

**Decisión tomada.** La pantalla mezcla hoy dos cosas que se miden distinto, y
ahí nace buena parte de la confusión. Se parte en dos bloques rotulados:

**Bloque 1 — "Salud del mes" (siempre mes en curso, NO sigue el filtro).**
Horas, punto de equilibrio, absorción. La intuición del usuario es correcta:
la estructura de costos está mensualizada, así que llevar estos números a
ventanas arbitrarias sería tan complejo como engañoso (¿cuánto costo fijo le
toca a "los últimos 17 días"?). Queda atado al mes calendario y **se dice en
pantalla**, que hoy no se dice.

**Bloque 2 — "Actividad comercial" (sigue el filtro, con rango personalizado).**
Pedidos completados, ticket promedio, productos más vendidos, top clientes,
conversión. Es exactamente lo que se pidió poder medir por período.

**El ranking de contribución por hora va al bloque 2.** Vale la pena explicarlo
porque no es obvio: la contribución de un ítem es `resultado − piso_absoluto`,
y `piso_absoluto` es un *snapshot por ítem* (material + empaquetado del momento
de cotizar). No depende de la mensualización del costo fijo. Es decir, la
contribución por hora **es comparable en cualquier ventana de tiempo**, a
diferencia de la absorción. Hoy está en el bloque mensual sólo porque se
implementó junto con el panel de horas, no por una razón de fondo.

### 2.2. El "353 h" y el "objetivo 297 h" no son el mismo tipo de número

- **297 h** = `horas_productivas_mes()` → **capacidad**: lo que el taller puede
  producir en el mes (operarios × horas/día × días × ratio productivo).
- **353 h** = `punto_equilibrio_hs` = costo fijo ÷ contribución promedio por
  hora → **lo que habría que vender** para no perder plata **al mix y a los
  precios de este mes**.

Que 353 > 297 **no es un detalle de redacción: es el hallazgo más importante de
la pantalla y hoy pasa completamente desapercibido**. Significa que, con lo que
se está cobrando, cada hora vendida deja ≈ $20.500 para cubrir estructura
cuando harían falta ≈ $24.400. Es decir: aun vendiendo el 100 % de la capacidad
del taller, el mes cerraría en pérdida. La conclusión práctica es *subir
precios o cambiar el mix*, y la pantalla hoy no la dice en ningún lado.

**Propuesta**: el número grande deja de ser una cifra de horas sin contexto y
pasa a ser un semáforo con una frase en castellano. Dos estados:

- `equilibrio ≤ capacidad` → "Necesitás vender **X h** de las **297 h** que
  podés producir. Vas **61,3 h**." (verde/ámbar según el avance).
- `equilibrio > capacidad` → "**Con los precios de este mes no cierra**: harían
  falta 353 h y el taller da 297 h. Falta ≈16 % de precio." (rojo).

La barra pasa a tener una sola escala (0 → capacidad) y la marca de equilibrio
sale del borde cuando no entra, en vez de clavarse al 100 %.

### 2.3. "Conversión cotizadas → vendidas 217 %" está mal calculada

No es que se haya vendido más rápido de lo estimado. **El numerador y el
denominador son conjuntos distintos** (`dashboard/metrics.py`):

- `horas_vendidas` = ítems de presupuestos que **se convirtieron en pedido este
  mes**, sin importar cuándo se presupuestaron (un presupuesto de septiembre
  que se cerró en noviembre suma acá).
- `horas_cotizadas` = ítems de presupuestos **creados este mes**, se hayan
  vendido o no.

Como son cohortes distintas, el cociente puede dar cualquier cosa y de hecho da
217 %. Una "conversión" que supera el 100 % es, por definición, un bug.

**Propuesta**: calcular por cohorte — de los presupuestos **creados en la
ventana**, qué proporción de sus horas terminó en pedido. Eso sí está acotado a
0–100 %. Va al bloque 2 (sigue el filtro). Como contrapartida, una ventana
reciente arranca baja (los presupuestos recién emitidos todavía no se
cerraron); se rotula con el período visible para que se entienda.

Si además se quiere la lectura de "ritmo" (horas vendidas vs. horas cotizadas
en la misma ventana, aunque vengan de cohortes distintas), va como **métrica
aparte y con otro nombre** — nunca llamada "conversión".

### 2.4. El card de absorción mide horas, no plata: cambiarlo por el resultado

Salió al escribir el capítulo 8 y lo confirmó el usuario leyendo el resultado.
El card derecho **no mira el precio cobrado en ningún momento**:

```
t_produccion         = (tiempo_setup + tiempo_unitario × cantidad) × factor_correccion
                       (factor_correccion está fijo en 1 desde 2026-08-29)
absorcion_recuperada = Σ t_produccion de los pedidos del mes × tasa
sub_absorcion        = absorcion_recuperada − costo_fijo
```

Como `tasa = costo_fijo ÷ horas_productivas`, eso es idénticamente
`(horas_vendidas − horas_productivas) × tasa`: **el card se pone en verde
exactamente cuando se vendieron las horas productivas del mes**, al precio que
sea. Es la misma información que la barra del card izquierdo, convertida a
pesos. No es un bug (es costeo por absorción de manual), pero como indicador
propio no agrega nada y puede contradecir al punto de equilibrio.

**Propuesta (confirmada con el usuario como la lectura que esperaba del card):
mostrar el resultado del mes en lugar de la absorción.**

```
resultado_mes = contribucion_mes − costo_fijo
              = Σ (resultado − piso_absoluto) − costo_fijo
```

Por qué es mejor:

1. `contribucion_mes` **ya se calcula** en `panel_horas()` (hoy sólo se usa para
   el promedio por hora). Falta exponer la resta: Django no divide ni resta en
   el template, así que va como clave nueva del dict.
2. **Los dos cards pasan a decir lo mismo en unidades distintas, pero esta vez
   de verdad**: `resultado_mes` cruza el cero *exactamente* cuando las horas
   vendidas alcanzan el punto de equilibrio (`contribucion_mes = costo_fijo` ⟺
   `horas_vendidas = punto_equilibrio_hs`). Izquierda en horas, derecha en pesos,
   el mismo umbral.
3. Se termina la contradicción: no hay forma de tener verde a la derecha y
   alarma a la izquierda.
4. No se pierde la lectura de uso de capacidad: eso es la barra.

Cuidados al implementarlo:

- **Nombre**: no es la ganancia del mes. La estructura de costos no incluye
  tercerizados ni compras, y cuenta pedidos creados en el mes estén cobrados o
  no. Va como "falta para cubrir la estructura" / "estructura cubierta, sobran
  $X", no como "resultado" ni "ganancia".
- Conviene conservar el término *absorción* sólo donde sigue aplicando (el piso
  de absorción del ítem), y sacarlo del card.
- Cuando esto entre, **sacar del capítulo 8** el recuadro "si la absorción y el
  punto de equilibrio no se dan la mano" y reescribir la tabla de colores del
  paso 4 (`core/templates/ayuda/capitulos/dashboard.html`). El capítulo describe
  el tablero de hoy.

### 2.5. Terminología

`absorción`, `piso de absorción`, `contribución` y `sub-absorción` son términos
de costeo correctos pero opacos para el uso diario. Los tooltips "(i)" ya los
explican, pero el texto visible debería poder leerse sin abrirlos. Pasada de
redacción sobre `core/glosario.py` y los templates del dashboard, con la regla:
**el texto visible dice qué hacer, el tooltip dice cómo se calcula**.

### 2.6. Card "Dinero por entrar"

Hoy "Pedidos en curso" muestra la cantidad de pedidos `No iniciado` + `En
proceso` y su saldo. Pasa a ser un card de **plata por cobrar**, con el total
arriba y el desglose debajo:

- saldo de pedidos en curso (trabajo por hacer y cobrar),
- saldo de `Terminado (falta pago)` (trabajo entregado, plata pendiente) —
  destacado distinto, porque es el que hay que ir a reclamar.

Cada línea linkea a la lista de pedidos con el filtro ya aplicado (ya existe
`irAPedidosConFiltro`).

### 2.7. Filtro de fechas personalizado

Rango *desde/hasta* junto a los botones de período, aplicado al bloque 2.
Afecta también a `exportar_excel` (que hoy recalcula el período por su cuenta a
partir del mismo `?periodo=`): conviene extraer la resolución del período a una
función única para que las dos vistas y el Excel no se desincronicen.

---

## 3. Lote C — Pedidos

- **Indicador de facturado**: `facturacion.Comprobante` tiene FK a `Pedido`
  (`related_name="comprobantes"`). Marca chica junto al número del pedido
  cuando existe un comprobante `autorizado`. Anotar en la queryset (`Exists`),
  no consultar por fila. Estados a distinguir: facturado / intento con error /
  sin facturar.
- **Filtro de rango de fechas** en la vista de pedidos, consistente con el del
  dashboard.

## 4. Lote D — Buscador en estructura de costos

Campo de búsqueda sobre la tabla de líneas de costo fijo en
`core/templates/core/configuracion_costos.html`. La tabla es chica y se arma en
el template: alcanza con filtrado en cliente (como las DataTables del resto del
proyecto), sin tocar la vista.

---

## 5. Lote E — "Producto estándar"

### 5.1. Qué problema resuelve (replanteado)

El pedido original hablaba de vincular precios, pero el dolor real es otro:
**hoy, cada vez que alguien pregunta por 100 tarjetas hay que volver a cargar
todo** — categoría, tipo de papel, cantidad, ancho y alto de la pieza, y el
texto del campo "Producto" que va en la línea del presupuesto. Para un trabajo
que se repite, es tiempo tirado y es una oportunidad de equivocarse.

Entonces un producto estándar es **una receta de cotización guardada**: se
elige de la lista, se pone la cantidad de packs y sale el precio. El vínculo de
precio con el material es la segunda mitad del problema, no la primera.

### 5.2. Decisiones tomadas

- **Unidad = pack.** "Tarjetas personales × 100" se cotiza poniendo 1, 2, 3…
  El consumo de insumos queda entero (13 hojas por pack, no 0,13 por tarjeta) y
  el circuito de faltantes sigue funcionando sin fracciones.
- **Las variantes no se modelan.** Si cambia el gramaje o pasa de simple a
  doble faz, ya no es el mismo estándar. Se resuelve con dos botones en vez de
  con un modelo de variantes:
  - **"Cotizar"** → precio × cantidad, directo.
  - **"Usar como base"** → precarga el formulario de cotización normal con la
    receta (papel, medidas, cantidad, texto) y se cotiza como siempre,
    cambiando lo que haga falta. Al final se puede guardar como un estándar
    nuevo.
- **Nombre autogenerado desde la receta** ("Tarjetas 9×5 · 300 g · ×100"),
  editable. Sin esto proliferan estándares casi iguales e indistinguibles.

### 5.3. Arquitectura propuesta

Reusar `Producto` con categoría "Producto estándar", agregándole:

- `producto_base` → FK a sí mismo (el material: el papel).
- `cantidad_base` → la magnitud que multiplicó al precio del material en la
  cotización original (ej: 13 hojas).
- `receta_cotizacion` → `JSONField` con los inputs del gráfico (tipo, ancho y
  alto de la pieza, separación, algoritmo, cantidad de piezas, texto del
  producto final). Sólo se usa para "Usar como base". `JSONField` ya se usa en
  el proyecto (`facturacion`, `tercerizados`), así que no agrega dependencias.

La ventaja de reusar `Producto` es que el estándar aparece solo en el desplegable
del cotizador, se cotiza por el camino tipo D (precio × cantidad) sin tocar el
flujo, y hereda la cascada de recálculo de precios y los `ComponenteProducto`
para el stock. La desventaja es que `Producto` ya está sobrecargado (hoy
guarda "Mano de obra" y "Empaquetado" como pseudo-productos). Se asume: el
costo de un modelo nuevo y su espejo es mayor.

### 5.4. ⚠️ Trampa: doble conteo de mano de obra y empaquetado

Esto hay que tenerlo claro **antes** de escribir una línea. La fórmula que se
cobra ([presupuestos/views.py:212](presupuestos/views.py)) es:

```
precio = cantidad × precio_producto × factor + horas_legacy × precio_hora + empaquetado
```

Si el producto estándar guardara en `precio` el **precio final del pack** (como
sugiere la intuición), al cotizarlo la fórmula le volvería a sumar mano de obra
y empaquetado. El pack saldría más caro que la cotización que lo originó, y
nadie entendería por qué.

**Regla**: el estándar guarda en `precio` **sólo la parte de material con
markup** —`cantidad_base × precio_base × factor_base`— y lleva `factor = 1`.
La mano de obra y el empaquetado los sigue agregando la fórmula normal, como
para cualquier otro producto. Así el precio queda vinculado al material (que
era el pedido) y nada se cuenta dos veces.

### 5.5. Detalles a resolver al implementar

1. **Recálculo en cascada**: hoy `_recalcular_precios_productos_con_insumo`
   ([productos/views.py:704](productos/views.py)) va `Insumo → Producto`. Hay
   que extenderla un eslabón: `Insumo → Producto → Producto estándar`. Cuidado
   con el orden (el estándar se recalcula después del base) y con los ciclos.
2. **Componentes para stock**: derivar los `ComponenteProducto` del estándar
   como los del base × `cantidad_base`, y re-derivarlos si cambia la receta del
   base.
3. **Tiempos**: `tiempo_setup` se hereda del base; `tiempo_unitario` = (el
   `t_produccion` de la cotización original − setup) por pack. Así cotizar 3
   packs no triplica el setup.
4. **Familias `[N-M]`**: la receta congela el producto **ya resuelto** por tier,
   no el representante de familia. Si no, al recotizar se dispara de nuevo la
   auto-resolución con una cantidad que ya no corresponde.
5. **Base desactivado o con receta cambiada**: hace falta un aviso en la lista
   de estándares. Borrar en cascada un estándar ya vendido no es opción.

---

## 6. Lote A — Manual de uso

> **Estado: capítulos 1 a 4 y 8 hechos** en la rama `feature/manual`. App
> `ayuda/`, wiki en `/ayuda/` con el índice en `ayuda/contenido.py`, ejemplos
> con datos reales en `ayuda/contexto.py`, PDF en `/ayuda/pdf` (con glosario al
> final, ya que en papel no hay tooltips) y link al final de la barra de
> navegación, a la derecha de "Gestión". 40 tests propios; la suite completa
> pasa (319).
>
> **El capítulo 8 (dashboard) se adelantó** por pedido del usuario: los
> capítulos 5 a 7 describen partes del cotizador que ya se usan sin problema,
> mientras que los conceptos del tablero son los que nadie termina de entender.
> No esperó al lote B porque explica los **conceptos** (de dónde sale cada
> número y qué decisión habilita), no los textos de la pantalla; cuando el lote
> B cambie la redacción visible habrá que repasar sólo el paso 5, que es el que
> menciona el "353 h vs 297 h".
>
> Los capítulos 5, 6, 7 y 9 quedan **listados como pendientes** en el índice
> (`estado=PENDIENTE` en `contenido.py`): se ven con su título y resumen, sin
> link y sin template, no entran al PDF y la navegación anterior/siguiente los
> saltea. Hay tests que verifican las tres cosas.

**Decisión: wiki dentro de la app, con export a PDF.** El PDF solo envejece mal
y nadie sabe cuál es la última versión; la wiki vive al lado de lo que explica.
Y el PDF sale gratis: **weasyprint ya está en `requirements.txt`** (lo usa la
impresión de presupuestos), así que las mismas páginas se renderizan a PDF para
quien lo quiera imprimir o mandar. Una sola fuente, dos salidas.

Implementación: sección `/ayuda/` con las páginas como templates de Django (sin
agregar una dependencia de markdown). Dos reglas:

- **Los conceptos salen de `core/glosario.py`**, que ya es la fuente única de
  los tooltips "(i)". El manual explica *procedimientos*; los *conceptos* los
  sigue definiendo el glosario, y la wiki los inyecta. Si divergen, se repite el
  problema que el glosario vino a resolver.
- **Los ejemplos numéricos se arman con los datos reales de la base** (tasa por
  hora, costo fijo, un producto concreto). Un manual que muestra *tus* números
  se entiende y se verifica; uno con números inventados no.

Índice:

1. Qué hace el cotizador y en qué orden se carga todo.
2. **Insumos**: unidad de compra vs. unidad de uso, factor de conversión,
   precio, stock. Con ejemplos (resma → hoja, rollo → cm²).
3. **Productos**: los 4 tipos de cálculo (A hojas, B m², C metros, D unidad),
   la receta de insumos, **qué es el `factor` y por qué se decide y no se
   calcula** (§6.1), **cómo se miden `tiempo_setup` y `tiempo_unitario`**, y
   las familias con rango `[N-M]`.
4. **Cotizar**: de dónde sale cada número del presupuesto y cómo se lee la
   comparación entre los dos precios (incluido "Agregar con precio sugerido").
5. **Pedidos, stock y faltantes**: qué dispara cada cambio de estado.
6. **Caja y facturación**.
7. **Tercerizados**.
8. **Dashboard**: cómo leer cada número y qué hacer con él (se escribe después
   del lote B).
9. Recetario: "quiero agregar un producto nuevo", "me subió el papel",
   "un trabajo salió más caro de lo cotizado".

### 6.1. El `factor`: por qué NO se explica cómo calcularlo

El primer borrador de los capítulos traía una sección que enseñaba a "despejar"
el factor desde el precio sugerido, con una tabla que comparaba, escalón por
escalón de una familia, lo cobrado contra lo sugerido y el "factor que daría el
sugerido". **Se sacó entera**, por dos razones que conviene no volver a pisar:

1. **Presupone que alguno de los dos métodos es la verdad.** El precio actual
   depende del `factor`, que es un remarcado que alguien decidió a mano. El
   precio sugerido depende de los tiempos del producto, que hoy son
   estimaciones puestas de arranque (ver §6.3). Derivar uno del otro no
   "calcula" nada: traslada una decisión arbitraria a otra. Son dos criterios
   distintos para responder la misma pregunta, y la diferencia entre ambos es
   información para decidir, no un error para corregir.
2. **La tabla además mentía por elegir mal la cantidad.** Tomaba el piso de
   cada escalón (1 hoja en `[1-5]`), un caso de borde donde el término de
   tiempo domina y el sugerido sale muy por encima de lo cobrado. En las
   cotizaciones reales pasa lo contrario: **5 de 6 tienen el sugerido por
   debajo de lo cobrado** (razones sugerido/cobrado de 0,47 a 0,71).

Lo que el capítulo dice ahora: *el factor no se calcula, se decide*. Y si hace
falta un procedimiento, es despejarlo desde **el precio que uno quiere cobrar**,
no desde el sugerido:

```
factor = (precio que querés cobrar − mano de obra − empaquetado) / costo_material
```

Dato importante que el capítulo deja explícito: **el precio sugerido no usa el
factor**. Al dar de alta un producto no hay que inventar ni justificar un factor
"correcto" pensando en el sugerido.

También se corrigió la causalidad de las **familias `[N-M]`**: el borrador
deducía que el factor baja porque el setup se diluye. Es al revés — se decidió
comercialmente que a mayor cantidad el precio por unidad tiene que bajar, y se
bajó el factor de los escalones grandes para que el cotizador lo cumpla. La
tabla de ejemplo ahora muestra sólo factor y precio por unidad por escalón, que
es la relación que sí existe, y hay un test que verifica que el precio por
unidad baje escalón a escalón.

> `_factor_ideal` y `_fila_tier` se borraron de `ayuda/contexto.py` junto con
> sus tests. Si alguien quiere reponer la comparación, que lea antes esta
> sección.

### 6.2. Lo que el manual tiene que dejar escrito sobre los tiempos

- `tiempo_setup`: desde que está el archivo hasta la primera copia buena
  (armar, calibrar, prueba). No depende de la cantidad.
- `tiempo_unitario`: `(tiempo real total − setup) / cantidad_producto`. La
  unidad es **la misma magnitud que multiplica al precio** (hoja, m², metro,
  unidad), **no** la cantidad de piezas. En tarjetas es por hoja, no por tarjeta.
- Y el dato que hoy no está escrito en ningún lado: **estos tiempos no mueven
  el precio que se cobra** (el método viejo usa `horas_legacy`, una constante).
  Alimentan el precio sugerido y las horas del dashboard. Cargarlos mal no
  rompe una cotización, pero **sí distorsiona el dashboard**.

---

### 6.3. Hallazgos al escribir los capítulos 1-4

Pasó lo que se esperaba: documentar destapa cosas. Ninguna se tocó en esta
entrega (son de otros lotes), pero quedan anotadas.

1. **Los tiempos de producción son estimaciones sembradas, no mediciones.**
   Los 229 productos activos tienen tiempos cargados, pero sólo **5
   combinaciones distintas** de (setup, unitario) entre todos: 101 productos
   comparten `0,25 h / 0` y 84 comparten `0,17 h / 0,017 h`. Son plantillas de
   arranque.
   Esto importa más de lo que parece, porque **el tiempo es lo que mueve las
   horas del dashboard**: las horas vendidas, el punto de equilibrio y la
   contribución por hora. El `0,017 h` por hoja (un minuto) es plausible en un
   trabajo chico y claramente alto en una tirada larga, donde además no hay
   ninguna economía de escala cargada. Antes de mover precios por lo que dice
   el panel de horas, conviene medir los productos que más se venden.
   El capítulo 3 ya se lo dice al usuario, con la tabla de los tiempos reales
   de la base.
2. **La mayoría de los precios sugeridos está por debajo de lo cobrado.** De
   las 6 cotizaciones con estructura que hay en la base local, 5 tienen el
   sugerido por debajo (ratios 0,47 / 0,48 / 0,71 / 0,71 / 1,00). Dicho de
   otro modo: el método de costeo, con los tiempos que hay hoy, devuelve
   precios **más baratos** que el remarcado que se viene cobrando. Hasta no
   medir tiempos no se puede saber si eso significa que se está cobrando caro
   o que los tiempos están subestimados. Conviene tenerlo presente antes de
   proponer "pasar al método nuevo".
3. **Hay un 404 en la barra de navegación**, en cualquier pantalla, para
   usuarios sin foto de perfil: `navbar.html` dibuja el `<img>` del toggler
   móvil con `src="{{ img }}"` sin condicional, así que cuando `img` está vacío
   el navegador pide `/<ruta-actual>/None`. No rompe nada (la imagen está
   oculta por CSS), pero ensucia la consola y los logs del servidor. Arreglo:
   envolver el `<img>` en un `{% if img %}`, como ya hace la versión de
   escritorio. Va con el lote B o C, donde se toquen templates.

## 7. Preguntas abiertas

Las tres originales quedaron resueltas (pack; el filtro corta en dos bloques;
wiki en la app). Quedan, para resolver al implementar cada lote:

1. Lote B: ¿el rango personalizado se guarda por usuario (como el `stateSave`
   de las tablas) o se pierde al salir?
2. Lote E: cuando se guarda un estándar desde una cotización con descuento,
   ¿el descuento se congela en el precio o se descarta? (Propuesta: se
   descarta — el descuento es de esa venta, no del producto.)
3. Lote A: ¿la wiki es visible para todos los roles o sólo para Gerencia y
   Administración? (Propuesta: todos; Ventas es quien más la necesita.)
