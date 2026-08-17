# CotizadorEasyPrint

Cotizador y gestor de stock para la imprenta **EasyPrint**. Web app en **Django 5.2**
+ **SQLite**, con frontend de templates de Django + Bootstrap + jQuery / DataTables.
Maneja insumos, productos (compuestos por insumos), cotizaciones (presupuestos),
pedidos y facturación electrónica contra ARCA.

> Este README es la guía de **puesta en marcha y mapa del sistema**. Para las
> convenciones profundas (formato de números AR, modelo de stock de insumos) ver
> [`CLAUDE.md`](CLAUDE.md), que es la fuente de verdad de esas reglas y **debe
> leerse antes de tocar precios o stock**.

---

## 1. Ubicación y estructura del repo

- El proyecto Django y el **repo git viven en `EasyPrint/`** (este directorio), no
  en la carpeta raíz `CotizadorEasyPrint/`.
- El **virtualenv** está en `../env/` (un nivel arriba de `manage.py`).
- **Base de datos**: `db.sqlite3` (en este directorio).
- Las **claves de ARCA** viven en `keys/<ambiente>/` (`homologacion` | `produccion`).
- Configuración sensible por `.env` (django-environ). Ver §7.

```
CotizadorEasyPrint/
├── env/                  ← virtualenv (python del venv)
├── DEPLOY_ORACLE.md      ← despliegue de respaldo en VM Oracle
└── EasyPrint/            ← REPO GIT + proyecto Django (correr manage.py desde acá)
    ├── Cotizador/        ← settings, urls raíz, wsgi/asgi
    ├── core/             ← base compartida: layout, utils, templates y static de TODAS las apps
    ├── clientes/
    ├── productos/
    ├── presupuestos/
    ├── pedidos/
    ├── facturacion/      ← integración ARCA (WSAA + WSFEv1)
    ├── dashboard/
    ├── keys/             ← certificados/claves ARCA por ambiente
    └── db.sqlite3
```

> **Ojo:** los templates y los archivos static de todas las apps viven
> centralizados bajo `core/templates/<app>/` y `core/static/<app>/`, **no** dentro
> de cada app. Ej: el JS de pedidos está en `core/static/pedidos/js/Pedidos_v2.js`.

---

## 2. Puesta en marcha rápida

Desde `EasyPrint/` (ajustá la ruta al python del venv):

```bash
../env/Scripts/python.exe manage.py runserver     # servidor de desarrollo
../env/Scripts/python.exe manage.py migrate        # aplicar migraciones
../env/Scripts/python.exe manage.py test           # toda la suite de tests
../env/Scripts/python.exe manage.py test core productos   # apps puntuales
```

Idioma/locale: `LANGUAGE_CODE = 'es-ar'`. Dependencias clave: Django 5.2,
matplotlib + rectpack (gráficos de packing), openpyxl (import/export Excel),
weasyprint + qrcode (PDF de comprobantes), cryptography (firma WSAA de ARCA).
Lista completa en [`requirements.txt`](requirements.txt).

---

## 3. Mapa de apps

| App | Responsabilidad | Modelos principales |
|-----|-----------------|---------------------|
| **core** | Base compartida: layout, home, `utils.py` (formateo/parseo de números AR), `decorators.py` (`@solo_gerencia`), context processors. Aloja templates y static de todas las apps. | — |
| **clientes** | ABM de clientes. `parsear_cliente()` resuelve el input `<id>\|<referencia>` / texto libre / vacío→"Consumidor final". | `Cliente` |
| **productos** | Insumos, productos (compuestos por insumos vía `ComponenteProducto`), categorías, import/export Excel, resolución de *tiers* por rango de cantidad. | `Insumo`, `Producto`, `ComponenteProducto`, `Categoria` |
| **presupuestos** | Cotización: form inicial, cálculo con packing (matplotlib/rectpack), generación de gráficos, y guardado como presupuesto. Registra `FaltanteInsumo` si no alcanza el stock. | `Presupuesto`, `ProductoCotizado` |
| **pedidos** | Tabla de pedidos (v2), completar/confirmar pedido a partir de un presupuesto, cambios de estado (descuenta/repone stock), viajes de cadete. | `Pedido`, viajes de cadete |
| **facturacion** | Facturación electrónica ARCA: autenticación WSAA + emisión WSFEv1, PDF con CAE y QR. | `Comprobante`, `TokenAcceso` |
| **dashboard** | Tablero de métricas y objetivos. | — |

