(function () {

    // ─── Plantillas de mensaje por tipo de entidad ───────────────────────────
    //
    // Cada función recibe el JSON del endpoint y devuelve HTML seguro.
    // Para agregar un tipo nuevo: una entrada acá + data-tipo en el botón.

    const PLANTILLAS = {

        presupuesto: (d) =>
            `¿Está seguro que desea eliminar el producto 
            <strong>${_esc(d.producto_nombre)}</strong> 
            del presupuesto? (Precio unitario: <strong>${_moneda(d.precio)}</strong>)`,

        insumo: (d) =>
            `¿Está seguro que desea eliminar el insumo 
            <strong>${_esc(d.nombre)}</strong>? 
            (Precio por unidad de uso: <strong>${_moneda(d.precio)}</strong>)`,

        producto: (d) => {
            const tercerizado = d.tercerizado
                ? ' <span class="badge bg-secondary">tercerizado</span>' : '';
            return `¿Está seguro que desea eliminar el producto${tercerizado} 
                    <strong>${_esc(d.nombre)}</strong>? 
                    (Precio: <strong>${_moneda(d.precio_proveedor)}</strong>)`;
        },

        categoria: (d) =>
            `¿Está seguro que desea eliminar la categoría 
            <strong>${_esc(d.nombre)}</strong>? 
            Todos los productos asociados perderán su categoría.`,

        pedido: (d) =>{
            const p = d.pedido;  // ← los datos están en d.pedido, no en d directamente
            const ref = p.cliente || 'cliente desconocido';
            return `¿Está seguro que desea eliminar el pedido 
                    <strong>#${_esc(String(p.numero))}</strong> 
                    del cliente <strong>${_esc(ref)}</strong> 
                    por un total de <strong>${_moneda(p.precio)}</strong>?`;
        },

        viaje: (d) =>
            `¿Está seguro que desea eliminar el viaje del 
            <strong>${_esc(d.fecha)}</strong>: 
            <strong>${_esc(d.origen)}</strong> → 
            <strong>${_esc(d.destino)}</strong> 
            (${_moneda(d.precio)})?`,

        cliente: (d) => {
            const ref = d.referencia || d.nombre || 'cliente sin nombre';
            return `¿Está seguro que desea eliminar al cliente 
                    <strong>${_esc(ref)}</strong>? 
                    Se eliminarán también todos sus pedidos asociados.`;
        },

        usuario: (d) =>
            `¿Está seguro que desea eliminar al usuario 
            <strong>${_esc(d.nombre_completo)}</strong>?`,
    };

    // Estados de pedido en los que NO se permite eliminar
    const ESTADOS_BLOQUEADOS = ['En proceso', 'Terminado (falta pago)'];

    // ─── Helpers ─────────────────────────────────────────────────────────────

    function _esc(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }

    function _moneda(valor) {
        if (valor === null || valor === undefined) return '—';
        return '$ ' + parseFloat(valor).toLocaleString('es-AR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function _mostrarToast(mensaje, tipo = 'warning') {
        // Usa el sistema de mensajes de Django si existe en la página,
        // o crea un toast Bootstrap simple.
        const contenedor = document.getElementById('toast-container')
            || (() => {
                const c = document.createElement('div');
                c.id = 'toast-container';
                c.className = 'toast-container position-fixed bottom-0 end-0 p-3';
                c.style.zIndex = 1100;
                document.body.appendChild(c);
                return c;
            })();

        const id = 'toast-' + Date.now();
        const iconos = {
            warning: 'fa-triangle-exclamation text-warning',
            danger:  'fa-circle-xmark text-danger',
            info:    'fa-circle-info text-info',
        };
        contenedor.insertAdjacentHTML('beforeend', `
            <div id="${id}" class="toast align-items-center border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="fa-solid ${iconos[tipo] || iconos.info} me-2"></i>
                        ${mensaje}
                    </div>
                    <button type="button" class="btn-close me-2 m-auto" 
                            data-bs-dismiss="toast" aria-label="Cerrar"></button>
                </div>
            </div>`);
        const toastEl = document.getElementById(id);
        bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 5000 }).show();
        toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
    }

    // ─── Lógica principal ─────────────────────────────────────────────────────

    const modal          = document.getElementById('modalEliminar');
    const elMensaje      = document.getElementById('modalEliminarMensaje');
    const elCargando     = document.getElementById('modalEliminarCargando');
    const elConfirmar    = document.getElementById('modalEliminarConfirmar');

    if (!modal) return; // El modal no está en esta página (no debería pasar con base.html)

    const bsModal = new bootstrap.Modal(modal);

    document.querySelectorAll('.btnEliminacion').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();

            const tipo     = btn.dataset.tipo;
            const fetchUrl = btn.dataset.fetchUrl;
            const urlFinal = btn.getAttribute('href');

            try {
                const respuesta = await fetch(fetchUrl);
                if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
                const datos = await respuesta.json();

                // Control especial para pedidos con estado bloqueado
                // → Ni abrimos el modal, directo al toast
                if (tipo === 'pedido') {
                    const pedido = datos.pedido;
                    if (!pedido) {
                        _mostrarToast('No se pudo obtener información del pedido.', 'danger');
                        return;
                    }
                    if (ESTADOS_BLOQUEADOS.includes(pedido.estado)) {
                        _mostrarToast(
                            `No se puede eliminar un pedido a menos que su estado sea 
                            <strong>"No iniciado"</strong> o <strong>"Terminado y pagado"</strong>.`,
                            'warning'
                        );
                        return;  // ← salimos sin abrir el modal
                    }
                }
                if (tipo === 'cliente' && datos.bloqueado) {
                    const lista = datos.pedidos_activos
                        .map(p => `#${p.numero} (${p.estado})`)
                        .join(', ');
                    _mostrarToast(
                        `No se puede eliminar al cliente <strong>${_esc(datos.referencia)}</strong> 
                        porque tiene pedidos sin finalizar: ${lista}.`,
                        'warning'
                    );
                    return;
                }

                // Recién acá abrimos el modal
                elMensaje.style.display   = 'none';
                elMensaje.innerHTML       = '';
                elConfirmar.style.display = 'none';
                elCargando.style.display  = 'block';
                bsModal.show();

                const plantilla = PLANTILLAS[tipo];
                const mensaje = plantilla
                    ? plantilla(datos)
                    : `¿Está seguro que desea eliminar este registro?`;

                elCargando.style.display  = 'none';
                elMensaje.innerHTML       = mensaje +
                    ' <strong class="text-danger">Esta acción no se puede deshacer.</strong>';
                elMensaje.style.display   = 'block';
                elConfirmar.href          = urlFinal;
                elConfirmar.style.display = 'inline-block';

            } catch (err) {
                console.error('modalEliminar fetch error:', err);
                // Si falló el fetch igual mostramos el modal con mensaje genérico
                elMensaje.style.display   = 'none';
                elConfirmar.style.display = 'none';
                elCargando.style.display  = 'block';
                bsModal.show();
                elCargando.style.display  = 'none';
                elMensaje.innerHTML       =
                    '¿Está seguro que desea eliminar este registro? ' +
                    '<strong class="text-danger">Esta acción no se puede deshacer.</strong>';
                elMensaje.style.display   = 'block';
                elConfirmar.href          = urlFinal;
                elConfirmar.style.display = 'inline-block';
            }
        });
    });

})();