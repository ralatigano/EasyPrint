let dataTable;
let dataTableIsInitilized=false;

const initDataTable=async() => {
    if(dataTableIsInitilized){
        dataTable.destroy();
    }
    dataTable=$("#Pedidos").DataTable({
        order: [[0, 'desc']],
        responsive: true,
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
    // document.getElementById("nav_item_pedidos").style.fontWeight = "bold";
});


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

const agregarSeniaModal = document.getElementById('agregarSeniaModal')
agregarSeniaModal.addEventListener('show.bs.modal', event => {
  const button = event.relatedTarget
  const recipient = button.getAttribute('data-bs-whatever')
  const modalTitle = agregarSeniaModal.querySelector('.modal-title-senia')
  const modalBodyInput = agregarSeniaModal.querySelector('.modal-body input')

  modalTitle.textContent = `Agregar seña para el pedido: ${recipient}`
  modalBodyInput.value = recipient
})