---

## 4. Flujo central del negocio

```
Cotización (presupuestos)  →  Presupuesto  →  Pedido  →  Factura (ARCA)
   form inicial + packing      guardado        completar/confirmar   Comprobante C
```

1. **Cotizar** (`presupuestos/inicio.html` + `core/js/cotizacion.js`): se elige
   **categoría → producto** (selects encadenados por eventos `change`), se cargan
   dimensiones, se corre el *packing* (Skyline / MaxRects) para tipos A/B/C o
   cálculo directo para tipo D, y se resuelve el **tier** del producto según la
   cantidad de hojas. Cada resultado se agrega a la tabla de la cotización.
2. **Guardar presupuesto**: persiste los `ProductoCotizado` bajo un `Presupuesto`.
3. **Completar pedido** (`pedidos/completar_pedido.html`): desde un presupuesto se
   pasa por un form de **confirmación** (cliente, seña, fecha de entrega, estado).
   `confirmar_pedido` crea el `Pedido` y **descuenta stock de insumos**.
4. **Cambios de estado** (`cambiar_estado`): a "Para retirar"/"Entregado" resuelve
   faltantes; "Cancelado" **repone** stock y bloquea el pedido de forma irreversible.
5. **Facturar** (opcional, desde el pedido): emite Factura C contra ARCA → `Comprobante`.

**Regla de números AR** (crítica): punto = miles, coma = decimal (`1.234,56`).
Todo valor monetario que venga de `request.POST` **debe** pasar por `parse_ar`,
nunca por `float()`/`Decimal()` directo. Helpers en `core/utils.py` (backend) y
`core/static/core/js/core.js` (front). Detalle completo en `CLAUDE.md`.

---

## 5. Facturación electrónica ARCA (app `facturacion`)

- **Contribuyente monotributista ⇒ Factura C** (`tipo_cbte=11`). También NC/ND C.
- **WSAA** (`services/wsaa.py`): firma un TRA como CMS/PKCS#7 con el certificado +
  clave y obtiene el **Token de Acceso (TA)**. El TA se cachea en DB
  (`TokenAcceso`, una fila por `ambiente`+`servicio`) y se reusa ~12 h. El modelo
  ya soporta pedir TA para servicios distintos de `wsfe` (útil para padrón).
- **WSFEv1** (`services/wsfev1.py`): solicita el CAE (autorización del comprobante).
- **Padrón A13** (`services/padron.py`): consulta razón social por CUIT
  (`ws_sr_padron_a13`, método `getPersona`, ns `http://a13.soap.ws.server.puc.sr/`).
  **Defensivo**: requiere que el CUIT emisor tenga *adherido* ese web service; si
  no está adherido o falla, devuelve `None` y la emisión sigue sin autocompletar.
  Endpoint HTTP: `GET /facturacion/padron/<cuit>`; el modal de facturación tiene
  un botón "Traer de ARCA" que lo consume. Para probar por CLI:
  `manage.py probar_padron <cuit> [--raw]`.
- **PDF** (`services/pdf.py`): comprobante con CAE + QR de ARCA (weasyprint).
- **Ambiente**: `AFIP_ENV` (`homologacion` | `produccion`) — **flag independiente de
  la rama git**. Cambia URLs y directorio de claves (`keys/<ambiente>/`) a la vez.
