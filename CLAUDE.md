# CotizadorEasyPrint

Cotizador / gestor de stock para una imprenta (EasyPrint). Django 5 + SQLite,
frontend con templates de Django + Bootstrap + jQuery/DataTables. La app maneja
insumos, productos (compuestos por insumos), presupuestos y pedidos.

## Ubicación importante

- El proyecto Django y el **repo git viven en el subdirectorio `EasyPrint/`**, no
  en la carpeta raíz `CotizadorEasyPrint/`.
- El virtualenv está en `CotizadorEasyPrint/env/` (un nivel arriba de `manage.py`).
- Base de datos: `EasyPrint/db.sqlite3`.

## Comandos

Ejecutar desde `EasyPrint/` (ajustar la ruta del python del venv):

```bash
../env/Scripts/python.exe manage.py runserver     # servidor de desarrollo
../env/Scripts/python.exe manage.py test           # toda la suite
../env/Scripts/python.exe manage.py test core productos   # apps puntuales
```

## Apps

- **core**: base compartida — layout, `utils.py` (formateo/parseo de números),
  `decorators.py` (`@solo_gerencia`, `@solo_dashboard`), `roles.py`, context
  processors, home.
- **productos**: `Insumo`, `Producto`, `ComponenteProducto` (M2M producto↔insumo
  con cantidad), categorías, y toda la ABM de insumos/productos + import/export Excel.
- **presupuestos**, **pedidos**: cotizaciones y pedidos; consumen stock de insumos
  y registran `FaltanteInsumo` cuando no alcanza.
- **clientes**, **dashboard**: ABM de clientes y tablero de métricas.

## Roles (`core/roles.py`)

Grupos de Django: **Gerencia** (todo), **Administración** (gestión: ABMs,
configuración, caja; sin Dashboard, Usuaries ni exportar caja) y **Ventas**.
Los permisos están en el dict `PERMISOS` de `core/roles.py` (permiso → grupos):
para mover un permiso entre roles, tocar solo ahí. Vistas: `@solo_gerencia`
(= permiso `gestion`), `@solo_dashboard`, `@solo_usuarios` o
`@requiere_permiso('x')`. Templates: `es_gerencia` (= gestión, incluye
Administración) y `puede.<permiso>`. No consultar `groups.filter(name=...)` a mano.

## Caja: cobros de pedidos (app `caja`)

- `caja.Movimiento`: cada seña / pago / devolución con fecha, medio (efectivo,
  transferencia, tarjeta; `sin_especificar` solo para históricos) y usuario.
  `monto` con signo (devolución < 0).
- `Pedido.senia` = **total cobrado** y `Pedido.saldo` = precio − cobrado; se
  recalculan desde los movimientos (`caja/services.py`). No escribirlos a mano:
  todo cobro pasa por `registrar_movimiento` / `registrar_saldo` / `devolver_cobrado`.
- Cambios de estado (individual y masivo) pasan por `pedidos/estados.py`
  (`cambiar_estado_pedido`): → "Terminado y pagado" puede registrar el saldo;
  → "Cancelado" repone stock, retiene o devuelve lo cobrado y marca
  `bloqueado_cancelado` (irreversible).
- Vista `/caja/` (permiso `caja`): totales por medio y movimientos por período.
  Por ahora solo ingresos; egresos (compras, alquiler, servicios) no se registran.

## Cotizador: gráfico y "Partir diseño" (`presupuestos/functions.py`)

- Tipos: A (hojas), B (m² en rollo), C (metros lineales), D (sin gráfico). Un
  rollo es un alto de `ALTO_ROLLO` (100000, "Según cálculo"). El consumo en
  rollo es ancho del producto × largo ocupado × 1,1 (sin márgenes laterales:
  `Producto.ancho` = ancho imprimible).
- **Partir diseño** (solo B/C, botón tijera junto al gráfico): `calcular_franjas`
  corta un solo lado (franjas, nunca grilla) en la menor cantidad (≥ 2) de
  franjas iguales que entren a lo ancho, con `solapamiento` cm (5 por defecto)
  entre vecinas. Con varias copias, `_filas_mixtas` parte solo las que hace
  falta: las que entran enteras (lado cortado a lo ancho) no se parten ni suman
  solapamiento; minimiza filas y, a igualdad, copias partidas. No elige entre
  direcciones ni contra "sin partir": muestra el resultado y el consumo sin
  partir para que el usuario decida. Regenerar alterna a cortar el otro lado solo si eso cambia el
  resultado y mejora lo de sin partir (desde "corto" siempre vuelve a "largo").

## Convención de números — formato argentino (IMPORTANTE)

Los precios se muestran/ingresan en formato AR: **punto = separador de miles,
coma = separador decimal** (ej: `1.234,56`). Esto es la fuente más común de bugs.

Helpers en `core/utils.py`:

- `format_ar(valor)` → string AR (`1234.56` → `"1.234,56"`).
- `parse_ar(valor)` → `Decimal`. Interpreta strings como formato AR. Es
  **tolerante**: descarta símbolos de moneda, espacios y otros caracteres no
  numéricos antes de parsear (ej: `"$ 1.234,56"` → `Decimal("1234.56")`), y si
  recibe un numérico (int/float/Decimal) lo convierte directo sin reinterpretar
  separadores. Ante entrada inválida/vacía devuelve `Decimal("0.00")`.

