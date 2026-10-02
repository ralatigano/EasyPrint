// ── DataTable ─────────────────────────────────────────────────────────────────
let dataTable;
let dataTableIsInitilized = false;

const initDataTable = async () => {
    if (dataTableIsInitilized) { dataTable.destroy(); }
    dataTable = $("#Pedidos").DataTable({
        order: [[1, 'desc']],
        responsive: false,
        // Conserva página/orden/búsqueda entre recargas (p. ej. al volver de editar
        // un pedido, que redirige a /pedidos/v2). stateDuration -1 = sessionStorage.
        stateSave: true,
        stateDuration: -1,
        columnDefs: [
            { orderable: false, responsivePriority: 99, targets: 0 }, // checkbox
            { responsivePriority: 1,  targets: 1 }, // Número
            { responsivePriority: 2,  targets: 2 }, // Cliente
            { responsivePriority: 3,  targets: 3 }, // Productos
            { responsivePriority: 4,  targets: 4 }, // Estado
            { responsivePriority: 5,  targets: 5 }, // Encargado
            { responsivePriority: 6,  targets: 6 }, // Observaciones
            { responsivePriority: 7,  targets: 7 }, // Saldo
            { responsivePriority: 8,  targets: 8 }, // Fecha entrega
            { orderable: false, responsivePriority: 99, targets: 9 }, // chevron
            { targets: [7], className: 'text-nowrap' },
        ],
        language: {
            lengthMenu:     'Mostrar _MENU_ pedidos por página',
            zeroRecords:    'No hay pedidos registrados',
            info:           'Mostrando de _START_ a _END_ de _TOTAL_ pedidos',
            infoEmpty:      'No hay pedidos',
            InfoFiltered:   '(filtrado de _MAX_ pedidos totales)',
            search:         'Buscar:',
            LoadingRecords: 'Cargando...',
            paginate: { first: 'Primero', last: 'Ultimo', next: 'Siguiente', previous: 'Anterior' }
        }
    });
    dataTableIsInitilized = true;
};

window.addEventListener("load", async () => {
    const buscarNumero = sessionStorage.getItem('pedidos_buscar');
    if (buscarNumero) {
        sessionStorage.removeItem('pedidos_buscar');
        window._buscarPedido = buscarNumero;
    }
    await initDataTable();
    if (window._buscarPedido) {
        dataTable.search(String(window._buscarPedido)).draw();
        delete window._buscarPedido;
    }
    restaurarFiltros();
    document.getElementById("nav_item_pedidos").style.fontWeight = "bold";
});

// ── Filas expandibles ─────────────────────────────────────────────────────────

