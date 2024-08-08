
let dataTable;
let dataTableIsInitilized=false;

const initDataTable=async() => {
    if(dataTableIsInitilized){
        dataTable.destroy();
    }
    dataTable=$("#Productos").DataTable({
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
    document.getElementById("nav_item_productos").style.fontWeight = "bold";
});

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


const editarProductoModal = document.getElementById('editarProductoModal');
editarProductoModal.addEventListener('show.bs.modal', event => {
  // Botón que lanza el modal
  const buttonEditar = event.relatedTarget;
  // Obtengo el código del producto y su nombre para mostrarlo en el modal
  // {{p.codigo}}|{{p.nombre}}|{{p.ancho}}|{{p.alto}}|{{p.precio}}|{{p.factor}}|{{p.categoria}}
  const recipient = buttonEditar.getAttribute('data-bs-whatever');
  var partes = recipient.split('|');
  const codigo = partes[0];
  const nombre = partes[1];
  const ancho = partes[2];
  const alto = partes[3];
  const precio = partes[4];
  const factor = partes[5];
  const categoriaActual = partes[6];
  // Cambio el texto del título del modal
  const modalTitle = editarProductoModal.querySelector('.modal-title-prod');
  modalTitle.textContent = `Editar producto: ${codigo + ' ' + nombre}`;

  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  $("#codigo").val(codigo);
  $("#nombre").val(nombre);
  $("#ancho").val(ancho);
  $("#alto").val(alto);
  $("#precio").val(precio);
  $("#factor_edit").val(factor);

  // Establecer la categoría actual como la opción seleccionada
  const selectCategorias = document.getElementById('categ');
  selectCategorias.innerHTML = ''; // Limpiar las opciones del select

  $.ajax({
    url: '/productos/infoEditarProducto',
    success: function(data) {
      $('#categ').empty();
      $.each(data.Cate, function(index, categoria) {
        $('#categ').append('<option value="'+ categoria.nombre +'">'+ categoria.nombre +'</option>');
      });

      // Establecer la categoría actual como la opción seleccionada
      selectCategorias.value = categoriaActual;
    },
    error: function(xhr, status, error) {
      console.error('Error:', error);
    }
  });
});

const agregarProductoModal = document.getElementById('agregarProductoModal')

function handleShowModal(event) {
  const buttonAgregar = event.relatedTarget;
  const modalTitle = agregarProductoModal.querySelector('.modal-title-add');
  const selectCategorias = document.getElementById('categ_add');

  // Verificar si el select ya tiene opciones
  if (selectCategorias.options.length > 0) {
    return;
  }

  modalTitle.textContent = `Agregar un nuevo producto`;

  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // Limpiar las opciones del select
  selectCategorias.innerHTML = '';

  $.ajax({
    url: '/productos/infoEditarProducto',  // Asegúrate de que esta URL apunta a la vista correcta
    success: function(data) {
      $('#categ_add').empty();
      $('#categ_add').append('<option value="">Seleccione una categoría</option>');
      $.each(data.Cate, function(index, categoria) {
        $('#categ_add').append('<option value="'+ categoria.nombre +'">'+ categoria.nombre +'</option>');
      });
    },
    error: function(xhr, status, error) {
      console.error('Error:', error);
    }
  });
}

agregarProductoModal.removeEventListener('show.bs.modal', handleShowModal);
agregarProductoModal.addEventListener('show.bs.modal', handleShowModal);
