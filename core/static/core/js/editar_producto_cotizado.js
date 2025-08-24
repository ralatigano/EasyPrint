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
  esPrecioArbitrario: false
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
  precioInput.value = parseFloat(data.precio);
  descuentoInput.value = data.descuento || 0;
  tiempoInput.value = data.tiempo_estimado || 0;
  empaquetadoCheckbox.checked = data.empaquetado || false;
  precioArbCheckbox.checked = data.precio_arbitrario || false;

  nuevoPrecioSpan.textContent = `$ ${formatearNumero(data.precio)}`;

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

  tiempoInput.addEventListener('input', actualizarVista);
  descuentoInput.addEventListener('input', actualizarVista);
  empaquetadoCheckbox.addEventListener('change', actualizarVista);

  nuevoPrecioSpan.textContent = `$ ${formatearNumero(data.resultado)}`;
  nuevoPrecioSpan.setAttribute('title', 'Precio cotizado originalmente con descuento aplicado.');

  precioArbCheckbox.addEventListener('change', function () {
    CotizacionEditor.esPrecioArbitrario = this.checked;
      if (this.checked) {
        precioInput.removeAttribute('readonly');
      } else {
        precioInput.setAttribute('readonly', true);
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
  const tiempoNuevo = parseFloat(tiempoInput.value) || 0;
  const descuentoNuevo = parseFloat(descuentoInput.value) || 0;
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

function actualizarVista() {
  const nuevoPrecioSpan = document.getElementById('nuevo_precio_calculado');
  const resultadoInput = document.getElementById('resultado_calculado');

  if (CotizacionEditor.esPrecioArbitrario) {
    const precioManual = parseFloat(precioInput.value) || 0;
    nuevoPrecioSpan.textContent = `$ ${formatearNumero(precioManual)}`;
    resultadoInput.value = precioManual.toFixed(2);
    nuevoPrecioSpan.setAttribute('title', 'Precio arbitrario definido por el usuario. No se aplican cálculos.');
    return;
  }

  const nuevoPrecio = calcularPrecioFinal();
  resultadoInput.value = nuevoPrecio.toFixed(2);
  nuevoPrecioSpan.textContent = `$ ${formatearNumero(nuevoPrecio)}`;
  nuevoPrecioSpan.setAttribute('title', generarResumenTooltip());
  //precioInput.value = nuevoPrecio.toFixed(2);
}

function generarResumenTooltip() {
  if (CotizacionEditor.esPrecioArbitrario) {
    return 'Precio arbitrario definido por el usuario. No se aplican cálculos.';
  }

  const tiempoNuevo = parseFloat(tiempoInput.value) || 0;
  const descuentoNuevo = parseFloat(descuentoInput.value) || 0;
  const empaquetadoNuevo = empaquetadoCheckbox.checked;

  const deltaTiempo = tiempoNuevo - CotizacionEditor.tiempoOriginal;
  const deltaManoObra = deltaTiempo * CotizacionEditor.precioHora;

  const deltaEmpaquetado = (empaquetadoNuevo !== CotizacionEditor.empaquetadoOriginal)
    ? (empaquetadoNuevo ? CotizacionEditor.precioEmpaquetado : -CotizacionEditor.precioEmpaquetado)
    : 0;

  const precioBase = CotizacionEditor.precioBase;
  const subtotal = precioBase + deltaManoObra + deltaEmpaquetado;
  const total = subtotal * (1 - descuentoNuevo / 100);

  return `  Base: $${formatearNumero(precioBase)}
  Mano de obra (${tiempoNuevo} hs): $${formatearNumero(deltaManoObra)}
  Empaquetado: $${formatearNumero(deltaEmpaquetado)}
  Descuento: -${formatearNumero(descuentoNuevo)}%
  Total: $${formatearNumero(total)}`;
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

  // Limpiar campos del DOM
  infoAdicionalInput.value = '';
  precioInput.value = '';
  descuentoInput.value = '';
  tiempoInput.value = '';
  empaquetadoCheckbox.checked = false;
  precioArbCheckbox.checked = false;
  nuevoPrecioSpan.textContent = '$ —';
  nuevoPrecioSpan.setAttribute('title', '');
}
