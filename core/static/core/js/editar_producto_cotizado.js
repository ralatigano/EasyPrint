// Referencias a elementos del DOM
const nombreProductoSpan = document.getElementById('nombre_producto_editar');
const infoAdicionalInput = document.getElementById('info_adicional_editar');
const precioInput = document.getElementById('precio_editar');
const descuentoInput = document.getElementById('descuento_editar');
const tiempoInput = document.getElementById('tiempo_editar');
const empaquetadoCheckbox = document.getElementById('empaquetado_editar');
const precioArbCheckbox = document.getElementById('precio_arb_checkbox');
const nuevoPrecioSpan = document.getElementById('nuevo_precio_calculado');
const idInput = document.getElementById('id_producto_editar');

document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('editarProductoPresupuestoModal');
    modal.addEventListener('show.bs.modal', function (event) {
    resetEditor();
    const button = event.relatedTarget;
    const productoId = button.getAttribute('data-bs-whatever');
    idInput.value = productoId;

    cargarProductoCotizado(productoId); // ← delegás todo
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
  precioHora: 0,
  precioEmpaquetado: 0,
  tiempoOriginal: 0,
  descuentoOriginal: 0,
  empaquetadoOriginal: false,
  esPrecioArbitrario: false,
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
  tiempoInput.value = _arNum(data.tiempo_estimado || 0);
  empaquetadoCheckbox.checked = data.empaquetado || false;
  precioArbCheckbox.checked = data.precio_arbitrario || false;

  nuevoPrecioSpan.textContent = `$ ${formatearNumeroLocal(data.precio)}`;

  inicializarEditor(data);
}

// 3. Inicializar estado y listeners
function inicializarEditor(data) {
  CotizacionEditor.precioBase = parseFloat(data.precio) || 0;
  CotizacionEditor.resultadoOriginal = parseFloat(data.resultado) || 0;
  CotizacionEditor.precioHora = parseFloat(data.precio_hora) || 0;
  CotizacionEditor.precioEmpaquetado = parseFloat(data.precio_empaquetado) || 0;
  CotizacionEditor.tiempoOriginal = parseFloat(data.tiempo_estimado) || 0;
  CotizacionEditor.empaquetadoOriginal = Boolean(data.empaquetado);
  CotizacionEditor.descuentoOriginal = parseFloat(data.descuento) || 0;
  CotizacionEditor.esPrecioArbitrario = Boolean(data.precio_arbitrario);
  CotizacionEditor.cantidad = parseFloat(data.cantidad) || 0;
  CotizacionEditor.precioSugerido = parseFloat(data.precio_sugerido) || 0;
  CotizacionEditor.pisoAbsoluto = parseFloat(data.piso_absoluto) || 0;
  CotizacionEditor.pisoAbsorcion = parseFloat(data.piso_absorcion) || 0;

  tiempoInput.addEventListener('input', actualizarVista);
  descuentoInput.addEventListener('input', actualizarVista);
  empaquetadoCheckbox.addEventListener('change', actualizarVista);

  nuevoPrecioSpan.textContent = `$ ${formatearNumeroLocal(data.resultado)}`;
  nuevoPrecioSpan.setAttribute('title', 'Precio cotizado originalmente con descuento aplicado.');

  precioArbCheckbox.addEventListener('change', function () {
    CotizacionEditor.esPrecioArbitrario = this.checked;
      if (this.checked) {
        precioInput.removeAttribute('readonly');
        // Quitar el "$" y dejar el número en formato AR: así se edita sin romper
        // el parseo (el "$" hacía que el semáforo no calculara).
        precioInput.value = formatearNumeroLocal(_parsePrecio(precioInput.value));
      } else {
        precioInput.setAttribute('readonly', true);
        precioInput.value = `$ ${formatearNumeroLocal(_parsePrecio(precioInput.value))}`;
      }
      actualizarVista();
    });
    precioInput.addEventListener('input', () => {
      if (CotizacionEditor.esPrecioArbitrario) {
        actualizarVista(); // actualiza el span y el tooltip
      }
    });
}

// 4. Cálculo reactivo
function calcularPrecioFinal() {
  const tiempoNuevo = parsearDecimalFlexible(tiempoInput.value);
  const descuentoNuevo = parsearDecimalFlexible(descuentoInput.value);
  const empaquetadoNuevo = empaquetadoCheckbox.checked;
  const subtotalInput = document.getElementById('subtotal_calculado');

  const tiempoOriginal = CotizacionEditor.tiempoOriginal;
  const empaquetadoOriginal = CotizacionEditor.empaquetadoOriginal;

  const deltaTiempo = tiempoNuevo - tiempoOriginal;
  const deltaManoObra = deltaTiempo * CotizacionEditor.precioHora;

  const deltaEmpaquetado = (empaquetadoNuevo !== empaquetadoOriginal)
    ? (empaquetadoNuevo ? CotizacionEditor.precioEmpaquetado : -CotizacionEditor.precioEmpaquetado)
    : 0;

  const nuevoBruto = CotizacionEditor.precioBase + deltaManoObra + deltaEmpaquetado;
  subtotalInput.value = nuevoBruto.toFixed(2);

  const precioFinal = nuevoBruto * (1 - descuentoNuevo / 100);

  return precioFinal;
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
  const resultadoInput = document.getElementById('resultado_calculado');

  if (CotizacionEditor.esPrecioArbitrario) {
    const precioManual = _parsePrecio(precioInput.value);
    nuevoPrecioSpan.textContent = `$ ${formatearNumeroLocal(precioManual)}`;
    resultadoInput.value = precioManual.toFixed(2);
    nuevoPrecioSpan.setAttribute('title', 'Precio arbitrario definido por el usuario. No se aplican cálculos.');
    actualizarSemaforo(precioManual);
    return;
  }

  const nuevoPrecio = calcularPrecioFinal();
  resultadoInput.value = nuevoPrecio.toFixed(2);
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
  if (CotizacionEditor.esPrecioArbitrario) {
    return 'Precio arbitrario definido por el usuario. No se aplican cálculos.';
  }

  const tiempoNuevo = parsearDecimalFlexible(tiempoInput.value);
  const descuentoNuevo = parsearDecimalFlexible(descuentoInput.value);
  const empaquetadoNuevo = empaquetadoCheckbox.checked;

  const deltaTiempo = tiempoNuevo - CotizacionEditor.tiempoOriginal;
  const deltaManoObra = deltaTiempo * CotizacionEditor.precioHora;

  const deltaEmpaquetado = (empaquetadoNuevo !== CotizacionEditor.empaquetadoOriginal)
    ? (empaquetadoNuevo ? CotizacionEditor.precioEmpaquetado : -CotizacionEditor.precioEmpaquetado)
    : 0;

  const precioBase = CotizacionEditor.precioBase;
  const subtotal = precioBase + deltaManoObra + deltaEmpaquetado;
  const total = subtotal * (1 - descuentoNuevo / 100);

  return `  Base: $${formatearNumeroLocal(precioBase)}
  Mano de obra (${tiempoNuevo} hs): $${formatearNumeroLocal(deltaManoObra)}
  Empaquetado: $${formatearNumeroLocal(deltaEmpaquetado)}
  Descuento: -${formatearNumeroLocal(descuentoNuevo)}%
  Total: $${formatearNumeroLocal(total)}`;
}

function resetEditor() {
  // Limpiar estado interno
  CotizacionEditor.precioBase = 0;
  CotizacionEditor.resultadoOriginal = 0;
  CotizacionEditor.precioHora = 0;
  CotizacionEditor.precioEmpaquetado = 0;
  CotizacionEditor.tiempoOriginal = 0;
  CotizacionEditor.empaquetadoOriginal = false;
  CotizacionEditor.descuentoOriginal = 0;
  CotizacionEditor.esPrecioArbitrario = false;
  CotizacionEditor.cantidad = 0;
  CotizacionEditor.precioSugerido = 0;
  CotizacionEditor.pisoAbsoluto = 0;
  CotizacionEditor.pisoAbsorcion = 0;

  // Limpiar campos del DOM
  infoAdicionalInput.value = '';
  precioInput.value = '';
  descuentoInput.value = '';
  tiempoInput.value = '';
  empaquetadoCheckbox.checked = false;
  precioArbCheckbox.checked = false;
  nuevoPrecioSpan.textContent = '$ —';
  nuevoPrecioSpan.setAttribute('title', '');

  // Ocultar semáforo y headroom (Fase 4)
  document.getElementById('semaforoPrecio')?.classList.add('d-none');
  document.getElementById('headroomPrecio')?.classList.add('d-none');
}
