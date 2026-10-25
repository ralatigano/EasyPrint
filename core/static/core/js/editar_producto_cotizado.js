// Referencias a elementos del DOM
const nombreProductoSpan = document.getElementById('nombre_producto_editar');
const infoAdicionalInput = document.getElementById('info_adicional_editar');
const precioInput = document.getElementById('precio_editar');
const descuentoInput = document.getElementById('descuento_editar');
const empaquetadoCheckbox = document.getElementById('empaquetado_editar');
const precioManualCheckbox = document.getElementById('precio_manual');
const nuevoPrecioSpan = document.getElementById('nuevo_precio_calculado');
const idInput = document.getElementById('id_producto_editar');

const _TOOLTIP_PRECIO_MANUAL =
  'Precio puesto a mano por el usuario. No se aplican cálculos.';

document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('editarProductoPresupuestoModal');
    modal.addEventListener('show.bs.modal', function (event) {
    resetEditor();
    const button = event.relatedTarget;
    const productoId = button.getAttribute('data-bs-whatever');
    idInput.value = productoId;

    cargarProductoCotizado(productoId); // ← delegás todo
    });

    // Listeners una sola vez: antes se registraban dentro de inicializarEditor,
    // así que cada apertura del modal sumaba otro handler sobre los mismos campos.
    descuentoInput.addEventListener('input', actualizarVista);
    empaquetadoCheckbox.addEventListener('change', actualizarVista);
    precioManualCheckbox.addEventListener('change', function () {
        aplicarModoPrecioManual(this.checked);
        actualizarVista();
    });
    precioInput.addEventListener('input', () => {
        if (CotizacionEditor.esPrecioManual) {
            actualizarVista(); // actualiza el span y el tooltip
        }
    });

    const nuevoPrecioSpan = document.getElementById('nuevo_precio_calculado');
    const tooltip = new bootstrap.Tooltip(nuevoPrecioSpan, {
        title: generarResumenTooltip(),
        placement: 'top',
        trigger: 'hover'
    });

    // Si querés actualizar el contenido dinámicamente:
    nuevoPrecioSpan.addEventListener('mouseenter', () => {
        tooltip.setContent({ '.tooltip-inner': generarResumenTooltip() });
    });

});

// Estado global
const CotizacionEditor = {
  precioBase: 0,
  precioEmpaquetado: 0,
  descuentoOriginal: 0,
  empaquetadoOriginal: false,
  esPrecioManual: false,
  // Snapshots para el semáforo (Fase 4)
  cantidad: 0,
  precioSugerido: 0,
  pisoAbsoluto: 0,
  pisoAbsorcion: 0
};

// 1. Entrada principal: se llama al abrir el modal
function cargarProductoCotizado(productoId) {
  fetch(`/presupuestos/infoProductoCotizado/${productoId}/`)
    .then(response => {
      if (!response.ok) throw new Error('Error al obtener datos del producto');
      return response.json();
    })
    .then(data => {
      mostrarModal(data);
    })
    .catch(error => {
      console.error('Error al cargar producto:', error);
      // Podés mostrar un toast o alerta si querés
    });
}

// 2. Poblar campos del modal
function mostrarModal(data) {
  const nombreProductoSpan = document.getElementById('nombre_producto_editar');
  nombreProductoSpan.textContent = data.producto_nombre;
  infoAdicionalInput.value = data.info_adicional || '';
  precioInput.value = `$ ${formatearNumeroLocal(data.precio)}`;
  // Precarga en formato AR (coma decimal), consistente con el resto de los campos.
  descuentoInput.value = _arNum(data.descuento || 0);
  empaquetadoCheckbox.checked = data.empaquetado || false;
  precioManualCheckbox.checked = Boolean(data.precio_manual);
  // Tildar por código no dispara el evento 'change': aplicar el modo a mano,
  // si no el precio de un ítem ya fijado a mano queda bloqueado.
  aplicarModoPrecioManual(precioManualCheckbox.checked);

  nuevoPrecioSpan.textContent = `$ ${formatearNumeroLocal(data.precio)}`;

  inicializarEditor(data);
}

// 3. Inicializar estado y listeners
function inicializarEditor(data) {
  CotizacionEditor.precioBase = parseFloat(data.precio) || 0;
  CotizacionEditor.resultadoOriginal = parseFloat(data.resultado) || 0;
  CotizacionEditor.precioEmpaquetado = parseFloat(data.precio_empaquetado) || 0;
  CotizacionEditor.empaquetadoOriginal = Boolean(data.empaquetado);
  CotizacionEditor.descuentoOriginal = parseFloat(data.descuento) || 0;
  CotizacionEditor.esPrecioManual = Boolean(data.precio_manual);
  CotizacionEditor.cantidad = parseFloat(data.cantidad) || 0;
  CotizacionEditor.precioSugerido = parseFloat(data.precio_sugerido) || 0;
  CotizacionEditor.pisoAbsoluto = parseFloat(data.piso_absoluto) || 0;
  CotizacionEditor.pisoAbsorcion = parseFloat(data.piso_absorcion) || 0;

  nuevoPrecioSpan.textContent = `$ ${formatearNumeroLocal(data.resultado)}`;
  nuevoPrecioSpan.setAttribute('title', CotizacionEditor.esPrecioManual
    ? _TOOLTIP_PRECIO_MANUAL
    : 'Precio cotizado originalmente con descuento aplicado.');
}

