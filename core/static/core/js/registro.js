let dataTable;
let dataTableIsInitilized=false;
// Lógica que inicializa la dataTable Usuarios.
const initDataTable=async() => {
    if(dataTableIsInitilized){
        dataTable.destroy();
    }
    dataTable=$("#Usuarios").DataTable({
        language: {
            lengthMenu: 'Mostrar _MENU_ productos por página',
            zeroRecords: 'No hay productos registrados',
            info: 'Mostrando de _START_ a _END_ de _TOTAL_ productos',
            infoEmpty: 'No hay productos',
            InfoFiltered: '(filtrado de _MAX_ productos totales)',
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
    document.getElementById("nav_item_usuarios").style.fontWeight = "bold";
});

// Lógica que evita la eliminación de objetos listados en la cotización por un click involuntario.
(function () {
    const btnEliminacion = document.querySelectorAll(".btnEliminacion");
    btnEliminacion.forEach(btn=>{
        btn.addEventListener("click", (e)=>{
            const confirmacion = confirm("¿Está segur@ de que desea continuar con el borrado? (Esto no se puede deshacer.)");
            if(!confirmacion){
                e.preventDefault();
            }    
        });
    });
})();

// Lógica que escucha el evento click sobre el botón de editar un usuario y muestra un modal con los datos del usuario correspondiente.
const editarUsuarioModal = document.getElementById('editarUsuarioModal');
editarUsuarioModal.addEventListener('show.bs.modal', event => {
  // Botón que lanza el modal
  const buttonEditar = event.relatedTarget;
  // Obtengo el código del producto y su nombre para mostrarlo en el modal
  // {{u.id}}|{{u.username}}|{{u.first_name}}|{{u.last_name}}|{{u.email}}|{{u.telefono}}|{{u.grupos}}
  const recipient = buttonEditar.getAttribute('data-bs-whatever');
  console.log(recipient);
  var partes = recipient.split('|');
  const id = partes[0];
  const username = partes[1];
  const nombre = partes[2];
  const apellido = partes[3];
  const correo = partes[4];
  const telefono = partes[5];
  const gruposActuales = partes[6] ? partes[6].split(',') : [];
  // Cambio el texto del título del modal
  const modalTitle = editarUsuarioModal.querySelector('.modal-title-prod');
  modalTitle.textContent = `Editar usuarie: ${nombre} ${apellido}`;

  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  $("#id").val(id);
  $("#username").val(username);
  $("#nombre").val(nombre);
  $("#apellido").val(apellido);
  $("#email").val(correo);
  $("#telefono").val(telefono);

  // Limpiar y cargar los grupos en el select
  const selectGrupos = document.getElementById('grupo');
  selectGrupos.innerHTML = ''; // Limpiar las opciones del select

  $.ajax({
    url: '/infoGrupos',
    success: function(data) {
        $('#grupo').empty();
        $.each(data.Group, function(index, group) {
            $('#grupo').append('<option value="'+ group.id +'">'+ group.nombre +'</option>');
        });

        // Establecer las opciones seleccionadas
        $('#grupo').val(gruposActuales); // Selecciona múltiples opciones si hay más de un grupo
    },
    error: function(xhr, status, error) {
      console.error('Error:', error);
    }
  });
});

//Lógica que ajusta las dimensiones de algunos elementos cuando se redimensiona la página.
document.addEventListener('DOMContentLoaded', function() {
    function ajustarFondo() {
        // Seleccionar los elementos
        const contenidoPrincipal = document.querySelector('.ContenidoPrincipal');
        const contenedor = document.querySelector('.container.mt-5');
        const fondo = document.querySelector('.recuadro-fondo-register');

        if (contenedor && fondo) {
            // Obtener las dimensiones del contenedor
            const anchoContenedor = contenedor.offsetWidth;
            const altoContenedor = contenedor.offsetHeight;

            // Ajustar las dimensiones del fondo
            fondo.style.width = `${anchoContenedor * 1.15}px`;
            fondo.style.height = `${altoContenedor * 1.15}px`;

            // Ajustar el tamaño del contenido principal
            contenidoPrincipal.style.minHeight = altoContenedor * 1.1 + 'px';

        }
    }

    // Ajustar el fondo cuando la página se carga y cuando se redimensiona
    ajustarFondo();
    window.addEventListener('resize', ajustarFondo);
});