function escAttr(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatMonto(val) {
    const n = parseFloat(val) || 0;
    return n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function buildDetailHtml(tr) {
    const d = tr.dataset;
    const cancelado = d.esCancelado === 'true';
    const dis = cancelado ? 'disabled' : '';
    const esGerencia = document.getElementById('js_es_gerencia')?.dataset.value === 'true';

    const saldoStyle = parseFloat(d.saldo) > 0 ? 'saldo-pendiente' : '';

    const obsHtml = d.descripcion
        ? `<span class="detail-obs-text">${escAttr(d.descripcion)}</span>`
        : `<span class="detail-obs-text text-muted" style="font-style:italic;">Sin observaciones</span>`;

    const deleteBtn = esGerencia ? `
        <a href="/pedidos/eliminarPedido/${escAttr(d.numero)}"
           class="btn btn-danger btn-xs btnEliminacion"
           data-tipo="pedido"
           data-fetch-url="/pedidos/obtenerDatosProductos?pedido_numero=${escAttr(d.numero)}&presupuesto_id=${escAttr(d.presupuesto)}"
           title="Eliminar pedido"
           style="grid-column:1/-1;">
            <i class="fa-solid fa-trash-can"></i> Eliminar pedido
        </a>` : '';

    return `
        <div class="detail-card">

            <div class="detail-section">
                <div class="detail-metric">
                    <span class="detail-metric-label">Total del pedido</span>
                    <span class="detail-metric-value">$ ${formatMonto(d.total)}</span>
                </div>
                <div class="detail-metric">
                    <span class="detail-metric-label">Cobrado</span>
                    <span class="detail-metric-value">$ ${formatMonto(d.senia)}</span>
                </div>
                <div class="detail-metric">
                    <span class="detail-metric-label">Saldo pendiente</span>
                    <span class="detail-metric-value ${saldoStyle}">$ ${formatMonto(d.saldo)}</span>
                </div>
            </div>

            <div class="detail-section">
                <span class="detail-metric-label">Observaciones completas</span>
                ${obsHtml}
            </div>

            <div class="detail-section">
                <div class="action-grid">
                    <button type="button" class="btn btn-dark btn-xs" ${dis}
                            data-bs-toggle="modal" data-bs-target="#cambiarEstadoModal"
                            data-bs-whatever="${escAttr(d.numero)}|${escAttr(d.estado)}">
                        <i class="fa-solid fa-arrows-rotate"></i> Cambiar estado
                    </button>
                    <button type="button" class="btn btn-dark btn-xs" ${dis}
                            data-bs-toggle="modal" data-bs-target="#cambiarEncargadoModal"
                            data-bs-whatever="${escAttr(d.numero)}">
                        <i class="fa-solid fa-user-pen"></i> Cambiar encargado
                    </button>
                    <button type="button" class="btn btn-dark btn-xs"
                            data-bs-toggle="modal" data-bs-target="#agregarDescripcionModal"
                            data-bs-whatever="${escAttr(d.numero)}|${escAttr(d.descripcion)}">
                        <i class="fa-solid fa-pencil"></i> Editar observación
                    </button>
                    <button type="button" class="btn btn-dark btn-xs" ${dis}
                            data-bs-toggle="modal" data-bs-target="#registrarPagoModal"
                            data-bs-whatever="${escAttr(d.numero)}">
                        <i class="fa-solid fa-dollar-sign"></i> Registrar pago
                    </button>
                    <button type="button" class="btn btn-dark btn-xs"
                            data-bs-toggle="modal" data-bs-target="#cambiarClienteModal"
                            data-bs-whatever="${escAttr(d.clienteId)}|${escAttr(d.clienteRef)}|${escAttr(d.numero)}|${escAttr(d.presupuesto)}">
                        <i class="fa-solid fa-user"></i> Cambiar cliente
                    </button>
                    <button type="button" class="btn btn-success btn-xs" ${dis}
                            data-bs-toggle="modal" data-bs-target="#facturarModal"
                            data-bs-whatever="${escAttr(d.numero)}|${escAttr(d.total)}">
                        <i class="fa-solid fa-file-invoice-dollar"></i> Facturar
                    </button>
                    ${deleteBtn}
                </div>
            </div>

        </div>`;
}

$(document).on('click', '#Pedidos tbody tr.main-row', function (e) {
    if (e.target.closest('input[type="checkbox"]') ||
        e.target.closest('.btn') ||
        e.target.closest('a') ||
        e.target.closest('.estado-trigger')) return;

    const row = dataTable.row(this);
    const chevron = this.querySelector('.chevron-icon');
    const isOpen = row.child.isShown();

    if (isOpen) {
        row.child.hide();
        $(this).removeClass('expanded');
        chevron.classList.remove('open');
    } else {
        row.child(buildDetailHtml(this)).show();
        $(this).addClass('expanded');
        chevron.classList.add('open');
    }
});

// ── Modales ───────────────────────────────────────────────────────────────────

const cambiarEstadoModal = document.getElementById('cambiarEstadoModal');
cambiarEstadoModal.addEventListener('show.bs.modal', event => {
    const button = event.relatedTarget;
    // data-bs-whatever = "numero|estadoActual" (el estado puede venir vacío).
    const partes = (button.getAttribute('data-bs-whatever') || '').split('|');
    const numero = partes[0];
    const estadoActual = partes[1] || '';
    cambiarEstadoModal.querySelector('.modal-title-estado').textContent = `Nuevo estado para el pedido: ${numero}`;
    document.getElementById('cambiarPedido_estado').value = numero;

    // Pre-seleccionar el pill del estado actual (y sincronizar el input oculto).
    const hidden = document.getElementById('estado');
    hidden.value = '';
    cambiarEstadoModal.querySelectorAll('.estado-option').forEach(pill => {
        const activo = pill.dataset.estado === estadoActual;
        pill.classList.toggle('selected', activo);
        if (activo) hidden.value = estadoActual;
    });
    configurarCobroEstadoIndividual();
});

// Selección de estado por pill.
cambiarEstadoModal.querySelectorAll('.estado-option').forEach(pill => {
    pill.addEventListener('click', function () {
        document.getElementById('estado').value = this.dataset.estado;
        configurarCobroEstadoIndividual();
        cambiarEstadoModal.querySelectorAll('.estado-option')
            .forEach(p => p.classList.toggle('selected', p === this));
    });
});

const cambiarEncargadoModal = document.getElementById('cambiarEncargadoModal');
cambiarEncargadoModal.addEventListener('show.bs.modal', event => {
    const button = event.relatedTarget;
    const recipient = button.getAttribute('data-bs-whatever');
    cambiarEncargadoModal.querySelector('.modal-title-enc').textContent = `Nuevo encargado para el pedido: ${recipient}`;
    cambiarEncargadoModal.querySelector('.modal-body input').value = recipient;

    const encargadoSelect = cambiarEncargadoModal.querySelector('#encargadoSelect');
    fetch('/obtenerUsuarios')
        .then(r => r.json())
        .then(data => {
            encargadoSelect.innerHTML = '';
            const sinAsignar = document.createElement('option');
            sinAsignar.value = 'None';
            sinAsignar.textContent = 'Sin asignar';
            encargadoSelect.appendChild(sinAsignar);
            data.usuarios.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u.id;
                opt.textContent = u.nombre_completo;
                encargadoSelect.appendChild(opt);
            });
        })
        .catch(err => console.error('Error al obtener usuarios:', err));
});