/** Pasa el input de precio a editable (precio a mano) o a solo-lectura. */
function aplicarModoPrecioManual(activo) {
  CotizacionEditor.esPrecioManual = activo;
  // Sin el "$": así se edita sin romper el parseo (el "$" hacía que el semáforo
  // no calculara).
  const valor = formatearNumeroLocal(_parsePrecio(precioInput.value));
  if (activo) {
    precioInput.removeAttribute('readonly');
    precioInput.value = valor;
  } else {
    precioInput.setAttribute('readonly', true);
    precioInput.value = `$ ${valor}`;
  }
}

// 4. Cálculo reactivo (solo para mostrar: el precio que se guarda lo
//    recalcula el servidor en editar_producto_cotizado)
function calcularPrecioFinal() {
  const descuentoNuevo = parsearDecimalFlexible(descuentoInput.value);
  const empaquetadoNuevo = empaquetadoCheckbox.checked;

  const deltaEmpaquetado = (empaquetadoNuevo !== CotizacionEditor.empaquetadoOriginal)
    ? (empaquetadoNuevo ? CotizacionEditor.precioEmpaquetado : -CotizacionEditor.precioEmpaquetado)
    : 0;

  const nuevoBruto = CotizacionEditor.precioBase + deltaEmpaquetado;

  return nuevoBruto * (1 - descuentoNuevo / 100);
}

// Parseo robusto de un precio en formato AR, tolerante a "$" y espacios.
// (parsearNumeroLocal por sí solo no descarta el símbolo de moneda.)
function _parsePrecio(v) {
  return parsearNumeroLocal(String(v).replace(/\$/g, '').trim());
}

// Muestra un número en formato AR simple (coma decimal), sin forzar decimales.
function _arNum(v) {
  return String(v).replace('.', ',');
}

function actualizarVista() {
  const nuevoPrecioSpan = document.getElementById('nuevo_precio_calculado');

  if (CotizacionEditor.esPrecioManual) {
    const precioManual = _parsePrecio(precioInput.value);
    nuevoPrecioSpan.textContent = `$ ${formatearNumeroLocal(precioManual)}`;
    nuevoPrecioSpan.setAttribute('title', _TOOLTIP_PRECIO_MANUAL);
    actualizarSemaforo(precioManual);
    return;
  }

  const nuevoPrecio = calcularPrecioFinal();
  nuevoPrecioSpan.textContent = `$ ${formatearNumeroLocal(nuevoPrecio)}`;
  nuevoPrecioSpan.setAttribute('title', generarResumenTooltip());
  actualizarSemaforo(nuevoPrecio);
  //precioInput.value = nuevoPrecio.toFixed(2);
}

// --- Semáforo de precio y headroom (Fase 4 / 4.1) -------------------------
// Compara el precio final contra los pisos y el sugerido (snapshots del momento
// de cotizar). Es informativo: NUNCA bloquea. El headroom aparece atado al precio
// que el vendedor está poniendo (capacidad de negociación a pedido, no un empujón
// a descontar).
const _ZONAS_PRECIO = {
  verde:   { color: '#198754', texto: 'Con este precio cubrís material, estructura y tu margen objetivo.' },
  amarillo:{ color: '#ffc107', texto: 'Con este precio cubrís material y estructura pero NO el margen objetivo. Estás resignando ganancia.' },
  naranja: { color: '#fd7e14', texto: 'Con este precio cubrís material pero no tu estructura. Estás trabajando gratis.' },
  rojo:    { color: '#dc3545', texto: 'Con este precio no cubrís nada.' },
};

