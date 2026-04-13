// ── Funciones globales (accesibles desde onclick en el HTML) ──────────────────

function colorSemaforo(pct) {
    const r = pct < 50 ? 220 : Math.round(220 - (pct - 50) * 3.6);
    const g = pct < 50 ? Math.round(pct * 3.6) : 180;
    return `rgb(${r},${g},40)`;
}

function irAPedidosConFiltro(estados) {
    const filtro = { clientes: [], productos: [], estados: estados };
    sessionStorage.setItem('pedidos_filtros', JSON.stringify(filtro));
    window.location.href = '/pedidos';
}

function editarObjetivo(id, nombre, monto, desde, hasta) {
    document.getElementById('objetivoIdInput').value = id;
    document.getElementById('objNombre').value = nombre;
    document.getElementById('objMonto').value = monto;
    document.getElementById('objDesde').value = desde;
    document.getElementById('objHasta').value = hasta;
    document.getElementById('modalObjetivoTitulo').textContent = 'Editar objetivo';
    bootstrap.Modal.getInstance(document.getElementById('modalListaObjetivos'))?.hide();
    new bootstrap.Modal(document.getElementById('modalObjetivo')).show();
}

// ── Lógica que requiere el DOM cargado ───────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    // Dar tiempo a que core.js resuelva el AJAX de getDarkMode antes de leer el tema
    setTimeout(inicializarDashboard, 150);
    document.getElementById('modalListaObjetivos').addEventListener('shown.bs.modal', function () {
        this.querySelectorAll('.progress-bar-semaforo').forEach(function(barra) {
            const pct = parseInt(barra.dataset.progreso) || 0;
            barra.style.width = pct + '%';
            barra.style.backgroundColor = colorSemaforo(pct);
        });
    });
});

function inicializarDashboard() {
    // Leer datos inyectados por Django de forma segura
    const rawEstados = JSON.parse(document.getElementById('raw-estados').textContent);
    const rawClientes = JSON.parse(document.getElementById('raw-clientes').textContent);

    const estadosData = {
        labels: rawEstados.map(e => e.estado),
        valores: rawEstados.map(e => e.cantidad)
    };
    const clientesData = {
        labels: rawClientes.map(c => c.cliente__negocio
            ? `${c.cliente__nombre} · ${c.cliente__negocio}`
            : c.cliente__nombre),
        valores: rawClientes.map(c => parseFloat(c.total_comprado))
    };

    // Barra de progreso semaforizada
    document.querySelectorAll('.progress-bar-semaforo').forEach(function(barra) {
        const pct = parseInt(barra.dataset.progreso) || 0;
        barra.style.width = pct + '%';
        barra.style.backgroundColor = colorSemaforo(pct);
    });

    // Tema claro/oscuro para Chart.js
    // Tema claro/oscuro para Chart.js
    const temaGuardado = localStorage.getItem('theme') || 'light';
    const isDark = temaGuardado === 'dark';
    const textColor = isDark ? '#e9ecef' : '#212529';
    const gridColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)';

    // Donut: pedidos por estado
    const ctxEstados = document.getElementById('chartEstados');
    if (ctxEstados && estadosData.labels.length) {
        // Paleta amplia — un color distinto por estado
        const paleta = [
            '#0d6efd', '#ffc107', '#198754', '#dc3545',
            '#6f42c1', '#0dcaf0', '#fd7e14', '#6c757d',
            '#20c997', '#d63384'
        ];
        new Chart(ctxEstados, {
            type: 'doughnut',
            data: {
                labels: estadosData.labels,
                datasets: [{
                    data: estadosData.valores,
                    backgroundColor: paleta.slice(0, estadosData.labels.length),
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 14,
                            padding: 16,
                            color: textColor,
                            font: { size: 13 }
                        }
                    }
                }
            }
        });
    }

    // Barras horizontales: top clientes
    const ctxClientes = document.getElementById('chartClientes');
    if (ctxClientes && clientesData.labels.length) {
        new Chart(ctxClientes, {
            type: 'bar',
            data: {
                labels: clientesData.labels,
                datasets: [{
                    label: 'Total comprado ($)',
                    data: clientesData.valores,
                    backgroundColor: '#0d6efd99',
                    borderColor: '#0d6efd',
                    borderWidth: 1,
                    borderRadius: 4,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        grid: { color: gridColor },
                        ticks: {
                            color: textColor,
                            font: { size: 12 },
                            callback: v => '$' + Number(v).toLocaleString('es-AR')
                        }
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            color: textColor,
                            font: { size: 12 }
                        }
                    }
                }
            }
        });
    }

    // Links a pedido por número
    document.querySelectorAll('.pedido-link').forEach(el => {
        el.addEventListener('click', function (e) {
            e.preventDefault();
            sessionStorage.removeItem('pedidos_filtros');
            sessionStorage.setItem('pedidos_buscar', this.dataset.numero);
            window.location.href = '/pedidos';
        });
    });

}

function limpiarFormObjetivo() {
    document.getElementById('objetivoIdInput').value = '';
    document.getElementById('objNombre').value = '';
    document.getElementById('objMonto').value = '';
    document.getElementById('objDesde').value = '';
    document.getElementById('objHasta').value = '';
    document.getElementById('modalObjetivoTitulo').textContent = 'Nuevo objetivo de ventas';
}