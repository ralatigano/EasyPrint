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
  `decorators.py` (`@solo_gerencia`), context processors, home.
- **productos**: `Insumo`, `Producto`, `ComponenteProducto` (M2M producto↔insumo
  con cantidad), categorías, y toda la ABM de insumos/productos + import/export Excel.
- **presupuestos**, **pedidos**: cotizaciones y pedidos; consumen stock de insumos
  y registran `FaltanteInsumo` cuando no alcanza.
- **clientes**, **dashboard**: ABM de clientes y tablero de métricas.

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
divide por el factor para guardar `stock`. Ver `guardar_insumo` y
`procesar_reposicion_insumo_por_edicion` en `productos/views.py`.

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

## Flujo guardar insumo desde la UI

1. `Insumos.js` intercepta el submit del form, arma `FormData` y hace POST a
   `/productos/guardarInsumo/`, esperando JSON `{ok, mensaje, info_reposicion}`.
2. `guardar_insumo` valida nombre/duplicados, parsea precio con `parse_ar`,
   convierte `stock_real` → `stock` dividiendo por `factor_conversion`, y en
   edición pasa por `procesar_reposicion_insumo_por_edicion` (compensa faltantes).
3. El front guarda el estado de la DataTable en `sessionStorage` y recarga.

El path de **import/export por Excel** es independiente del modal (usa openpyxl en
`importar_insumos_excel`); por eso puede comportarse distinto al alta/edición manual.
