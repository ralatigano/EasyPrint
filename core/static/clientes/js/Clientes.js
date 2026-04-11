let dataTable;
let dataTableIsInitilized=false;
// Función para inicializar DataTable Clientes
const initDataTable=async() => {
    if(dataTableIsInitilized){
        dataTable.destroy();
    }
    dataTable=$("#Clientes").DataTable({
        language: {
            lengthMenu: 'Mostrar _MENU_ clientes por página',
            zeroRecords: 'No hay clientes registrados',
            info: 'Mostrando de _START_ a _END_ de _TOTAL_ clientes',
            infoEmpty: 'No hay clientes',
            InfoFiltered: '(filtrado de _MAX_ clientes totales)',
            search: 'Buscar:',
            LoadingRecords: 'Cargando...',
            paginate: {
                first: 'Primero',
                last: 'Ultimo',
                next: 'Siguiente',
                previous: 'Anterior'
            }
        }
    });
    dataTableIsInitilized=true;
}

window.addEventListener("load", async() => {
    await initDataTable();
    document.getElementById("nav_item_clientes").style.fontWeight = "bold";
});

// Función que controla el modal de editar cliente, toma valores del data-bs-whatever y los muestra en el modal
const editarClienteModal = document.getElementById('editarClienteModal');
editarClienteModal.addEventListener('show.bs.modal', event => {
  const button = event.relatedTarget;
  const recipient = button.getAttribute('data-bs-whatever');
  const partes = recipient.split('|');

  const id = partes[0];
  const nombre = partes[1];
  const negocio = partes[2];
  const cuit = partes[3];
  const telefono = partes[4];
  const direccion = partes[5];
  const met_contacto = partes[6];

  const modalTitle = editarClienteModal.querySelector('.modal-title');
  modalTitle.textContent = `Editar Cliente: ${nombre}`;

  // Helper para aplicar clase si está vacío
  function setCampo(idCampo, valor, placeholder) {
    const campo = $(`#${idCampo}`);
    campo.val(valor);
    campo.attr("placeholder", placeholder);
    if (!valor || valor.trim() === "") {
      campo.addClass("campo-vacio");
    } else {
      campo.removeClass("campo-vacio");
    }
  }

  $("#id").val(id);
  setCampo("nombre", nombre, "Sin dato");
  setCampo("negocio", negocio, "Sin dato");
  setCampo("cuit", cuit, "Sin dato");
  setCampo("telefono", telefono, "Sin dato");
  setCampo("direccion", direccion, "Sin dato");

  $("#met_contacto").val(met_contacto);

  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });
});

// ── Ficha cliente ──────────────────────────────────────────
const modalFicha = new bootstrap.Modal(document.getElementById('modalFichaCliente'));

function llenarTablaFicha(idTabla, items) {
    const tbody = document.querySelector(`#${idTabla} tbody`);
    tbody.innerHTML = '';
    if (!items || items.length === 0) {
        const cols = document.querySelectorAll(`#${idTabla} thead th`).length;
        tbody.innerHTML = `<tr><td colspan="${cols}" class="text-center text-muted">Sin datos</td></tr>`;
        return;
    }
    items.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = Object.values(item).map(v => `<td style="white-space: nowrap">${v}</td>`).join('');
        tbody.appendChild(tr);
    });
}

document.querySelectorAll('.btn-ficha-cliente').forEach(btn => {
    btn.addEventListener('click', () => {
        const id = btn.dataset.id;

        fetch(`/clientes/infoCliente/${id}`)
            .then(res => res.json())
            .then(data => {
                document.getElementById('fichaClienteNombre').textContent = data.nombre;

                document.getElementById('fichaTelefono').textContent = data.telefono || '-';
                const wapp = document.getElementById('fichaWapp');
                if (data.telefono) { wapp.href = `https://wa.me/${data.telefono}`; wapp.style.display = ''; }
                else { wapp.style.display = 'none'; }

                document.getElementById('fichaEmail').textContent = data.email || '-';
                const mailto = document.getElementById('fichaMailto');
                if (data.email) { mailto.href = `mailto:${data.email}`; mailto.style.display = ''; }
                else { mailto.style.display = 'none'; }

                document.getElementById('fichaNegocio').textContent = data.negocio || '-';
                document.getElementById('fichaCuit').textContent = data.cuit || '-';

                document.getElementById('fichaDireccion').textContent = data.direccion || '-';
                const maps = document.getElementById('fichaMaps');
                if (data.direccion) { maps.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(data.direccion)}`; maps.style.display = ''; }
                else { maps.style.display = 'none'; }

                llenarTablaFicha('tablaFichaPedidosActivos', data.pedidos_activos);
                llenarTablaFicha('tablaFichaPedidosFinalizados', data.pedidos_finalizados);
                llenarTablaFicha('tablaFichaPresupuestos', data.presupuestos_pendientes);

                modalFicha.show();
            })
            .catch(() => alert('Error al obtener la información del cliente'));
    });
});