const agregarDescripcionModal = document.getElementById('agregarDescripcionModal');
agregarDescripcionModal.addEventListener('show.bs.modal', event => {
    const button = event.relatedTarget;
    const recipient = button.getAttribute('data-bs-whatever');
    const partes = recipient.split('|');
    const numero = partes[0];
    const descripcion = partes[1] || '';
    agregarDescripcionModal.querySelector('.modal-title-desc').textContent = `Nueva anotación para el pedido: ${numero}`;
    document.getElementById('cambiarPedido_desc').value = numero;
    document.getElementById('descripcion').value = descripcion;
});

// ── Cobros ────────────────────────────────────────────────────────────────────

function filaPedido(numero) {
    return document.querySelector(`#Pedidos tr.main-row[data-numero="${CSS.escape(String(numero))}"]`);
}

/**
 * Muestra en `cont` (seccion_cobro.html) qué hacer con el dinero según el
 * estado elegido. `saldo`/`cobrado` son totales (de un pedido o de la
 * selección en el cambio masivo). Si no hay nada que decidir, la oculta.
 */
function configurarSeccionCobro(cont, estado, saldo, cobrado, sufijo = '') {
    const seccion = cont.querySelector('.cobro-seccion');
    const pagado = seccion.querySelector('.cobro-pagado');
    const cancelado = seccion.querySelector('.cobro-cancelado');
    const radio = v => seccion.querySelector(`input[name="cobro_accion"][value="${v}"]`);
    seccion.querySelectorAll('input[name="cobro_accion"]').forEach(r => { r.checked = false; });
    seccion.querySelector('select[name="cobro_medio"]').value = '';
    pagado.classList.add('d-none');
    cancelado.classList.add('d-none');

    let visible = false;
    if (estado === 'Terminado y pagado' && saldo > 0.005) {
        seccion.querySelector('.cobro-texto-pagado').textContent =
            `Saldo pendiente${sufijo}: $ ${formatMonto(saldo)}.`;
        radio('registrar').checked = true;
        pagado.classList.remove('d-none');
        visible = true;
    } else if (estado === 'Cancelado' && cobrado > 0.005) {
        seccion.querySelector('.cobro-texto-cancelado').textContent =
            `Cobrado hasta ahora${sufijo}: $ ${formatMonto(cobrado)}. ¿Qué pasa con ese dinero?`;
        radio('retener').checked = true;
        cancelado.classList.remove('d-none');
        visible = true;
    }
    seccion.classList.toggle('d-none', !visible);
    actualizarMedioCobro(cont);
}

