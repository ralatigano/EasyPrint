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