function actualizarSemaforo(precio) {
  const cont = document.getElementById('semaforoPrecio');
  const headroom = document.getElementById('headroomPrecio');
  const { precioSugerido, pisoAbsoluto, pisoAbsorcion } = CotizacionEditor;

  // Sin snapshots (cotización vieja anterior a la Fase 3) o precio inválido: ocultar.
  if (!isFinite(precio) || (precioSugerido <= 0 && pisoAbsorcion <= 0 && pisoAbsoluto <= 0)) {
    cont.classList.add('d-none');
    headroom.classList.add('d-none');
    return;
  }

  // El número entre paréntesis es el precio a copiar en el input para quedar
  // justo en ese umbral.
  let zona, faltaTxt;
  if (precio >= precioSugerido) {
    zona = 'verde';
    faltaTxt = `Estás $ ${formatearNumeroLocal(precio - precioSugerido)} por encima del sugerido (precio = $ ${formatearNumeroLocal(precioSugerido)}).`;
  } else if (precio >= pisoAbsorcion) {
    zona = 'amarillo';
    faltaTxt = `Faltan $ ${formatearNumeroLocal(precioSugerido - precio)} para el precio sugerido (precio = $ ${formatearNumeroLocal(precioSugerido)}).`;
  } else if (precio >= pisoAbsoluto) {
    zona = 'naranja';
    faltaTxt = `Faltan $ ${formatearNumeroLocal(pisoAbsorcion - precio)} para cubrir la estructura (precio = $ ${formatearNumeroLocal(pisoAbsorcion)}).`;
  } else {
    zona = 'rojo';
    faltaTxt = `Faltan $ ${formatearNumeroLocal(pisoAbsoluto - precio)} para no perder plata (precio = $ ${formatearNumeroLocal(pisoAbsoluto)}).`;
  }

  const info = _ZONAS_PRECIO[zona];
  document.getElementById('semaforoDot').style.backgroundColor = info.color;
  const txtEl = document.getElementById('semaforoTexto');
  txtEl.textContent = info.texto;
  txtEl.style.color = info.color;
  document.getElementById('semaforoDetalle').textContent = faltaTxt;
  cont.classList.remove('d-none');

  // Headroom (4.1): cuánto descuento se puede aplicar antes de cada piso. Es
  // capacidad a pedido: solo se muestra el margen que realmente existe.
  const hastaAbsorcion = precio - pisoAbsorcion;
  const hastaNoPerder = precio - pisoAbsoluto;
  const descPct = (piso) => precio > 0 ? formatearNumeroLocal((precio - piso) / precio * 100) : '0';

  const lineas = [];
  if (hastaAbsorcion > 0) {
    lineas.push(`Podés aplicar un descuento de hasta ${descPct(pisoAbsorcion)}% (precio = $ ${formatearNumeroLocal(pisoAbsorcion)}) y aún cubrirías tu estructura.`);
  }
  if (hastaNoPerder > 0) {
    lineas.push(`Podés aplicar un descuento de hasta ${descPct(pisoAbsoluto)}% (precio = $ ${formatearNumeroLocal(pisoAbsoluto)}) si querés vender al costo.`);
  }

  if (lineas.length) {
    headroom.innerHTML = lineas.join('<br>');
    headroom.classList.remove('d-none');
  } else {
    headroom.classList.add('d-none');
  }
}

function generarResumenTooltip() {
  if (CotizacionEditor.esPrecioManual) {
    return _TOOLTIP_PRECIO_MANUAL;
  }

  const descuentoNuevo = parsearDecimalFlexible(descuentoInput.value);
  const empaquetadoNuevo = empaquetadoCheckbox.checked;

  const deltaEmpaquetado = (empaquetadoNuevo !== CotizacionEditor.empaquetadoOriginal)
    ? (empaquetadoNuevo ? CotizacionEditor.precioEmpaquetado : -CotizacionEditor.precioEmpaquetado)
    : 0;

  const precioBase = CotizacionEditor.precioBase;
  const subtotal = precioBase + deltaEmpaquetado;
  const total = subtotal * (1 - descuentoNuevo / 100);

  return `  Base: $${formatearNumeroLocal(precioBase)}
  Empaquetado: $${formatearNumeroLocal(deltaEmpaquetado)}
  Descuento: -${formatearNumeroLocal(descuentoNuevo)}%
  Total: $${formatearNumeroLocal(total)}`;
}

function resetEditor() {
  // Limpiar estado interno
  CotizacionEditor.precioBase = 0;
  CotizacionEditor.resultadoOriginal = 0;
  CotizacionEditor.precioEmpaquetado = 0;
  CotizacionEditor.empaquetadoOriginal = false;
  CotizacionEditor.descuentoOriginal = 0;
  CotizacionEditor.esPrecioManual = false;
  CotizacionEditor.cantidad = 0;
  CotizacionEditor.precioSugerido = 0;
  CotizacionEditor.pisoAbsoluto = 0;
  CotizacionEditor.pisoAbsorcion = 0;

  // Limpiar campos del DOM
  infoAdicionalInput.value = '';
  precioInput.value = '';
  descuentoInput.value = '';
  empaquetadoCheckbox.checked = false;
  precioManualCheckbox.checked = false;
  // El ítem anterior pudo dejar el precio editable.
  precioInput.setAttribute('readonly', true);
  nuevoPrecioSpan.textContent = '$ —';
  nuevoPrecioSpan.setAttribute('title', '');

  // Ocultar semáforo y headroom (Fase 4)
  document.getElementById('semaforoPrecio')?.classList.add('d-none');
  document.getElementById('headroomPrecio')?.classList.add('d-none');
}
