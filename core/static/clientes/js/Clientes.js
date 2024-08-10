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
const editarClienteModal = document.getElementById('editarClienteModal')
editarClienteModal.addEventListener('show.bs.modal', event => {
  //botón que lanza el modal
  const button = event.relatedTarget
  //obtengo el código del producto y su nombre para mostrarlo en el modal
  //{{c.id}}|{{c.nombre}}|{{c.negocio}}|{{c.cuit}}|{{c.telefono}}|{{c.direccion}}|{{c.metodo_contacto}}
  const recipient = button.getAttribute('data-bs-whatever')
  var partes = recipient.split('|');
  const id = partes[0];
  const nombre = partes[1];
  const negocio = partes[2];
  const cuit = partes[3];
  const telefono = partes[4];
  const direccion = partes[5];
  const met_contacto = partes[6];

  //cambio el texto del título del modal
  const modalTitle = editarClienteModal.querySelector('.modal-title')
  modalTitle.textContent = `Editar Cliente: ${nombre}`

  $("#id").val(id);
  $("#nombre").val(nombre);
  $("#negocio").val(negocio);
  $("#cuit").val(cuit);
  $("#telefono").val(telefono);
  $("#direccion").val(direccion);
  $("#met_contacto").val(met_contacto);

  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
  var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl)
  });

});
