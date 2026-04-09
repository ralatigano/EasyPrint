let dataTable;
let dataTableIsInitilized=false;
// Lógica que inicializa la dataTable Pedidos.
const initDataTable=async() => {
    if(dataTableIsInitilized){
        dataTable.destroy();
    }
    dataTable=$("#Pedidos").DataTable({
        order: [[0, 'desc']],
        responsive: true,
        columnDefs: [
            { responsivePriority: 1, targets: 0 }, // Número
            { responsivePriority: 2, targets: 1 }, // Cliente
            { responsivePriority: 3, targets: 2 }, // Productos/Servicios
            { responsivePriority: 4, targets: 3 }, // Estado
            { responsivePriority: 5, targets: 4 }, // Encargado
            { responsivePriority: 6, targets: 5 }, // Observaciones
            { responsivePriority: 7, targets: 6 }, // Total
            { responsivePriority: 8, targets: 7 }, // Seña
            { responsivePriority: 9, targets: 8 }, // Saldo
            { responsivePriority: 10, targets: 9 }, // Presupuesto
            { responsivePriority: 11, targets: 10 }, // Fecha de creación
            { targets: [6, 7, 8], className: 'text-nowrap' },
        ],
        language: {
            lengthMenu: 'Mostrar _MENU_ pedidos por página',
            zeroRecords: 'No hay pedidos registrados',
            info: 'Mostrando de _START_ a _END_ de _TOTAL_ pedidos',
            infoEmpty: 'No hay pedidos',
            InfoFiltered: '(filtrado de _MAX_ pedidos totales)',
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
    document.getElementById("nav_item_pedidos").style.fontWeight = "bold";
});

// Lógica que escucha el evento de click del botón para editar el pedido en relación al estado del mismo.
const cambiarEstadoModal = document.getElementById('cambiarEstadoModal')
cambiarEstadoModal.addEventListener('show.bs.modal', event => {
  // Button that triggered the modal
  const button = event.relatedTarget
  // Extract info from data-bs-* attributes
  const recipient = button.getAttribute('data-bs-whatever')

  // Update the modal's content.
  const modalTitle = cambiarEstadoModal.querySelector('.modal-title-estado')
  const modalBodyInput = cambiarEstadoModal.querySelector('.modal-body input')
  const modalPedidoInput = cambiarEstadoModal.querySelector('.cambiarPedido_estado')

  modalTitle.textContent = `Nuevo estado para el pedido: ${recipient}`
  modalBodyInput.value = recipient
});
// Lógica que escucha el evento de click del botón para editar el pedido en relación al encargado del mismo.
const cambiarEncargadoModal = document.getElementById('cambiarEncargadoModal')
cambiarEncargadoModal.addEventListener('show.bs.modal', event => {
  const button = event.relatedTarget
  const recipient = button.getAttribute('data-bs-whatever')
  const modalTitle = cambiarEncargadoModal.querySelector('.modal-title-enc')
  const modalBodyInput = cambiarEncargadoModal.querySelector('.modal-body input')
  const encargadoSelect = cambiarEncargadoModal.querySelector('#encargadoSelect');

  modalTitle.textContent = `Nuevo encargado para el pedido: ${recipient}`
  modalBodyInput.value = recipient
  // Realizar la solicitud AJAX para obtener los usuarios
  fetch('/obtenerUsuarios')
  .then(response => response.json())
  .then(data => {
      // Limpiar el select antes de llenarlo
      encargadoSelect.innerHTML = '';

      // Añadir la opción 'Sin asignar'
      const sinAsignarOption = document.createElement('option');
      sinAsignarOption.value = 'None';
      sinAsignarOption.textContent = 'Sin asignar';
      encargadoSelect.appendChild(sinAsignarOption)

      // Llenar el select con los usuarios
      data.usuarios.forEach(usuario => {
          const option = document.createElement('option');
          option.value = usuario.id;
          option.textContent = usuario.nombre_completo;
          encargadoSelect.appendChild(option);
      });
  })
  .catch(error => console.error('Error al obtener los usuarios:', error));
});
// Lógica que escucha el evento de click del botón para editar la descripción del pedido.
const agregarDescripcionModal = document.getElementById('agregarDescripcionModal')
agregarDescripcionModal.addEventListener('show.bs.modal', event => {
  const button = event.relatedTarget
  const recipient = button.getAttribute('data-bs-whatever')
  var partes = recipient.split('|');
  const numero = partes[0];
  const descripcion = partes[1];
  
  const modalTitle = agregarDescripcionModal.querySelector('.modal-title-desc')
  const modalPedidoInput = document.getElementById('cambiarPedido_desc')
  const modalBodyTextArea = document.getElementById('descripcion')

  modalTitle.textContent = `Nueva anotación para el pedido: ${numero}`
  modalBodyTextArea.value = descripcion
  modalPedidoInput.value = numero
});
// Lógica que escucha el evento de click del botón para agregar la seña del pedido.
const agregarSeniaModal = document.getElementById('agregarSeniaModal')
agregarSeniaModal.addEventListener('show.bs.modal', event => {
  const button = event.relatedTarget
  const recipient = button.getAttribute('data-bs-whatever')
  const modalTitle = agregarSeniaModal.querySelector('.modal-title-senia')
  const modalBodyInput = agregarSeniaModal.querySelector('.modal-body input')

  modalTitle.textContent = `Agregar seña para el pedido: ${recipient}`
  modalBodyInput.value = recipient
})

//Función que maneja la apertura del modal de detalles haciendo una petición ajax al backend para obtener información de los productos de un pedido.
$('#detallesModal').on('show.bs.modal', function (event) {
  var button = $(event.relatedTarget);  // Botón que activó el modal
  var info = button.data('info').split('|');  // Separar los valores
  var numero = info[0];  // p.numero
  var presupuestoId = info[1];  // p.presupuesto

  // Actualizar el título del modal dinámicamente
  var modal = $(this);
  modal.find('.modal-title-detalles').text('Detalles del pedido: ' + numero);

  // Hacer la petición AJAX
  $.ajax({
      url: '/pedidos/obtenerDatosProductos',
      type: 'GET',
      data: {
          'presupuesto_id': presupuestoId
      },
      success: function (data) {
          // Limpiar la tabla antes de llenarla
          $('#productosTableBody').empty();

          // Llenar la tabla con los datos obtenidos
          data.productos.forEach(function (producto) {
            var empaquetado = producto.empaquetado ? 'Si' : 'No';
            $('#productosTableBody').append(
                '<tr><td>' + producto.insumo + '</td><td>' + producto.descripcion + '</td><td>' + producto.info_adic + '</td><td>' + empaquetado + '</td><td>' + producto.cantidad + '</td></tr>'
            );
        });
      }
  });
});

$('#confirmacionModal').on('show.bs.modal', function (event) {
    var button = $(event.relatedTarget);
    var info = button.data('info').split('|');
    var numero = info[0];
    var presupuestoId = info[1];

    var modal = $(this);

    // Título dinámico
    modal.find('.modal-title-confirmacion').text('Confirmación del pedido: ' + numero);

    $.ajax({
        url: '/pedidos/obtenerDatosProductos',
        type: 'GET',
        data: {
            'presupuesto_id': presupuestoId,
            'pedido_numero': numero
        },
        success: function (data) {

            // Datos del pedido
            modal.find('#confCliente').text(data.pedido.cliente);
            modal.find('#confFechaPedido').text(data.pedido.fecha_pedido);
            modal.find('#confFechaEntrega').text(
                data.pedido.fecha_entrega && data.pedido.fecha_entrega.trim() !== ''
                    ? data.pedido.fecha_entrega
                    : 'A determinar'
            );
            modal.find('#confPrecio').text(formatearNumeroLocal(data.pedido.precio));
            modal.find('#confSenia').text(formatearNumeroLocal(data.pedido.senia));
            modal.find('#confSaldo').text(formatearNumeroLocal(data.pedido.saldo));

            // Productos
            var html = '';
            data.productos.forEach(function (p) {
                html += `
                    <p>
                        <strong>${p.cantidad} ${p.producto_final}</strong><br>
                        ${p.info_adic}
                    </p>
                `;
            });

            modal.find('#confProductos').html(html);
        }
    });
});

/* Funcionalidad para evitar la eliminación de objetos listados en la vista por un click involuntario. */
// (function () {
//     const btnEliminacion = document.querySelectorAll(".btnEliminacion");
//     btnEliminacion.forEach(btn=>{
//         btn.addEventListener("click", (e)=>{
//             const confirmacion = confirm("¿Está segur@ de que desea eliminar este elemento?");
//             if(!confirmacion){
//                 e.preventDefault();
//             }    
//         });
//     });
// })();

// Función que evita que se cancele un pedido sin confirmación.
(function () {
    const formularioEstado = document.querySelector('#cambiarEstadoModal form');
    const selectEstado = document.querySelector('#estado');

    if (formularioEstado && selectEstado) {
        formularioEstado.addEventListener('submit', function (e) {
            const estadoSeleccionado = selectEstado.value;

            if (estadoSeleccionado === 'Cancelado') {
                const confirmacion = confirm(
                    "⚠️ Atención: estás por cancelar este pedido.\n\nEsta acción es irreversible.\nSi luego necesitás reactivarlo, deberás crear uno nuevo.\n\n¿Deseás continuar?"
                );
                if (!confirmacion) {
                    e.preventDefault();
                }
            }
        });
    }
})();


//Manejo de filtros en vista de pedidos.
const FILTROS_KEY = 'pedidos_filtros';
const IDS_FILTRO = ['filtroCliente', 'filtroProducto', 'filtroEstado'];

function manejarTodos(selectEl, e) {
    const opcionTodos = selectEl.querySelector('option[value=""]');
    if (!opcionTodos) return;

    if (e.target === opcionTodos || opcionTodos.selected) {
        // Si se clickeó "Todos" o quedó seleccionado, deseleccionar todo lo demás
        if (opcionTodos.selected) {
            Array.from(selectEl.options).forEach(o => {
                if (o.value !== '') o.selected = false;
            });
        }
    } else {
        opcionTodos.selected = false;
    }
}

['filtroCliente', 'filtroProducto', 'filtroEstado'].forEach(id => {
    const el = document.getElementById(id);
    el.addEventListener('change', (e) => {
        manejarTodos(el, e);
        aplicarFiltros();
    });
});
function getSeleccionados(id) {
    return Array.from(document.getElementById(id).selectedOptions)
                .map(o => o.value.toLowerCase());
}

function aplicarFiltros() {
    const clienteFiltro   = document.getElementById('filtroCliente').value;
    const productosFiltro = getSeleccionados('filtroProducto');
    const estadosFiltro   = getSeleccionados('filtroEstado');

    sessionStorage.setItem(FILTROS_KEY, JSON.stringify({
        cliente:   clienteFiltro,
        productos: productosFiltro,
        estados:   estadosFiltro
    }));

    document.querySelectorAll('#tableBody_Pedido tr').forEach(fila => {
        const clienteId = fila.children[1].dataset.clienteId || '';
        const productos = fila.children[2].querySelector('.contenido').textContent.toLowerCase();
        const estado    = fila.children[3].querySelector('.contenido').textContent.toLowerCase();

        const okCliente  = !clienteFiltro        || clienteId === clienteFiltro;
        const okProducto = !productosFiltro.length || productosFiltro.some(p => productos.includes(p));
        const okEstado   = !estadosFiltro.length   || estadosFiltro.includes(estado);

        fila.style.display = (okCliente && okProducto && okEstado) ? '' : 'none';
    });
}

function restaurarFiltros() {
    const guardados = sessionStorage.getItem(FILTROS_KEY);
    if (!guardados) return;

    const { cliente, productos, estados } = JSON.parse(guardados);

    if (cliente) document.getElementById('filtroCliente').value = cliente;

    ['filtroProducto', 'filtroEstado'].forEach((id, i) => {
        const vals = i === 0 ? productos : estados;
        if (!vals?.length) return;
        Array.from(document.getElementById(id).options).forEach(o => {
            o.selected = vals.includes(o.value.toLowerCase());
        });
    });

    aplicarFiltros();
}

function limpiarFiltros() {
    sessionStorage.removeItem(FILTROS_KEY);
    document.getElementById('filtroCliente').value = '';
    ['filtroProducto', 'filtroEstado'].forEach(id => {
        Array.from(document.getElementById(id).options).forEach(o => o.selected = false);
    });
    document.querySelectorAll('#tableBody_Pedido tr').forEach(f => f.style.display = '');
}

document.getElementById('filtroCliente').addEventListener('change', aplicarFiltros);
document.getElementById('filtroProducto').addEventListener('change', aplicarFiltros);
document.getElementById('filtroEstado').addEventListener('change', aplicarFiltros);
document.getElementById('limpiarFiltros').addEventListener('click', limpiarFiltros);

window.addEventListener('load', restaurarFiltros);

cambiarClienteModal.addEventListener('show.bs.modal', function (event) {
    const button = event.relatedTarget;
    const info = button.getAttribute('data-bs-whatever');
    const [clienteId, clienteRef, pedidoNumero, presupuestoNumero] = info.split('|');

    document.getElementById('pedidoNumero').value = pedidoNumero;
    document.getElementById('presupuestoNumero').value = presupuestoNumero;

    // Rellenar el input con <id>|<referencia>
    document.getElementById('nuevoCliente').value = `${clienteId}|${clienteRef}`;
});
