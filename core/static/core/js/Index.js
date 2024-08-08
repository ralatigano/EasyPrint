
// Inicializar DataTable y otros elementos después de que el DOM esté completamente cargado
document.addEventListener("DOMContentLoaded", async() => {
    await initDataTable();
    document.getElementById("nav_item_inicio").style.fontWeight = "bold";
});

let dataTable;
let dataTableIsInitilized=false;
const initDataTable=async() => {
    if(dataTableIsInitilized){
        dataTable.destroy();
    }
    dataTable=$("#NuevoPresupuesto").DataTable({
        responsive: true,
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
    dataTable.on('draw.dt', function() {
        footerCallback(null, dataTable.data(), 0, dataTable.data().length, {});
    });


};

/* Funcionalidad para evitar la eliminación de objetos listados en la cotización por un click involuntario. */
(function () {
    const btnEliminacion = document.querySelectorAll(".btnEliminacion");
    btnEliminacion.forEach(btn=>{
        btn.addEventListener("click", (e)=>{
            const confirmacion = confirm("¿Está segur@ de que desea eliminar este elemento?");
            if(!confirmacion){
                e.preventDefault();
            }    
        });
    });
})();


const calcularCantPorHojaModal = document.getElementById('calcularCantPorHojaModal')
calcularCantPorHojaModal.addEventListener('show.bs.modal', event => {
  //botón que lanza el modal
  const buttonCalcular = event.relatedTarget

  //cambio el texto del título del modal
  const modalTitle = calcularCantPorHojaModal.querySelector('.modal-title-prod')
  modalTitle.textContent = `Calcular unidades por hoja/pliego`

  // Limpiar los valores de los inputs
  document.getElementById('ancho_hoja').value = '';
  document.getElementById('alto_hoja').value = '';
  document.getElementById('ancho_elemento').value = '';
  document.getElementById('alto_elemento').value = '';
  document.getElementById('separacion').value = '0';
  document.getElementById('cant_deseada').value = '1';

  // Limpiar los valores de los spans
  document.getElementById('cant_resultado').innerText = '';
  document.getElementById('cant_hojas').innerText = '';

  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
  var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl)
  });


});
// Función que calcula la cantidad de hojas para un presupuesto según lo que se quiera imprimir en esa hoja.
function submitCalculation() {
    const form = document.getElementById('calcular_cantidad_por_hoja_form');
    const formData = new FormData(form);

    // Llama a closeModal para borrar la imagen existente
    closeModal();

    fetch('/presupuestos/calcularCantHojas', {
        method: 'POST',
        body: formData,
        headers: {
        'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
        } else {
            document.getElementById('cant_resultado').innerText = data.cant_resultado;
            document.getElementById('cant_hojas').innerText = data.cant_hojas;
            document.getElementById('area_ocupada').innerText = data.area_ocupada;
            var imgElement = document.getElementById('img_hoja');
            imgElement.src = data.img_hoja;
            
            imgElement.onload = function() {
                var modalContent = document.querySelector('.modal-content');
                var newModalWidth = imgElement.width * 1.1;
                modalContent.style.width = newModalWidth + 'px';
            };
        }
    })

};

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
        }
    }
    }
    return cookieValue;
}
//Función que borra la imagen que se genera en el servidor cada vez que se hace un cálculo de la cantidad de hojas
function closeModal() {
    var modal = document.getElementById('calcularCantPorHojaModal');

    // Limpia la imagen generada en el servidor
    fetch('/presupuestos/borrarImagenGenerada', {
        method: 'POST',
        headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json'
        },
        body: JSON.stringify({ imgPath: document.getElementById('img_hoja').src })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Imagen eliminada:', data.message);
    })
    .catch(error => {
        console.error('Error al eliminar la imagen:', error);
    });
    const imgElement = modal.querySelector('img');
    imgElement.src = ''; // Limpia la URL de la imagen
}
//Función que realiza la carga del selector de categorías y el de los productos cada vez que se elije una categoría.
$(document).ready(function() {
    $('#categoria').on('change', function() {
        var categoriaId = $(this).val();
        if (categoriaId) {
            $.ajax({
                url: '/presupuestos/obtenerProductos',  // Asegúrate de que esta URL apunta a la vista correcta
                data: {
                    'categoria_nombre': categoriaId
                },
                success: function(data) {
                    $('#producto').empty();
                    $('#producto').append('<option value="">Seleccione un producto</option>');
                    $.each(data.productos, function(index, producto) {
                        $('#producto').append('<option value="'+ producto.codigo +'">'+ producto.nombre +'</option>');
                    });
                }
            });
        } else {
            $('#producto').empty();
            $('#producto').append('<option value="">Seleccione un producto</option>');
        }
    });
});
// Función que abre el modal con los datos del cálculo realizado. En este modal se puede decidir si incorporar el producto al presupuesto actual o no.
function previoModal() {
    const form = document.getElementById('nueva_cotizacion_form');
    const formData = new FormData(form);

    // Mostrar el modal antes de realizar la llamada fetch
    var modal = new bootstrap.Modal(document.getElementById('resultadoPrevioModal'), {
        keyboard: false
    });
    modal.show();

    fetch('/presupuestos/calculoRapido', {
        method: 'POST',
        body: formData,
        headers: {
        'X-CSRFToken': getCookie('csrftoken')
        }
    })

    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
        } else {
            document.getElementById('prod_prev').innerText = data.producto;
            document.getElementById('cant_prev').innerText = data.cantidad;
            document.getElementById('cant_area_prev').innerText = data.cant_area;
            document.getElementById('precio_prev').innerText = data.precio;
            document.getElementById('empaquetado_prev').innerText = data.empaquetado;
            document.getElementById('t_produccion_prev').innerText = data.t_produccion;
            document.getElementById('detalle_prev').innerText =  data.detalle;
            document.getElementById('descuento_prev').innerText = data.descuento === 0 ? '0 %' : data.descuento +'%';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Hubo un error al procesar la solicitud.');
    })
};
//Función que escucha el evento click sobre el botón de editar un producto y muestra un modal con los datos del producto que se pueden editar.
document.addEventListener('DOMContentLoaded', function() {
    var editarProductoModal = document.getElementById('editarProductoModal');
    editarProductoModal.addEventListener('show.bs.modal', function(event) {
        var button = event.relatedTarget;
        var data = button.getAttribute('data-bs-whatever').split(' | ');
        //{{c.codigo}} | {{c.nombre}} | {{c.info_adic}} | {{c.cantidad}} | {{c.cant_area}} | {{c.desc_porcentaje}} | {{c.empaquetado}} | {{c.t_produccion}}
        var codigo = data[0];
        var nombre = data[1];
        var infoAdic = data[2];
        var cantidad = data[3];
        var cant_area = data[4];
        var descPorcentaje = data[5];
        var empaquetado = data[6] === 'True';
        var tProduccion = data[7];
        // Actualizar los campos del modal
        document.getElementById('cod_edit').value = codigo;
        document.getElementById('prod_edit').value = nombre;
        document.getElementById('detalle_edit').value = infoAdic;
        document.getElementById('cant_edit').value = cantidad;
        document.getElementById('cant_area_edit').value = cant_area;
        document.getElementById('desc_edit').value = descPorcentaje;
        document.getElementById('t_prod_edit').value = tProduccion;
        // Evaluar el dato que viene en empaquetado para saber si rellenar o no el checkbox
        var empaqEditCheckbox = document.getElementById('empaq_edit');
        if (empaquetado) {
            empaqEditCheckbox.checked = true;
        } else {
            empaqEditCheckbox.checked = false;
        }
    });
});


document.addEventListener('DOMContentLoaded', function() {
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('#navbarSupportedContent');

    // Escucha eventos de Bootstrap para ajustar el estado del botón
    navbarCollapse.addEventListener('show.bs.collapse', function() {
      navbarToggler.setAttribute('aria-expanded', 'true');
    });

    navbarCollapse.addEventListener('hide.bs.collapse', function() {
      navbarToggler.setAttribute('aria-expanded', 'false');
    });
});
