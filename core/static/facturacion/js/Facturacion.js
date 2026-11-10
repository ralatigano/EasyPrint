// Facturación electrónica: modal de emisión de comprobantes desde un pedido.
(function () {
    const modalEl = document.getElementById('facturarModal');
    if (!modalEl) return;

    let contexto = null;   // datos del pedido cargados por AJAX
    let emitioOk = false;  // si hubo emisión exitosa, recargamos al cerrar

    const el = (id) => document.getElementById(id);

    function csrf() {
        const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    function resetForm() {
        emitioOk = false;
        const res = el('facturarResultado');
        res.classList.add('d-none');
        res.innerHTML = '';
        el('facturarPreviosWrap').classList.add('d-none');
        el('facturarPrevios').innerHTML = '';
        el('facturarTipo').value = '11';
        el('facturarFecha').value = '';
        el('facturarFechaAyuda').textContent = '';
        el('facturarAsociadoWrap').classList.add('d-none');
        el('recConsumidorFinal').checked = true;
        el('facturarIdentificadoWrap').classList.add('d-none');
        el('facturarDocNro').value = '';
        el('facturarDocTipo').value = '80';
        el('facturarRazonSocial').value = '';
        el('facturarNombre').value = '';
        el('facturarNegocio').value = '';
        el('facturarPadronMsg').innerHTML = '';
        el('facturarCondIva').value = '5';
        el('facturarEditarMonto').checked = false;
        el('facturarMonto').readOnly = true;
        const btn = el('btnEmitirFactura');
        btn.disabled = false;
        btn.classList.remove('d-none');
    }

    function mostrarAmbiente() {
        const aviso = el('facturarAmbienteAviso');
        const prod = contexto && contexto.ambiente === 'produccion';
        aviso.className = 'alert py-2 px-3 mb-3 ' + (prod ? 'alert-danger' : 'alert-warning');
        aviso.innerHTML = prod
            ? '<strong>PRODUCCIÓN</strong> — el comprobante es real y tiene efecto fiscal.'
            : '<strong>HOMOLOGACIÓN</strong> — comprobante de prueba, sin validez fiscal.';
    }

    function poblarPrevios() {
        const wrap = el('facturarPreviosWrap');
        const ul = el('facturarPrevios');
        const cs = (contexto && contexto.comprobantes) || [];
        if (!cs.length) { wrap.classList.add('d-none'); return; }
        ul.innerHTML = cs.map(c => {
            const pdf = (c.estado === 'autorizado')
                ? ` — <a href="/facturacion/comprobante/${c.id}/pdf" target="_blank" rel="noopener">PDF</a>`
                : '';
            return `<li>${c.tipo_label} <strong>${c.numero}</strong> — ${c.estado_label} — $ ${c.importe}${pdf}</li>`;
        }).join('');
        wrap.classList.remove('d-none');
    }

    function poblarAsociadas() {
        const sel = el('facturarAsociado');
        sel.innerHTML = '';
        const asociables = ((contexto && contexto.comprobantes) || []).filter(c => c.asociable);
        if (!asociables.length) {
            const o = document.createElement('option');
            o.value = '';
            o.textContent = '(no hay facturas autorizadas para asociar)';
            sel.appendChild(o);
            return;
        }
        asociables.forEach(c => {
            const o = document.createElement('option');
            o.value = c.id;
            o.textContent = `${c.tipo_label} ${c.numero} — $ ${c.importe}`;
            sel.appendChild(o);
        });
    }

    function toggleReceptor() {
        const identificado = el('recIdentificado').checked;
        el('facturarIdentificadoWrap').classList.toggle('d-none', !identificado);
        if (identificado && contexto && contexto.cliente) {
            const c = contexto.cliente;
            // Precarga doc y condición IVA desde los datos del cliente en la base.
            if (c.cuit && !el('facturarDocNro').value) {
                el('facturarDocTipo').value = '80';
                el('facturarDocNro').value = c.cuit;
            }
            if (c.condicion_iva) {
                el('facturarCondIva').value = c.condicion_iva;
            }
            // Precarga los datos de identidad si están vacíos (no pisa lo editado).
            if (!el('facturarRazonSocial').value) el('facturarRazonSocial').value = c.razon_social || '';
            if (!el('facturarNombre').value) el('facturarNombre').value = c.nombre || '';
            if (!el('facturarNegocio').value) el('facturarNegocio').value = c.negocio || '';
        }
    }

    // Trae la razón social desde el padrón de ARCA a partir del CUIT ingresado.
    async function traerPadron() {
        const msg = el('facturarPadronMsg');
        const cuit = (el('facturarDocNro').value || '').replace(/\D/g, '');
        if (cuit.length !== 11) {
            msg.className = 'text-danger';
            msg.textContent = 'Ingresá un CUIT de 11 dígitos para consultar ARCA.';
            return;
        }
        const btn = el('btnTraerPadron');
        const original = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
        msg.className = 'text-muted';
        msg.textContent = 'Consultando ARCA…';
        try {
            const res = await fetch(`/facturacion/padron/${cuit}`);
            const data = await res.json();
            if (data.ok && data.razon_social) {
                el('facturarRazonSocial').value = data.razon_social;
                if (data.condicion_iva) el('facturarCondIva').value = data.condicion_iva;
                msg.className = 'text-success';
                msg.textContent = `Razón social: ${data.razon_social}`;
            } else {
                msg.className = 'text-warning';
                msg.textContent = data.error || 'ARCA no devolvió datos para ese CUIT.';
            }
        } catch (err) {
            msg.className = 'text-danger';
            msg.textContent = 'No se pudo consultar el padrón de ARCA.';
        } finally {
            btn.disabled = false;
            btn.innerHTML = original;
        }
    }

    function toggleTipo() {
        const tipo = el('facturarTipo').value;
        const esNota = (tipo === '12' || tipo === '13');
        el('facturarAsociadoWrap').classList.toggle('d-none', !esNota);
        aplicarLimitesFecha();
    }

    // ── Fecha del comprobante ─────────────────────────────────────────────────
    // El rango lo manda el servidor (services/fechas.py es la fuente única);
    // acá sólo se traduce a los `min`/`max` del input. Una nota de crédito o
    // débito, además, no puede ser anterior a la factura que corrige.
    function aplicarLimitesFecha() {
        const campo = el('facturarFecha');
        const ayuda = el('facturarFechaAyuda');
        const limites = contexto && contexto.fechas;
        if (!limites) { campo.removeAttribute('min'); campo.removeAttribute('max'); return; }

        let minima = limites.minima;
        const asociada = fechaDeAsociada();
        if (asociada && asociada > minima) minima = asociada;

        campo.min = minima;
        campo.max = limites.maxima;
        if (campo.value && campo.value < minima) campo.value = minima;

        ayuda.textContent = asociada && asociada === minima
            ? `No puede ser anterior a la factura que corrige (${aFechaAr(minima)}).`
            : `ARCA acepta hasta ${limites.dias} días hacia atrás: desde el ${aFechaAr(minima)}.`;
    }

    function fechaDeAsociada() {
        const tipo = el('facturarTipo').value;
        if (tipo !== '12' && tipo !== '13') return null;
        const id = el('facturarAsociado').value;
        if (!id) return null;
        const c = ((contexto && contexto.comprobantes) || [])
            .find(x => String(x.id) === String(id));
        return (c && c.fecha) || null;
    }

    function aFechaAr(iso) {
        const [a, m, d] = iso.split('-');
        return `${d}/${m}/${a}`;
    }

    function mostrarResultado(ok, payload) {
        const box = el('facturarResultado');
        box.classList.remove('d-none');
        if (ok) {
            emitioOk = true;
            box.className = 'alert alert-success';
            box.innerHTML =
                `<strong>✅ Comprobante autorizado</strong><br>` +
                `N°: <strong>${payload.numero}</strong><br>` +
                `CAE: ${payload.cae} (vence ${payload.cae_vto})<br>` +
                `<a class="btn btn-sm btn-outline-success mt-2" target="_blank" rel="noopener" ` +
                `href="/facturacion/comprobante/${payload.comprobante_id}/pdf">` +
                `<i class="fa-solid fa-file-pdf"></i> Descargar PDF</a>`;
            el('btnEmitirFactura').classList.add('d-none');
        } else {
            box.className = 'alert alert-danger';
            box.innerHTML = (typeof payload === 'string') ? payload : (payload.error || 'Error');
        }
    }

    // ── Apertura del modal: carga el contexto del pedido ──────────────────────
    modalEl.addEventListener('show.bs.modal', function (event) {
        resetForm();
        const info = (event.relatedTarget?.getAttribute('data-bs-whatever') || '').split('|');
        const numero = info[0];
        el('facturarPedidoNumero').value = numero;
        el('facturarModalLabel').textContent = `Facturar pedido N° ${numero}`;
        el('facturarMonto').value = '…';
        contexto = null;

        fetch(`/facturacion/contexto/${numero}`)
            .then(r => r.json())
            .then(data => {
                contexto = data;
                el('facturarMonto').value = formatearNumeroLocal(data.total);
                mostrarAmbiente();
                poblarPrevios();
                poblarAsociadas();
                el('facturarFecha').value = data.fechas ? data.fechas.hoy : '';
                aplicarLimitesFecha();
            })
            .catch(() => {
                el('facturarMonto').value = formatearNumeroLocal(info[1] || '0');
            });
    });

    modalEl.addEventListener('hidden.bs.modal', function () {
        if (emitioOk) window.location.reload();
    });

    // ── Toggles ───────────────────────────────────────────────────────────────
    el('facturarTipo').addEventListener('change', toggleTipo);
    el('facturarAsociado').addEventListener('change', aplicarLimitesFecha);
    document.querySelectorAll('input[name="facturarReceptor"]').forEach(r =>
        r.addEventListener('change', toggleReceptor));
    el('facturarEditarMonto').addEventListener('change', function () {
        el('facturarMonto').readOnly = !this.checked;
        if (this.checked) el('facturarMonto').focus();
    });
    el('btnTraerPadron').addEventListener('click', traerPadron);

    // ── Emisión ───────────────────────────────────────────────────────────────
    el('btnEmitirFactura').addEventListener('click', async function () {
        const tipo = el('facturarTipo').value;
        const receptor = el('recIdentificado').checked ? 'identificado' : 'consumidor_final';
        const payload = {
            pedido_numero: parseInt(el('facturarPedidoNumero').value, 10),
            tipo_cbte: parseInt(tipo, 10),
            receptor: receptor,
            importe: el('facturarMonto').value,
            fecha: el('facturarFecha').value,
        };
        if (receptor === 'identificado') {
            payload.doc_tipo = parseInt(el('facturarDocTipo').value, 10);
            payload.doc_nro = (el('facturarDocNro').value || '').replace(/\D/g, '');
            payload.cond_iva_receptor = parseInt(el('facturarCondIva').value, 10);
            payload.razon_social = el('facturarRazonSocial').value.trim();
            payload.nombre = el('facturarNombre').value.trim();
            payload.negocio = el('facturarNegocio').value.trim();
            if (!payload.doc_nro) {
                mostrarResultado(false, 'Ingresá el número de documento del receptor.');
                return;
            }
        }
        if (tipo === '12' || tipo === '13') {
            const asoc = el('facturarAsociado').value;
            if (!asoc) { mostrarResultado(false, 'Seleccioná la factura asociada.'); return; }
            payload.comprobante_asociado_id = parseInt(asoc, 10);
        }
        // Avisar acá en vez de hacer el viaje: el servidor valida igual, pero
        // el mensaje llega antes y sin esperar a ARCA.
        if (!el('facturarFecha').checkValidity()) {
            mostrarResultado(false, el('facturarFechaAyuda').textContent
                || 'La fecha del comprobante está fuera del rango que acepta ARCA.');
            return;
        }

        const original = this.innerHTML;
        this.disabled = true;
        this.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Emitiendo…';
        try {
            const res = await fetch('/facturacion/emitir', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (data.ok) {
                mostrarResultado(true, data);
            } else {
                const detalle = (data.observaciones && data.observaciones.length)
                    ? data.error + '<ul class="mb-0 mt-1">' +
                      data.observaciones.map(o => `<li>${o}</li>`).join('') + '</ul>'
                    : data.error;
                mostrarResultado(false, detalle);
            }
        } catch (err) {
            mostrarResultado(false, 'Error de conexión al emitir.');
        } finally {
            this.disabled = false;
            this.innerHTML = original;
        }
    });
})();