// El medio solo se pide si efectivamente se mueve dinero.
function actualizarMedioCobro(cont) {
    const seccion = cont.querySelector('.cobro-seccion');
    const accion = seccion.querySelector('input[name="cobro_accion"]:checked')?.value;
    const pide = !seccion.classList.contains('d-none') && (accion === 'registrar' || accion === 'devolver');
    seccion.querySelector('.cobro-medio-wrap').classList.toggle('d-none', !pide);
    return pide;
}

// Devuelve {accion, medio} o null si falta el medio (y avisa).
function leerSeccionCobro(cont) {
    const seccion = cont.querySelector('.cobro-seccion');
    if (seccion.classList.contains('d-none')) return { accion: '', medio: '' };
    const accion = seccion.querySelector('input[name="cobro_accion"]:checked')?.value || '';
    const medio = seccion.querySelector('select[name="cobro_medio"]').value;
    if (actualizarMedioCobro(cont) && !medio) {
        alert('Elegí el medio de pago.');
        return null;
    }
    return { accion, medio };
}

document.querySelectorAll('.cobro-seccion').forEach(seccion => {
    seccion.addEventListener('change', e => {
        if (e.target.name === 'cobro_accion') actualizarMedioCobro(seccion.parentElement);
    });
});

const registrarPagoModal = document.getElementById('registrarPagoModal');
registrarPagoModal.addEventListener('show.bs.modal', event => {
    const numero = event.relatedTarget.getAttribute('data-bs-whatever');
    const fila = filaPedido(numero);
    const saldo = parseFloat(fila?.dataset.saldo) || 0;
    document.getElementById('pagoPedido').value = numero;
    document.getElementById('registrarPagoModalLabel').textContent = `Registrar pago — pedido ${numero}`;
    document.getElementById('pagoInfo').textContent =
        `Total $ ${formatMonto(fila?.dataset.total)} · Cobrado $ ${formatMonto(fila?.dataset.senia)} · Saldo $ ${formatMonto(saldo)}`;
    document.getElementById('pagoMonto').value = '';
    document.getElementById('pagoMedio').value = '';
    document.getElementById('pagoNota').value = '';
    document.getElementById('btnPagoSaldo').dataset.saldo = saldo;
    document.getElementById('btnPagoSaldo').disabled = saldo <= 0;
});
document.getElementById('btnPagoSaldo').addEventListener('click', function () {
    document.getElementById('pagoMonto').value = formatearNumeroLocal(this.dataset.saldo);
});
document.getElementById('registrarPagoForm').addEventListener('submit', function (e) {
    if (parsearNumeroLocal(document.getElementById('pagoMonto').value) <= 0) {
        e.preventDefault();
        alert('Ingresá un monto mayor a cero.');
    }
});

function configurarCobroEstadoIndividual() {
    const numero = document.getElementById('cambiarPedido_estado').value;
    const fila = filaPedido(numero);
    configurarSeccionCobro(
        cambiarEstadoModal, document.getElementById('estado').value,
        parseFloat(fila?.dataset.saldo) || 0, parseFloat(fila?.dataset.senia) || 0);
}

(function () {
    const formularioEstado = document.querySelector('#cambiarEstadoModal form');
    const selectEstado = document.querySelector('#estado');
    if (formularioEstado && selectEstado) {
        formularioEstado.addEventListener('submit', function (e) {
            if (!selectEstado.value) {
                e.preventDefault();
                alert('Elegí un estado para el pedido.');
                return;
            }
            if (!leerSeccionCobro(cambiarEstadoModal)) {
                e.preventDefault();
                return;
            }
            if (selectEstado.value === 'Cancelado') {
                const ok = confirm(
                    "⚠️ Atención: estás por cancelar este pedido.\n\nEsta acción es irreversible.\nSi luego necesitás reactivarlo, deberás crear uno nuevo.\n\n¿Deseás continuar?"
                );
                if (!ok) e.preventDefault();
            }
        });
    }
})();