Helpers equivalentes en JS: `formatearNumeroLocal` / `parsearNumeroLocal` en
`core/static/core/js/core.js`.

Regla: **cualquier valor monetario que venga de un `request.POST` debe pasar por
`parse_ar`**, nunca por `float()`/`Decimal()` directo, porque el string trae comas.
El modal de insumos precarga el precio con `formatearNumeroLocal(...)` (formato AR,
sin símbolo de moneda; ver `core/static/productos/js/Insumos.js`). Aun así
`parse_ar` es tolerante a símbolos de moneda por defensa en profundidad.

> Historial: un bug hacía que al editar un insumo por la UI el precio se guardara
> en 0 porque el campo se precargaba como `"$ 350,50"` y `parse_ar` devolvía 0 al
> no poder parsear el `$`. Se corrigió (1) haciendo `parse_ar` tolerante y (2)
> quitando el prefijo `"$ "` del precarga en `Insumos.js`. Test de regresión en
> `core/tests.py::ParseArTests`.

## Modelo de stock de insumos (concepto clave)

`Insumo` distingue dos magnitudes:

- `unidad_medida`: unidad de **compra** (ej: "resma", "rollo").
- `unidad_composicion`: unidad de **uso** (ej: "hoja", "cm²").
- `factor_conversion`: cuántas unidades de uso hay por unidad de compra
  (ej: 1 resma = 500 hojas → factor 500).
- `stock`: se guarda internamente en **unidad de compra**.
- `stock_real()` = `stock * factor_conversion` → unidad de uso.

En la UI el usuario ingresa/ve el **stock real** (unidades de uso). El backend
divide por el factor para guardar `stock`. Ver `guardar_insumo` en
`productos/views.py` y `reemplazar_stock` en `productos/stock.py`.

`precio` es el costo por unidad de compra. Al editar un insumo se recalcula el
precio de todos los productos no tercerizados que lo usan
(`_recalcular_precios_productos_con_insumo`).

**Decimales / unidades de uso enteras**: las unidades de uso (stock real) se
cuentan por unidades enteras (hojas, unidades, etc.). Como el stock interno se
guarda en unidad de compra (float) y `stock_real()` = `stock * factor`, la
conversión puede arrastrar decimales espurios (ej: "102,27 hojas"). Por eso el
**stock real se redondea a entero solo a nivel de presentación**: la tabla de
insumos usa `floatformat:"0"` y el endpoint `info_insumo` devuelve
`round(stock_real())` para precargar el modal. **No** redondear en el modelo:
`stock_real()` se usa en la lógica de consumo de stock de `pedidos`
(`pedidos/views.py`) y debe conservar precisión.

Unicidad de insumos: constraint `UniqueConstraint(Lower('nombre'))` — no puede
haber dos insumos con el mismo nombre ignorando mayúsculas. La importación por
Excel busca con `nombre__iexact` para no crear duplicados.

## Faltantes de insumos (`productos/stock.py`)

Toda la lógica de stock/faltantes vive en `productos/stock.py`; las vistas de
pedidos y productos solo la llaman.

- Al confirmar un pedido, `descontar_producto` reserva insumos; si no alcanzan,
  el stock queda en 0 y se crea un `FaltanteInsumo` (en unidad de uso).
- Invariante: stock > 0 ⇒ sin faltantes abiertos. Todo ingreso de material
  (`aplicar_ingreso`: compra, edición, importación) cubre primero los faltantes.
- **Prioridad**: fecha de entrega más cercana primero (sin fecha al final),
  luego orden de registro. `Faltantes.js` simula con el mismo orden: si se
  cambia uno, cambiar el otro. Al registrar una compra se puede alterar por
  pedido (`priorizados` primero, `postergados` al final, sin excluirlos).
- `FaltanteInsumo.motivo_cierre`: `'stock'` (llegó material; legacy `''` se
  trata igual) o `'pedido'` (el pedido pasó a Terminado). Solo los `'pedido'` se
  reactivan si el pedido vuelve a abrirse (`aplicar_cambio_estado`).
- `reponer_pedido` (borrar/cancelar) devuelve solo lo realmente descontado:
  necesario − lo que nunca se cubrió. Un pedido terminado no devuelve nada.
- Vista `/productos/insumos/faltantes/` (+ lista de compra en Excel y
  "Registrar compra"). `Proveedor` se vincula a `Insumo.proveedor`.

## Flujo guardar insumo desde la UI

1. `Insumos.js` intercepta el submit del form, arma `FormData` y hace POST a
   `/productos/guardarInsumo/`, esperando JSON `{ok, mensaje, info_reposicion}`.
2. `guardar_insumo` valida nombre/duplicados, parsea precio con `parse_ar`,
   convierte `stock_real` → `stock` dividiendo por `factor_conversion`, y en
   edición pasa por `procesar_reposicion_insumo_por_edicion` (compensa faltantes).
3. El front guarda el estado de la DataTable en `sessionStorage` y recarga.

El path de **import/export por Excel** es independiente del modal (usa openpyxl en
`importar_insumos_excel`); por eso puede comportarse distinto al alta/edición manual.