- **Emisión**: `POST /facturacion/emitir` desde el modal del pedido. Receptor puede
  ser *consumidor final* (doc 99) o *identificado* (CUIT/CUIL/DNI + condición IVA).
- Datos del emisor y URLs por ambiente en `Cotizador/settings.py` (`AFIP`,
  `AFIP_EMISOR`, `AFIP_URLS`).

Comando de prueba: `manage.py probar_arca`.

---

## 6. Endpoints / URLs notables

- `/pedidos/v2` — **tabla de pedidos vigente** (v2, aceptada y en uso).
- `/pedidos/` — versión vieja, mantenida como respaldo (candidata a retirar).
- `/pedidos/completarPedido`, `/pedidos/confirmarPedido` — alta de pedido.
- `/pedidos/cambiarEstado`, `.../cambiarEncargado`, `.../agregarSenia` — ediciones
  (todas redirigen a `/pedidos/v2` al terminar).
- `/facturacion/contexto/<pedido>`, `/facturacion/emitir`,
  `/facturacion/comprobantes`, `/facturacion/comprobante/<id>/pdf`.
- `/productos/obtenerCategorias`, `/productos/productosPorCategoria/<id>`,
  `/productos/obtenerDimensiones/<id>`, `/productos/resolverTier`.

---

## 7. Configuración por entorno (`.env`)

Se lee con django-environ (`environ.Env.read_env()`). Claves relevantes:

| Variable | Uso |
|----------|-----|
| `AFIP_ENV` | `homologacion` / `produccion`. |
| `AFIP_CUIT`, `AFIP_PUNTO_VENTA` | CUIT emisor y punto de venta. |
| `AFIP_CERT_PATH`, `AFIP_KEY_PATH` | Override de la ubicación de cert/clave (por defecto `keys/<ambiente>/`). |
| `AFIP_RAZON_SOCIAL`, `AFIP_NOMBRE_FANTASIA`, `AFIP_DOMICILIO`, `AFIP_CONDICION_IVA`, `AFIP_INGRESOS_BRUTOS`, `AFIP_INICIO_ACTIVIDADES` | Datos del emisor para el PDF. |

---

## 8. Ramas y despliegue

- **`main`** — producción. **`staging`** — pruebas. **`feature/facturacion`** —
  desarrollo de la facturación ARCA (rama activa al momento de escribir esto).
- Despliegue de **respaldo** en VM Oracle (`easyprint1.duckdns.org`, 157.151.9.45),
  temporal mientras el hosting principal (PythonAnywhere) está caído. Ver
  [`../DEPLOY_ORACLE.md`](../DEPLOY_ORACLE.md).

---

## 9. Gotchas conocidos (leer antes de tocar)

- **`Cliente.cuit` es `IntegerField`** → se desborda en Postgres (un CUIT de 11
  dígitos supera int32). Migrar a `BigIntegerField`/`CharField` **antes** de usarlo
  en producción con Postgres para facturación.
- **Números AR**: ver §4 y `CLAUDE.md`. Fuente #1 de bugs.
- **Stock de insumos**: se guarda en *unidad de compra*; el usuario ve/ingresa
  *stock real* (unidad de uso). No redondear en el modelo (`stock_real()` se usa en
  la lógica de consumo). Detalle en `CLAUDE.md`.
- **Import de insumos por Excel**: usa `nombre__iexact` para no duplicar. "Borrar
  lista de insumos" corta el vínculo con productos por CASCADE.
- **Templates/static centralizados** en `core/`, no en cada app (ver §1).
- **Selects encadenados** categoría→producto en el form de cotización: la lógica
  vive en `core/js/cotizacion.js` y depende de eventos `change` nativos. Cualquier
  cambio (p. ej. Select2) debe re-disparar `change` para no romper el encadenado.

---

## 10. Historial de cambios

Ver [`Changelog.txt`](Changelog.txt) (versionado propio, actualmente serie v3.x) y
`Correcciones y mejoras.txt` para el backlog informal.
</content>
</invoke>