$('#detallesModal').on('show.bs.modal', function (event) {
    const button = $(event.relatedTarget);
    const info = button.data('info').split('|');
    const numero = info[0];
    const presupuestoId = info[1];
    $(this).find('.modal-title-detalles').text('Detalles del pedido: ' + numero);
    $.ajax({
        url: '/pedidos/obtenerDatosProductos',
        type: 'GET',
        data: { 'presupuesto_id': presupuestoId },
        success: function (data) {
            $('#productosTableBody').empty();
            data.productos.forEach(function (producto) {
                const empaquetado = producto.empaquetado ? 'Si' : 'No';
                $('#productosTableBody').append(
                    '<tr><td>' + producto.insumo + '</td><td>' + producto.descripcion +
                    '</td><td>' + producto.info_adic + '</td><td>' + empaquetado +
                    '</td><td>' + producto.cantidad + '</td></tr>'
                );
            });
        }
    });
});

$('#confirmacionModal').on('show.bs.modal', function (event) {
    const button = $(event.relatedTarget);
    const info = button.data('info').split('|');
    const numero = info[0];
    const presupuestoId = info[1];
    $(this).find('.modal-title-confirmacion').text('Confirmación del pedido: ' + numero);
    $.ajax({
        url: '/pedidos/obtenerDatosProductos',
        type: 'GET',
        data: { 'presupuesto_id': presupuestoId, 'pedido_numero': numero },
        success: function (data) {
            $('#confCliente').text(data.pedido.cliente);
            $('#confFechaPedido').text(data.pedido.fecha_pedido);
            $('#confFechaEntrega').text(
                data.pedido.fecha_entrega && data.pedido.fecha_entrega.trim() !== ''
                    ? data.pedido.fecha_entrega : 'A determinar'
            );
            $('#confPrecio').text(formatearNumeroLocal(data.pedido.precio));
            $('#confSenia').text(formatearNumeroLocal(data.pedido.senia));
            $('#confSaldo').text(formatearNumeroLocal(data.pedido.saldo));
            let html = '';
            data.productos.forEach(function (p) {
                html += `<p><strong>${p.cantidad} ${p.producto_final}</strong><br>${p.info_adic}</p>`;
            });
            $('#confProductos').html(html);
        }
    });
});

const cambiarClienteModal = document.getElementById('cambiarClienteModal');
cambiarClienteModal.addEventListener('show.bs.modal', function (event) {
    const button = event.relatedTarget;
    const info = button.getAttribute('data-bs-whatever');
    const [clienteId, clienteRef, pedidoNumero, presupuestoNumero] = info.split('|');
    document.getElementById('pedidoNumero').value = pedidoNumero;
    document.getElementById('presupuestoNumero').value = presupuestoNumero;
    document.getElementById('nuevoCliente').value = `${clienteId}|${clienteRef}`;
});

// ── Filtros ───────────────────────────────────────────────────────────────────
const FILTROS_KEY = 'pedidos_filtros';
let filtroActivo = { clientes: [], productos: [], estados: [], soloConSaldo: false };

$.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
    if (settings.nTable.id !== 'Pedidos') return true;

    const { clientes, productos, estados, soloConSaldo } = filtroActivo;
    const nodoFila = settings.aoData[dataIndex].nTr;
    if (!nodoFila) return true;

    const clienteId      = nodoFila.children[2]?.dataset.clienteId || '';
    const productosTexto = nodoFila.children[3]?.querySelector('.prod-text')?.textContent.trim().toLowerCase() || '';
    const estadoTexto    = nodoFila.children[4]?.textContent.trim().toLowerCase() || '';
    const saldo          = parseFloat(nodoFila.dataset.saldo) || 0;

    const okCliente  = !clientes.length  || clientes.includes(clienteId);
    const okProducto = !productos.length || productos.some(p => productosTexto.includes(p.toLowerCase()));
    const okEstado   = !estados.length   || estados.map(e => e.toLowerCase()).includes(estadoTexto);
    const okSaldo    = !soloConSaldo     || saldo > 0;

    return okCliente && okProducto && okEstado && okSaldo;
});

function getSeleccionados(id) {
    return Array.from(document.getElementById(id).selectedOptions)
                .map(o => o.value).filter(v => v !== '');
}

