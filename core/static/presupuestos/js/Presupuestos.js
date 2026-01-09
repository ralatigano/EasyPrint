
let dataTable;
let dataTableIsInitilized=false;
//Lógica que inicializa la dataTable Presupuestos.
const initDataTable=async() => {
    if(dataTableIsInitilized){
        dataTable.destroy();
    }
    dataTable=$("#Presupuestos").DataTable({
        order: [[0, 'desc']],
        responsive: true,
        language: {
            lengthMenu: 'Mostrar _MENU_ presupuestos por página',
            zeroRecords: 'No hay presupuestos registrados',
            info: 'Mostrando de _START_ a _END_ de _TOTAL_ presupuestos',
            infoEmpty: 'No hay presupuestos',
            InfoFiltered: '(filtrado de _MAX_ presupuestos totales)',
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
    document.getElementById("nav_item_presupuestos").style.fontWeight = "bold";
});


// Cuando se abre el modal, obtenemos el número de presupuesto y hacemos la consulta AJAX
var cambiarClienteModal = document.getElementById('cambiarClienteModal');
cambiarClienteModal.addEventListener('show.bs.modal', function (event) {
  var button = event.relatedTarget; // El botón que disparó el modal
  var presupuestoNumero = button.getAttribute('data-bs-whatever'); // Obtiene el número de presupuesto
  // Colocamos el número en el input oculto
  document.getElementById('presupuestoNumero').value = presupuestoNumero;

  // Realizamos una consulta AJAX para traer el nombre actual del cliente
  fetch(`/presupuestos/obtenerCliente/?numero=${presupuestoNumero}`)
    .then(response => response.json())
    .then(data => {
      // Si se obtuvo el dato, lo asignamos al input del cliente
      document.getElementById('nuevoCliente').value =
      data.id && data.referencia ? `${data.id}|${data.referencia}` : '';
    })
    .catch(error => console.error('Error obteniendo cliente:', error));
});

// Capturamos el evento submit del formulario del modal
document.getElementById('cambiarClienteForm').addEventListener('submit', function (e) {
  e.preventDefault(); // Prevenir el comportamiento por defecto del form

  // Obtenemos los datos del formulario
  const presupuestoNumero = document.getElementById('presupuestoNumero').value;
  let nuevoCliente = document.getElementById('nuevoCliente').value.trim();
  const csrftoken = getCookie('csrftoken');

    if (!nuevoCliente) {
        nuevoCliente = ""; // Para que parsear_cliente use Consumidor Final
    }

  // Enviamos la petición AJAX para actualizar al cliente
  fetch('/presupuestos/cambiarCliente/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      // Se requiere el token CSRF, si usás Django lo podes insertar en la plantilla
      'X-CSRFToken': csrftoken
    },
    body: `numero=${encodeURIComponent(presupuestoNumero)}&cliente=${encodeURIComponent(nuevoCliente)}`
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      // Actualizamos la interfaz si es necesario, por ejemplo recargando la página
      location.reload();
    } else {
      console.error('Error:', data.error);
    }
  })
  .catch(error => console.error('Error al cambiar el cliente:', error));
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        let cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            let cookie = cookies[i].trim();
            // Verificamos si este cookie comienza con el nombre adecuado seguido de '='
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

$(document).on('click', '.ver-productos-btn', function () {
    const numeroPresupuesto = $(this).data('numero');

    $.ajax({
        url: `/presupuestos/productosPorPresupuesto/${numeroPresupuesto}`,
        method: 'GET',
        success: function (data) {
            const tbody = $('#tablaProductosPresupuesto');
            tbody.empty();

            data.data.forEach(prod => {
                tbody.append(`
                    <tr>
                        <td>${prod.nombre}</td>
                        <td>${prod.cantidad}</td>
                    </tr>
                `);
            });

            $('#btnEditarPresupuesto').attr('href', `/presupuestos/verPresupuesto/${numeroPresupuesto}`);
            $('#btnConvertirPedido').attr('href', `/pedidos/prepararCompletarPedido/${numeroPresupuesto}`);
            $('#modalProductosPresupuesto').modal('show');
        },
        error: function () {
            alert('No se pudieron cargar los productos del presupuesto.');
        }
    });
});