function aplicarFiltros() {
    filtroActivo = {
        clientes:  getSeleccionados('filtroCliente'),
        productos: getSeleccionados('filtroProducto'),
        estados:   getSeleccionados('filtroEstado'),
        soloConSaldo: document.getElementById('filtroSaldo').checked,
    };
    sessionStorage.setItem(FILTROS_KEY, JSON.stringify(filtroActivo));
    dataTable.draw();
}

function manejarTodos(selectEl) {
    const opcionTodos = selectEl.querySelector('option[value=""]');
    if (!opcionTodos) return;
    if (opcionTodos.selected) {
        Array.from(selectEl.options).forEach(o => { if (o.value !== '') o.selected = false; });
    } else {
        opcionTodos.selected = false;
    }
}

function restaurarFiltros() {
    const guardados = sessionStorage.getItem(FILTROS_KEY);
    if (!guardados) return;
    const { clientes, productos, estados, soloConSaldo } = JSON.parse(guardados);
    const mapa = { filtroCliente: clientes, filtroProducto: productos, filtroEstado: estados };
    Object.entries(mapa).forEach(([id, vals]) => {
        if (!vals?.length) return;
        Array.from(document.getElementById(id).options).forEach(o => {
            o.selected = o.value !== '' && vals.includes(o.value);
        });
    });
    document.getElementById('filtroSaldo').checked = !!soloConSaldo;
    filtroActivo = {
        clientes: clientes || [], productos: productos || [], estados: estados || [],
        soloConSaldo: !!soloConSaldo,
    };
    // draw(false): NO resetear la paginación, para conservar la página que
    // restauró stateSave (importante al volver de editar un pedido).
    dataTable.draw(false);
}

function limpiarFiltros() {
    sessionStorage.removeItem(FILTROS_KEY);
    filtroActivo = { clientes: [], productos: [], estados: [], soloConSaldo: false };
    ['filtroCliente', 'filtroProducto', 'filtroEstado'].forEach(id => {
        Array.from(document.getElementById(id).options).forEach(o => o.selected = false);
    });
    document.getElementById('filtroSaldo').checked = false;
    dataTable.draw();
}

['filtroCliente', 'filtroProducto', 'filtroEstado'].forEach(id => {
    const el = document.getElementById(id);
    el.addEventListener('change', () => { manejarTodos(el); aplicarFiltros(); });
});

document.getElementById('filtroSaldo').addEventListener('change', aplicarFiltros);

document.getElementById('limpiarFiltros').addEventListener('click', limpiarFiltros);

// ── Acciones en lote (bulk) ───────────────────────────────────────────────────
const selectedIds = new Set();

function getCsrfToken() {
    const value = `; ${document.cookie}`;
    const parts = value.split('; csrftoken=');
    if (parts.length === 2) return parts.pop().split(';').shift();
}

function updateBulkBar() {
    const n = selectedIds.size;
    const panel = document.getElementById('bulkActions');
    if (n > 0) {
        panel.classList.remove('d-none');
        const label = `(${n} pedido${n > 1 ? 's' : ''})`;
        document.getElementById('bulkEstadoLabel').textContent = `Cambiar estado ${label}`;
        document.getElementById('bulkEncLabel').textContent    = `Cambiar encargado ${label}`;
    } else {
        panel.classList.add('d-none');
    }
}

function syncCheckAll() {
    const visible = document.querySelectorAll('.bulk-check');
    const allChecked = visible.length > 0 && Array.from(visible).every(cb => cb.checked);
    const checkAll = document.getElementById('checkAll');
    if (checkAll) checkAll.checked = allChecked;
}

function applyRowHighlight(cb) {
    const tr = cb.closest('tr');
    if (tr) tr.classList.toggle('row-selected', cb.checked);
}

$(document).on('draw.dt', '#Pedidos', function () {
    document.querySelectorAll('.bulk-check').forEach(cb => {
        cb.checked = selectedIds.has(cb.dataset.numero);
        applyRowHighlight(cb);
    });
    syncCheckAll();
});

$(document).on('change', '.bulk-check', function () {
    if (this.checked) { selectedIds.add(this.dataset.numero); }
    else              { selectedIds.delete(this.dataset.numero); }
    applyRowHighlight(this);
    updateBulkBar();
    syncCheckAll();
});

document.getElementById('checkAll').addEventListener('change', function () {
    document.querySelectorAll('.bulk-check').forEach(cb => {
        cb.checked = this.checked;
        if (this.checked) { selectedIds.add(cb.dataset.numero); }
        else              { selectedIds.delete(cb.dataset.numero); }
        applyRowHighlight(cb);
    });
    updateBulkBar();
});

document.getElementById('btnDeselectAll').addEventListener('click', function () {
    selectedIds.clear();
    document.querySelectorAll('.bulk-check').forEach(cb => {
        cb.checked = false;
        applyRowHighlight(cb);
    });
    const checkAll = document.getElementById('checkAll');
    if (checkAll) checkAll.checked = false;
    updateBulkBar();
});

document.getElementById('bulkEstadoModal').addEventListener('show.bs.modal', function () {
    const n = selectedIds.size;
    document.getElementById('bulkEstadoInfo').textContent =
        `Se cambiará el estado de ${n} pedido${n > 1 ? 's' : ''}.`;
    document.getElementById('bulkEstadoSelect').value = '';
    configurarCobroBulk();
});

document.getElementById('bulkEncargadoModal').addEventListener('show.bs.modal', function () {
    const n = selectedIds.size;
    document.getElementById('bulkEncargadoInfo').textContent =
        `Se reasignarán ${n} pedido${n > 1 ? 's' : ''} al encargado seleccionado.`;
    const sel = document.getElementById('bulkEncargadoSelect');
    sel.innerHTML = '';
    fetch('/obtenerUsuarios')
        .then(r => r.json())
        .then(data => {
            const sinAsignar = document.createElement('option');
            sinAsignar.value = 'None';
            sinAsignar.textContent = 'Sin asignar';
            sel.appendChild(sinAsignar);
            data.usuarios.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u.id;
                opt.textContent = u.nombre_completo;
                sel.appendChild(opt);
            });
        })
        .catch(err => console.error('Error al obtener usuarios:', err));
});

async function enviarBulk(url, payload) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.redirect_url) window.location.href = data.redirect_url;
}

function configurarCobroBulk() {
    let saldo = 0, cobrado = 0;
    selectedIds.forEach(numero => {
        const fila = filaPedido(numero);
        if (!fila || fila.dataset.esCancelado === 'true') return;
        saldo += Math.max(parseFloat(fila.dataset.saldo) || 0, 0);
        cobrado += Math.max(parseFloat(fila.dataset.senia) || 0, 0);
    });
    configurarSeccionCobro(
        document.getElementById('bulkEstadoForm'),
        document.getElementById('bulkEstadoSelect').value,
        saldo, cobrado, ' (suma de los pedidos seleccionados)');
}
document.getElementById('bulkEstadoSelect').addEventListener('change', configurarCobroBulk);

document.getElementById('btnConfirmarBulkEstado').addEventListener('click', async function () {
    const estado = document.getElementById('bulkEstadoSelect').value;
    if (!estado) { alert('Por favor seleccioná un estado.'); return; }
    const cobro = leerSeccionCobro(document.getElementById('bulkEstadoForm'));
    if (!cobro) return;
    if (estado === 'Cancelado') {
        const ok = confirm(
            `⚠️ Atención: estás por cancelar ${selectedIds.size} pedido(s).\n\nEsta acción es irreversible.\n\n¿Deseás continuar?`
        );
        if (!ok) return;
    }
    bootstrap.Modal.getInstance(document.getElementById('bulkEstadoModal')).hide();
    await enviarBulk('/pedidos/cambiarEstadoBulk', {
        ids: [...selectedIds], estado, cobro_accion: cobro.accion, cobro_medio: cobro.medio,
    });
});

document.getElementById('btnConfirmarBulkEncargado').addEventListener('click', async function () {
    const encargado_id = document.getElementById('bulkEncargadoSelect').value;
    bootstrap.Modal.getInstance(document.getElementById('bulkEncargadoModal')).hide();
    await enviarBulk('/pedidos/cambiarEncargadoBulk', { ids: [...selectedIds], encargado_id });
});
